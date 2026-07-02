"""Role/scope/org/MFA guards + PHI access logging dependency.

The `phi_log` dependency runs before the handler, records the access as
`viewed`, and lets the handler add richer entries via ActivityService.log()
for writes. Every guard returns a callable dependency you attach with
`Depends(...)`.
"""
from __future__ import annotations

import uuid
from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal, current_principal
from app.database import get_db
from app.models.activity_log import ActivityLog
from app.models.patient import Patient


def require_kinds(*kinds: str) -> Callable:
    async def _dep(p: Principal = Depends(current_principal)) -> Principal:
        if p.kind not in kinds:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "wrong principal kind")
        return p
    return _dep


def require_staff() -> Callable:
    return require_kinds("user")


def require_patient() -> Callable:
    return require_kinds("patient")


def require_role(*roles: str) -> Callable:
    async def _dep(p: Principal = Depends(current_principal)) -> Principal:
        if p.kind != "user":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "staff only")
        if p.is_super_admin:
            return p
        if not any(r in p.roles for r in roles):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "missing role")
        return p
    return _dep


def require_super_admin() -> Callable:
    async def _dep(p: Principal = Depends(current_principal)) -> Principal:
        if p.kind != "user" or not p.is_super_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "super_admin only")
        return p
    return _dep


def require_scope(*scopes: str) -> Callable:
    async def _dep(p: Principal = Depends(current_principal)) -> Principal:
        if p.kind != "api_key":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "api key required")
        if not any(s in p.scopes for s in scopes):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient scope")
        return p
    return _dep


def require_mfa() -> Callable:
    async def _dep(p: Principal = Depends(current_principal)) -> Principal:
        if p.kind == "user" and not p.mfa_ok:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "mfa required")
        return p
    return _dep


def enforce_org_access(org_id_param: str = "org_id") -> Callable:
    async def _dep(request: Request, p: Principal = Depends(current_principal)) -> Principal:
        if getattr(p, "is_super_admin", False):
            return p
        target = request.path_params.get(org_id_param) or request.query_params.get(org_id_param)
        if target and str(p.org_id) != str(target):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "org mismatch")
        return p
    return _dep


async def ensure_patient_in_org(
    db: AsyncSession, patient_id: uuid.UUID, org_id: uuid.UUID
) -> None:
    """Verify a patient row belongs to the caller's org (tenant isolation).

    Call this in every handler that accepts a ``patient_id`` from the request
    body or query string before using it. Raises 404 — never an empty 200 or a
    403 — when the patient does not exist or belongs to another org, so a caller
    can neither read cross-tenant data nor probe for the existence of IDs in
    other tenants (IDOR / enumeration defense).
    """
    found = (await db.execute(
        select(Patient.id).where(
            Patient.id == patient_id,
            Patient.org_id == org_id,
            Patient.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "patient not found")


def phi_log(entity_type: str, action: str = "viewed") -> Callable:
    async def _dep(
        request: Request,
        p: Principal = Depends(current_principal),
        db: AsyncSession = Depends(get_db),
    ) -> Principal:
        entity_id_raw = request.path_params.get("id") or request.path_params.get(f"{entity_type}_id")
        entity_id: uuid.UUID | None = None
        if entity_id_raw:
            try:
                entity_id = uuid.UUID(str(entity_id_raw))
            except ValueError:
                entity_id = None
        db.add(ActivityLog(
            org_id=p.org_id,
            actor_type=p.kind,
            actor_id=p.subject_id,
            actor_email=p.email,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            changes={},
            phi_accessed=True,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            request_id=request.headers.get("x-request-id"),
        ))
        return p
    return _dep
