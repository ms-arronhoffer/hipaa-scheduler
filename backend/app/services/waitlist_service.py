"""Waitlist auto-fill on cancellation.

Trigger: an Appointment transitions to `canceled` OR a new slot opens for
another reason. We select up to N candidate WaitlistEntry rows whose window
overlaps the freed slot and (optionally) match the provider preference; issue
each one a short-lived magic booking link; row-lock so a concurrent trigger
doesn't double-notify the same entry.

First patient to click + confirm wins — the router does an atomic UPDATE
against `status='notified'` → `'booked'`; late clickers get a 409.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.waitlist import WaitlistEntry


NOTIFY_TOP_N = 3
NOTIFY_TTL = timedelta(hours=6)


async def candidates_for_slot(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    appointment_type_id: uuid.UUID,
    provider_id: uuid.UUID | None,
    slot_start: datetime,
    slot_end: datetime,
    limit: int = NOTIFY_TOP_N,
) -> list[WaitlistEntry]:
    q = select(WaitlistEntry).where(
        WaitlistEntry.org_id == org_id,
        WaitlistEntry.appointment_type_id == appointment_type_id,
        WaitlistEntry.status == "open",
        WaitlistEntry.deleted_at.is_(None),
        WaitlistEntry.earliest_at <= slot_end,
        WaitlistEntry.latest_at >= slot_start,
    )
    if provider_id is not None:
        q = q.where(or_(WaitlistEntry.provider_pref_id.is_(None), WaitlistEntry.provider_pref_id == provider_id))
    q = q.order_by(WaitlistEntry.created_at.asc()).limit(limit).with_for_update(skip_locked=True)
    return list((await db.execute(q)).scalars().all())


async def mark_notified(db: AsyncSession, entry: WaitlistEntry, now: datetime | None = None) -> WaitlistEntry:
    entry.status = "notified"
    entry.notified_at = now or datetime.utcnow()
    await db.flush()
    return entry


async def try_claim(db: AsyncSession, entry_id: uuid.UUID, appointment_id: uuid.UUID) -> bool:
    """Atomic notified→booked transition. Returns True on success (this claimant wins)."""
    result = await db.execute(
        update(WaitlistEntry)
        .where(WaitlistEntry.id == entry_id, WaitlistEntry.status == "notified")
        .values(status="booked", booked_appointment_id=appointment_id)
    )
    return (result.rowcount or 0) == 1


async def expire_stale(db: AsyncSession, now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    result = await db.execute(
        update(WaitlistEntry)
        .where(
            WaitlistEntry.status == "notified",
            WaitlistEntry.notified_at.is_not(None),
            WaitlistEntry.notified_at < now - NOTIFY_TTL,
        )
        .values(status="open", notified_at=None)
    )
    return result.rowcount or 0
