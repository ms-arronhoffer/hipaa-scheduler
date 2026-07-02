"""Appointment + RecurringAppointmentSeries.

Conflict prevention: a Postgres exclusion constraint over
`tstzrange(start_at, end_at)` per provider (and per resource) is added in the
initial migration. Booking runs in a serializable transaction and translates
`ExclusionViolation` into HTTP 409 at the router layer.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date, DateTime, ForeignKey, Index, Integer, String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScoped, SoftDeleteMixin, TimestampMixin, UUIDPk
from app.models.types import EncryptedString


APPOINTMENT_STATUSES = (
    "scheduled", "confirmed", "checked_in", "completed", "canceled", "no_show",
)
APPOINTMENT_SOURCES = ("staff", "portal", "magic", "guest", "api")


class RecurringAppointmentSeries(Base, UUIDPk, OrgScoped, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "recurring_appointment_series"

    rrule: Mapped[str] = mapped_column(String(500), nullable=False)
    dtstart: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exdates: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    template: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class Appointment(Base, UUIDPk, OrgScoped, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "appointments"
    __table_args__ = (
        Index("ix_appt_org_provider_start", "org_id", "provider_id", "start_at"),
        Index("ix_appt_org_patient_start", "org_id", "patient_id", "start_at"),
        Index("ix_appt_org_status_start", "org_id", "status", "start_at"),
    )

    office_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("offices.id", ondelete="RESTRICT"), nullable=False
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("provider_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False
    )
    appointment_type_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("appointment_types.id", ondelete="RESTRICT"), nullable=False
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("resources.id", ondelete="SET NULL"), nullable=True
    )
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("recurring_appointment_series.id", ondelete="SET NULL"),
        nullable=True,
    )
    occurrence_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)
    source: Mapped[str] = mapped_column(String(10), default="staff", nullable=False)

    confirm_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cancel_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)

    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_by_actor_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    no_show_marked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    notes: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)  # PHI — encrypted at rest
