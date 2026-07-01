"""Provider TimeOff CRUD (blocks scheduling for a datetime range)."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import require_role
from app.models.availability import TimeOff
from app.schemas.availability import TimeOffCreate, TimeOffOut


router = APIRouter(prefix="/timeoff", tags=["timeoff"])


@router.get("", response_model=list[TimeOffOut])
async def list_timeoff(
    provider_id: uuid.UUID | None = None,
    range_start: datetime | None = Query(default=None),
    range_end: datetime | None = Query(default=None),
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> list[TimeOff]:
    stmt = select(TimeOff).where(TimeOff.org_id == p.org_id, TimeOff.deleted_at.is_(None))
    if provider_id is not None:
        stmt = stmt.where(TimeOff.provider_id == provider_id)
    if range_start is not None:
        stmt = stmt.where(TimeOff.end_at >= range_start)
    if range_end is not None:
        stmt = stmt.where(TimeOff.start_at <= range_end)
    stmt = stmt.order_by(TimeOff.start_at)
    return list((await db.execute(stmt)).scalars().all())


@router.post("", response_model=TimeOffOut, status_code=status.HTTP_201_CREATED)
async def create_timeoff(
    body: TimeOffCreate,
    p: Principal = Depends(require_role("practice_admin", "provider")),
    db: AsyncSession = Depends(get_db),
) -> TimeOff:
    row = TimeOff(org_id=p.org_id, **body.model_dump())
    db.add(row)
    await db.flush()
    return row


@router.delete("/{timeoff_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timeoff(
    timeoff_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin", "provider")),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(
        select(TimeOff).where(
            TimeOff.id == timeoff_id,
            TimeOff.org_id == p.org_id,
            TimeOff.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    row.deleted_at = datetime.utcnow()
