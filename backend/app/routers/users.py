"""Staff user CRUD (practice_admin scope).

Passwords are bcrypt-hashed at rest. MFA enrollment/reset happens via /auth
routes — this router only edits identity + roles. Deleting a user is a soft
delete + revoked login (locked_until set far in the future).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password
from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import require_role
from app.models.activity_log import ActivityLog
from app.models.user import User
from app.schemas.user import STAFF_ROLES, UserCreate, UserOut, UserUpdate
from app.services import password_service
from app.auth import password_policy


router = APIRouter(prefix="/users", tags=["users"])


def _validate_roles(roles: list[str] | None) -> None:
    if roles is None:
        return
    for r in roles:
        if r not in STAFF_ROLES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown role {r}")


def _password_error(exc: Exception) -> HTTPException:
    reasons = getattr(exc, "reasons", None) or [str(exc)]
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"password": reasons})


@router.get("", response_model=list[UserOut])
async def list_users(
    include_disabled: bool = False,
    p: Principal = Depends(require_role("practice_admin", "billing")),
    db: AsyncSession = Depends(get_db),
) -> list[User]:
    stmt = select(User).where(User.org_id == p.org_id)
    if not include_disabled:
        stmt = stmt.where(User.deleted_at.is_(None))
    rows = (await db.execute(stmt.order_by(User.email))).scalars().all()
    return list(rows)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> User:
    _validate_roles(body.roles)
    row = User(
        org_id=p.org_id,
        email=body.email.lower(),
        first_name=body.first_name,
        last_name=body.last_name,
        roles=body.roles,
        password_hash=None,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already exists in this org")
    if body.password:
        try:
            await password_service.set_password(db, row, body.password)
        except (password_policy.PasswordPolicyError, password_service.PasswordReuseError) as exc:
            raise _password_error(exc)
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="user", entity_id=row.id, action="created",
        changes={"email": row.email, "roles": row.roles},
    ))
    return row


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin", "billing")),
    db: AsyncSession = Depends(get_db),
) -> User:
    row = (await db.execute(
        select(User).where(User.id == user_id, User.org_id == p.org_id)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return row


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> User:
    row = (await db.execute(
        select(User).where(
            User.id == user_id, User.org_id == p.org_id, User.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    data = body.model_dump(exclude_unset=True)
    _validate_roles(data.get("roles"))
    if "password" in data:
        pw = data.pop("password")
        if pw:
            try:
                await password_service.set_password(db, row, pw)
            except (password_policy.PasswordPolicyError, password_service.PasswordReuseError) as exc:
                raise _password_error(exc)
    for k, v in data.items():
        setattr(row, k, v)
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="user", entity_id=row.id, action="updated",
        changes={k: v for k, v in data.items() if k != "password"},
    ))
    return row


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    if user_id == p.subject_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot delete yourself")
    row = (await db.execute(
        select(User).where(
            User.id == user_id, User.org_id == p.org_id, User.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    row.deleted_at = datetime.utcnow()
    row.locked_until = datetime.utcnow() + timedelta(days=365 * 100)
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="user", entity_id=row.id, action="disabled",
        changes={"email": row.email},
    ))


async def _load_org_user(db: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID) -> User:
    row = (await db.execute(
        select(User).where(
            User.id == user_id, User.org_id == org_id, User.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return row


@router.post("/{user_id}/mfa/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_user_mfa(
    user_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Support action: clear a staff user's MFA enrollment so they can re-enroll.

    Used when a user loses their authenticator + backup codes. Wipes the TOTP
    secret, backup codes, and enrollment flag; the user re-enrolls via
    ``/auth/mfa/enroll/*`` on next login. Logged for audit.
    """
    row = await _load_org_user(db, user_id, p.org_id)
    row.mfa_enrolled = False
    row.totp_secret = None
    row.backup_codes = []
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="user", entity_id=row.id, action="mfa_reset",
        changes={"email": row.email},
    ))


@router.post("/{user_id}/sign-out-everywhere", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out_everywhere(
    user_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Invalidate all of a user's existing sessions (access + refresh tokens).

    Sets ``sessions_invalid_after`` to now; every token issued at-or-before this
    instant is rejected by the principal resolver, forcing re-login everywhere.
    """
    row = await _load_org_user(db, user_id, p.org_id)
    row.sessions_invalid_after = datetime.utcnow()
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="user", entity_id=row.id, action="sessions_revoked",
        changes={"email": row.email},
    ))
