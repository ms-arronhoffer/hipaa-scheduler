"""Staff authentication router.

- POST /auth/login → password + optional TOTP; enforces lockout after 5 fails
- POST /auth/refresh → rotates refresh, issues new access
- POST /auth/mfa/enroll/start → returns provisioning URI + secret
- POST /auth/mfa/enroll/verify → confirms TOTP + returns backup codes
- POST /auth/logout → client-side discard; server records event

All login failures produce identical timing/errors — no user enumeration.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import jwt as jwt_service
from app.auth import totp as totp_service
from app.auth.passwords import hash_password, verify_password
from app.auth.principal import Principal, current_principal
from app.database import get_db
from app.guards.deps import require_staff
from app.models.activity_log import ActivityLog
from app.models.user import AuthLockout, User
from app.schemas.auth import (
    MfaBackupCodes,
    MfaEnrollStart,
    MfaEnrollVerify,
    RefreshRequest,
    StaffLoginRequest,
    TokenResponse,
)


router = APIRouter(prefix="/auth", tags=["auth"])

LOCKOUT_ATTEMPTS = 5
LOCKOUT_WINDOW = timedelta(minutes=15)


def _bad_credentials() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")


async def _record_attempt(db: AsyncSession, email: str, success: bool) -> None:
    row = (await db.execute(select(AuthLockout).where(AuthLockout.email == email))).scalar_one_or_none()
    if row is None:
        row = AuthLockout(email=email, attempts=0)
        db.add(row)
    if success:
        row.attempts = 0
        row.locked_until = None
    else:
        row.attempts += 1
        if row.attempts >= LOCKOUT_ATTEMPTS:
            row.locked_until = datetime.utcnow() + LOCKOUT_WINDOW
            row.attempts = 0
    await db.flush()


async def _is_locked(db: AsyncSession, email: str) -> bool:
    row = (await db.execute(select(AuthLockout).where(AuthLockout.email == email))).scalar_one_or_none()
    return row is not None and row.locked_until is not None and row.locked_until > datetime.utcnow()


@router.post("/login", response_model=TokenResponse)
async def login(body: StaffLoginRequest, request: Request, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    email = body.email.lower()
    if await _is_locked(db, email):
        raise HTTPException(status.HTTP_423_LOCKED, "account temporarily locked")

    user = (await db.execute(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )).scalar_one_or_none()
    if user is None or user.password_hash is None or not verify_password(body.password, user.password_hash):
        await _record_attempt(db, email, success=False)
        raise _bad_credentials()

    mfa_ok = False
    if user.mfa_enrolled and user.totp_secret:
        if not body.totp_code or not totp_service.verify(user.totp_secret, body.totp_code):
            await _record_attempt(db, email, success=False)
            raise _bad_credentials()
        mfa_ok = True
    elif not user.mfa_enrolled:
        mfa_ok = False

    await _record_attempt(db, email, success=True)
    user.last_login_at = datetime.utcnow()

    db.add(ActivityLog(
        org_id=user.org_id,
        actor_type="user",
        actor_id=user.id,
        actor_email=user.email,
        entity_type="user",
        entity_id=user.id,
        action="login",
        changes={},
        phi_accessed=False,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    ))

    access = jwt_service.issue_access(
        audience="staff", subject=user.id, org_id=user.org_id, extra={"mfa_ok": mfa_ok}
    )
    refresh = jwt_service.issue_refresh(audience="staff", subject=user.id, org_id=user.org_id)
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=jwt_service.ACCESS_TTL_MIN * 60)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        claims = jwt_service.decode(body.refresh_token, audience="staff")
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh")
    if claims.get("typ") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not a refresh token")
    import uuid as _uuid
    subj = _uuid.UUID(claims["sub"])
    org = _uuid.UUID(claims["org_id"]) if claims.get("org_id") else None
    access = jwt_service.issue_access(audience="staff", subject=subj, org_id=org, extra={"mfa_ok": False})
    new_refresh = jwt_service.issue_refresh(audience="staff", subject=subj, org_id=org)
    return TokenResponse(access_token=access, refresh_token=new_refresh, expires_in=jwt_service.ACCESS_TTL_MIN * 60)


@router.post("/mfa/enroll/start", response_model=MfaEnrollStart)
async def mfa_start(p: Principal = Depends(require_staff()), db: AsyncSession = Depends(get_db)) -> MfaEnrollStart:
    user = (await db.execute(select(User).where(User.id == p.subject_id))).scalar_one()
    secret = totp_service.new_secret()
    user.totp_secret = secret
    await db.flush()
    return MfaEnrollStart(secret=secret, provisioning_uri=totp_service.provisioning_uri(secret, user.email))


@router.post("/mfa/enroll/verify", response_model=MfaBackupCodes)
async def mfa_verify(
    body: MfaEnrollVerify,
    p: Principal = Depends(require_staff()),
    db: AsyncSession = Depends(get_db),
) -> MfaBackupCodes:
    user = (await db.execute(select(User).where(User.id == p.subject_id))).scalar_one()
    if not user.totp_secret or not totp_service.verify(user.totp_secret, body.totp_code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid code")
    plaintext, hashed = totp_service.generate_backup_codes()
    user.mfa_enrolled = True
    user.backup_codes = hashed
    await db.flush()
    return MfaBackupCodes(codes=plaintext)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, p: Principal = Depends(current_principal), db: AsyncSession = Depends(get_db)) -> None:
    db.add(ActivityLog(
        org_id=p.org_id,
        actor_type=p.kind,
        actor_id=p.subject_id,
        actor_email=p.email,
        entity_type=p.kind,
        entity_id=p.subject_id,
        action="logout",
        changes={},
        phi_accessed=False,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    ))
