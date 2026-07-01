"""Short-lived hashed tokens: magic-link login and one-click confirm/cancel."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPk


class MagicLinkToken(Base, UUIDPk, TimestampMixin):
    """Passwordless patient login token. Only sha256(token) is stored."""
    __tablename__ = "magic_link_tokens"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    patient_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("patient_accounts.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_issued: Mapped[str | None] = mapped_column(String(64), nullable=True)


CONFIRM_TOKEN_KINDS = ("confirm", "cancel", "reschedule", "claim_account")


class ConfirmToken(Base, UUIDPk, TimestampMixin):
    """One-click signed token for appointment confirm / cancel / claim."""
    __tablename__ = "confirm_tokens"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=True, index=True
    )
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
