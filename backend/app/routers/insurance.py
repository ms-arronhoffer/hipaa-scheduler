"""Patient InsurancePolicy CRUD.

Priority is 1..5 (1 = primary). We prevent two active policies from sharing
the same priority for the same patient — soft-deleted rows are ignored.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import ensure_patient_in_org, phi_log, require_role
from app.models.activity_log import ActivityLog
from app.models.patient_records import InsurancePolicy
from app.schemas.patient_records import InsuranceCreate, InsuranceOut, InsuranceUpdate


router = APIRouter(prefix="/insurance", tags=["insurance"])


async def _priority_conflict(
    db: AsyncSession, *, org_id: uuid.UUID, patient_id: uuid.UUID,
    priority: int, exclude_id: uuid.UUID | None = None,
) -> bool:
    stmt = select(InsurancePolicy.id).where(
        InsurancePolicy.org_id == org_id,
        InsurancePolicy.patient_id == patient_id,
        InsurancePolicy.priority == priority,
        InsurancePolicy.active.is_(True),
        InsurancePolicy.deleted_at.is_(None),
    )
    if exclude_id is not None:
        stmt = stmt.where(InsurancePolicy.id != exclude_id)
    return (await db.execute(stmt)).scalar_one_or_none() is not None


@router.get("", response_model=list[InsuranceOut])
async def list_insurance(
    patient_id: uuid.UUID | None = None,
    p: Principal = Depends(phi_log("insurance", "listed")),
    db: AsyncSession = Depends(get_db),
) -> list[InsurancePolicy]:
    stmt = select(InsurancePolicy).where(
        InsurancePolicy.org_id == p.org_id, InsurancePolicy.deleted_at.is_(None)
    )
    if patient_id is not None:
        await ensure_patient_in_org(db, patient_id, p.org_id)
        stmt = stmt.where(InsurancePolicy.patient_id == patient_id)
    stmt = stmt.order_by(InsurancePolicy.patient_id, InsurancePolicy.priority)
    return list((await db.execute(stmt)).scalars().all())


@router.post("", response_model=InsuranceOut, status_code=status.HTTP_201_CREATED)
async def create_insurance(
    body: InsuranceCreate,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "billing")),
    db: AsyncSession = Depends(get_db),
) -> InsurancePolicy:
    await ensure_patient_in_org(db, body.patient_id, p.org_id)
    if await _priority_conflict(db, org_id=p.org_id, patient_id=body.patient_id, priority=body.priority):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"patient already has an active policy at priority {body.priority}",
        )
    row = InsurancePolicy(org_id=p.org_id, **body.model_dump())
    db.add(row)
    await db.flush()
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="insurance", entity_id=row.id, action="created",
        changes={"patient_id": str(body.patient_id), "carrier": body.carrier, "priority": body.priority},
        phi_accessed=True,
    ))
    return row


@router.get("/{policy_id}", response_model=InsuranceOut)
async def get_insurance(
    policy_id: uuid.UUID,
    p: Principal = Depends(phi_log("insurance", "viewed")),
    db: AsyncSession = Depends(get_db),
) -> InsurancePolicy:
    row = (await db.execute(
        select(InsurancePolicy).where(
            InsurancePolicy.id == policy_id,
            InsurancePolicy.org_id == p.org_id,
            InsurancePolicy.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return row


@router.patch("/{policy_id}", response_model=InsuranceOut)
async def update_insurance(
    policy_id: uuid.UUID,
    body: InsuranceUpdate,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "billing")),
    db: AsyncSession = Depends(get_db),
) -> InsurancePolicy:
    row = (await db.execute(
        select(InsurancePolicy).where(
            InsurancePolicy.id == policy_id,
            InsurancePolicy.org_id == p.org_id,
            InsurancePolicy.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    data = body.model_dump(exclude_unset=True)
    new_priority = data.get("priority", row.priority)
    will_be_active = data.get("active", row.active)
    if will_be_active and await _priority_conflict(
        db, org_id=p.org_id, patient_id=row.patient_id,
        priority=new_priority, exclude_id=row.id,
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"patient already has an active policy at priority {new_priority}",
        )
    for k, v in data.items():
        setattr(row, k, v)
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="insurance", entity_id=row.id, action="updated",
        changes={k: str(v) for k, v in data.items()}, phi_accessed=True,
    ))
    return row


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_insurance(
    policy_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin", "billing")),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(
        select(InsurancePolicy).where(
            InsurancePolicy.id == policy_id,
            InsurancePolicy.org_id == p.org_id,
            InsurancePolicy.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    row.deleted_at = datetime.utcnow()
    row.active = False
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="insurance", entity_id=row.id, action="deleted",
        changes={"carrier": row.carrier}, phi_accessed=True,
    ))
