"""Intake form + submission schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class IntakeFormCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    schema_: dict = Field(alias="schema", default_factory=dict)
    active: bool = True

    model_config = {"populate_by_name": True}


class IntakeFormUpdate(BaseModel):
    name: str | None = None
    schema_: dict | None = Field(default=None, alias="schema")
    active: bool | None = None

    model_config = {"populate_by_name": True}


class IntakeFormOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    version: int
    schema_: dict = Field(alias="schema")
    active: bool

    model_config = {"populate_by_name": True, "from_attributes": True}


class IntakeSubmissionCreate(BaseModel):
    form_id: uuid.UUID
    patient_id: uuid.UUID
    appointment_id: uuid.UUID | None = None
    answers: dict = Field(default_factory=dict)
    signature_name: str | None = Field(default=None, max_length=120)


class IntakeSubmissionOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    form_id: uuid.UUID
    form_version: int
    patient_id: uuid.UUID
    appointment_id: uuid.UUID | None
    answers: dict
    signed_at: datetime | None
    signature_name: str | None
    created_at: datetime
