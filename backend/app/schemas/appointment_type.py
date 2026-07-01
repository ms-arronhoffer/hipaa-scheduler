"""Appointment type schemas."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class AppointmentTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    duration_min: int = Field(ge=5, le=8 * 60)
    buffer_before_min: int = Field(default=0, ge=0, le=240)
    buffer_after_min: int = Field(default=0, ge=0, le=240)
    color: str | None = Field(default=None, max_length=9)
    requires_provider: bool = True
    requires_resource: bool = False
    intake_form_id: uuid.UUID | None = None
    reminder_rule_id: uuid.UUID | None = None
    cancellation_window_hours: int = Field(default=24, ge=0, le=30 * 24)
    active: bool = True


class AppointmentTypeUpdate(BaseModel):
    name: str | None = None
    duration_min: int | None = Field(default=None, ge=5, le=8 * 60)
    buffer_before_min: int | None = Field(default=None, ge=0)
    buffer_after_min: int | None = Field(default=None, ge=0)
    color: str | None = None
    requires_provider: bool | None = None
    requires_resource: bool | None = None
    intake_form_id: uuid.UUID | None = None
    reminder_rule_id: uuid.UUID | None = None
    cancellation_window_hours: int | None = Field(default=None, ge=0)
    active: bool | None = None


class AppointmentTypeOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    duration_min: int
    buffer_before_min: int
    buffer_after_min: int
    color: str | None
    requires_provider: bool
    requires_resource: bool
    intake_form_id: uuid.UUID | None
    reminder_rule_id: uuid.UUID | None
    cancellation_window_hours: int
    active: bool
