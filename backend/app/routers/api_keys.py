"""API key management (`hs_` prefix, sha256-hashed at rest).

Plaintext is shown ONCE at creation. Rotate = revoke + create new.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.api_key import generate
from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import require_role
from app.models.activity_log import ActivityLog
from app.models.api_key import ApiKey
from app.schemas.integrations import ApiKeyCreate, ApiKeyCreated, ApiKeyOut


router = APIRouter(prefix="/api-keys", tags=["api_keys"])


@router.get("", response_model=list[ApiKeyOut])
async def list_api_keys(
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> list[ApiKey]:
    rows = (await db.execute(
        select(ApiKey).where(
            ApiKey.org_id == p.org_id, ApiKey.deleted_at.is_(None),
        ).order_by(ApiKey.created_at.desc())
    )).scalars().all()
    return list(rows)


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreated:
    plaintext, prefix, digest = generate()
    row = ApiKey(
        org_id=p.org_id,
        name=body.name,
        prefix=prefix,
        key_hash=digest,
        scopes=body.scopes,
        created_by_user_id=p.subject_id,
        expires_at=body.expires_at,
        active=True,
    )
    db.add(row)
    await db.flush()
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="api_key", entity_id=row.id, action="created",
        changes={"name": body.name, "scopes": body.scopes, "prefix": prefix},
    ))
    return ApiKeyCreated(id=row.id, plaintext=plaintext, prefix=prefix, scopes=body.scopes)


@router.post("/{key_id}/revoke", response_model=ApiKeyOut)
async def revoke_api_key(
    key_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    row = (await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id, ApiKey.org_id == p.org_id, ApiKey.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    row.active = False
    row.revoked_at = datetime.utcnow()
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="api_key", entity_id=row.id, action="revoked",
        changes={"prefix": row.prefix},
    ))
    return row


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id, ApiKey.org_id == p.org_id, ApiKey.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    row.active = False
    row.revoked_at = row.revoked_at or datetime.utcnow()
    row.deleted_at = datetime.utcnow()
