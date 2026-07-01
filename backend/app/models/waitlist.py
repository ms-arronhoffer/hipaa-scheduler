"""WaitlistEntry — auto-fill candidate list."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScoped, SoftDeleteMixin, TimestampMixin, UUIDPk


WAITLIST_STATUSES = ("open", "notified", "booked", "expired", "canceled")


class WaitlistEntry(Base, UUIDPk, OrgScoped, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "waitlist_entries"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    appointment_type_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("appointment_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider_pref_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("provider_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    office_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("offices.id", ondelete="SET NULL"), nullable=True
    )
    earliest_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latest_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    booked_appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
