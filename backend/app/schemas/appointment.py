"""Appointment schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class AppointmentCreate(BaseModel):
    office_id: uuid.UUID
    provider_id: uuid.UUID
    patient_id: uuid.UUID
    appointment_type_id: uuid.UUID
    start_at: datetime
    resource_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


class AppointmentReschedule(BaseModel):
    start_at: datetime


class AppointmentCancel(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class AppointmentOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    office_id: uuid.UUID
    provider_id: uuid.UUID
    patient_id: uuid.UUID
    appointment_type_id: uuid.UUID
    resource_id: uuid.UUID | None
    series_id: uuid.UUID | None
    start_at: datetime
    end_at: datetime
    duration_min: int
    status: str
    source: str
    created_at: datetime
    updated_at: datetime


class AppointmentListOut(BaseModel):
    items: list[AppointmentOut]
    total: int


class SlotOut(BaseModel):
    start_at: datetime
    end_at: datetime


class AvailabilityQuery(BaseModel):
    office_id: uuid.UUID
    provider_id: uuid.UUID
    appointment_type_id: uuid.UUID
    range_start: datetime
    range_end: datetime
