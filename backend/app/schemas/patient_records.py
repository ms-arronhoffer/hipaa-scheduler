"""Consent + Document + InsurancePolicy schemas."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ConsentCreate(BaseModel):
    patient_id: uuid.UUID
    kind: str = Field(max_length=30)
    document_version: str = Field(max_length=30)
    body_hash: str = Field(max_length=128)
    signer_name: str = Field(max_length=120)


class ConsentOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    patient_id: uuid.UUID
    kind: str
    document_version: str
    body_hash: str
    signed_at: datetime
    signer_name: str
    signer_ip: str | None


class DocumentCreate(BaseModel):
    patient_id: uuid.UUID
    kind: str = Field(max_length=40)
    filename: str = Field(max_length=255)
    mime_type: str = Field(max_length=100)
    size_bytes: int = Field(ge=0)
    storage_key: str = Field(max_length=500)
    sha256: str = Field(min_length=64, max_length=64)


class DocumentOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    patient_id: uuid.UUID
    kind: str
    filename: str
    mime_type: str
    size_bytes: int
    storage_key: str
    sha256: str
    created_at: datetime


class InsuranceCreate(BaseModel):
    patient_id: uuid.UUID
    priority: int = Field(default=1, ge=1, le=5)
    carrier: str = Field(max_length=120)
    plan_name: str | None = None
    member_id: str = Field(max_length=60)
    group_number: str | None = None
    subscriber_name: str | None = None
    subscriber_dob: date | None = None
    subscriber_relation: str | None = None
    effective_date: date | None = None
    termination_date: date | None = None
    card_document_id: uuid.UUID | None = None
    extra: dict = Field(default_factory=dict)


class InsuranceUpdate(BaseModel):
    priority: int | None = None
    carrier: str | None = None
    plan_name: str | None = None
    member_id: str | None = None
    group_number: str | None = None
    subscriber_name: str | None = None
    subscriber_dob: date | None = None
    subscriber_relation: str | None = None
    effective_date: date | None = None
    termination_date: date | None = None
    active: bool | None = None
    card_document_id: uuid.UUID | None = None
    extra: dict | None = None


class InsuranceOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    patient_id: uuid.UUID
    priority: int
    carrier: str
    plan_name: str | None
    member_id: str
    group_number: str | None
    subscriber_name: str | None
    subscriber_dob: date | None
    subscriber_relation: str | None
    effective_date: date | None
    termination_date: date | None
    active: bool
    card_document_id: uuid.UUID | None
    extra: dict
