"""CalendarConnection management (staff view of Google/O365/CalDAV links).

OAuth authorization redirects and token exchange are handled by dedicated auth
endpoints; this router lists, disables, and deletes connections. Encrypted
tokens are never returned. The worker `calendar_pull` refreshes access tokens
and reconciles events.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import require_role
from app.models.activity_log import ActivityLog
from app.models.calendar_connection import CALENDAR_PROVIDERS, CalendarConnection
from app.schemas.integrations import CalendarConnectionOut, CalendarConnectionUpdate


router = APIRouter(prefix="/calendar-connections", tags=["calendar_sync"])


@router.get("", response_model=list[CalendarConnectionOut])
async def list_connections(
    provider: str | None = None,
    user_id: uuid.UUID | None = None,
    p: Principal = Depends(require_role("practice_admin", "provider")),
    db: AsyncSession = Depends(get_db),
) -> list[CalendarConnection]:
    stmt = select(CalendarConnection).where(
        CalendarConnection.org_id == p.org_id,
        CalendarConnection.deleted_at.is_(None),
    )
    if provider is not None:
        if provider not in CALENDAR_PROVIDERS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown provider {provider}")
        stmt = stmt.where(CalendarConnection.provider == provider)
    # Providers can only list their own connections; admins see all.
    if "practice_admin" not in p.roles:
        stmt = stmt.where(CalendarConnection.user_id == p.subject_id)
    elif user_id is not None:
        stmt = stmt.where(CalendarConnection.user_id == user_id)
    rows = (await db.execute(stmt.order_by(CalendarConnection.created_at.desc()))).scalars().all()
    return list(rows)


@router.get("/{conn_id}", response_model=CalendarConnectionOut)
async def get_connection(
    conn_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin", "provider")),
    db: AsyncSession = Depends(get_db),
) -> CalendarConnection:
    row = (await db.execute(
        select(CalendarConnection).where(
            CalendarConnection.id == conn_id,
            CalendarConnection.org_id == p.org_id,
            CalendarConnection.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if "practice_admin" not in p.roles and row.user_id != p.subject_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    return row


@router.patch("/{conn_id}", response_model=CalendarConnectionOut)
async def update_connection(
    conn_id: uuid.UUID,
    body: CalendarConnectionUpdate,
    p: Principal = Depends(require_role("practice_admin", "provider")),
    db: AsyncSession = Depends(get_db),
) -> CalendarConnection:
    row = (await db.execute(
        select(CalendarConnection).where(
            CalendarConnection.id == conn_id,
            CalendarConnection.org_id == p.org_id,
            CalendarConnection.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if "practice_admin" not in p.roles and row.user_id != p.subject_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="calendar_connection", entity_id=row.id, action="updated",
        changes=data,
    ))
    return row


@router.delete("/{conn_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    conn_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin", "provider")),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(
        select(CalendarConnection).where(
            CalendarConnection.id == conn_id,
            CalendarConnection.org_id == p.org_id,
            CalendarConnection.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if "practice_admin" not in p.roles and row.user_id != p.subject_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    row.active = False
    row.deleted_at = datetime.utcnow()
    # Clear ciphertext at soft-delete time so refresh cannot silently continue.
    row.access_token_ct = ""
    row.refresh_token_ct = None
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="calendar_connection", entity_id=row.id, action="disconnected",
        changes={"provider": row.provider, "account_email": row.account_email},
    ))
