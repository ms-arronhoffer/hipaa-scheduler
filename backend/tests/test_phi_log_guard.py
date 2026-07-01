"""HIPAA audit invariant: the `phi_log` dependency MUST enqueue an
ActivityLog row with `phi_accessed=True` for every request routed through it.

This is a pure-DB test — no FastAPI transport needed. We construct a Request
manually and invoke the dependency's inner function, then assert the row
landed in the session.
"""
import os
import uuid

import pytest
from starlette.requests import Request

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x/x")
os.environ.setdefault("JWT_SECRET", "test-secret-please-ignore-32-bytes-min")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "test-admin-pw")

from app.guards.deps import phi_log  # noqa: E402
from app.models.activity_log import ActivityLog  # noqa: E402


class _FakePrincipal:
    def __init__(self):
        self.kind = "staff"
        self.subject_id = uuid.uuid4()
        self.org_id = uuid.uuid4()
        self.email = "tester@example.test"


class _FakeSession:
    """Just enough of AsyncSession for phi_log — it only calls .add()."""

    def __init__(self):
        self.added: list = []

    def add(self, obj):
        self.added.append(obj)


def _make_request(path: str, path_params: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "headers": [(b"user-agent", b"pytest"), (b"x-request-id", b"req-1")],
        "query_string": b"",
        "path_params": path_params,
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_phi_log_writes_activity_row_with_phi_accessed_true():
    dep = phi_log("patient", action="viewed")
    principal = _FakePrincipal()
    session = _FakeSession()
    patient_id = uuid.uuid4()
    request = _make_request(f"/patients/{patient_id}", {"id": str(patient_id)})

    # phi_log's `_dep` is the closure returned by phi_log(...). It expects
    # request, principal, db — bypassing FastAPI's Depends chain.
    returned = await dep(request=request, p=principal, db=session)

    assert returned is principal
    assert len(session.added) == 1
    row = session.added[0]
    assert isinstance(row, ActivityLog)
    assert row.phi_accessed is True
    assert row.entity_type == "patient"
    assert row.entity_id == patient_id
    assert row.action == "viewed"
    assert row.actor_id == principal.subject_id
    assert row.org_id == principal.org_id
    assert row.ip == "127.0.0.1"
    assert row.user_agent == "pytest"
    assert row.request_id == "req-1"


@pytest.mark.asyncio
async def test_phi_log_tolerates_missing_entity_id():
    """List endpoints have no {id} — the row still lands, entity_id null."""
    dep = phi_log("patient", action="listed")
    session = _FakeSession()
    request = _make_request("/patients", {})

    await dep(request=request, p=_FakePrincipal(), db=session)

    assert len(session.added) == 1
    assert session.added[0].entity_id is None
    assert session.added[0].phi_accessed is True


@pytest.mark.asyncio
async def test_phi_log_ignores_non_uuid_path_param():
    """A malformed id in the URL must NOT crash the guard — audit still writes."""
    dep = phi_log("patient")
    session = _FakeSession()
    request = _make_request("/patients/not-a-uuid", {"id": "not-a-uuid"})

    await dep(request=request, p=_FakePrincipal(), db=session)

    assert len(session.added) == 1
    assert session.added[0].entity_id is None
    assert session.added[0].phi_accessed is True
