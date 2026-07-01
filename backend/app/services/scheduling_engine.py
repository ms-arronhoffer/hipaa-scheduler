"""Conflict-safe booking + cancel/reschedule.

The Postgres GiST exclusion constraint on `tstzrange(start_at, end_at)` per
provider (and resource) is the source of truth for overlap prevention. Booking
opens a SERIALIZABLE transaction, INSERTs, and translates `ExclusionViolation`
(SQLSTATE 23P01) into `SlotConflict` which routers surface as HTTP 409.

Callers are expected to have already vetted that the slot appears in
`generate_slots(...)` — this layer is the last line of defense against races.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType


class SlotConflict(Exception):
    """Raised when the exclusion constraint rejects an overlapping insert."""


class InvalidBooking(Exception):
    """Raised when inputs are self-inconsistent (bad times, wrong duration)."""


@dataclass
class BookRequest:
    org_id: uuid.UUID
    office_id: uuid.UUID
    provider_id: uuid.UUID
    patient_id: uuid.UUID
    appointment_type: AppointmentType
    start_at: datetime
    end_at: datetime
    resource_id: uuid.UUID | None = None
    source: str = "staff"
    series_id: uuid.UUID | None = None
    notes: str | None = None


def _is_exclusion_violation(err: IntegrityError) -> bool:
    orig = getattr(err, "orig", None)
    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    return sqlstate == "23P01"


async def book_appointment(db: AsyncSession, req: BookRequest) -> Appointment:
    if req.end_at <= req.start_at:
        raise InvalidBooking("end_at must be after start_at")
    expected_min = req.appointment_type.duration_min
    actual_min = int((req.end_at - req.start_at).total_seconds() // 60)
    if actual_min != expected_min:
        raise InvalidBooking(f"duration {actual_min} does not match type {expected_min}")

    await db.execute(text("SET LOCAL TRANSACTION ISOLATION LEVEL SERIALIZABLE"))

    appt = Appointment(
        org_id=req.org_id,
        office_id=req.office_id,
        provider_id=req.provider_id,
        patient_id=req.patient_id,
        appointment_type_id=req.appointment_type.id,
        resource_id=req.resource_id,
        series_id=req.series_id,
        start_at=req.start_at,
        end_at=req.end_at,
        duration_min=expected_min,
        status="scheduled",
        source=req.source,
        notes=req.notes,
    )
    db.add(appt)
    try:
        await db.flush()
    except IntegrityError as e:
        if _is_exclusion_violation(e):
            raise SlotConflict("time slot no longer available") from e
        raise
    return appt


async def cancel_appointment(
    db: AsyncSession,
    appt: Appointment,
    *,
    actor_type: str,
    reason: str | None = None,
    when: datetime | None = None,
) -> Appointment:
    appt.status = "canceled"
    appt.canceled_at = when or datetime.utcnow()
    appt.canceled_by_actor_type = actor_type
    appt.cancel_reason = reason
    await db.flush()
    return appt


async def mark_no_show(db: AsyncSession, appt: Appointment, when: datetime | None = None) -> Appointment:
    appt.status = "no_show"
    appt.no_show_marked_at = when or datetime.utcnow()
    await db.flush()
    return appt


async def reschedule_appointment(
    db: AsyncSession, appt: Appointment, *, new_start: datetime, new_end: datetime
) -> Appointment:
    if new_end <= new_start:
        raise InvalidBooking("end_at must be after start_at")
    await db.execute(text("SET LOCAL TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
    appt.start_at = new_start
    appt.end_at = new_end
    appt.duration_min = int((new_end - new_start).total_seconds() // 60)
    try:
        await db.flush()
    except IntegrityError as e:
        if _is_exclusion_violation(e):
            raise SlotConflict("new slot not available") from e
        raise
    return appt
