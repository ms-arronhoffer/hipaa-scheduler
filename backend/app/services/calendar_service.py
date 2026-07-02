"""Calendar OAuth token maintenance for two-way sync connections.

Full bidirectional event reconciliation (pulling external events and pushing
appointment changes) is a large integration surface; this module implements the
piece the worker needs to keep connections *alive*: refreshing OAuth access
tokens before they expire so a later reconcile pass has valid credentials.

Only the refresh half is wired here. Event reconciliation is intentionally a
documented hook (:func:`reconcile_events`) rather than a silent no-op, so the
remaining work is discoverable.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.calendar_connection import CalendarConnection

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
    """Pull/push events for a connection.

    NOT YET IMPLEMENTED — placeholder hook for the remaining two-way sync work.
    Returns the number of events reconciled (always 0 today). Kept explicit so
    the gap is visible in code rather than hidden behind a silent pass.
    """
    return 0
