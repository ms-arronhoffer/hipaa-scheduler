"""ActivityLog read API (audit trail viewer).

Every mutation and PHI read in the system writes an ActivityLog row.
This is the read side — filter/paginate the immutable trail. No POST/PATCH/DELETE:
audit records must never be modified.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import require_role
from app.models.activity_log import ActivityLog
from app.schemas.common import ORMModel
from app.services import audit_chain


router = APIRouter(prefix="/activity-log", tags=["activity_log"])


class ActivityLogOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    actor_type: str
    actor_id: uuid.UUID | None
    actor_email: str | None
    entity_type: str
    entity_id: uuid.UUID | None
    action: str
    changes: dict
    phi_accessed: bool
    ip: str | None
    user_agent: str | None
    request_id: str | None
    created_at: datetime


class ActivityLogPage(ORMModel):
    items: list[ActivityLogOut]
    total: int
    limit: int
    offset: int


@router.get("", response_model=ActivityLogPage)
async def list_activity(
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    action: str | None = None,
    phi_only: bool = False,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    p: Principal = Depends(require_role("practice_admin", "billing")),
    db: AsyncSession = Depends(get_db),
) -> ActivityLogPage:
    stmt = select(ActivityLog).where(ActivityLog.org_id == p.org_id)
    count_stmt = select(func.count()).select_from(ActivityLog).where(ActivityLog.org_id == p.org_id)
    if entity_type is not None:
        stmt = stmt.where(ActivityLog.entity_type == entity_type)
        count_stmt = count_stmt.where(ActivityLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(ActivityLog.entity_id == entity_id)
        count_stmt = count_stmt.where(ActivityLog.entity_id == entity_id)
    if actor_id is not None:
        stmt = stmt.where(ActivityLog.actor_id == actor_id)
        count_stmt = count_stmt.where(ActivityLog.actor_id == actor_id)
    if action is not None:
        stmt = stmt.where(ActivityLog.action == action)
        count_stmt = count_stmt.where(ActivityLog.action == action)
    if phi_only:
        stmt = stmt.where(ActivityLog.phi_accessed.is_(True))
        count_stmt = count_stmt.where(ActivityLog.phi_accessed.is_(True))
    if since is not None:
        stmt = stmt.where(ActivityLog.created_at >= since)
        count_stmt = count_stmt.where(ActivityLog.created_at >= since)
    if until is not None:
        stmt = stmt.where(ActivityLog.created_at <= until)
        count_stmt = count_stmt.where(ActivityLog.created_at <= until)

    total = (await db.execute(count_stmt)).scalar_one()
    rows = (await db.execute(
        stmt.order_by(ActivityLog.created_at.desc()).limit(limit).offset(offset)
    )).scalars().all()
    return ActivityLogPage(
        items=[ActivityLogOut.model_validate(r) for r in rows],
        total=total, limit=limit, offset=offset,
    )


class ChainVerifyResult(ORMModel):
    ok: bool
    checked: int
    broken_at: int | None


@router.get("/verify", response_model=ChainVerifyResult)
async def verify_audit_chain(
    limit: int = Query(default=10000, ge=1, le=100000),
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> ChainVerifyResult:
    """Re-walk this org's audit hash chain and report the first break, if any.

    A ``broken_at`` sequence number means a row was altered or removed after it
    was written — evidence of tampering with the "immutable" audit trail.
    """
    rows = (await db.execute(
        select(ActivityLog)
        .where(ActivityLog.org_id == p.org_id, ActivityLog.entry_hash.is_not(None))
        .order_by(ActivityLog.seq.asc())
        .limit(limit)
    )).scalars().all()
    result = audit_chain.verify_chain(rows)
    return ChainVerifyResult(**result)
