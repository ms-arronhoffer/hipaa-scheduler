"""Super-admin: seat utilization per tenant.

Active seat = User row with deleted_at IS NULL. Locked users still count —
they occupy a seat until removed. Used by billing to reconcile overage.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import require_super_admin
from app.models.organization import Organization
from app.models.user import User
from app.schemas.common import ORMModel


router = APIRouter(prefix="/admin", tags=["admin_seats"])


class SeatUsage(ORMModel):
    org_id: uuid.UUID
    org_name: str
    seats: int
    active_users: int
    over: int


class SeatUsagePage(ORMModel):
    items: list[SeatUsage]
    total: int
    limit: int
    offset: int


@router.get("/seats", response_model=SeatUsagePage)
async def list_seat_usage(
    over_only: bool = False,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _p: Principal = Depends(require_super_admin()),
    db: AsyncSession = Depends(get_db),
) -> SeatUsagePage:
    active_users = (
        select(User.org_id, func.count(User.id).label("cnt"))
        .where(User.deleted_at.is_(None))
        .group_by(User.org_id)
        .subquery()
    )
    stmt = (
        select(
            Organization.id, Organization.name, Organization.seats,
            func.coalesce(active_users.c.cnt, 0).label("active"),
        )
        .outerjoin(active_users, active_users.c.org_id == Organization.id)
        .where(Organization.deleted_at.is_(None))
    )
    if over_only:
        stmt = stmt.where(func.coalesce(active_users.c.cnt, 0) > Organization.seats)
    total = (await db.execute(
        select(func.count()).select_from(stmt.subquery())
    )).scalar_one()
    rows = (await db.execute(
        stmt.order_by(Organization.name).limit(limit).offset(offset)
    )).all()
    items = [
        SeatUsage(
            org_id=r.id, org_name=r.name, seats=r.seats, active_users=r.active,
            over=max(0, r.active - r.seats),
        )
        for r in rows
    ]
    return SeatUsagePage(items=items, total=total, limit=limit, offset=offset)


@router.get("/tenants/{org_id}/seats", response_model=SeatUsage)
async def tenant_seat_usage(
    org_id: uuid.UUID,
    _p: Principal = Depends(require_super_admin()),
    db: AsyncSession = Depends(get_db),
) -> SeatUsage:
    org = (await db.execute(select(Organization).where(
        Organization.id == org_id, Organization.deleted_at.is_(None),
    ))).scalar_one_or_none()
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    active = (await db.execute(
        select(func.count(User.id)).where(User.org_id == org_id, User.deleted_at.is_(None))
    )).scalar_one()
    return SeatUsage(
        org_id=org.id, org_name=org.name, seats=org.seats, active_users=active,
        over=max(0, active - org.seats),
    )
