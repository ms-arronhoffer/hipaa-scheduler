"""Google / Microsoft 365 OAuth authorization-code flow for calendar sync.

This module owns everything needed to *establish* a :class:`CalendarConnection`:

- provider metadata (authorize/token/userinfo endpoints + requested scopes)
- a signed, short-lived ``state`` token that carries the initiating org + user
  across the provider round-trip (CSRF + identity binding; verified on the
  callback, which arrives without our own auth cookie/JWT)
- building the provider authorization URL
- exchanging the returned ``code`` for tokens
- reading the authorized account's email so the connection can be labelled

Token *refresh* and event *reconciliation* live in
:mod:`app.services.calendar_service`; this module is only the front door.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt

from app.config import settings

log = logging.getLogger(__name__)

OAUTH_PROVIDERS = ("google", "o365")

# State token is signed with the app JWT secret under a dedicated audience so it
# can never be confused with a staff/patient access token.
_STATE_AUD = "calendar_oauth"
_STATE_TTL = timedelta(minutes=10)
_STATE_ALG = "HS256"


class OAuthError(Exception):
    """Raised for any recoverable problem in the authorization flow."""


@dataclass(frozen=True)
class ProviderMeta:
    authorize_url: str
    token_url: str
    userinfo_url: str
    scopes: tuple[str, ...]
    # Extra params merged into the authorization request (provider specific).
    extra_authorize_params: dict[str, str]


PROVIDER_META: dict[str, ProviderMeta] = {
    "google": ProviderMeta(
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://www.googleapis.com/oauth2/v3/userinfo",
        scopes=(
            "openid",
            "email",
            "https://www.googleapis.com/auth/calendar.events",
        ),
        # offline + consent guarantees a refresh_token is returned every time.
        extra_authorize_params={
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        },
    ),
    "o365": ProviderMeta(
        authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        userinfo_url="https://graph.microsoft.com/v1.0/me",
        scopes=(
            "offline_access",
            "openid",
            "email",
            "https://graph.microsoft.com/Calendars.ReadWrite",
        ),
        extra_authorize_params={"response_mode": "query"},
    ),
}


def _client_credentials(provider: str) -> tuple[str, str]:
    if provider == "google":
        cid, secret = settings.google_oauth_id, settings.google_oauth_secret
    elif provider == "o365":
        cid, secret = settings.ms_oauth_id, settings.ms_oauth_secret
    else:  # pragma: no cover - guarded by callers
        raise OAuthError(f"unknown provider {provider}")
    if not cid or not secret:
        raise OAuthError(f"{provider} OAuth is not configured")
    return cid, secret.get_secret_value()


def is_configured(provider: str) -> bool:
    try:
        _client_credentials(provider)
    except OAuthError:
        return False
    return True


def redirect_uri(provider: str) -> str:
    """Public callback URI the provider redirects the browser back to."""
    if provider == "google" and settings.google_oauth_redirect_uri:
        return settings.google_oauth_redirect_uri
    if provider == "o365" and settings.ms_oauth_redirect_uri:
        return settings.ms_oauth_redirect_uri
    base = settings.frontend_url.rstrip("/")
    return f"{base}/api/v1/calendar-connections/oauth/{provider}/callback"


# ---- signed state -------------------------------------------------------------


def sign_state(*, org_id: uuid.UUID, user_id: uuid.UUID, provider: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "aud": _STATE_AUD,
        "iss": settings.jwt_issuer,
        "org_id": str(org_id),
        "user_id": str(user_id),
        "provider": provider,
        "nonce": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int((now + _STATE_TTL).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=_STATE_ALG)


def verify_state(state: str) -> dict:
    try:
        claims = jwt.decode(
            state,
            settings.jwt_secret.get_secret_value(),
            algorithms=[_STATE_ALG],
            audience=_STATE_AUD,
        )
    except jwt.PyJWTError as exc:
        raise OAuthError("invalid or expired state") from exc
    if claims.get("provider") not in OAUTH_PROVIDERS:
        raise OAuthError("state provider mismatch")
    return claims


# ---- authorization URL --------------------------------------------------------


def build_authorize_url(provider: str, *, state: str) -> str:
    if provider not in PROVIDER_META:
        raise OAuthError(f"unknown provider {provider}")
    client_id, _ = _client_credentials(provider)
    meta = PROVIDER_META[provider]
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri(provider),
        "response_type": "code",
        "scope": " ".join(meta.scopes),
        "state": state,
        **meta.extra_authorize_params,
    }
    return f"{meta.authorize_url}?{urlencode(params)}"


# ---- token exchange -----------------------------------------------------------


@dataclass(frozen=True)
class TokenBundle:
    access_token: str
    refresh_token: str | None
    expires_at: datetime
    scopes: tuple[str, ...]


def _parse_token_response(provider: str, payload: dict) -> TokenBundle:
    access = payload.get("access_token")
    if not access:
        raise OAuthError(f"{provider} token response missing access_token")
    expires_in = int(payload.get("expires_in", 3600))
    scope_str = payload.get("scope") or " ".join(PROVIDER_META[provider].scopes)
    return TokenBundle(
        access_token=access,
        refresh_token=payload.get("refresh_token"),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        scopes=tuple(scope_str.split()),
    )


async def exchange_code(provider: str, *, code: str) -> TokenBundle:
    client_id, client_secret = _client_credentials(provider)
    meta = PROVIDER_META[provider]
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri(provider),
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(meta.token_url, data=data)
    except httpx.HTTPError as exc:
        raise OAuthError(f"token exchange failed: {type(exc).__name__}") from exc
    if resp.status_code >= 300:
        log.warning("calendar.oauth_exchange_failed", extra={"provider": provider, "status": resp.status_code})
        raise OAuthError("token exchange rejected by provider")
    return _parse_token_response(provider, resp.json())


async def fetch_account_email(provider: str, *, access_token: str) -> str:
    """Return the authorized account's email (best-effort, falls back to '')."""
    meta = PROVIDER_META[provider]
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(meta.userinfo_url, headers=headers)
        if resp.status_code >= 300:
            return ""
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return ""
    # google userinfo → "email"; graph /me → "mail" or "userPrincipalName".
    return data.get("email") or data.get("mail") or data.get("userPrincipalName") or ""
