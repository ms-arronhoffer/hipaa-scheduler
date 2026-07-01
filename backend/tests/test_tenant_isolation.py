"""P1 tenant-isolation regression tests.

Covers the shared ``ensure_patient_in_org`` guard (remediation item P1.4): every
handler that accepts a ``patient_id`` from the request body/query must verify the
patient belongs to the caller's org and return 404 — never an empty 200 — on a
cross-tenant mismatch. This is the primary defense against cross-tenant IDOR and
ID enumeration.

These are DB-free unit tests: a tiny fake ``AsyncSession`` stands in for Postgres
so we can assert both the guard's behavior and that its query is org- and
soft-delete-scoped.
"""
import os
import uuid

import pytest
from fastapi import HTTPException

# Bare-minimum env so app.config imports without prompting.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x/x")
os.environ.setdefault("JWT_SECRET", "test-secret-please-ignore-32-bytes-min")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "test-admin-pw")

from app.guards.deps import ensure_patient_in_org  # noqa: E402


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    """Records the executed statement and returns a canned scalar result."""

    def __init__(self, value):
        self._value = value
        self.executed = None

    async def execute(self, stmt):
        self.executed = stmt
        return _FakeResult(self._value)


class TestEnsurePatientInOrg:
    async def test_patient_in_org_passes(self):
        pid, org = uuid.uuid4(), uuid.uuid4()
        db = _FakeSession(value=pid)  # row found
        # Should not raise.
        await ensure_patient_in_org(db, pid, org)

    async def test_cross_tenant_raises_404(self):
        pid, org = uuid.uuid4(), uuid.uuid4()
        db = _FakeSession(value=None)  # no row for this (id, org)
        with pytest.raises(HTTPException) as exc:
            await ensure_patient_in_org(db, pid, org)
        assert exc.value.status_code == 404

    async def test_missing_patient_raises_404_not_empty_or_403(self):
        pid, org = uuid.uuid4(), uuid.uuid4()
        db = _FakeSession(value=None)
        with pytest.raises(HTTPException) as exc:
            await ensure_patient_in_org(db, pid, org)
        # Explicitly 404 — not 403 (which would confirm existence) and not a
        # silent empty success.
        assert exc.value.status_code == 404

    async def test_query_is_org_and_soft_delete_scoped(self):
        pid, org = uuid.uuid4(), uuid.uuid4()
        db = _FakeSession(value=pid)
        await ensure_patient_in_org(db, pid, org)
        compiled = str(db.executed).lower()
        # The lookup must constrain by id, org_id, and exclude soft-deleted rows.
        assert "patients.id" in compiled
        assert "patients.org_id" in compiled
        assert "deleted_at is null" in compiled
