"""ReminderRule CRUD.

Offsets_min are minutes before start_at (e.g., [1440, 120] = 24h and 2h ahead).
The reminder_sweep worker walks active rules every 5 min.
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
from app.models.notification import NOTIFICATION_CHANNELS, ReminderRule
from app.schemas.notification import ReminderRuleCreate, ReminderRuleOut, ReminderRuleUpdate


router = APIRouter(prefix="/reminders", tags=["reminders"])


def _validate_rule(offsets: list[int] | None, channels: list[str] | None) -> None:
    if offsets is not None:
        for m in offsets:
            if m <= 0:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "offsets_min must be positive")
    if channels is not None:
        for ch in channels:
            if ch not in NOTIFICATION_CHANNELS:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"channel {ch} invalid")


@router.get("/rules", response_model=list[ReminderRuleOut])
async def list_rules(
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> list[ReminderRule]:
    rows = (await db.execute(
        select(ReminderRule).where(
            ReminderRule.org_id == p.org_id, ReminderRule.deleted_at.is_(None),
        ).order_by(ReminderRule.name)
    )).scalars().all()
    return list(rows)


@router.post("/rules", response_model=ReminderRuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: ReminderRuleCreate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> ReminderRule:
    _validate_rule(body.offsets_min, body.channels)
    row = ReminderRule(org_id=p.org_id, **body.model_dump())
    db.add(row)
    await db.flush()
    return row


@router.patch("/rules/{rule_id}", response_model=ReminderRuleOut)
async def update_rule(
    rule_id: uuid.UUID,
    body: ReminderRuleUpdate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> ReminderRule:
    row = (await db.execute(
        select(ReminderRule).where(
            ReminderRule.id == rule_id,
            ReminderRule.org_id == p.org_id,
            ReminderRule.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    data = body.model_dump(exclude_unset=True)
    _validate_rule(data.get("offsets_min"), data.get("channels"))
    for k, v in data.items():
        setattr(row, k, v)
    return row


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_rule(
    rule_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(
        select(ReminderRule).where(
            ReminderRule.id == rule_id,
            ReminderRule.org_id == p.org_id,
            ReminderRule.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    row.deleted_at = datetime.utcnow()
