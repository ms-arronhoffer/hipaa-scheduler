"""Offices + Resources CRUD (practice_admin only for writes)."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import require_role
from app.models.appointment_type import Resource
from app.models.office import Office
from app.schemas.office import (
    OfficeCreate,
    OfficeOut,
    OfficeUpdate,
    ResourceCreate,
    ResourceOut,
    ResourceUpdate,
)


router = APIRouter(prefix="/offices", tags=["offices"])
resources_router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("", response_model=list[OfficeOut])
async def list_offices(
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> list[Office]:
    rows = (await db.execute(
        select(Office).where(Office.org_id == p.org_id, Office.deleted_at.is_(None)).order_by(Office.name)
    )).scalars().all()
    return list(rows)


@router.post("", response_model=OfficeOut, status_code=status.HTTP_201_CREATED)
async def create_office(
    body: OfficeCreate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> Office:
    row = Office(org_id=p.org_id, **body.model_dump())
    db.add(row)
    await db.flush()
    return row


@router.get("/{office_id}", response_model=OfficeOut)
async def get_office(
    office_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> Office:
    row = (await db.execute(
        select(Office).where(Office.id == office_id, Office.org_id == p.org_id, Office.deleted_at.is_(None))
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return row


@router.patch("/{office_id}", response_model=OfficeOut)
async def update_office(
    office_id: uuid.UUID,
    body: OfficeUpdate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> Office:
    row = (await db.execute(
        select(Office).where(Office.id == office_id, Office.org_id == p.org_id, Office.deleted_at.is_(None))
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    return row


@router.delete("/{office_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_office(
    office_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(
        select(Office).where(Office.id == office_id, Office.org_id == p.org_id, Office.deleted_at.is_(None))
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    row.deleted_at = datetime.utcnow()


# ---- resources (rooms/chairs) --------------------------------------------------


@resources_router.get("", response_model=list[ResourceOut])
async def list_resources(
    office_id: uuid.UUID | None = None,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> list[Resource]:
    stmt = select(Resource).where(Resource.org_id == p.org_id, Resource.deleted_at.is_(None))
    if office_id is not None:
        stmt = stmt.where(Resource.office_id == office_id)
    return list((await db.execute(stmt.order_by(Resource.name))).scalars().all())


@resources_router.post("", response_model=ResourceOut, status_code=status.HTTP_201_CREATED)
async def create_resource(
    body: ResourceCreate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> Resource:
    row = Resource(org_id=p.org_id, **body.model_dump())
    db.add(row)
    await db.flush()
    return row


@resources_router.patch("/{resource_id}", response_model=ResourceOut)
async def update_resource(
    resource_id: uuid.UUID,
    body: ResourceUpdate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> Resource:
    row = (await db.execute(
        select(Resource).where(Resource.id == resource_id, Resource.org_id == p.org_id, Resource.deleted_at.is_(None))
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    return row


@resources_router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_resource(
    resource_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(
        select(Resource).where(Resource.id == resource_id, Resource.org_id == p.org_id, Resource.deleted_at.is_(None))
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    row.deleted_at = datetime.utcnow()
