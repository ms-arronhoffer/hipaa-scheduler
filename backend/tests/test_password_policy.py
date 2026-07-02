"""Password strength/breach/reuse policy — unit-tier (no DB, mocked HIBP)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.auth import password_policy
from app.services import password_service


class TestValidateStrength:
    def test_too_short_rejected(self, monkeypatch):
        monkeypatch.setattr(password_policy.settings, "password_min_length", 12)
        with pytest.raises(password_policy.PasswordPolicyError) as ei:
            password_policy.validate_strength("Ab1!xyz")  # 7 chars
        assert any("at least 12" in r for r in ei.value.reasons)

    def test_common_password_rejected(self, monkeypatch):
        monkeypatch.setattr(password_policy.settings, "password_min_length", 6)
        with pytest.raises(password_policy.PasswordPolicyError):
            password_policy.validate_strength("password123")

    def test_low_entropy_repeated_char_rejected(self, monkeypatch):
        monkeypatch.setattr(password_policy.settings, "password_min_length", 12)
        with pytest.raises(password_policy.PasswordPolicyError):
            password_policy.validate_strength("aaaaaaaaaaaaaaaa")

    def test_context_email_rejected(self, monkeypatch):
        monkeypatch.setattr(password_policy.settings, "password_min_length", 8)
        with pytest.raises(password_policy.PasswordPolicyError) as ei:
            password_policy.validate_strength(
                "Jsmith-Str0ng!!", user_inputs=["jsmith@clinic.test"]
            )
        assert any("name or email" in r for r in ei.value.reasons)

    def test_strong_password_passes(self, monkeypatch):
        monkeypatch.setattr(password_policy.settings, "password_min_length", 12)
        password_policy.validate_strength("Tr0ub4dour&3xplorer")  # no raise


class TestHibpParse:
    def test_match_returns_count(self):
        body = "0018A45C4D1DEF81644B54AB7F969B88D65:42\nAAAA:1"
        assert password_policy._parse_hibp_response(body, "0018A45C4D1DEF81644B54AB7F969B88D65") == 42

    def test_no_match_returns_zero(self):
        body = "0018A45C4D1DEF81644B54AB7F969B88D65:42"
        assert password_policy._parse_hibp_response(body, "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF") == 0

    def test_case_insensitive(self):
        body = "abcdef:7"
        assert password_policy._parse_hibp_response(body, "ABCDEF") == 7


class TestEnforce:
    async def test_enforce_blocks_breached(self, monkeypatch):
        monkeypatch.setattr(password_policy.settings, "password_min_length", 8)

        async def fake_count(_pw):
            return 999

        monkeypatch.setattr(password_policy, "hibp_breach_count", fake_count)
        with pytest.raises(password_policy.PasswordPolicyError) as ei:
            await password_policy.enforce("Str0ng-Uniqu3-Pass!", check_breach=True)
        assert any("breach" in r for r in ei.value.reasons)

    async def test_enforce_skips_breach_when_disabled(self, monkeypatch):
        monkeypatch.setattr(password_policy.settings, "password_min_length", 8)

        async def fake_count(_pw):  # pragma: no cover - must not be called
            raise AssertionError("should not check breach")

        monkeypatch.setattr(password_policy, "hibp_breach_count", fake_count)
        await password_policy.enforce("Str0ng-Uniqu3-Pass!", check_breach=False)

    async def test_hibp_fails_open_outside_production(self, monkeypatch):
        monkeypatch.setattr(password_policy.settings, "password_hibp_enabled", True)
        monkeypatch.setattr(password_policy.settings, "app_env", "development")
        assert await password_policy.hibp_breach_count("anything") == 0


class TestExpiry:
    def test_no_expiry_never_expired(self):
        u = SimpleNamespace(password_expires_at=None)
        assert password_service.is_expired(u) is False

    def test_past_expiry_is_expired(self):
        past = datetime.now(timezone.utc) - timedelta(days=1)
        u = SimpleNamespace(password_expires_at=past)
        assert password_service.is_expired(u) is True

    def test_future_expiry_not_expired(self):
        future = datetime.now(timezone.utc) + timedelta(days=1)
        u = SimpleNamespace(password_expires_at=future)
        assert password_service.is_expired(u) is False
