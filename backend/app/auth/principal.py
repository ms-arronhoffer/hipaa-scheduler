"""Request-scoped auth principal and dependency injection.

`Principal` covers three authenticated identities in one shape:
- staff user (JWT aud=staff)
- patient (JWT aud=patient, from full/magic/guest session)
- api key holder (X-API-Key header)

Guards below refuse mismatched kinds — a staff endpoint will never accept a
patient JWT or an API key without the right scope.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Literal

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode as jwt_decode
from app.database import get_db
from app.models.api_key import ApiKey
from app.models.user import User
from app.models.patient import PatientAccount

PrincipalKind = Literal["user", "patient", "api_key"]

_bearer = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    kind: PrincipalKind
    subject_id: uuid.UUID
    org_id: uuid.UUID
    email: str | None = None
    roles: list[str] = field(default_factory=list)
    is_super_admin: bool = False
    scopes: list[str] = field(default_factory=list)  # api_key only
    mfa_ok: bool = False  # staff: MFA satisfied on this session


def _unauth(detail: str = "unauthorized") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


async def _resolve_user(db: AsyncSession, sub: str, org_id: str | None, mfa_claim: bool, iat: int | None = None) -> Principal:
    try:
        uid = uuid.UUID(sub)
    except ValueError:
        raise _unauth()
    row = (await db.execute(select(User).where(User.id == uid, User.deleted_at.is_(None)))).scalar_one_or_none()
    if row is None or row.locked_until is not None:
        raise _unauth()
    if org_id and str(row.org_id) != str(org_id):
        raise _unauth("org mismatch")
    # "Sign out everywhere": reject any token issued at or before the cutoff.
    if row.sessions_invalid_after is not None and iat is not None:
        cutoff = row.sessions_invalid_after
        if cutoff.tzinfo is None:
            from datetime import timezone as _tz
            cutoff = cutoff.replace(tzinfo=_tz.utc)
        if iat <= int(cutoff.timestamp()):
            raise _unauth("session revoked")
    return Principal(
        kind="user",
        subject_id=row.id,
        org_id=row.org_id,
        email=row.email,
        roles=list(row.roles or []),
        is_super_admin=bool(row.is_super_admin),
        mfa_ok=bool(mfa_claim),
    )


async def _resolve_patient(db: AsyncSession, sub: str, org_id: str | None) -> Principal:
    try:
        pid = uuid.UUID(sub)
    except ValueError:
        raise _unauth()
    row = (await db.execute(select(PatientAccount).where(PatientAccount.id == pid, PatientAccount.deleted_at.is_(None)))).scalar_one_or_none()
    if row is None:
        raise _unauth()
    if not org_id:
        raise _unauth("org missing")
    return Principal(
        kind="patient",
        subject_id=row.id,
        org_id=uuid.UUID(org_id),
        email=row.email,
    )


async def _resolve_api_key(db: AsyncSession, presented: str) -> Principal:
    if not presented.startswith("hs_"):
        raise _unauth()
    digest = hashlib.sha256(presented.encode()).hexdigest()
    row = (await db.execute(select(ApiKey).where(ApiKey.key_hash == digest, ApiKey.active.is_(True), ApiKey.deleted_at.is_(None)))).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        raise _unauth()
    return Principal(
        kind="api_key",
        subject_id=row.id,
        org_id=row.org_id,
        scopes=list(row.scopes or []),
    )


async def current_principal(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_api_key: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    """Resolve the caller — API key wins if present, otherwise Bearer JWT."""
    if x_api_key:
        p = await _resolve_api_key(db, x_api_key)
        request.state.principal = p
        return p

    if creds is None or not creds.credentials:
        raise _unauth()

    token = creds.credentials
    # Try staff audience first, then patient. jwt raises on aud mismatch.
    try:
        claims = jwt_decode(token, audience="staff")
        p = await _resolve_user(db, claims["sub"], claims.get("org_id"), bool(claims.get("mfa_ok", False)), claims.get("iat"))
    except Exception:
        try:
            claims = jwt_decode(token, audience="patient")
            p = await _resolve_patient(db, claims["sub"], claims.get("org_id"))
        except Exception:
            raise _unauth()
    request.state.principal = p
    return p


async def optional_principal(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_api_key: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Principal | None:
    if not (creds and creds.credentials) and not x_api_key:
        return None
    try:
        return await current_principal(request, creds, x_api_key, db)
    except HTTPException:
        return None
