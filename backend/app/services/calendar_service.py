"""Calendar OAuth token maintenance + two-way event reconciliation.

This module keeps connected Google / Microsoft 365 calendars in sync with the
scheduler:

- :func:`needs_refresh` / :func:`refresh_token` keep OAuth access tokens alive
  (the worker refreshes before each reconcile pass so credentials are valid).
- :func:`reconcile_events` mirrors appointments into the external calendar and
  repairs drift: it creates events for new appointments, patches changed ones,
  deletes events for canceled/expired appointments, and recreates events that
  were deleted directly in the provider UI.

The scheduler DB is the source of truth; the external calendar is a PHI-free
mirror (generic summary + opaque appointment id only). The
:class:`~app.models.calendar_sync_link.CalendarSyncLink` table maps each
appointment to its external event so updates and deletes never duplicate.

Establishing a connection (the OAuth authorization-code flow) lives in
:mod:`app.services.calendar_oauth`.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.appointment import Appointment
from app.models.calendar_connection import CalendarConnection
from app.models.calendar_sync_link import CalendarSyncLink
from app.models.user import ProviderProfile

log = logging.getLogger(__name__)

# Refresh when the access token expires within this window.
REFRESH_MARGIN = timedelta(minutes=10)

_TOKEN_URLS = {
    "google": "https://oauth2.googleapis.com/token",
    "o365": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
}


def _oauth_client(provider: str) -> tuple[str | None, str | None]:
    if provider == "google":
        secret = settings.google_oauth_secret
        return settings.google_oauth_id, secret.get_secret_value() if secret else None
    if provider == "o365":
        secret = settings.ms_oauth_secret
        return settings.ms_oauth_id, secret.get_secret_value() if secret else None
    return None, None


def needs_refresh(conn: CalendarConnection, *, now: datetime | None = None) -> bool:
    """True if this connection's access token is missing or about to expire."""
    if not conn.active or conn.deleted_at is not None:
        return False
    if conn.provider not in _TOKEN_URLS:
        return False
    if not conn.refresh_token_ct:
        return False
    if conn.token_expires_at is None:
        return True
    now = now or datetime.now(timezone.utc)
    expires = conn.token_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires - now <= REFRESH_MARGIN


async def refresh_token(db: AsyncSession, conn: CalendarConnection) -> bool:
    """Exchange the refresh token for a new access token. Returns True on success.

    Network/credential problems are swallowed (logged) so one broken connection
    never aborts the whole sweep; the connection simply keeps its stale token
    until the next pass.
    """
    client_id, client_secret = _oauth_client(conn.provider)
    if not (client_id and client_secret):
        log.info("calendar.refresh_skipped_no_oauth", extra={"provider": conn.provider})
        return False
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": conn.refresh_token_ct,  # EncryptedString decrypts on read
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_TOKEN_URLS[conn.provider], data=data)
        if resp.status_code >= 300:
            log.warning(
                "calendar.refresh_failed",
                extra={"provider": conn.provider, "status": resp.status_code},
            )
            return False
        payload = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("calendar.refresh_error", extra={"err": type(exc).__name__})
        return False

    access = payload.get("access_token")
    if not access:
        return False
    conn.access_token_ct = access
    if payload.get("refresh_token"):
        conn.refresh_token_ct = payload["refresh_token"]
    expires_in = int(payload.get("expires_in", 3600))
    conn.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    conn.last_sync_at = datetime.now(timezone.utc)
    return True


