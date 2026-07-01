"""Physical office/location within an organization."""
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScoped, SoftDeleteMixin, TimestampMixin, UUIDPk


class Office(Base, UUIDPk, OrgScoped, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "offices"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York", nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    hours: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)  # weekday → open/close
    holidays: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
