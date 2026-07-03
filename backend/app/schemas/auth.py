"""Auth request/response schemas — staff + patient."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field


class StaffLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
    totp_code: str | None = Field(default=None, min_length=6, max_length=8)
    backup_code: str | None = Field(default=None, min_length=8, max_length=64)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int


class CurrentUserOut(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str | None = None
    last_name: str | None = None
    roles: list[str] = Field(default_factory=list)
    is_super_admin: bool = False
    mfa_enrolled: bool = False
    org_id: uuid.UUID | None = None


class MfaChallenge(BaseModel):
    mfa_required: bool = True
    session_ticket: str  # short-lived one-time value the client returns with totp_code


class MfaEnrollStart(BaseModel):
    secret: str
    provisioning_uri: str


class MfaEnrollVerify(BaseModel):
    totp_code: str = Field(min_length=6, max_length=8)


class MfaBackupCodes(BaseModel):
    codes: list[str]


class PatientMagicLinkRequest(BaseModel):
    email: EmailStr


class PatientMagicLinkConsume(BaseModel):
    token: str = Field(min_length=32, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordForgotRequest(BaseModel):
    email: EmailStr


class PasswordResetRequest(BaseModel):
    token: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=1, max_length=200)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)
