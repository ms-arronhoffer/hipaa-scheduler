"""Super-admin: tenant (organization) CRUD across the platform.

Every write here creates an ActivityLog with actor_type=super_admin scoped to
the target org so tenant admins see admin actions in their audit log.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password
from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import require_super_admin
from app.models.activity_log import ActivityLog
from app.models.organization import Organization
from app.models.user import User
from app.schemas.common import ORMModel
from app.schemas.organization import OrganizationCreate, OrganizationOut, OrganizationUpdate


router = APIRouter(prefix="/admin/tenants", tags=["admin_tenants"])


class TenantPage(ORMModel):
    items: list[OrganizationOut]
    total: int
    limit: int
    offset: int


@router.get("", response_model=TenantPage)
async def list_tenants(
    q: str | None = None,
    status_filter: str | None = None,
    include_deleted: bool = False,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _p: Principal = Depends(require_super_admin()),
    db: AsyncSession = Depends(get_db),
) -> TenantPage:
    stmt = select(Organization)
    count_stmt = select(func.count()).select_from(Organization)
    if not include_deleted:
        stmt = stmt.where(Organization.deleted_at.is_(None))
        count_stmt = count_stmt.where(Organization.deleted_at.is_(None))
    if status_filter is not None:
        stmt = stmt.where(Organization.status == status_filter)
        count_stmt = count_stmt.where(Organization.status == status_filter)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(func.lower(Organization.name).like(like) | func.lower(Organization.slug).like(like))
        count_stmt = count_stmt.where(func.lower(Organization.name).like(like) | func.lower(Organization.slug).like(like))
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (await db.execute(
        stmt.order_by(Organization.created_at.desc()).limit(limit).offset(offset)
    )).scalars().all()
    return TenantPage(
        items=[OrganizationOut.model_validate(r) for r in rows],
        total=total, limit=limit, offset=offset,
    )


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    body: OrganizationCreate,
    p: Principal = Depends(require_super_admin()),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    org = Organization(
        name=body.name,
        slug=body.slug.lower(),
        plan=body.plan,
        seats=body.seats,
        mfa_required=body.mfa_required,
    )
    db.add(org)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "slug already taken")
    if body.admin_email and body.admin_password:
        admin = User(
            org_id=org.id,
            email=body.admin_email.lower(),
            password_hash=hash_password(body.admin_password),
            roles=["practice_admin"],
        )
        db.add(admin)
        await db.flush()
    db.add(ActivityLog(
        org_id=org.id, actor_type="super_admin", actor_id=p.subject_id, actor_email=p.email,
        entity_type="organization", entity_id=org.id, action="provisioned",
        changes={"plan": org.plan, "seats": org.seats},
    ))
    return org


@router.get("/{org_id}", response_model=OrganizationOut)
async def get_tenant(
    org_id: uuid.UUID,
    _p: Principal = Depends(require_super_admin()),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    row = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return row


@router.patch("/{org_id}", response_model=OrganizationOut)
async def update_tenant(
    org_id: uuid.UUID,
    body: OrganizationUpdate,
    p: Principal = Depends(require_super_admin()),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    row = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    db.add(ActivityLog(
        org_id=org_id, actor_type="super_admin", actor_id=p.subject_id, actor_email=p.email,
        entity_type="organization", entity_id=row.id, action="updated",
        changes=data,
    ))
    return row


@router.post("/{org_id}/sign-baa", response_model=OrganizationOut)
async def sign_baa(
    org_id: uuid.UUID,
    p: Principal = Depends(require_super_admin()),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    row = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    row.baa_signed_at = datetime.utcnow()
    db.add(ActivityLog(
        org_id=org_id, actor_type="super_admin", actor_id=p.subject_id, actor_email=p.email,
        entity_type="organization", entity_id=row.id, action="baa_signed",
        changes={"baa_signed_at": row.baa_signed_at.isoformat()},
    ))
    return row


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    org_id: uuid.UUID,
    p: Principal = Depends(require_super_admin()),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(select(Organization).where(
        Organization.id == org_id, Organization.deleted_at.is_(None),
    ))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    # Retention floor prevents hard delete of PHI-owning rows; org row is soft-deleted
    # and the retention_sweep worker enforces the 6yr floor before any purge.
    row.status = "suspended"
    row.deleted_at = datetime.utcnow()
    db.add(ActivityLog(
        org_id=org_id, actor_type="super_admin", actor_id=p.subject_id, actor_email=p.email,
        entity_type="organization", entity_id=row.id, action="suspended",
        changes={},
    ))
