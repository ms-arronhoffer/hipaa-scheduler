"""Patient Consent records (HIPAA/telehealth/SMS/financial)."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import ensure_patient_in_org, phi_log, require_role
from app.models.activity_log import ActivityLog
from app.models.patient_records import CONSENT_KINDS, Consent
from app.schemas.patient_records import ConsentCreate, ConsentOut


router = APIRouter(prefix="/consents", tags=["consents"])


@router.get("", response_model=list[ConsentOut])
async def list_consents(
    patient_id: uuid.UUID | None = None,
    kind: str | None = None,
    p: Principal = Depends(phi_log("consent", "listed")),
    db: AsyncSession = Depends(get_db),
) -> list[Consent]:
    stmt = select(Consent).where(Consent.org_id == p.org_id, Consent.deleted_at.is_(None))
    if patient_id is not None:
        await ensure_patient_in_org(db, patient_id, p.org_id)
        stmt = stmt.where(Consent.patient_id == patient_id)
    if kind is not None:
        stmt = stmt.where(Consent.kind == kind)
    stmt = stmt.order_by(Consent.signed_at.desc())
    return list((await db.execute(stmt)).scalars().all())


@router.post("", response_model=ConsentOut, status_code=status.HTTP_201_CREATED)
async def create_consent(
    body: ConsentCreate,
    request: Request,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider")),
    db: AsyncSession = Depends(get_db),
) -> Consent:
    if body.kind not in CONSENT_KINDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"kind must be one of {CONSENT_KINDS}")
    await ensure_patient_in_org(db, body.patient_id, p.org_id)
    row = Consent(
        org_id=p.org_id,
        patient_id=body.patient_id,
        kind=body.kind,
        document_version=body.document_version,
        body_hash=body.body_hash,
        signed_at=datetime.utcnow(),
        signer_name=body.signer_name,
        signer_ip=request.client.host if request.client else None,
    )
    db.add(row)
    await db.flush()
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="consent", entity_id=row.id, action="created",
        changes={"kind": body.kind, "patient_id": str(body.patient_id), "version": body.document_version},
        phi_accessed=True,
    ))
    return row


@router.get("/{consent_id}", response_model=ConsentOut)
async def get_consent(
    consent_id: uuid.UUID,
    p: Principal = Depends(phi_log("consent", "viewed")),
    db: AsyncSession = Depends(get_db),
) -> Consent:
    row = (await db.execute(
        select(Consent).where(
            Consent.id == consent_id,
            Consent.org_id == p.org_id,
            Consent.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return row


@router.delete("/{consent_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def revoke_consent(
    consent_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(
        select(Consent).where(
            Consent.id == consent_id,
            Consent.org_id == p.org_id,
            Consent.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    row.deleted_at = datetime.utcnow()
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="consent", entity_id=row.id, action="revoked",
        changes={"kind": row.kind}, phi_accessed=True,
    ))