async def reconcile_events(db: AsyncSession, conn: CalendarConnection) -> int:
    """Two-way reconcile a connection's calendar with local appointments.

    Direction of truth is the scheduler DB: appointments are the source and the
    external calendar is a mirror. Each pass, within a bounded forward window:

    * **push** — create an external event for every active appointment that has
      no link yet; patch the event when the appointment's time/status changed;
    * **retire** — delete the external event (and its link) for appointments
      that were canceled, completed, deleted, or fell outside the window;
    * **pull / drift-repair** — for links left otherwise untouched, confirm the
      remote event still exists; if it was deleted directly in the provider UI,
      recreate it so the two calendars converge again.

    Every event carries only PHI-free data (a generic summary + opaque
    appointment id in a private extended property). Per-event errors are logged
    and skipped so one bad event never aborts the sweep. Returns the number of
    remote mutations performed.
    """
    if not conn.active or conn.deleted_at is not None:
        return 0
    if conn.provider not in _EVENT_API:
        return 0
    access_token = conn.access_token_ct  # EncryptedString decrypts on read
    if not access_token:
        return 0
    if conn.token_expires_at is not None and needs_refresh(conn):
        # Token is stale and could not be refreshed this pass — skip to avoid
        # a burst of 401s; the next sweep retries after a successful refresh.
        return 0

    provider_id = (await db.execute(
        select(ProviderProfile.id).where(
            ProviderProfile.user_id == conn.user_id,
            ProviderProfile.org_id == conn.org_id,
            ProviderProfile.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if provider_id is None:
        # No provider calendar to mirror for this user.
        conn.last_sync_at = datetime.now(timezone.utc)
        return 0

    now = datetime.now(timezone.utc)
    window_end = now + timedelta(days=settings.calendar_sync_window_days)

    links = (await db.execute(
        select(CalendarSyncLink).where(CalendarSyncLink.connection_id == conn.id)
    )).scalars().all()
    links_by_appt = {link.appointment_id: link for link in links}

    appts = (await db.execute(
        select(Appointment).where(
            Appointment.org_id == conn.org_id,
            Appointment.provider_id == provider_id,
            Appointment.deleted_at.is_(None),
            Appointment.status.in_(SYNC_PUSH_STATUSES),
            Appointment.end_at > now,
            Appointment.start_at < window_end,
        )
    )).scalars().all()
    appts_by_id = {a.id: a for a in appts}

    async with httpx.AsyncClient(timeout=10.0) as client:
        mutations = 0
        # --- push: create / update -------------------------------------------
        for appt in appts:
            payload = _event_payload(conn.provider, appt)
            digest = _payload_hash(payload)
            link = links_by_appt.get(appt.id)
            try:
                if link is None:
                    event_id = await _create_event(client, conn, access_token, payload)
                    if event_id:
                        db.add(CalendarSyncLink(
                            org_id=conn.org_id, connection_id=conn.id,
                            appointment_id=appt.id, external_event_id=event_id,
                            payload_hash=digest, last_pushed_at=now,
                        ))
                        mutations += 1
                elif link.payload_hash != digest:
                    ok = await _update_event(client, conn, access_token, link.external_event_id, payload)
                    if not ok:
                        # Remote copy vanished — recreate it (drift repair).
                        event_id = await _create_event(client, conn, access_token, payload)
                        if event_id:
                            link.external_event_id = event_id
                    link.payload_hash = digest
                    link.last_pushed_at = now
                    mutations += 1
            except httpx.HTTPError as exc:
                log.warning("calendar.push_error", extra={"provider": conn.provider, "err": type(exc).__name__})

        # --- retire: appointments that should no longer be mirrored ----------
        for link in links:
            if link.appointment_id in appts_by_id:
                continue
            try:
                await _delete_event(client, conn, access_token, link.external_event_id)
            except httpx.HTTPError as exc:
                log.warning("calendar.delete_error", extra={"provider": conn.provider, "err": type(exc).__name__})
            await db.delete(link)
            mutations += 1

        # --- pull / drift-repair: unchanged links still present remotely? ----
        for appt in appts:
            link = links_by_appt.get(appt.id)
            if link is None or link.last_pushed_at == now:
                continue  # freshly created/updated above — no need to re-check
            try:
                if not await _event_exists(client, conn, access_token, link.external_event_id):
                    payload = _event_payload(conn.provider, appt)
                    event_id = await _create_event(client, conn, access_token, payload)
                    if event_id:
                        link.external_event_id = event_id
                        link.payload_hash = _payload_hash(payload)
                        link.last_pushed_at = now
                        mutations += 1
            except httpx.HTTPError as exc:
                log.warning("calendar.pull_error", extra={"provider": conn.provider, "err": type(exc).__name__})

    conn.last_sync_at = now
    return mutations


# ---- provider event REST adapters --------------------------------------------

# A PHI-free title. Times/durations sit inside the covered-entity's own
# calendar (Google Workspace / M365 under BAA); patient identifiers never leave.
SYNC_SUMMARY = "Appointment"

# Statuses that should have a live mirror event.
SYNC_PUSH_STATUSES = ("scheduled", "confirmed", "checked_in")

_EVENT_API = {
    "google": "https://www.googleapis.com/calendar/v3/calendars/{cal}/events",
    "o365": "https://graph.microsoft.com/v1.0/me/events",
}


def _payload_hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


def _event_payload(provider: str, appt: Appointment) -> dict:
    """Build the PHI-free provider event body for an appointment."""
    start = appt.start_at
    end = appt.end_at
    if provider == "google":
        return {
            "summary": SYNC_SUMMARY,
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
            "extendedProperties": {"private": {"hs_appointment_id": str(appt.id)}},
        }
    # o365 / Microsoft Graph
    return {
        "subject": SYNC_SUMMARY,
        "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
        "singleValueExtendedProperties": [
            {"id": "String {00020329-0000-0000-C000-000000000046} Name hs_appointment_id",
             "value": str(appt.id)},
        ],
    }


def _events_url(conn: CalendarConnection) -> str:
    template = _EVENT_API[conn.provider]
    return template.format(cal=conn.calendar_id or "primary")


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": _bearer(access_token)}


async def _create_event(
    client: httpx.AsyncClient, conn: CalendarConnection, access_token: str, payload: dict
) -> str | None:
    resp = await client.post(_events_url(conn), headers=_auth_headers(access_token), json=payload)
    if resp.status_code >= 300:
        log.warning("calendar.create_rejected", extra={"provider": conn.provider, "status": resp.status_code})
        return None
    return resp.json().get("id")


async def _update_event(
    client: httpx.AsyncClient, conn: CalendarConnection, access_token: str,
    event_id: str, payload: dict,
) -> bool:
    """PATCH an event. Returns False if the remote event no longer exists."""
    url = f"{_events_url(conn)}/{event_id}"
    resp = await client.patch(url, headers=_auth_headers(access_token), json=payload)
    if resp.status_code == 404:
        return False
    if resp.status_code >= 300:
        log.warning("calendar.update_rejected", extra={"provider": conn.provider, "status": resp.status_code})
    return resp.status_code < 300


async def _delete_event(
    client: httpx.AsyncClient, conn: CalendarConnection, access_token: str, event_id: str
) -> None:
    url = f"{_events_url(conn)}/{event_id}"
    resp = await client.delete(url, headers=_auth_headers(access_token))
    # 404/410 → already gone; treat as success.
    if resp.status_code not in (200, 202, 204, 404, 410):
        log.warning("calendar.delete_rejected", extra={"provider": conn.provider, "status": resp.status_code})


async def _event_exists(
    client: httpx.AsyncClient, conn: CalendarConnection, access_token: str, event_id: str
) -> bool:
    url = f"{_events_url(conn)}/{event_id}"
    resp = await client.get(url, headers=_auth_headers(access_token))
    if resp.status_code in (404, 410):
        return False
    # For any non-success other than not-found, assume it still exists so we do
    # not create duplicates on a transient error.
    return True


def _bearer(access_token: str) -> str:
    return "Bearer " + access_token

