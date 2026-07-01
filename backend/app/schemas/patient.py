"""Patient schemas."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class PatientCreate(BaseModel):
    mrn: str = Field(min_length=1, max_length=40)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    middle_name: str | None = None
    dob: date
    sex: str | None = Field(default=None, min_length=1, max_length=1)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    address: dict = Field(default_factory=dict)
    preferred_office_id: uuid.UUID | None = None


class PatientUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    dob: date | None = None
    sex: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: dict | None = None
    preferred_office_id: uuid.UUID | None = None


class PatientOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    mrn: str
    first_name: str
    last_name: str
    middle_name: str | None
    dob: date
    sex: str | None
    email: str | None
    phone: str | None
    address: dict
    preferred_office_id: uuid.UUID | None
    sms_opt_in_at: datetime | None
    created_at: datetime
    updated_at: datetime
