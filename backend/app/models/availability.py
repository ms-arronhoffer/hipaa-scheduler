"""ProviderAvailability weekly template + TimeOff blocks."""
import uuid
from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Time
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScoped, SoftDeleteMixin, TimestampMixin, UUIDPk


class ProviderAvailability(Base, UUIDPk, OrgScoped, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "provider_availability"

    provider_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("provider_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    office_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("offices.id", ondelete="CASCADE"), nullable=True
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon..6=Sun
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_until: Mapped[date | None] = mapped_column(Date, nullable=True)


class TimeOff(Base, UUIDPk, OrgScoped, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "time_off"

    provider_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("provider_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
