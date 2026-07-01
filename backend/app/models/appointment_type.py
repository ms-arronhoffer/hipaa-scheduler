"""AppointmentType (service catalog), Resource (room/chair)."""
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScoped, SoftDeleteMixin, TimestampMixin, UUIDPk


class AppointmentType(Base, UUIDPk, OrgScoped, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "appointment_types"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    buffer_before_min: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    buffer_after_min: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    color: Mapped[str | None] = mapped_column(String(9), nullable=True)
    requires_provider: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_resource: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    intake_form_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("intake_forms.id", ondelete="SET NULL"), nullable=True
    )
    reminder_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("reminder_rules.id", ondelete="SET NULL"), nullable=True
    )
    cancellation_window_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Resource(Base, UUIDPk, OrgScoped, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "resources"

    office_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("offices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), default="room", nullable=False)
