"""Slot generation for a provider + appointment type in a bounded window.

Available slots = (ProviderAvailability weekly template)
                  ∩ (Office.hours per weekday)
                  − (TimeOff blocks)
                  − (existing active Appointments extended by buffers)
                  − (Office.holidays)

Slot start times step by `type.duration_min + buffer_after_min` (we treat the
buffer_after as part of the block cost, and buffer_before as pre-block padding
applied when checking overlap). Timezone-aware throughout: the office timezone
governs "which weekday" and "which day" a slot belongs to.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.models.availability import ProviderAvailability, TimeOff
from app.models.office import Office


ACTIVE_STATUSES = ("scheduled", "confirmed", "checked_in", "completed")


@dataclass(frozen=True)
class Slot:
    start_at: datetime
    end_at: datetime


def _combine(d: date, t: time, tz: ZoneInfo) -> datetime:
    return datetime.combine(d, t).replace(tzinfo=tz)


def _office_window(office: Office, day: date, tz: ZoneInfo) -> tuple[datetime, datetime] | None:
    """Return (open, close) datetimes for `day` in office tz, or None if closed."""
    if any(str(h) == day.isoformat() for h in (office.holidays or [])):
        return None
    hours = (office.hours or {}).get(str(day.weekday()))
    if not hours or not hours.get("open") or not hours.get("close"):
        return None
    open_t = time.fromisoformat(hours["open"])
    close_t = time.fromisoformat(hours["close"])
    return _combine(day, open_t, tz), _combine(day, close_t, tz)


def _availability_windows(
    availabilities: list[ProviderAvailability], day: date, tz: ZoneInfo
) -> list[tuple[datetime, datetime]]:
    windows: list[tuple[datetime, datetime]] = []
    for a in availabilities:
        if a.weekday != day.weekday():
            continue
        if a.effective_from and day < a.effective_from:
            continue
        if a.effective_until and day > a.effective_until:
            continue
        windows.append((_combine(day, a.start_time, tz), _combine(day, a.end_time, tz)))
    return windows


def _subtract(base: list[tuple[datetime, datetime]], blocks: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """Interval subtraction: base intervals minus block intervals."""
    result = base[:]
    for bs, be in blocks:
        new_result: list[tuple[datetime, datetime]] = []
        for ws, we in result:
            if be <= ws or bs >= we:
                new_result.append((ws, we))
                continue
            if bs > ws:
                new_result.append((ws, bs))
            if be < we:
                new_result.append((be, we))
        result = new_result
    return result


async def generate_slots(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    office: Office,
    provider_id: uuid.UUID,
    appointment_type: AppointmentType,
    range_start: datetime,
    range_end: datetime,
) -> list[Slot]:
    """Return bookable slot start/end pairs (UTC) within [range_start, range_end)."""
    tz = ZoneInfo(office.timezone or "UTC")
    if range_end <= range_start:
        return []

    duration = timedelta(minutes=appointment_type.duration_min)
    step = timedelta(minutes=appointment_type.duration_min + appointment_type.buffer_after_min)
    buf_before = timedelta(minutes=appointment_type.buffer_before_min)
    buf_after = timedelta(minutes=appointment_type.buffer_after_min)

    avail = (await db.execute(
        select(ProviderAvailability).where(
            ProviderAvailability.org_id == org_id,
            ProviderAvailability.provider_id == provider_id,
            ProviderAvailability.deleted_at.is_(None),
        )
    )).scalars().all()

    time_off = (await db.execute(
        select(TimeOff).where(
            TimeOff.org_id == org_id,
            TimeOff.provider_id == provider_id,
            TimeOff.deleted_at.is_(None),
            TimeOff.end_at > range_start,
            TimeOff.start_at < range_end,
        )
    )).scalars().all()

    appts = (await db.execute(
        select(Appointment).where(
            Appointment.org_id == org_id,
            Appointment.provider_id == provider_id,
            Appointment.deleted_at.is_(None),
            Appointment.status.in_(ACTIVE_STATUSES),
            Appointment.end_at > range_start,
            Appointment.start_at < range_end,
        )
    )).scalars().all()

    blocks: list[tuple[datetime, datetime]] = [(t.start_at, t.end_at) for t in time_off]
    for a in appts:
        blocks.append((a.start_at - buf_before, a.end_at + buf_after))

    slots: list[Slot] = []
    day = range_start.astimezone(tz).date()
    last_day = (range_end.astimezone(tz) - timedelta(seconds=1)).date()
    while day <= last_day:
        office_win = _office_window(office, day, tz)
        if office_win is None:
            day += timedelta(days=1)
            continue
        avail_wins = _availability_windows(avail, day, tz)
        if not avail_wins:
            day += timedelta(days=1)
            continue

        combined: list[tuple[datetime, datetime]] = []
        for aw_s, aw_e in avail_wins:
            s = max(aw_s, office_win[0])
            e = min(aw_e, office_win[1])
            if e > s:
                combined.append((s, e))

        free = _subtract(combined, blocks)

        for ws, we in free:
            cursor = ws
            while cursor + duration <= we:
                slot_start = cursor
                slot_end = cursor + duration
                if slot_end > range_start and slot_start < range_end:
                    slots.append(Slot(start_at=slot_start, end_at=slot_end))
                cursor += step
        day += timedelta(days=1)

    return slots
