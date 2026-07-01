"""Office schemas."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class OfficeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    timezone: str = Field(default="America/New_York", max_length=64)
    phone: str | None = Field(default=None, max_length=30)
    address: dict = Field(default_factory=dict)
    hours: dict = Field(default_factory=dict)
    holidays: list = Field(default_factory=list)


class OfficeUpdate(BaseModel):
    name: str | None = None
    timezone: str | None = None
    phone: str | None = None
    address: dict | None = None
    hours: dict | None = None
    holidays: list | None = None


class OfficeOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    timezone: str
    phone: str | None
    address: dict
    hours: dict
    holidays: list


class ResourceCreate(BaseModel):
    office_id: uuid.UUID
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(default="room", max_length=40)


class ResourceUpdate(BaseModel):
    name: str | None = None
    kind: str | None = None


class ResourceOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    office_id: uuid.UUID
    name: str
    kind: str
