"""API key + webhook schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from app.schemas.common import ORMModel


class ApiKeyCreate(BaseModel):
    name: str = Field(max_length=120)
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class ApiKeyOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    prefix: str
    scopes: list[str]
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    active: bool
    created_at: datetime


class ApiKeyCreated(BaseModel):
    """One-time payload — plaintext key is shown ONCE at creation."""
    id: uuid.UUID
    plaintext: str
    prefix: str
    scopes: list[str]


class WebhookSubscriptionCreate(BaseModel):
    name: str = Field(max_length=120)
    target_url: HttpUrl
    events: list[str] = Field(default_factory=list)
    active: bool = True


class WebhookSubscriptionUpdate(BaseModel):
    name: str | None = None
    target_url: HttpUrl | None = None
    events: list[str] | None = None
    active: bool | None = None


class WebhookSubscriptionOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    target_url: str
    events: list[str]
    active: bool
    last_success_at: datetime | None
    last_failure_at: datetime | None
    failure_count: int


class WebhookSubscriptionCreated(BaseModel):
    id: uuid.UUID
    secret: str  # returned once, then only sha256 stored
    target_url: str
    events: list[str]


class WebhookDeliveryOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    subscription_id: uuid.UUID
    event: str
    attempt: int
    status: str
    response_status: int | None
    response_body_snippet: str | None = None
    next_attempt_at: datetime | None
    last_attempt_at: datetime | None = None
    delivered_at: datetime | None
    created_at: datetime


class CalendarConnectionOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID
    provider: str
    account_email: str
    calendar_id: str
    token_expires_at: datetime | None
    last_sync_at: datetime | None
    scopes: dict
    active: bool
    created_at: datetime


class CalendarConnectionUpdate(BaseModel):
    active: bool | None = None
    calendar_id: str | None = None
