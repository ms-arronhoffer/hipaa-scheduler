"""Staff user (super_admin, practice_admin, provider, front_desk, billing).

Patient login lives on `PatientAccount` — never mix patient auth with staff.
"""
import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScoped, SoftDeleteMixin, TimestampMixin, UUIDPk
from app.models.types import EncryptedString


class User(Base, UUIDPk, OrgScoped, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("org_id", "email", name="uq_users_org_email"),
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    roles: Mapped[list[str]] = mapped_column(ARRAY(String(30)), default=list, nullable=False)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    totp_secret: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    mfa_enrolled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    backup_codes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Password lifecycle. `password_changed_at` anchors expiry; `password_expires_at`
    # is denormalised (computed from policy at set-time) so a login check is a
    # single column read. `sessions_invalid_after` powers "sign out everywhere":
    # any access/refresh token issued at-or-before this instant is rejected.
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sessions_invalid_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProviderProfile(Base, UUIDPk, OrgScoped, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "provider_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    npi: Mapped[str | None] = mapped_column(String(20), nullable=True)
    specialty: Mapped[str | None] = mapped_column(String(80), nullable=True)
    default_office_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("offices.id", ondelete="SET NULL"), nullable=True
    )
    color: Mapped[str | None] = mapped_column(String(9), nullable=True)
    bookable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AuthLockout(Base, UUIDPk, TimestampMixin):
    __tablename__ = "auth_lockouts"

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PasswordHistory(Base, UUIDPk, TimestampMixin):
    """Prior password hashes, newest kept for reuse prevention.

    Only bcrypt hashes are stored (never plaintext). The reuse check verifies a
    candidate against each remembered hash; the depth is bounded by
    ``settings.password_history_depth``.
    """
    __tablename__ = "password_history"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)


class PasswordResetToken(Base, UUIDPk, TimestampMixin):
    """Single-use, time-boxed staff password-reset token.

    Only the sha256 of the token is stored; the raw token travels in the emailed
    link and is never persisted. Consumed (``used_at``) on first successful use.
    """
    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
