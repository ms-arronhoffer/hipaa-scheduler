"""One-click confirm/cancel/reschedule tokens tied to a specific appointment.

The plaintext token is emailed/SMS'd as `?t=<token>`; we store only sha256.
`consume(...)` looks up by hash, verifies not expired / not already used,
marks used, and returns the appointment id + intended action.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import new_token
from app.models.tokens import ConfirmToken


DEFAULT_TTL = timedelta(days=7)


CONFIRM_KINDS = {"confirm", "cancel", "reschedule", "claim_account"}


class TokenError(Exception):
    pass


async def issue(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    kind: str,
    appointment_id: uuid.UUID | None = None,
    patient_id: uuid.UUID | None = None,
    ttl: timedelta = DEFAULT_TTL,
) -> tuple[str, ConfirmToken]:
    if kind not in CONFIRM_KINDS:
        raise TokenError(f"unknown kind {kind}")
    plaintext, digest = new_token()
    row = ConfirmToken(
        org_id=org_id,
        kind=kind,
        token_hash=digest,
        appointment_id=appointment_id,
        patient_id=patient_id,
        expires_at=datetime.utcnow() + ttl,
    )
    db.add(row)
    await db.flush()
    return plaintext, row


async def consume(db: AsyncSession, *, plaintext: str, expect_kind: str) -> ConfirmToken:
    digest = hashlib.sha256(plaintext.encode()).hexdigest()
    row = (await db.execute(
        select(ConfirmToken).where(ConfirmToken.token_hash == digest)
    )).scalar_one_or_none()
    if row is None:
        raise TokenError("unknown token")
    if row.kind != expect_kind:
        raise TokenError("wrong kind")
    if row.used_at is not None:
        raise TokenError("already used")
    if row.expires_at and row.expires_at < datetime.utcnow():
        raise TokenError("expired")
    row.used_at = datetime.utcnow()
    await db.flush()
    return row
