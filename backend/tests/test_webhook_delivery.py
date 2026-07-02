"""Webhook delivery state machine — retry/backoff/dead-letter transitions.

Unit-tier: no DB. We hand-build a lightweight delivery stand-in with the
attributes ``deliver_once`` touches and drive it through a stubbed HTTP client.
"""
from __future__ import annotations

import types

import pytest

from app.services import webhook_service


class _Delivery:
    """Minimal stand-in for the WebhookDelivery ORM row."""

    def __init__(self):
        self.attempt = 0
        self.status = "pending"
        self.response_status = None
        self.response_body_snippet = None
        self.next_attempt_at = None
        self.last_attempt_at = None
        self.delivered_at = None
        self.payload = {"event": "appointment.created", "data": {}}
        self.event = "appointment.created"
        self.id = "00000000-0000-0000-0000-000000000001"


class _Resp:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


class _Client:
    """Async-context stub mimicking httpx.AsyncClient with a canned response."""

    def __init__(self, resp=None, raise_exc=None):
        self._resp = resp
        self._raise = raise_exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, *a, **k):
        if self._raise:
            raise self._raise
        return self._resp


@pytest.fixture
def db():
    # deliver_once never touches the session in the unit path.
    return None


async def _run(monkeypatch, delivery, resp=None, raise_exc=None, *, secret="whsec_x"):
    monkeypatch.setattr(
        webhook_service.httpx,
        "AsyncClient",
        lambda *a, **k: _Client(resp=resp, raise_exc=raise_exc),
    )
    return await webhook_service.deliver_once(
        None, delivery, subscription_secret=secret, target_url="https://example.test/hook"
    )


class TestDeliverOnce:
    async def test_2xx_marks_delivered(self, monkeypatch):
        d = _Delivery()
        await _run(monkeypatch, d, resp=_Resp(200, "ok"))
        assert d.status == "delivered"
        assert d.delivered_at is not None
        assert d.next_attempt_at is None
        assert d.attempt == 1

    async def test_5xx_reschedules_pending_with_backoff(self, monkeypatch):
        d = _Delivery()
        await _run(monkeypatch, d, resp=_Resp(500, "boom"))
        assert d.status == "pending"
        assert d.next_attempt_at is not None
        assert d.response_status == 500

    async def test_transport_error_reschedules(self, monkeypatch):
        d = _Delivery()
        await _run(monkeypatch, d, raise_exc=webhook_service.httpx.ConnectError("down"))
        assert d.status == "pending"
        assert d.response_status is None
        assert d.response_body_snippet.startswith("transport:")

    async def test_exhaustion_dead_letters(self, monkeypatch):
        d = _Delivery()
        d.attempt = webhook_service.max_attempts() - 1  # this call is the last
        await _run(monkeypatch, d, resp=_Resp(503))
        assert d.status == "dead_letter"
        assert d.next_attempt_at is None


class TestMaxAttemptsConfig:
    def test_max_attempts_reads_config(self, monkeypatch):
        monkeypatch.setattr(webhook_service.settings, "webhook_max_attempts", 3)
        assert webhook_service.max_attempts() == 3

    def test_backoff_index_is_clamped(self):
        # Beyond the schedule length, reuse the last (longest) delay.
        last = webhook_service.RETRY_DELAYS[-1]
        assert webhook_service._retry_delay(999) == last
        assert webhook_service._retry_delay(1) == webhook_service.RETRY_DELAYS[0]
