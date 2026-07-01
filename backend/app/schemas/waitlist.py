"""Waitlist schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class WaitlistCreate(BaseModel):
    patient_id: uuid.UUID
    appointment_type_id: uuid.UUID
    provider_pref_id: uuid.UUID | None = None
    office_id: uuid.UUID | None = None
    earliest_at: datetime
    latest_at: datetime
    notes: str | None = Field(default=None, max_length=500)


class WaitlistUpdate(BaseModel):
    provider_pref_id: uuid.UUID | None = None
    office_id: uuid.UUID | None = None
    earliest_at: datetime | None = None
    latest_at: datetime | None = None
    notes: str | None = None
    status: str | None = None


class WaitlistOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    patient_id: uuid.UUID
    appointment_type_id: uuid.UUID
    provider_pref_id: uuid.UUID | None
    office_id: uuid.UUID | None
    earliest_at: datetime
    latest_at: datetime
    notified_at: datetime | None
    booked_appointment_id: uuid.UUID | None
    status: str
    notes: str | None
    created_at: datetime
