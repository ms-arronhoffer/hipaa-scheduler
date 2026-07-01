"""IntakeForm (versioned schema) + IntakeSubmission."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScoped, SoftDeleteMixin, TimestampMixin, UUIDPk


class IntakeForm(Base, UUIDPk, OrgScoped, TimestampMixin, SoftDeleteMixin):
    """Configurable intake form.

    `schema` shape: {version, pages:[{sections:[{fields:[{key,type,label,required,options,validators,showIf}]}]}]}.
    Submissions store the form_version so schema evolution never breaks history.
    """
    __tablename__ = "intake_forms"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    schema: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class IntakeSubmission(Base, UUIDPk, OrgScoped, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "intake_submissions"

    form_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("intake_forms.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    form_version: Mapped[int] = mapped_column(Integer, nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True
    )
    answers: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signature_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
