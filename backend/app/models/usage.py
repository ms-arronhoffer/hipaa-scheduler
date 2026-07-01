"""UsageEvent — per-tenant metering for plan/seat enforcement and analytics."""
import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScoped, TimestampMixin, UUIDPk


class UsageEvent(Base, UUIDPk, OrgScoped, TimestampMixin):
    __tablename__ = "usage_events"

    kind: Mapped[str] = mapped_column(String(60), nullable=False, index=True)  # appointments_created, sms_sent, ...
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    actor_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    context: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
