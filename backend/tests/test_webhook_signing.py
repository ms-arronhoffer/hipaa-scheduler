"""Webhook HMAC signer / verifier — the format is contractual with subscribers,
so any accidental change should break these tests loudly."""
from datetime import datetime

import pytest

from app.services.webhook_service import sign_payload, verify_signature, build_envelope


class TestSignPayload:
    def test_format_matches_documented_contract(self):
        header = sign_payload("secret", b'{"hello":"world"}', ts=1700000000)
        assert header.startswith("t=1700000000,v1=")
        _, sig = header.split("v1=")
        assert len(sig) == 64  # sha256 hex
        assert all(c in "0123456789abcdef" for c in sig)

    def test_different_secret_produces_different_sig(self):
        body = b"payload"
        assert sign_payload("a", body, 1) != sign_payload("b", body, 1)

    def test_different_body_produces_different_sig(self):
        assert sign_payload("s", b"a", 1) != sign_payload("s", b"b", 1)

    def test_different_ts_produces_different_sig(self):
        assert sign_payload("s", b"body", 1) != sign_payload("s", b"body", 2)


class TestVerifySignature:
    def test_roundtrip_valid(self):
        body = b'{"event":"appointment.created"}'
        ts = int(datetime.utcnow().timestamp())
        header = sign_payload("shh", body, ts)
        assert verify_signature("shh", body, header) is True

    def test_wrong_secret_rejected(self):
        body = b"x"
        ts = int(datetime.utcnow().timestamp())
        header = sign_payload("right", body, ts)
        assert verify_signature("wrong", body, header) is False

    def test_tampered_body_rejected(self):
        ts = int(datetime.utcnow().timestamp())
        header = sign_payload("s", b"original", ts)
        assert verify_signature("s", b"tampered", header) is False

    def test_stale_ts_rejected(self):
        stale = int(datetime.utcnow().timestamp()) - 3600
        header = sign_payload("s", b"x", stale)
        assert verify_signature("s", b"x", header) is False

    def test_future_ts_rejected(self):
        future = int(datetime.utcnow().timestamp()) + 3600
        header = sign_payload("s", b"x", future)
        assert verify_signature("s", b"x", header) is False

    def test_malformed_header_rejected(self):
        assert verify_signature("s", b"x", "garbage") is False
        assert verify_signature("s", b"x", "t=abc,v1=def") is False
        assert verify_signature("s", b"x", "") is False

    def test_custom_skew_window(self):
        old = int(datetime.utcnow().timestamp()) - 400
        header = sign_payload("s", b"x", old)
        assert verify_signature("s", b"x", header, max_skew_seconds=60) is False
        assert verify_signature("s", b"x", header, max_skew_seconds=600) is True


class TestBuildEnvelope:
    def test_envelope_shape(self):
        import uuid
        org = uuid.uuid4()
        env = build_envelope("appointment.canceled", org, {"id": "abc"})
        assert env["event"] == "appointment.canceled"
        assert env["org_id"] == str(org)
        assert env["data"] == {"id": "abc"}
        assert "id" in env and "occurred_at" in env
        # occurred_at is ISO 8601 with Z suffix
        assert env["occurred_at"].endswith("Z")
