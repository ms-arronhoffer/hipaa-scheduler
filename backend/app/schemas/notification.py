"""Notification template + reminder rule + log schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class TemplateCreate(BaseModel):
    name: str = Field(max_length=120)
    channel: str = Field(max_length=10)  # email, sms, inapp
    event: str = Field(max_length=60)
    subject: str | None = Field(default=None, max_length=255)
    body: str = Field(max_length=8000)
    active: bool = True


class TemplateUpdate(BaseModel):
    name: str | None = None
    subject: str | None = None
    body: str | None = None
    active: bool | None = None


class TemplateOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    channel: str
    event: str
    subject: str | None
    body: str
    active: bool


class ReminderRuleCreate(BaseModel):
    name: str = Field(max_length=120)
    offsets_min: list[int] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    active: bool = True


class ReminderRuleUpdate(BaseModel):
    name: str | None = None
    offsets_min: list[int] | None = None
    channels: list[str] | None = None
    active: bool | None = None


class ReminderRuleOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    offsets_min: list[int]
    channels: list[str]
    active: bool


class NotificationLogOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    channel: str
    event: str
    appointment_id: uuid.UUID | None
    patient_id: uuid.UUID | None
    to_address: str
    provider_message_id: str | None
    status: str
    error: str | None
    sent_at: datetime | None
    context: dict
    created_at: datetime
