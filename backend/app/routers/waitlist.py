"""Waitlist CRUD (staff-only, PHI-logged)."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import phi_log, require_role
from app.models.activity_log import ActivityLog
from app.models.waitlist import WAITLIST_STATUSES, WaitlistEntry
from app.schemas.waitlist import WaitlistCreate, WaitlistOut, WaitlistUpdate


router = APIRouter(prefix="/waitlist", tags=["waitlist"])


@router.get("", response_model=list[WaitlistOut])
async def list_waitlist(
    status_filter: str | None = None,
    patient_id: uuid.UUID | None = None,
    p: Principal = Depends(phi_log("waitlist", "listed")),
    db: AsyncSession = Depends(get_db),
) -> list[WaitlistEntry]:
    stmt = select(WaitlistEntry).where(
        WaitlistEntry.org_id == p.org_id, WaitlistEntry.deleted_at.is_(None)
    )
    if status_filter is not None:
        stmt = stmt.where(WaitlistEntry.status == status_filter)
    if patient_id is not None:
        stmt = stmt.where(WaitlistEntry.patient_id == patient_id)
    stmt = stmt.order_by(WaitlistEntry.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


@router.post("", response_model=WaitlistOut, status_code=status.HTTP_201_CREATED)
async def create_waitlist(
    body: WaitlistCreate,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider")),
    db: AsyncSession = Depends(get_db),
) -> WaitlistEntry:
    if body.latest_at <= body.earliest_at:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "latest_at must be after earliest_at")
    row = WaitlistEntry(org_id=p.org_id, **body.model_dump())
    db.add(row)
    await db.flush()
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="waitlist", entity_id=row.id, action="created",
        changes={"patient_id": str(body.patient_id)}, phi_accessed=True,
    ))
    return row


@router.patch("/{entry_id}", response_model=WaitlistOut)
async def update_waitlist(
    entry_id: uuid.UUID,
    body: WaitlistUpdate,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider")),
    db: AsyncSession = Depends(get_db),
) -> WaitlistEntry:
    row = (await db.execute(
        select(WaitlistEntry).where(
            WaitlistEntry.id == entry_id,
            WaitlistEntry.org_id == p.org_id,
            WaitlistEntry.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in WAITLIST_STATUSES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"status must be one of {WAITLIST_STATUSES}")
    for k, v in data.items():
        setattr(row, k, v)
    return row


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_waitlist(
    entry_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider")),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(
        select(WaitlistEntry).where(
            WaitlistEntry.id == entry_id,
            WaitlistEntry.org_id == p.org_id,
            WaitlistEntry.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    row.status = "canceled"
    row.deleted_at = datetime.utcnow()
