"""Patient (PHI-bearing) + PatientAccount for portal login."""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScoped, SoftDeleteMixin, TimestampMixin, UUIDPk
from app.models.types import EncryptedString


class Patient(Base, UUIDPk, OrgScoped, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("org_id", "mrn", name="uq_patients_org_mrn"),
        Index("ix_patients_org_lastname", "org_id", "last_name"),
        Index("ix_patients_org_dob", "org_id", "dob"),
    )

    mrn: Mapped[str] = mapped_column(String(40), nullable=False)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    dob: Mapped[date] = mapped_column(Date, nullable=False)
    sex: Mapped[str | None] = mapped_column(String(1), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    preferred_office_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("offices.id", ondelete="SET NULL"), nullable=True
    )
    sms_opt_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    merged_into_patient_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True
    )


class PatientAccount(Base, UUIDPk, TimestampMixin, SoftDeleteMixin):
    """Patient portal login — separate from staff User table.

    auth_mode reflects the last successful authentication path:
    - full: password + optional MFA
    - magic: passwordless magic-link only
    - guest: identity captured during a public booking; not yet claimed
    """
    __tablename__ = "patient_accounts"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_mode: Mapped[str] = mapped_column(String(10), default="magic", nullable=False)
    mfa_enrolled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    totp_secret: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
