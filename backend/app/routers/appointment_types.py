"""AppointmentType CRUD (practice_admin writes; staff reads)."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import require_role
from app.models.appointment_type import AppointmentType
from app.schemas.appointment_type import (
    AppointmentTypeCreate,
    AppointmentTypeOut,
    AppointmentTypeUpdate,
)


router = APIRouter(prefix="/appointment-types", tags=["appointment_types"])


@router.get("", response_model=list[AppointmentTypeOut])
async def list_types(
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> list[AppointmentType]:
    rows = (await db.execute(
        select(AppointmentType).where(
            AppointmentType.org_id == p.org_id, AppointmentType.deleted_at.is_(None)
        ).order_by(AppointmentType.name)
    )).scalars().all()
    return list(rows)


@router.post("", response_model=AppointmentTypeOut, status_code=status.HTTP_201_CREATED)
async def create_type(
    body: AppointmentTypeCreate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> AppointmentType:
    row = AppointmentType(org_id=p.org_id, **body.model_dump())
    db.add(row)
    await db.flush()
    return row


@router.get("/{type_id}", response_model=AppointmentTypeOut)
async def get_type(
    type_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> AppointmentType:
    row = (await db.execute(
        select(AppointmentType).where(
            AppointmentType.id == type_id,
            AppointmentType.org_id == p.org_id,
            AppointmentType.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return row


@router.patch("/{type_id}", response_model=AppointmentTypeOut)
async def update_type(
    type_id: uuid.UUID,
    body: AppointmentTypeUpdate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> AppointmentType:
    row = (await db.execute(
        select(AppointmentType).where(
            AppointmentType.id == type_id,
            AppointmentType.org_id == p.org_id,
            AppointmentType.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    return row


@router.delete("/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_type(
    type_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(
        select(AppointmentType).where(
            AppointmentType.id == type_id,
            AppointmentType.org_id == p.org_id,
            AppointmentType.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    row.deleted_at = datetime.utcnow()
