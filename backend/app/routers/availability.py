"""ProviderAvailability weekly template CRUD."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import require_role
from app.models.availability import ProviderAvailability
from app.schemas.availability import (
    AvailabilityCreate,
    AvailabilityOut,
    AvailabilityUpdate,
)


router = APIRouter(prefix="/availability", tags=["availability"])


@router.get("", response_model=list[AvailabilityOut])
async def list_availability(
    provider_id: uuid.UUID | None = None,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> list[ProviderAvailability]:
    stmt = select(ProviderAvailability).where(
        ProviderAvailability.org_id == p.org_id,
        ProviderAvailability.deleted_at.is_(None),
    )
    if provider_id is not None:
        stmt = stmt.where(ProviderAvailability.provider_id == provider_id)
    stmt = stmt.order_by(ProviderAvailability.weekday, ProviderAvailability.start_time)
    return list((await db.execute(stmt)).scalars().all())


@router.post("", response_model=AvailabilityOut, status_code=status.HTTP_201_CREATED)
async def create_availability(
    body: AvailabilityCreate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> ProviderAvailability:
    row = ProviderAvailability(org_id=p.org_id, **body.model_dump())
    db.add(row)
    await db.flush()
    return row


@router.patch("/{availability_id}", response_model=AvailabilityOut)
async def update_availability(
    availability_id: uuid.UUID,
    body: AvailabilityUpdate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> ProviderAvailability:
    row = (await db.execute(
        select(ProviderAvailability).where(
            ProviderAvailability.id == availability_id,
            ProviderAvailability.org_id == p.org_id,
            ProviderAvailability.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    if row.end_time <= row.start_time:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "end_time must be after start_time")
    return row


@router.delete("/{availability_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_availability(
    availability_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(
        select(ProviderAvailability).where(
            ProviderAvailability.id == availability_id,
            ProviderAvailability.org_id == p.org_id,
            ProviderAvailability.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    row.deleted_at = datetime.utcnow()
