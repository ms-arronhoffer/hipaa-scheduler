"""Organization self-service (staff view of their own tenant).

Super-admin cross-tenant CRUD lives at /admin/tenants. Practice admins can
read and update only their own org.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import require_role
from app.models.activity_log import ActivityLog
from app.models.organization import Organization
from app.schemas.organization import OrganizationOut, OrganizationUpdate


router = APIRouter(prefix="/organization", tags=["organization"])


@router.get("", response_model=OrganizationOut)
async def get_my_org(
    p: Principal = Depends(require_role("practice_admin", "billing", "front_desk", "provider")),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    row = (await db.execute(
        select(Organization).where(
            Organization.id == p.org_id,
            Organization.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return row


@router.patch("", response_model=OrganizationOut)
async def update_my_org(
    body: OrganizationUpdate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    row = (await db.execute(
        select(Organization).where(
            Organization.id == p.org_id,
            Organization.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    data = body.model_dump(exclude_unset=True)
    # Practice admins cannot self-change plan/seats/status — those are super_admin surfaces.
    for locked in ("plan", "seats", "status"):
        data.pop(locked, None)
    for k, v in data.items():
        setattr(row, k, v)
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="organization", entity_id=row.id, action="updated",
        changes=data,
    ))
    return row
