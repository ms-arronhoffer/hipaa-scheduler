"""Patient-portal self-service API (`/pub/me/...`).

Everything here runs under a *patient* JWT (aud=patient) and is scoped to the
signed-in patient's own records — never another patient's. The patient id is
resolved from the account behind the token, so no patient_id is ever accepted
from the request (IDOR-safe by construction).

Surfaces:
- consents  — list own consents + sign a new one
- documents — list own document metadata (uploads happen out-of-band)
- intake    — list the org's active forms + submit / list own submissions
- security  — view the current session and "sign out everywhere"
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal, current_principal
from app.database import get_db
from app.models.activity_log import ActivityLog
from app.models.intake_form import IntakeForm, IntakeSubmission
from app.models.patient import PatientAccount
from app.models.patient_records import CONSENT_KINDS, Consent, Document
from app.routers.intake_forms import _validate_submission
from app.schemas.intake_form import IntakeFormOut, IntakeSubmissionOut
from app.schemas.patient_records import ConsentOut, DocumentOut
from app.schemas.portal import PortalConsentSign, PortalIntakeSubmit, PortalSessionOut

router = APIRouter(prefix="/pub/me", tags=["patient-portal"])


async def _account(db: AsyncSession, p: Principal) -> PatientAccount:
    """Resolve the signed-in patient's account, enforcing patient audience."""
    if p.kind != "patient":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "patient session required")
    account = (await db.execute(
        select(PatientAccount).where(
            PatientAccount.id == p.subject_id,
            PatientAccount.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found")
    return account


# ---- consents ----------------------------------------------------------------


@router.get("/consents", response_model=list[ConsentOut])
async def my_consents(
    p: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[Consent]:
    account = await _account(db, p)
    rows = (await db.execute(
        select(Consent).where(
            Consent.org_id == p.org_id,
            Consent.patient_id == account.patient_id,
            Consent.deleted_at.is_(None),
        ).order_by(Consent.signed_at.desc())
    )).scalars().all()
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="patient", actor_id=account.id, actor_email=account.email,
        entity_type="consent", entity_id=account.patient_id, action="listed",
        changes={"count": len(rows)}, phi_accessed=True,
    ))
    return list(rows)


@router.post("/consents", response_model=ConsentOut, status_code=status.HTTP_201_CREATED)
async def sign_consent(
    body: PortalConsentSign,
    request: Request,
    p: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_db),
) -> Consent:
    account = await _account(db, p)
    if body.kind not in CONSENT_KINDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"kind must be one of {CONSENT_KINDS}")
    row = Consent(
        org_id=p.org_id,
        patient_id=account.patient_id,
        kind=body.kind,
        document_version=body.document_version,
        body_hash=body.body_hash,
        signed_at=datetime.now(timezone.utc),
        signer_name=body.signer_name,
        signer_ip=request.client.host if request.client else None,
    )
    db.add(row)
    await db.flush()
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="patient", actor_id=account.id, actor_email=account.email,
        entity_type="consent", entity_id=row.id, action="signed",
        changes={"kind": body.kind, "version": body.document_version}, phi_accessed=True,
    ))
    return row


# ---- documents ---------------------------------------------------------------


@router.get("/documents", response_model=list[DocumentOut])
async def my_documents(
    p: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[Document]:
    account = await _account(db, p)
    rows = (await db.execute(
        select(Document).where(
            Document.org_id == p.org_id,
            Document.patient_id == account.patient_id,
            Document.deleted_at.is_(None),
        ).order_by(Document.created_at.desc())
    )).scalars().all()
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="patient", actor_id=account.id, actor_email=account.email,
        entity_type="document", entity_id=account.patient_id, action="listed",
        changes={"count": len(rows)}, phi_accessed=True,
    ))
    return list(rows)


# ---- intake forms ------------------------------------------------------------


@router.get("/intake/forms", response_model=list[IntakeFormOut])
async def active_forms(
    p: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[IntakeForm]:
    await _account(db, p)
    rows = (await db.execute(
        select(IntakeForm).where(
            IntakeForm.org_id == p.org_id,
            IntakeForm.active.is_(True),
            IntakeForm.deleted_at.is_(None),
        ).order_by(IntakeForm.name)
    )).scalars().all()
    return list(rows)


@router.get("/intake/submissions", response_model=list[IntakeSubmissionOut])
async def my_submissions(
    p: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[IntakeSubmission]:
    account = await _account(db, p)
    rows = (await db.execute(
        select(IntakeSubmission).where(
            IntakeSubmission.org_id == p.org_id,
            IntakeSubmission.patient_id == account.patient_id,
            IntakeSubmission.deleted_at.is_(None),
        ).order_by(IntakeSubmission.created_at.desc())
    )).scalars().all()
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="patient", actor_id=account.id, actor_email=account.email,
        entity_type="intake_submission", entity_id=account.patient_id, action="listed",
        changes={"count": len(rows)}, phi_accessed=True,
    ))
    return list(rows)


@router.post("/intake/submissions", response_model=IntakeSubmissionOut, status_code=status.HTTP_201_CREATED)
async def submit_intake(
    body: PortalIntakeSubmit,
    p: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_db),
) -> IntakeSubmission:
    account = await _account(db, p)
    form = (await db.execute(
        select(IntakeForm).where(
            IntakeForm.id == body.form_id,
            IntakeForm.org_id == p.org_id,
            IntakeForm.active.is_(True),
            IntakeForm.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if form is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "form not found")
    _validate_submission(form.schema or {}, body.answers or {})
    row = IntakeSubmission(
        org_id=p.org_id,
        form_id=form.id,
        form_version=form.version,
        patient_id=account.patient_id,
        appointment_id=body.appointment_id,
        answers=body.answers,
        signed_at=datetime.now(timezone.utc) if body.signature_name else None,
        signature_name=body.signature_name,
    )
    db.add(row)
    await db.flush()
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="patient", actor_id=account.id, actor_email=account.email,
        entity_type="intake_submission", entity_id=row.id, action="created",
        changes={"form_id": str(form.id)}, phi_accessed=True,
    ))
    return row


# ---- session / device management ---------------------------------------------


@router.get("/security", response_model=PortalSessionOut)
async def my_session(
    request: Request,
    p: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_db),
) -> PortalSessionOut:
    account = await _account(db, p)
    issued_at: datetime | None = None
    claims = getattr(request.state, "token_claims", None)
    if isinstance(claims, dict) and claims.get("iat"):
        issued_at = datetime.fromtimestamp(int(claims["iat"]), tz=timezone.utc)
    return PortalSessionOut(
        email=account.email,
        auth_mode=account.auth_mode,
        mfa_enrolled=account.mfa_enrolled,
        last_login_at=account.last_login_at,
        sessions_invalid_after=account.sessions_invalid_after,
        current_session_issued_at=issued_at,
    )


@router.post("/security/sign-out-everywhere", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def sign_out_everywhere(
    p: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    account = await _account(db, p)
    account.sessions_invalid_after = datetime.now(timezone.utc)
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="patient", actor_id=account.id, actor_email=account.email,
        entity_type="patient_account", entity_id=account.id, action="sessions_revoked",
        changes={}, phi_accessed=False,
    ))
