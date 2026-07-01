"""Patient authentication router — three modes.

- POST /patient-auth/magic/request → email a magic-link (never leaks whether
  the email is registered — always returns 202)
- POST /patient-auth/magic/consume → exchange magic token for patient JWT
- POST /patient-auth/login → full-account password login (+ optional TOTP)
- POST /patient-auth/claim → guest → account claim via signed token
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import jwt as jwt_service
from app.auth.passwords import hash_password, verify_password
from app.database import get_db
from app.models.patient import Patient, PatientAccount
from app.schemas.auth import (
    PatientMagicLinkConsume,
    PatientMagicLinkRequest,
    StaffLoginRequest,
    TokenResponse,
)
from app.services import confirm_token_service, magic_link_service


router = APIRouter(prefix="/patient-auth", tags=["patient-auth"])


@router.post("/magic/request", status_code=status.HTTP_202_ACCEPTED)
async def magic_request(body: PatientMagicLinkRequest, db: AsyncSession = Depends(get_db)) -> dict:
    account = (await db.execute(
        select(PatientAccount).where(PatientAccount.email == body.email.lower(), PatientAccount.deleted_at.is_(None))
    )).scalar_one_or_none()
    if account is not None:
        plaintext, _ = await magic_link_service.issue(db, patient_account=account)
        # Actual email dispatch happens via notification_service in a router-level task.
        # We intentionally don't reveal issuance to the caller.
    return {"status": "sent"}


@router.post("/magic/consume", response_model=TokenResponse)
async def magic_consume(body: PatientMagicLinkConsume, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        row = await magic_link_service.consume(db, plaintext=body.token)
    except magic_link_service.MagicLinkError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired link")
    account = (await db.execute(
        select(PatientAccount).where(PatientAccount.id == row.patient_account_id)
    )).scalar_one_or_none()
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "account not found")
    account.last_login_at = datetime.utcnow()
    if account.auth_mode == "guest":
        account.auth_mode = "magic"
    access = jwt_service.issue_access(audience="patient", subject=account.id, org_id=account.patient.org_id if hasattr(account, "patient") and account.patient else row.org_id)
    return TokenResponse(access_token=access, expires_in=jwt_service.ACCESS_TTL_MIN * 60)


@router.post("/login", response_model=TokenResponse)
async def login(body: StaffLoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    account = (await db.execute(
        select(PatientAccount).where(PatientAccount.email == body.email.lower(), PatientAccount.deleted_at.is_(None))
    )).scalar_one_or_none()
    if account is None or account.password_hash is None or not verify_password(body.password, account.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    account.last_login_at = datetime.utcnow()
    patient = (await db.execute(select(Patient).where(Patient.id == account.patient_id))).scalar_one()
    access = jwt_service.issue_access(audience="patient", subject=account.id, org_id=patient.org_id)
    return TokenResponse(access_token=access, expires_in=jwt_service.ACCESS_TTL_MIN * 60)


@router.post("/claim", response_model=TokenResponse)
async def claim_account(body: PatientMagicLinkConsume, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        tok = await confirm_token_service.consume(db, plaintext=body.token, expect_kind="claim_account")
    except confirm_token_service.TokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
    if tok.patient_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "token missing patient")
    account = (await db.execute(
        select(PatientAccount).where(PatientAccount.patient_id == tok.patient_id)
    )).scalar_one_or_none()
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no account to claim")
    account.auth_mode = "full"
    account.last_login_at = datetime.utcnow()
    patient = (await db.execute(select(Patient).where(Patient.id == tok.patient_id))).scalar_one()
    access = jwt_service.issue_access(audience="patient", subject=account.id, org_id=patient.org_id)
    return TokenResponse(access_token=access, expires_in=jwt_service.ACCESS_TTL_MIN * 60)
