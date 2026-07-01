"""Patient CRUD (staff-only, PHI-logged)."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import phi_log, require_role
from app.models.activity_log import ActivityLog
from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientOut, PatientUpdate


router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
async def create_patient(
    body: PatientCreate,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider")),
    db: AsyncSession = Depends(get_db),
) -> Patient:
    dup = (await db.execute(select(Patient).where(Patient.org_id == p.org_id, Patient.mrn == body.mrn))).scalar_one_or_none()
    if dup is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "mrn already exists")
    patient = Patient(org_id=p.org_id, **body.model_dump())
    db.add(patient)
    await db.flush()
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="patient", entity_id=patient.id, action="created",
        changes={k: str(v) for k, v in body.model_dump().items()},
        phi_accessed=True,
    ))
    return patient


@router.get("", response_model=list[PatientOut])
async def list_patients(
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    p: Principal = Depends(phi_log("patient", "listed")),
    db: AsyncSession = Depends(get_db),
) -> list[Patient]:
    stmt = select(Patient).where(Patient.org_id == p.org_id, Patient.deleted_at.is_(None))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            Patient.last_name.ilike(like),
            Patient.first_name.ilike(like),
            Patient.mrn.ilike(like),
            Patient.email.ilike(like),
        ))
    stmt = stmt.order_by(Patient.last_name.asc(), Patient.first_name.asc()).limit(limit).offset(offset)
    return list((await db.execute(stmt)).scalars().all())


@router.get("/{patient_id}", response_model=PatientOut)
async def get_patient(
    patient_id: uuid.UUID,
    p: Principal = Depends(phi_log("patient", "viewed")),
    db: AsyncSession = Depends(get_db),
) -> Patient:
    row = (await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.org_id == p.org_id, Patient.deleted_at.is_(None))
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return row


@router.patch("/{patient_id}", response_model=PatientOut)
async def update_patient(
    patient_id: uuid.UUID,
    body: PatientUpdate,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider")),
    db: AsyncSession = Depends(get_db),
) -> Patient:
    row = (await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.org_id == p.org_id, Patient.deleted_at.is_(None))
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    changes = {}
    for k, v in body.model_dump(exclude_unset=True).items():
        old = getattr(row, k)
        if old != v:
            setattr(row, k, v)
            changes[k] = {"from": str(old), "to": str(v)}
    if changes:
        db.add(ActivityLog(
            org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
            entity_type="patient", entity_id=row.id, action="updated",
            changes=changes, phi_accessed=True,
        ))
    return row


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def soft_delete_patient(
    patient_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.org_id == p.org_id, Patient.deleted_at.is_(None))
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    row.deleted_at = datetime.utcnow()
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="patient", entity_id=row.id, action="deleted",
        changes={}, phi_accessed=True,
    ))
