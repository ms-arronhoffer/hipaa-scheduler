"""Public booking schemas (patient portal + guest)."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.appointment import AppointmentOut, SlotOut


class PublicSlotQuery(BaseModel):
    org_slug: str
    office_id: uuid.UUID
    provider_id: uuid.UUID
    appointment_type_id: uuid.UUID
    range_start: datetime
    range_end: datetime


class GuestPatientDetails(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    dob: date
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)


class GuestBookingRequest(BaseModel):
    org_slug: str
    office_id: uuid.UUID
    provider_id: uuid.UUID
    appointment_type_id: uuid.UUID
    start_at: datetime
    patient: GuestPatientDetails
    accept_hipaa_version: str = Field(min_length=1, max_length=30)
    notes: str | None = Field(default=None, max_length=500)


class PatientBookingRequest(BaseModel):
    office_id: uuid.UUID
    provider_id: uuid.UUID
    appointment_type_id: uuid.UUID
    start_at: datetime
    notes: str | None = Field(default=None, max_length=500)


class BookingResponse(BaseModel):
    appointment: AppointmentOut
    claim_token: str | None = None  # only present for guest bookings — 24h upgrade path


class PublicSlotsResponse(BaseModel):
    slots: list[SlotOut]
