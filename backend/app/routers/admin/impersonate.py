"""Super-admin: impersonate a tenant practice_admin.

Issues a short-TTL (15-min) staff JWT bound to the target org with
`impersonating=True` in the payload. The frontend inspects that claim and
renders a persistent banner + "end session" affordance. Both start and end
are logged to the target org's ActivityLog so tenant admins see the trail.

There is no server-side session store to end — the token simply expires.
The `end` endpoint exists to write the audit row when the super-admin clicks
"return to admin".
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import jwt as jwt_service
from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import require_super_admin
from app.models.activity_log import ActivityLog
from app.models.organization import Organization
from app.schemas.organization import ImpersonateRequest


router = APIRouter(prefix="/admin/impersonate", tags=["admin_impersonate"])

IMPERSONATION_TTL_MIN = 15


class ImpersonateResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_min: int = IMPERSONATION_TTL_MIN
    org_id: str
    org_name: str


@router.post("", response_model=ImpersonateResponse)
async def start_impersonation(
    body: ImpersonateRequest,
    p: Principal = Depends(require_super_admin()),
    db: AsyncSession = Depends(get_db),
) -> ImpersonateResponse:
    org = (await db.execute(select(Organization).where(
        Organization.id == body.org_id, Organization.deleted_at.is_(None),
    ))).scalar_one_or_none()
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "org not found")
    token = jwt_service.issue_access(
        audience="staff",
        subject=p.subject_id,
        org_id=org.id,
        extra={
            "impersonating": True,
            "impersonator_email": p.email,
            "roles": ["practice_admin"],
            "reason": body.reason,
            "mfa_ok": True,
        },
        ttl_min=IMPERSONATION_TTL_MIN,
    )
    db.add(ActivityLog(
        org_id=org.id, actor_type="super_admin", actor_id=p.subject_id, actor_email=p.email,
        entity_type="organization", entity_id=org.id, action="impersonation_started",
        changes={"reason": body.reason, "ttl_min": IMPERSONATION_TTL_MIN},
    ))
    return ImpersonateResponse(
        access_token=token,
        org_id=str(org.id),
        org_name=org.name,
    )


class ImpersonationEnd(BaseModel):
    org_id: str


@router.post("/end", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def end_impersonation(
    body: ImpersonationEnd,
    p: Principal = Depends(require_super_admin()),
    db: AsyncSession = Depends(get_db),
) -> None:
    # The client dropped the impersonation token; record it so the tenant
    # audit log shows a clean start/end pair.
    try:
        import uuid as _uuid
        target_org = _uuid.UUID(body.org_id)
    except (ValueError, AttributeError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid org_id")
    db.add(ActivityLog(
        org_id=target_org, actor_type="super_admin", actor_id=p.subject_id, actor_email=p.email,
        entity_type="organization", entity_id=target_org, action="impersonation_ended",
        changes={},
    ))
