"""Super-admin: plan and seat overrides on a tenant.

Separate from /admin/tenants patch so plan changes leave a distinct action in
the audit log (`plan_changed`) and can be gated later on a billing workflow.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import require_super_admin
from app.models.activity_log import ActivityLog
from app.models.organization import Organization
from app.schemas.organization import OrganizationOut


router = APIRouter(prefix="/admin/tenants", tags=["admin_plans"])


class PlanOverride(BaseModel):
    plan: str | None = Field(default=None, max_length=40)
    seats: int | None = Field(default=None, ge=1)


@router.post("/{org_id}/plan", response_model=OrganizationOut)
async def override_plan(
    org_id: uuid.UUID,
    body: PlanOverride,
    p: Principal = Depends(require_super_admin()),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    if body.plan is None and body.seats is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "nothing to change")
    row = (await db.execute(select(Organization).where(
        Organization.id == org_id, Organization.deleted_at.is_(None),
    ))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    before = {"plan": row.plan, "seats": row.seats}
    if body.plan is not None:
        row.plan = body.plan
    if body.seats is not None:
        row.seats = body.seats
    db.add(ActivityLog(
        org_id=org_id, actor_type="super_admin", actor_id=p.subject_id, actor_email=p.email,
        entity_type="organization", entity_id=row.id, action="plan_changed",
        changes={"before": before, "after": {"plan": row.plan, "seats": row.seats}},
    ))
    return row
