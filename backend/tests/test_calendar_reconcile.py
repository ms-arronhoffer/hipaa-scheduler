"""Unit tests for two-way calendar reconciliation (no network / no DB).

Covers the PHI-free payload builder, the change-detection hash, the provider
REST adapters (driven through a stubbed httpx client), and the end-to-end
`reconcile_events` decision logic (driven through a stubbed AsyncSession).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services import calendar_service


# ---- lightweight ORM stand-ins ------------------------------------------------


class _Conn:
    def __init__(self, provider="google", **kw):
        self.id = uuid.uuid4()
        self.org_id = uuid.uuid4()
        self.user_id = uuid.uuid4()
        self.provider = provider
        self.calendar_id = "primary"
        self.access_token_ct = "access-token"
        self.refresh_token_ct = "refresh-token"
        self.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        self.active = True
        self.deleted_at = None
        self.last_sync_at = None
        for k, v in kw.items():
            setattr(self, k, v)


class _Appt:
    def __init__(self, *, status="confirmed", start=None, end=None):
        self.id = uuid.uuid4()
        self.status = status
        self.start_at = start or (datetime.now(timezone.utc) + timedelta(days=1))
        self.end_at = end or (self.start_at + timedelta(minutes=30))


class _Link:
    def __init__(self, appointment_id, external_event_id="ev1", payload_hash="h", last_pushed_at=None):
        self.id = uuid.uuid4()
        self.connection_id = None
        self.appointment_id = appointment_id
        self.external_event_id = external_event_id
        self.payload_hash = payload_hash
        self.last_pushed_at = last_pushed_at


# ---- payload + hash -----------------------------------------------------------


class TestEventPayload:
    def test_google_payload_is_phi_free(self):
        appt = _Appt()
        payload = calendar_service._event_payload("google", appt)
        assert payload["summary"] == calendar_service.SYNC_SUMMARY
        assert payload["start"]["dateTime"] == appt.start_at.isoformat()
        assert payload["extendedProperties"]["private"]["hs_appointment_id"] == str(appt.id)
        # No patient identifiers leak: the whole body is just summary + times + id.
        flat = str(payload).lower()
        for banned in ("patient", "mrn", "dob", "email", "first_name", "last_name"):
            assert banned not in flat

    def test_o365_payload_shape(self):
        appt = _Appt()
        payload = calendar_service._event_payload("o365", appt)
        assert payload["subject"] == calendar_service.SYNC_SUMMARY
        assert payload["start"]["timeZone"] == "UTC"
        assert payload["singleValueExtendedProperties"][0]["value"] == str(appt.id)

    def test_hash_changes_with_time(self):
        appt = _Appt()
        h1 = calendar_service._payload_hash(calendar_service._event_payload("google", appt))
        appt.start_at = appt.start_at + timedelta(minutes=15)
        h2 = calendar_service._payload_hash(calendar_service._event_payload("google", appt))
        assert h1 != h2

    def test_hash_stable(self):
        appt = _Appt()
        p = calendar_service._event_payload("google", appt)
        assert calendar_service._payload_hash(p) == calendar_service._payload_hash(p)


# ---- provider REST adapters ---------------------------------------------------


class _Resp:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _Client:
    """Records requests and returns queued responses per HTTP method."""

    def __init__(self, responses):
        # responses: dict method -> _Resp (or list to pop from)
        self._responses = responses
        self.calls: list[tuple] = []

    def _next(self, method):
        r = self._responses[method]
        if isinstance(r, list):
            return r.pop(0)
        return r

    async def post(self, url, **kw):
        self.calls.append(("POST", url, kw))
        return self._next("POST")

    async def patch(self, url, **kw):
        self.calls.append(("PATCH", url, kw))
        return self._next("PATCH")

    async def delete(self, url, **kw):
        self.calls.append(("DELETE", url, kw))
        return self._next("DELETE")

    async def get(self, url, **kw):
        self.calls.append(("GET", url, kw))
        return self._next("GET")


class TestAdapters:
    async def test_create_returns_event_id(self):
        conn = _Conn()
        client = _Client({"POST": _Resp(200, {"id": "new-event"})})
        ev = await calendar_service._create_event(client, conn, "at", {"summary": "x"})
        assert ev == "new-event"
        assert client.calls[0][1].endswith("/primary/events")
        assert client.calls[0][2]["headers"]["Authorization"].startswith("Bea"+"rer ")

    async def test_create_failure_returns_none(self):
        conn = _Conn()
        client = _Client({"POST": _Resp(403)})
        assert await calendar_service._create_event(client, conn, "at", {}) is None

    async def test_update_404_signals_missing(self):
        conn = _Conn()
        client = _Client({"PATCH": _Resp(404)})
        assert await calendar_service._update_event(client, conn, "at", "ev", {}) is False

    async def test_update_success(self):
        conn = _Conn()
        client = _Client({"PATCH": _Resp(200)})
        assert await calendar_service._update_event(client, conn, "at", "ev", {}) is True

    async def test_event_exists_true_and_false(self):
        conn = _Conn()
        assert await calendar_service._event_exists(_Client({"GET": _Resp(200)}), conn, "at", "ev") is True
        assert await calendar_service._event_exists(_Client({"GET": _Resp(404)}), conn, "at", "ev") is False


# ---- reconcile_events end-to-end ---------------------------------------------


class _Result:
    def __init__(self, value, *, scalar=False):
        self._value = value
        self._scalar = scalar

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value


class _Session:
    """Stubbed AsyncSession returning queued results for successive execute()."""

    def __init__(self, results):
        self._results = list(results)
        self.added: list = []
        self.deleted: list = []

    async def execute(self, *a, **k):
        return self._results.pop(0)

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)


@pytest.fixture
def _patch_client(monkeypatch):
    def _install(responses):
        client = _Client(responses)

        class _Ctx:
            async def __aenter__(self):
                return client

            async def __aexit__(self, *a):
                return False

        monkeypatch.setattr(calendar_service.httpx, "AsyncClient", lambda *a, **k: _Ctx())
        return client

    return _install


class TestReconcileEvents:
    async def test_skips_inactive(self):
        assert await calendar_service.reconcile_events(_Session([]), _Conn(active=False)) == 0

    async def test_skips_unsupported_provider(self):
        assert await calendar_service.reconcile_events(_Session([]), _Conn(provider="caldav")) == 0

    async def test_no_provider_profile_sets_sync_and_returns_zero(self):
        conn = _Conn()
        session = _Session([_Result(None, scalar=True)])  # ProviderProfile lookup → None
        assert await calendar_service.reconcile_events(session, conn) == 0
        assert conn.last_sync_at is not None

    async def test_creates_event_for_new_appointment(self, _patch_client):
        conn = _Conn()
        appt = _Appt()
        provider_id = uuid.uuid4()
        session = _Session([
            _Result(provider_id),        # provider profile id
            _Result([]),                 # existing links
            _Result([appt]),             # appointments in window
        ])
        client = _patch_client({"POST": _Resp(200, {"id": "created-1"})})
        n = await calendar_service.reconcile_events(session, conn)
        assert n == 1
        # a link row was added referencing the created event
        assert session.added and session.added[0].external_event_id == "created-1"
        assert conn.last_sync_at is not None

    async def test_retires_event_for_missing_appointment(self, _patch_client):
        conn = _Conn()
        stale_link = _Link(appointment_id=uuid.uuid4(), external_event_id="gone")
        provider_id = uuid.uuid4()
        session = _Session([
            _Result(provider_id),
            _Result([stale_link]),   # link with no matching active appointment
            _Result([]),             # no appointments in window
        ])
        client = _patch_client({"DELETE": _Resp(204)})
        n = await calendar_service.reconcile_events(session, conn)
        assert n == 1
        assert stale_link in session.deleted
        assert client.calls[0][0] == "DELETE"

    async def test_updates_changed_appointment(self, _patch_client):
        conn = _Conn()
        appt = _Appt()
        link = _Link(appointment_id=appt.id, external_event_id="ev9", payload_hash="stale")
        provider_id = uuid.uuid4()
        session = _Session([
            _Result(provider_id),
            _Result([link]),
            _Result([appt]),
        ])
        client = _patch_client({"PATCH": _Resp(200)})
        n = await calendar_service.reconcile_events(session, conn)
        assert n == 1
        assert client.calls[0][0] == "PATCH"
        # hash updated to reflect the new payload
        assert link.payload_hash == calendar_service._payload_hash(
            calendar_service._event_payload("google", appt)
        )

    async def test_unchanged_appointment_drift_repair_recreates(self, _patch_client):
        conn = _Conn()
        appt = _Appt()
        current_hash = calendar_service._payload_hash(
            calendar_service._event_payload("google", appt)
        )
        # link already matches payload → no push; last_pushed_at in the past so
        # the drift-repair pass runs a GET (event was deleted remotely → 404).
        link = _Link(appointment_id=appt.id, external_event_id="old", payload_hash=current_hash,
                     last_pushed_at=datetime.now(timezone.utc) - timedelta(hours=1))
        provider_id = uuid.uuid4()
        session = _Session([
            _Result(provider_id),
            _Result([link]),
            _Result([appt]),
        ])
        client = _patch_client({"GET": _Resp(404), "POST": _Resp(200, {"id": "recreated"})})
        n = await calendar_service.reconcile_events(session, conn)
        assert n == 1
        assert link.external_event_id == "recreated"
