"""NotificationTemplate, NotificationLog, ReminderRule.

Templates are Jinja2 sandbox-rendered. Whitelisted variables only —
PHI (name, dob, MRN, address) is NEVER interpolated into email subject/body or SMS body.
"""
import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScoped, SoftDeleteMixin, TimestampMixin, UUIDPk


NOTIFICATION_CHANNELS = ("email", "sms", "inapp")
NOTIFICATION_STATUSES = ("queued", "sent", "delivered", "failed", "bounced", "opted_out")


class NotificationTemplate(Base, UUIDPk, OrgScoped, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "notification_templates"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    event: Mapped[str] = mapped_column(String(60), nullable=False)  # e.g., appointment_reminder, cancellation
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(String(8000), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ReminderRule(Base, UUIDPk, OrgScoped, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "reminder_rules"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    offsets_min: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list, nullable=False)
    channels: Mapped[list[str]] = mapped_column(ARRAY(String(10)), default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class NotificationLog(Base, UUIDPk, OrgScoped, TimestampMixin):
    __tablename__ = "notification_log"

    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    event: Mapped[str] = mapped_column(String(60), nullable=False)
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    to_address: Mapped[str] = mapped_column(String(255), nullable=False)  # email or phone
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    context: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)  # non-PHI metadata only
