"""Unit tests for SMS opt-in keyword parsing, Twilio signature validation,
and notification delivery-retry scheduling (no DB)."""
from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime

import pytest
from pydantic import SecretStr

from app.config import settings
from app.services import notification_service, sms_service


class TestParseInboundKeyword:
    @pytest.mark.parametrize("word", ["STOP", "stop", " Stop ", "UNSUBSCRIBE", "cancel", "QUIT"])
    def test_stop_variants(self, word):
        assert sms_service.parse_inbound_keyword(word) == "stop"

    @pytest.mark.parametrize("word", ["START", "unstop"])
    def test_start_variants(self, word):
        assert sms_service.parse_inbound_keyword(word) == "start"

    @pytest.mark.parametrize("word", ["YES", "y", "opt in"])
    def test_confirm_variants(self, word):
        assert sms_service.parse_inbound_keyword(word) == "confirm"

    @pytest.mark.parametrize("word", ["", None, "hello", "please stop it"])
    def test_unrecognized(self, word):
        assert sms_service.parse_inbound_keyword(word) is None


class TestVerifyTwilioSignature:
    def _sign(self, token: str, url: str, params: dict) -> str:
        data = url + "".join(k + params[k] for k in sorted(params))
        digest = hmac.new(token.encode(), data.encode(), hashlib.sha1).digest()
        return base64.b64encode(digest).decode()

    def test_valid_signature(self, monkeypatch):
        token = "test-twilio-token"
        monkeypatch.setattr(settings, "twilio_token", SecretStr(token))
        url = "https://api.example.com/api/v1/pub/sms/inbound"
        params = {"From": "+15550001111", "Body": "STOP"}
        sig = self._sign(token, url, params)
        assert sms_service.verify_twilio_signature(url, params, sig) is True

    def test_tampered_body_rejected(self, monkeypatch):
        token = "test-twilio-token"
        monkeypatch.setattr(settings, "twilio_token", SecretStr(token))
        url = "https://api.example.com/api/v1/pub/sms/inbound"
        params = {"From": "+15550001111", "Body": "STOP"}
        sig = self._sign(token, url, params)
        params["Body"] = "START"
        assert sms_service.verify_twilio_signature(url, params, sig) is False

    def test_missing_token_fails_closed(self, monkeypatch):
        monkeypatch.setattr(settings, "twilio_token", None)
        assert sms_service.verify_twilio_signature("u", {}, "sig") is False

    def test_missing_signature_fails_closed(self, monkeypatch):
        monkeypatch.setattr(settings, "twilio_token", SecretStr("tok"))
        assert sms_service.verify_twilio_signature("u", {}, None) is False


class TestNextRetryAt:
    def test_first_failure_schedules_soon(self, monkeypatch):
        monkeypatch.setattr(settings, "notification_max_attempts", 4)
        monkeypatch.setattr(settings, "notification_retry_delays_min", [1, 5, 30, 120])
        now = datetime(2026, 7, 2, 12, 0, 0)
        nxt = notification_service.next_retry_at(1, now=now)
        assert nxt == datetime(2026, 7, 2, 12, 1, 0)

    def test_backoff_increases(self, monkeypatch):
        monkeypatch.setattr(settings, "notification_max_attempts", 4)
        monkeypatch.setattr(settings, "notification_retry_delays_min", [1, 5, 30, 120])
        now = datetime(2026, 7, 2, 12, 0, 0)
        assert notification_service.next_retry_at(2, now=now) == datetime(2026, 7, 2, 12, 5, 0)
        assert notification_service.next_retry_at(3, now=now) == datetime(2026, 7, 2, 12, 30, 0)

    def test_exhausted_returns_none(self, monkeypatch):
        monkeypatch.setattr(settings, "notification_max_attempts", 4)
        assert notification_service.next_retry_at(4) is None
        assert notification_service.next_retry_at(9) is None

    def test_delay_index_clamped(self, monkeypatch):
        monkeypatch.setattr(settings, "notification_max_attempts", 10)
        monkeypatch.setattr(settings, "notification_retry_delays_min", [1, 5])
        now = datetime(2026, 7, 2, 12, 0, 0)
        # attempts beyond the schedule reuse the last (longest) delay
        assert notification_service.next_retry_at(5, now=now) == datetime(2026, 7, 2, 12, 5, 0)
