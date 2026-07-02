"""Patient-portal (self-service) request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PortalConsentSign(BaseModel):
    """A patient signing a consent for themselves in the portal."""
    kind: str = Field(max_length=30)
    document_version: str = Field(max_length=30)
    body_hash: str = Field(max_length=128)
    signer_name: str = Field(min_length=1, max_length=120)


class PortalIntakeSubmit(BaseModel):
    form_id: uuid.UUID
    appointment_id: uuid.UUID | None = None
    answers: dict = Field(default_factory=dict)
    signature_name: str | None = Field(default=None, max_length=120)


class PortalSessionOut(ORMModel):
    """The patient's own account/session summary (no secrets)."""
    email: str
    auth_mode: str
    mfa_enrolled: bool
    last_login_at: datetime | None
    sessions_invalid_after: datetime | None
    current_session_issued_at: datetime | None = None
