"""Super-admin: cross-tenant ActivityLog search.

Tenant admins get scoped audit under /activity-log; this endpoint drops the
org_id constraint so super-admins can investigate incidents across the fleet.
Every search is itself logged (against the target org when filtered, else null).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import require_super_admin
from app.models.activity_log import ActivityLog
from app.schemas.common import ORMModel


router = APIRouter(prefix="/admin/audit", tags=["admin_audit"])


class ActivityLogRow(ORMModel):
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
    created_at: datetime


class ActivityLogPage(ORMModel):
    items: list[ActivityLogRow]
    total: int
    limit: int
    offset: int


@router.get("/search", response_model=ActivityLogPage)
async def search_audit(
    org_id: uuid.UUID | None = None,
    actor_email: str | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    action: str | None = None,
    phi_only: bool = False,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    p: Principal = Depends(require_super_admin()),
    db: AsyncSession = Depends(get_db),
) -> ActivityLogPage:
    stmt = select(ActivityLog)
    count_stmt = select(func.count()).select_from(ActivityLog)
    conds = []
    if org_id is not None:
        conds.append(ActivityLog.org_id == org_id)
    if actor_email:
        conds.append(func.lower(ActivityLog.actor_email) == actor_email.lower())
    if entity_type:
        conds.append(ActivityLog.entity_type == entity_type)
    if entity_id is not None:
        conds.append(ActivityLog.entity_id == entity_id)
    if action:
        conds.append(ActivityLog.action == action)
    if phi_only:
        conds.append(ActivityLog.phi_accessed.is_(True))
    if from_ts is not None:
        conds.append(ActivityLog.created_at >= from_ts)
    if to_ts is not None:
        conds.append(ActivityLog.created_at <= to_ts)
    for c in conds:
        stmt = stmt.where(c)
        count_stmt = count_stmt.where(c)
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (await db.execute(
        stmt.order_by(ActivityLog.created_at.desc()).limit(limit).offset(offset)
    )).scalars().all()
    # Log the search itself. Scope to target org when filtered so tenant admins
    # can see that a super-admin queried their logs; org_id may be None for
    # fleet-wide searches.
    if org_id is not None:
        db.add(ActivityLog(
            org_id=org_id, actor_type="super_admin", actor_id=p.subject_id, actor_email=p.email,
            entity_type="activity_log", entity_id=None, action="searched",
            changes={"filters": {
                "actor_email": actor_email, "entity_type": entity_type,
                "action": action, "phi_only": phi_only,
            }},
        ))
    return ActivityLogPage(
        items=[ActivityLogRow.model_validate(r) for r in rows],
        total=total, limit=limit, offset=offset,
    )
