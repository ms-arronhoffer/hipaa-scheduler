"""ProviderProfile CRUD (practice_admin writes; staff reads)."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import require_role
from app.models.user import ProviderProfile, User
from app.schemas.user import ProviderCreate, ProviderOut, ProviderUpdate


router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=list[ProviderOut])
async def list_providers(
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> list[ProviderProfile]:
    rows = (await db.execute(
        select(ProviderProfile).where(
            ProviderProfile.org_id == p.org_id, ProviderProfile.deleted_at.is_(None)
        )
    )).scalars().all()
    return list(rows)


@router.post("", response_model=ProviderOut, status_code=status.HTTP_201_CREATED)
async def create_provider(
    body: ProviderCreate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> ProviderProfile:
    user = (await db.execute(
        select(User).where(User.id == body.user_id, User.org_id == p.org_id, User.deleted_at.is_(None))
    )).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    if "provider" not in (user.roles or []):
        user.roles = list((user.roles or [])) + ["provider"]
    existing = (await db.execute(
        select(ProviderProfile).where(
            ProviderProfile.user_id == body.user_id,
            ProviderProfile.org_id == p.org_id,
            ProviderProfile.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "provider profile already exists for user")
    row = ProviderProfile(org_id=p.org_id, **body.model_dump())
    db.add(row)
    await db.flush()
    return row


@router.get("/{provider_id}", response_model=ProviderOut)
async def get_provider(
    provider_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> ProviderProfile:
    row = (await db.execute(
        select(ProviderProfile).where(
            ProviderProfile.id == provider_id,
            ProviderProfile.org_id == p.org_id,
            ProviderProfile.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return row


@router.patch("/{provider_id}", response_model=ProviderOut)
async def update_provider(
    provider_id: uuid.UUID,
    body: ProviderUpdate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> ProviderProfile:
    row = (await db.execute(
        select(ProviderProfile).where(
            ProviderProfile.id == provider_id,
            ProviderProfile.org_id == p.org_id,
            ProviderProfile.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    return row


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(
        select(ProviderProfile).where(
            ProviderProfile.id == provider_id,
            ProviderProfile.org_id == p.org_id,
            ProviderProfile.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    row.deleted_at = datetime.utcnow()
