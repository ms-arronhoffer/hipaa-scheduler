"""ActivityLog — immutable audit trail.

`phi_accessed=True` on any row involving PHI reads or writes.
Retention: 6-year HIPAA floor; never hard-deleted before that.
"""
import uuid

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScoped, TimestampMixin, UUIDPk


ACTOR_TYPES = ("user", "patient_account", "api_key", "system", "super_admin")


class ActivityLog(Base, UUIDPk, OrgScoped, TimestampMixin):
    __tablename__ = "activity_log"
    __table_args__ = (
        Index("ix_activity_org_created", "org_id", "created_at"),
        Index("ix_activity_org_entity", "org_id", "entity_type", "entity_id"),
        Index("ix_activity_org_actor", "org_id", "actor_type", "actor_id"),
        Index("ix_activity_org_phi", "org_id", "phi_accessed", "created_at"),
    )

    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    action: Mapped[str] = mapped_column(String(60), nullable=False)  # created, updated, deleted, viewed, exported, login, ...
    changes: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    phi_accessed: Mapped[bool] = mapped_column(default=False, nullable=False)

    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
