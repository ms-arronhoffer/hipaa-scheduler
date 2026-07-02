"""Unit tests for the calendar OAuth authorization flow (no network / no DB).

Network calls (`exchange_code`, `fetch_account_email`) are exercised through a
stubbed `httpx.AsyncClient`, mirroring the pattern in `test_webhook_delivery`.
"""
from __future__ import annotations

import uuid

import pytest
from pydantic import SecretStr

from app.services import calendar_oauth


@pytest.fixture(autouse=True)
def _configure_google(monkeypatch):
    monkeypatch.setattr(calendar_oauth.settings, "google_oauth_id", "gid.apps", raising=False)
    monkeypatch.setattr(calendar_oauth.settings, "google_oauth_secret", SecretStr("gsecret"), raising=False)
    monkeypatch.setattr(calendar_oauth.settings, "ms_oauth_id", None, raising=False)
    monkeypatch.setattr(calendar_oauth.settings, "ms_oauth_secret", None, raising=False)
    monkeypatch.setattr(calendar_oauth.settings, "google_oauth_redirect_uri", None, raising=False)
    monkeypatch.setattr(calendar_oauth.settings, "frontend_url", "https://portal.example", raising=False)


class _Resp:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _Client:
    """Stub httpx.AsyncClient recording the last request."""

    def __init__(self, resp):
        self._resp = resp
        self.calls: list[tuple] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, **kw):
        self.calls.append(("POST", url, kw))
        return self._resp

    async def get(self, url, **kw):
        self.calls.append(("GET", url, kw))
        return self._resp


# ---- state signing ------------------------------------------------------------


class TestState:
    def test_roundtrip(self):
        org, user = uuid.uuid4(), uuid.uuid4()
        token = calendar_oauth.sign_state(org_id=org, user_id=user, provider="google")
        claims = calendar_oauth.verify_state(token)
        assert claims["org_id"] == str(org)
        assert claims["user_id"] == str(user)
        assert claims["provider"] == "google"

    def test_tampered_state_rejected(self):
        token = calendar_oauth.sign_state(org_id=uuid.uuid4(), user_id=uuid.uuid4(), provider="google")
        with pytest.raises(calendar_oauth.OAuthError):
            calendar_oauth.verify_state(token + "x")

    def test_expired_state_rejected(self, monkeypatch):
        import datetime as _dt

        token = calendar_oauth.sign_state(org_id=uuid.uuid4(), user_id=uuid.uuid4(), provider="google")
        # Fast-forward past the 10-minute TTL by patching jwt's clock leeway is
        # awkward; instead re-sign with an already-expired exp.
        real = calendar_oauth._STATE_TTL
        monkeypatch.setattr(calendar_oauth, "_STATE_TTL", _dt.timedelta(seconds=-1))
        expired = calendar_oauth.sign_state(org_id=uuid.uuid4(), user_id=uuid.uuid4(), provider="google")
        monkeypatch.setattr(calendar_oauth, "_STATE_TTL", real)
        with pytest.raises(calendar_oauth.OAuthError):
            calendar_oauth.verify_state(expired)


# ---- authorize url ------------------------------------------------------------


class TestAuthorizeUrl:
    def test_contains_required_params(self):
        state = "state123"
        url = calendar_oauth.build_authorize_url("google", state=state)
        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
        assert "client_id=gid.apps" in url
        assert "response_type=code" in url
        assert "state=state123" in url
        assert "access_type=offline" in url
        # scope is url-encoded; calendar.events must be present
        assert "calendar.events" in url

    def test_unknown_provider_raises(self):
        with pytest.raises(calendar_oauth.OAuthError):
            calendar_oauth.build_authorize_url("dropbox", state="x")

    def test_unconfigured_provider_raises(self):
        with pytest.raises(calendar_oauth.OAuthError):
            calendar_oauth.build_authorize_url("o365", state="x")


class TestRedirectUri:
    def test_derived_from_frontend_url(self):
        assert calendar_oauth.redirect_uri("google") == (
            "https://portal.example/api/v1/calendar-connections/oauth/google/callback"
        )

    def test_explicit_override(self, monkeypatch):
        monkeypatch.setattr(
            calendar_oauth.settings, "google_oauth_redirect_uri",
            "https://api.example/cb", raising=False,
        )
        assert calendar_oauth.redirect_uri("google") == "https://api.example/cb"


class TestIsConfigured:
    def test_google_configured(self):
        assert calendar_oauth.is_configured("google") is True

    def test_o365_not_configured(self):
        assert calendar_oauth.is_configured("o365") is False


# ---- token exchange -----------------------------------------------------------


class TestExchangeCode:
    async def test_success(self, monkeypatch):
        resp = _Resp(200, {"access_token": "at", "refresh_token": "rt", "expires_in": 3600, "scope": "a b"})
        client = _Client(resp)
        monkeypatch.setattr(calendar_oauth.httpx, "AsyncClient", lambda *a, **k: client)
        bundle = await calendar_oauth.exchange_code("google", code="thecode")
        assert bundle.access_token == "at"
        assert bundle.refresh_token == "rt"
        assert bundle.scopes == ("a", "b")
        # posted to google's token endpoint with the code
        method, url, kw = client.calls[0]
        assert url == "https://oauth2.googleapis.com/token"
        assert kw["data"]["code"] == "thecode"
        assert kw["data"]["grant_type"] == "authorization_code"

    async def test_provider_error_raises(self, monkeypatch):
        client = _Client(_Resp(400, {"error": "invalid_grant"}))
        monkeypatch.setattr(calendar_oauth.httpx, "AsyncClient", lambda *a, **k: client)
        with pytest.raises(calendar_oauth.OAuthError):
            await calendar_oauth.exchange_code("google", code="bad")

    async def test_missing_access_token_raises(self, monkeypatch):
        client = _Client(_Resp(200, {"refresh_token": "rt"}))
        monkeypatch.setattr(calendar_oauth.httpx, "AsyncClient", lambda *a, **k: client)
        with pytest.raises(calendar_oauth.OAuthError):
            await calendar_oauth.exchange_code("google", code="x")


class TestFetchAccountEmail:
    async def test_google_email(self, monkeypatch):
        client = _Client(_Resp(200, {"email": "doc@example.com"}))
        monkeypatch.setattr(calendar_oauth.httpx, "AsyncClient", lambda *a, **k: client)
        email = await calendar_oauth.fetch_account_email("google", access_token="at")
        assert email == "doc@example.com"

    async def test_graph_upn_fallback(self, monkeypatch):
        client = _Client(_Resp(200, {"userPrincipalName": "doc@contoso.com"}))
        monkeypatch.setattr(calendar_oauth.httpx, "AsyncClient", lambda *a, **k: client)
        email = await calendar_oauth.fetch_account_email("o365", access_token="at")
        assert email == "doc@contoso.com"

    async def test_error_returns_empty(self, monkeypatch):
        client = _Client(_Resp(500))
        monkeypatch.setattr(calendar_oauth.httpx, "AsyncClient", lambda *a, **k: client)
        email = await calendar_oauth.fetch_account_email("google", access_token="at")
        assert email == ""
