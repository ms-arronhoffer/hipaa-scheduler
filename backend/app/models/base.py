"""Shared base and mixins for all ORM models.

- UUID primary key
- Org-scoped multi-tenancy: every business table carries `org_id`
- TimestampMixin: created_at / updated_at
- SoftDeleteMixin: deleted_at (null = active)
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.database import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UUIDPk:
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=_uuid
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class OrgScoped:
    """Every org-scoped table declares `org_id` and indexes it."""

    @declared_attr
    def org_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805
        return mapped_column(
            PG_UUID(as_uuid=True),
            ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )


__all__ = ["Base", "UUIDPk", "TimestampMixin", "SoftDeleteMixin", "OrgScoped", "_uuid", "_now"]
