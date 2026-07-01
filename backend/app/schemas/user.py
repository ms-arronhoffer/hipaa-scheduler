"""Staff user + provider profile schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


STAFF_ROLES = ("practice_admin", "provider", "front_desk", "billing")


class UserCreate(BaseModel):
    email: EmailStr
    first_name: str | None = Field(default=None, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    roles: list[str] = Field(default_factory=list)
    password: str | None = Field(default=None, min_length=12, max_length=128)


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    roles: list[str] | None = None
    password: str | None = Field(default=None, min_length=12, max_length=128)


class UserOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    roles: list[str]
    mfa_enrolled: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProviderCreate(BaseModel):
    user_id: uuid.UUID
    npi: str | None = Field(default=None, max_length=20)
    specialty: str | None = Field(default=None, max_length=80)
    default_office_id: uuid.UUID | None = None
    color: str | None = Field(default=None, max_length=9)
    bookable: bool = True


class ProviderUpdate(BaseModel):
    npi: str | None = None
    specialty: str | None = None
    default_office_id: uuid.UUID | None = None
    color: str | None = None
    bookable: bool | None = None


class ProviderOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID
    npi: str | None
    specialty: str | None
    default_office_id: uuid.UUID | None
    color: str | None
    bookable: bool
