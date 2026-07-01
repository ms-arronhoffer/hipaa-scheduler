"""Magic-link issuance and consumption for patient auth mode #2.

Flow:
    1) Patient enters email at portal → `issue(...)` creates a MagicLinkToken
       (32-byte plaintext, sha256 stored) and emails a URL like
       `https://<patient_url>/magic?t=<plaintext>`.
    2) Patient clicks → `consume(...)` validates + marks used → app issues a
       short-lived patient JWT (see `app.auth.jwt.issue_access(aud="patient")`).

Rate limiting is enforced at the router layer.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import new_token
from app.models.patient import PatientAccount
from app.models.tokens import MagicLinkToken


TTL = timedelta(minutes=15)


class MagicLinkError(Exception):
    pass


async def issue(
    db: AsyncSession, *, patient_account: PatientAccount
) -> tuple[str, MagicLinkToken]:
    plaintext, digest = new_token()
    row = MagicLinkToken(
        org_id=patient_account.org_id,
        patient_account_id=patient_account.id,
        email=patient_account.email,
        token_hash=digest,
        expires_at=datetime.utcnow() + TTL,
    )
    db.add(row)
    await db.flush()
    return plaintext, row


async def consume(db: AsyncSession, *, plaintext: str) -> MagicLinkToken:
    digest = hashlib.sha256(plaintext.encode()).hexdigest()
    row = (await db.execute(
        select(MagicLinkToken).where(MagicLinkToken.token_hash == digest)
    )).scalar_one_or_none()
    if row is None:
        raise MagicLinkError("unknown token")
    if row.used_at is not None:
        raise MagicLinkError("already used")
    if row.expires_at < datetime.utcnow():
        raise MagicLinkError("expired")
    row.used_at = datetime.utcnow()
    await db.flush()
    return row
