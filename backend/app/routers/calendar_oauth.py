"""Google / Microsoft 365 calendar OAuth authorization endpoints.

Two-legged browser flow:

1. ``POST /calendar-connections/oauth/{provider}/authorize`` — staff-authenticated.
   Returns the provider ``authorization_url`` (with a signed ``state`` that binds
   the connection to the caller's org + user). The SPA sends the browser there.
2. ``GET  /calendar-connections/oauth/{provider}/callback`` — the provider
   redirects the browser back here with ``code`` + ``state``. There is no app
   JWT on this request, so identity comes entirely from the verified ``state``.
   We exchange the code, upsert the :class:`CalendarConnection`, then redirect
   the browser to the staff settings page.

The worker (``calendar_pull``) keeps the tokens fresh and reconciles events.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.config import settings
from app.database import get_db
from app.guards.deps import require_role
from app.models.activity_log import ActivityLog
from app.models.calendar_connection import CalendarConnection
from app.schemas.integrations import CalendarAuthorizeResponse
from app.services import calendar_oauth

router = APIRouter(prefix="/calendar-connections/oauth", tags=["calendar_sync"])


def _require_provider(provider: str) -> str:
    if provider not in calendar_oauth.OAUTH_PROVIDERS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown provider")
    if not calendar_oauth.is_configured(provider):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"{provider} OAuth not configured")
    return provider


def _settings_redirect(outcome: str) -> RedirectResponse:
    base = settings.frontend_url.rstrip("/")
    path = settings.calendar_oauth_success_path
    if not path.startswith("/"):
        path = "/" + path
    return RedirectResponse(url=f"{base}{path}?calendar={outcome}", status_code=status.HTTP_302_FOUND)


@router.post("/{provider}/authorize", response_model=CalendarAuthorizeResponse)
async def start_authorization(
    provider: str,
    p: Principal = Depends(require_role("practice_admin", "provider")),
) -> CalendarAuthorizeResponse:
    _require_provider(provider)
    state = calendar_oauth.sign_state(org_id=p.org_id, user_id=p.subject_id, provider=provider)
    url = calendar_oauth.build_authorize_url(provider, state=state)
    return CalendarAuthorizeResponse(authorization_url=url, state=state)


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    _require_provider(provider)
    if error or not code or not state:
        return _settings_redirect("error")
    try:
        claims = calendar_oauth.verify_state(state)
    except calendar_oauth.OAuthError:
        return _settings_redirect("error")
    if claims.get("provider") != provider:
        return _settings_redirect("error")

    import uuid as _uuid

    org_id = _uuid.UUID(claims["org_id"])
    user_id = _uuid.UUID(claims["user_id"])

    try:
        bundle = await calendar_oauth.exchange_code(provider, code=code)
    except calendar_oauth.OAuthError:
        return _settings_redirect("error")

    account_email = await calendar_oauth.fetch_account_email(
        provider, access_token=bundle.access_token
    )

    # Upsert on (org, user, provider, account_email). A soft-deleted row is
    # revived rather than duplicated.
    existing = (await db.execute(
        select(CalendarConnection).where(
            CalendarConnection.org_id == org_id,
            CalendarConnection.user_id == user_id,
            CalendarConnection.provider == provider,
            CalendarConnection.account_email == account_email,
        )
    )).scalar_one_or_none()

    scopes_map = {"granted": list(bundle.scopes)}
    if existing is None:
        conn = CalendarConnection(
            org_id=org_id,
            user_id=user_id,
            provider=provider,
            account_email=account_email,
            calendar_id="primary",
            access_token_ct=bundle.access_token,
            refresh_token_ct=bundle.refresh_token,
            token_expires_at=bundle.expires_at,
            scopes=scopes_map,
            active=True,
        )
        db.add(conn)
        action = "connected"
    else:
        existing.access_token_ct = bundle.access_token
        if bundle.refresh_token:
            existing.refresh_token_ct = bundle.refresh_token
        existing.token_expires_at = bundle.expires_at
        existing.scopes = scopes_map
        existing.active = True
        existing.deleted_at = None
        conn = existing
        action = "reconnected"

    await db.flush()
    db.add(ActivityLog(
        org_id=org_id, actor_type="user", actor_id=user_id, actor_email=account_email or None,
        entity_type="calendar_connection", entity_id=conn.id, action=action,
        changes={"provider": provider, "account_email": account_email},
    ))
    return _settings_redirect("connected")
