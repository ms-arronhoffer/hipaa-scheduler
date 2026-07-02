"""Unit tests for patient-portal session revocation ("sign out everywhere").

Pure/no-I/O: the AsyncSession is stubbed so we exercise only the
`_resolve_patient` iat-vs-cutoff logic.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.auth import principal as principal_mod


class _Result:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class _Session:
    def __init__(self, obj):
        self._obj = obj

    async def execute(self, _stmt):
        return _Result(self._obj)


class _Account:
    def __init__(self, sessions_invalid_after):
        self.id = uuid.uuid4()
        self.email = "pt@example.com"
        self.sessions_invalid_after = sessions_invalid_after


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


@pytest.mark.asyncio
async def test_resolve_patient_ok_when_no_cutoff():
    acct = _Account(sessions_invalid_after=None)
    p = await principal_mod._resolve_patient(_Session(acct), str(acct.id), str(uuid.uuid4()), _now_ts())
    assert p.kind == "patient"
    assert p.subject_id == acct.id


@pytest.mark.asyncio
async def test_resolve_patient_ok_when_token_newer_than_cutoff():
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    acct = _Account(sessions_invalid_after=cutoff)
    # token issued now (after cutoff) → still valid
    p = await principal_mod._resolve_patient(_Session(acct), str(acct.id), str(uuid.uuid4()), _now_ts())
    assert p.kind == "patient"


@pytest.mark.asyncio
async def test_resolve_patient_rejected_when_token_at_or_before_cutoff():
    cutoff = datetime.now(timezone.utc) + timedelta(minutes=5)
    acct = _Account(sessions_invalid_after=cutoff)
    # token issued now (<= future cutoff) → revoked
    with pytest.raises(HTTPException) as exc:
        await principal_mod._resolve_patient(_Session(acct), str(acct.id), str(uuid.uuid4()), _now_ts())
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_resolve_patient_handles_naive_cutoff():
    # a naive datetime (no tzinfo) must be treated as UTC, not crash
    cutoff = datetime.utcnow() + timedelta(minutes=5)  # noqa: DTZ003 - intentional naive
    acct = _Account(sessions_invalid_after=cutoff)
    with pytest.raises(HTTPException):
        await principal_mod._resolve_patient(_Session(acct), str(acct.id), str(uuid.uuid4()), _now_ts())


@pytest.mark.asyncio
async def test_resolve_patient_no_iat_skips_revocation_check():
    cutoff = datetime.now(timezone.utc) + timedelta(minutes=5)
    acct = _Account(sessions_invalid_after=cutoff)
    # legacy token without iat → cannot be revoked, still resolves
    p = await principal_mod._resolve_patient(_Session(acct), str(acct.id), str(uuid.uuid4()), None)
    assert p.kind == "patient"
