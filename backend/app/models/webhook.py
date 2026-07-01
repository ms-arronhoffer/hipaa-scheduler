"""WebhookSubscription + WebhookDelivery.

Delivery uses HMAC-SHA256 signing with an exponential backoff retry schedule
[30s, 2m, 10m, 1h, 6h, 24h]. Each attempt writes a WebhookDelivery row.
"""
import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScoped, SoftDeleteMixin, TimestampMixin, UUIDPk


WEBHOOK_DELIVERY_STATUSES = ("pending", "delivered", "failed", "dead_letter")


class WebhookSubscription(Base, UUIDPk, OrgScoped, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "webhook_subscriptions"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    target_url: Mapped[str] = mapped_column(String(500), nullable=False)
    events: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list, nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(128), nullable=False)  # sha256 of shared HMAC secret
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class WebhookDelivery(Base, UUIDPk, OrgScoped, TimestampMixin):
    __tablename__ = "webhook_deliveries"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    event: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
