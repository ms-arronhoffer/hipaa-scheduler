"""Organization + super-admin schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class OrganizationCreate(BaseModel):
    name: str = Field(max_length=255)
    slug: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9-]+$")
    plan: str = Field(default="starter", max_length=40)
    seats: int = Field(default=5, ge=1)
    mfa_required: bool = True
    admin_email: EmailStr | None = None  # optional: bootstrap admin user
    admin_password: str | None = Field(default=None, min_length=12, max_length=128)


class OrganizationUpdate(BaseModel):
    name: str | None = None
    plan: str | None = None
    seats: int | None = Field(default=None, ge=1)
    mfa_required: bool | None = None
    status: str | None = None
    settings: dict | None = None


class OrganizationOut(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    seats: int
    baa_signed_at: datetime | None
    mfa_required: bool
    status: str
    settings: dict
    created_at: datetime
    updated_at: datetime


class ImpersonateRequest(BaseModel):
    org_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=500)


class AuditSearchQuery(BaseModel):
    org_id: uuid.UUID | None = None
    actor_email: str | None = None
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    action: str | None = None
    phi_only: bool = False
    from_ts: datetime | None = None
    to_ts: datetime | None = None
