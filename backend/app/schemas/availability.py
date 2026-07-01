"""ProviderAvailability + TimeOff schemas."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel


class AvailabilityCreate(BaseModel):
    provider_id: uuid.UUID
    office_id: uuid.UUID | None = None
    weekday: int = Field(ge=0, le=6)  # 0=Mon..6=Sun
    start_time: time
    end_time: time
    effective_from: date | None = None
    effective_until: date | None = None

    @model_validator(mode="after")
    def _check_order(self) -> "AvailabilityCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AvailabilityUpdate(BaseModel):
    office_id: uuid.UUID | None = None
    weekday: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    effective_from: date | None = None
    effective_until: date | None = None


class AvailabilityOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    provider_id: uuid.UUID
    office_id: uuid.UUID | None
    weekday: int
    start_time: time
    end_time: time
    effective_from: date | None
    effective_until: date | None


class TimeOffCreate(BaseModel):
    provider_id: uuid.UUID
    start_at: datetime
    end_at: datetime
    reason: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _check_order(self) -> "TimeOffCreate":
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class TimeOffOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    provider_id: uuid.UUID
    start_at: datetime
    end_at: datetime
    reason: str | None
