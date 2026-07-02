"""Consent, Document, InsurancePolicy — patient-attached PHI records."""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScoped, SoftDeleteMixin, TimestampMixin, UUIDPk
from app.models.types import EncryptedString


CONSENT_KINDS = ("hipaa_privacy", "telehealth", "sms", "financial", "custom")


class Consent(Base, UUIDPk, OrgScoped, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "consents"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    document_version: Mapped[str] = mapped_column(String(30), nullable=False)
    body_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    signer_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Document(Base, UUIDPk, OrgScoped, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "documents"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)  # id_card, insurance_card, xray, upload
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by_actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    uploaded_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class InsurancePolicy(Base, UUIDPk, OrgScoped, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "insurance_policies"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1=primary, 2=secondary
    carrier: Mapped[str] = mapped_column(String(120), nullable=False)
    plan_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    member_id: Mapped[str] = mapped_column(EncryptedString, nullable=False)  # PHI — encrypted at rest
    group_number: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)  # PHI — encrypted at rest
    subscriber_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    subscriber_dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    subscriber_relation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    card_document_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    extra: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
