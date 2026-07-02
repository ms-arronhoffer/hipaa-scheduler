"""Staff password lifecycle: policy enforcement, history/reuse, expiry, reset.

Centralises everything that must happen when a staff password changes so the
auth and users routers stay thin and can't drift apart:

- policy gate (:mod:`app.auth.password_policy`)
- reuse prevention against the last ``password_history_depth`` hashes
- hashing + stamping ``password_changed_at`` / ``password_expires_at``
- pruning history beyond the configured depth

Reset tokens are single-use and time-boxed; only their sha256 is stored.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import password_policy
from app.auth.passwords import hash_password, verify_password
from app.config import settings
from app.models.user import PasswordHistory, PasswordResetToken, User


class PasswordReuseError(ValueError):
    def __init__(self) -> None:
        super().__init__("password was used recently and cannot be reused")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _expiry_from(now: datetime) -> datetime | None:
    days = int(settings.password_expiry_days)
    return now + timedelta(days=days) if days > 0 else None


def is_expired(user: User, *, now: datetime | None = None) -> bool:
    """True if the user's password is past its expiry instant."""
    if user.password_expires_at is None:
        return False
    now = now or _now()
    exp = user.password_expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp <= now


async def _assert_not_reused(db: AsyncSession, user: User, new_plain: str) -> None:
    depth = int(settings.password_history_depth)
    if depth <= 0:
        return
    candidates: list[str] = []
    if user.password_hash:
        candidates.append(user.password_hash)
    rows = (await db.execute(
        select(PasswordHistory.password_hash)
        .where(PasswordHistory.user_id == user.id)
        .order_by(PasswordHistory.created_at.desc())
        .limit(depth)
    )).scalars().all()
    candidates.extend(rows)
    for old_hash in candidates[:depth]:
        if verify_password(new_plain, old_hash):
            raise PasswordReuseError()


async def _prune_history(db: AsyncSession, user_id: uuid.UUID) -> None:
    depth = int(settings.password_history_depth)
    keep = (await db.execute(
        select(PasswordHistory.id)
        .where(PasswordHistory.user_id == user_id)
        .order_by(PasswordHistory.created_at.desc())
        .limit(depth)
    )).scalars().all()
    stmt = select(PasswordHistory).where(PasswordHistory.user_id == user_id)
    if keep:
        stmt = stmt.where(PasswordHistory.id.notin_(keep))
    for row in (await db.execute(stmt)).scalars().all():
        await db.delete(row)


async def set_password(
    db: AsyncSession,
    user: User,
    new_plain: str,
    *,
    check_breach: bool = True,
    enforce_reuse: bool = True,
) -> None:
    """Validate, reuse-check, hash, stamp lifecycle fields, and record history.

    Raises ``PasswordPolicyError`` or ``PasswordReuseError`` before any mutation.
    """
    await password_policy.enforce(
        new_plain,
        user_inputs=[user.email or "", user.first_name or "", user.last_name or ""],
        check_breach=check_breach,
    )
    if enforce_reuse:
        await _assert_not_reused(db, user, new_plain)

    now = _now()
    # Retire the current hash into history before overwriting it.
    if user.password_hash:
        db.add(PasswordHistory(user_id=user.id, password_hash=user.password_hash))

    user.password_hash = hash_password(new_plain)
    user.password_changed_at = now
    user.password_expires_at = _expiry_from(now)
    await db.flush()
    await _prune_history(db, user.id)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def issue_reset_token(db: AsyncSession, user: User) -> str:
    """Create a single-use reset token and return the raw value (email it)."""
    raw = f"hsr_{secrets.token_urlsafe(32)}"
    db.add(PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(raw),
        expires_at=_now() + timedelta(minutes=int(settings.password_reset_ttl_min)),
    ))
    await db.flush()
    return raw


async def consume_reset_token(db: AsyncSession, raw: str) -> User | None:
    """Validate + consume a reset token, returning its user, or None if invalid."""
    row = (await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash_token(raw))
    )).scalar_one_or_none()
    if row is None or row.used_at is not None:
        return None
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp <= _now():
        return None
    user = (await db.execute(
        select(User).where(User.id == row.user_id, User.deleted_at.is_(None))
    )).scalar_one_or_none()
    if user is None:
        return None
    row.used_at = _now()
    return user
