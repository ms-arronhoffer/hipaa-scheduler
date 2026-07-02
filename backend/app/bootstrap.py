"""First-run bootstrap of the platform super-admin.

Idempotent seeding invoked from the FastAPI lifespan. On a freshly migrated
(empty) database this creates:

* a reserved ``platform`` organization that hosts platform operators, and
* a super-admin :class:`~app.models.user.User` built from
  ``DEFAULT_ADMIN_EMAIL`` / ``DEFAULT_ADMIN_PASSWORD``,

and grants ``is_super_admin`` to every address listed in ``SUPER_ADMIN_EMAILS``.

Without this, a fresh deploy has no way to log in: creating tenants requires a
super-admin (``require_super_admin``), but nothing else ever sets that flag.

Safe to run on every boot:

* rows are looked up before insert, so nothing is duplicated;
* an existing admin's password is **never** overwritten, so a credential
  rotated after first boot survives restarts.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password
from app.config import settings
from app.models.activity_log import ActivityLog
from app.models.organization import Organization
from app.models.user import User

log = logging.getLogger(__name__)

# Reserved tenant that owns platform operators (super-admins). The slug is
# unique across organizations, so it doubles as the idempotency key.
PLATFORM_ORG_SLUG = "platform"
PLATFORM_ORG_NAME = "Platform Administration"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _password_expiry(now: datetime) -> datetime | None:
    days = int(settings.password_expiry_days)
    return now + timedelta(days=days) if days > 0 else None


async def _get_or_create_platform_org(db: AsyncSession) -> Organization:
    org = (
        await db.execute(
            select(Organization).where(Organization.slug == PLATFORM_ORG_SLUG)
        )
    ).scalar_one_or_none()
    if org is not None:
        return org
    org = Organization(
        name=PLATFORM_ORG_NAME,
        slug=PLATFORM_ORG_SLUG,
        plan="enterprise",
        seats=0,
        mfa_required=settings.mfa_required_default,
        status="active",
    )
    db.add(org)
    await db.flush()
    log.info("bootstrap.platform_org_created", extra={"org_id": str(org.id)})
    return org


async def _ensure_default_admin(db: AsyncSession, org: Organization) -> bool:
    """Create the default super-admin if absent. Returns True when created."""
    email = settings.default_admin_email.strip().lower()
    existing = (
        await db.execute(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if existing is not None:
        # Never clobber an existing account's password — just make sure the
        # bootstrap identity retains its platform privileges.
        if not existing.is_super_admin:
            existing.is_super_admin = True
            log.info("bootstrap.default_admin_promoted", extra={"email": email})
        return False

    now = _now()
    user = User(
        org_id=org.id,
        email=email,
        password_hash=hash_password(settings.default_admin_password.get_secret_value()),
        roles=[],
        is_super_admin=True,
        password_changed_at=now,
        password_expires_at=_password_expiry(now),
    )
    db.add(user)
    await db.flush()
    db.add(
        ActivityLog(
            org_id=org.id,
            actor_type="system",
            actor_email="bootstrap",
            entity_type="user",
            entity_id=user.id,
            action="created",
            changes={"is_super_admin": True, "source": "bootstrap"},
            phi_accessed=False,
        )
    )
    log.info(
        "bootstrap.default_admin_created",
        extra={"email": email, "org_id": str(org.id)},
    )
    return True


async def _grant_super_admins(db: AsyncSession) -> None:
    """Promote any existing users whose email is in ``SUPER_ADMIN_EMAILS``."""
    emails = [e for e in settings.super_admin_email_list if e]
    if not emails:
        return
    rows = (
        await db.execute(
            select(User).where(User.email.in_(emails), User.deleted_at.is_(None))
        )
    ).scalars().all()
    for user in rows:
        if not user.is_super_admin:
            user.is_super_admin = True
            log.info("bootstrap.super_admin_granted", extra={"email": user.email})


async def run_bootstrap(db: AsyncSession) -> None:
    """Seed platform org + super-admin using the given session, then commit."""
    org = await _get_or_create_platform_org(db)
    await _ensure_default_admin(db, org)
    await _grant_super_admins(db)
    await db.commit()


async def bootstrap_super_admin() -> None:
    """Lifespan entry point: open a session and run the idempotent bootstrap.

    Failures are logged but never propagated — a bootstrap hiccup must not stop
    the API from serving (operators can re-run by restarting the backend).
    """
    from app.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            await run_bootstrap(db)
    except Exception:  # pragma: no cover - defensive; logged for operators
        log.exception("bootstrap.failed")
