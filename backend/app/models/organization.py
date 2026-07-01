"""Tenant (practice/office group) — top-level container for all PHI."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPk


class Organization(Base, UUIDPk, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(40), default="free", nullable=False)
    seats: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    baa_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mfa_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
