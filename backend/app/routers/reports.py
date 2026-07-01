"""Aggregate reports (staff dashboard).

All queries scoped to org. No PHI in responses — just counts and buckets.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import require_role
from app.models.appointment import Appointment
from app.models.notification import NotificationLog
from app.models.patient import Patient
from app.models.waitlist import WaitlistEntry
from app.schemas.common import ORMModel


router = APIRouter(prefix="/reports", tags=["reports"])


class StatusCount(ORMModel):
    key: str
    count: int


class AppointmentSummary(ORMModel):
    range_start: date
    range_end: date
    total: int
    by_status: list[StatusCount]
    by_source: list[StatusCount]
    by_provider: list[StatusCount]


class NoShowReport(ORMModel):
    range_start: date
    range_end: date
    total_scheduled: int
    total_no_show: int
    no_show_rate: float
    by_provider: list[StatusCount]


class NotificationReport(ORMModel):
    range_start: date
    range_end: date
    by_channel: list[StatusCount]
    by_status: list[StatusCount]


class WaitlistReport(ORMModel):
    total_open: int
    by_status: list[StatusCount]


class DashboardSummary(ORMModel):
    active_patients: int
    upcoming_appointments_7d: int
    canceled_last_7d: int
    open_waitlist: int


def _range_defaults(range_start: date | None, range_end: date | None) -> tuple[date, date]:
    end = range_end or date.today()
    start = range_start or (end - timedelta(days=30))
    return start, end


def _bounds(range_start: date, range_end: date) -> tuple[datetime, datetime]:
    return datetime.combine(range_start, datetime.min.time()), datetime.combine(
        range_end + timedelta(days=1), datetime.min.time()
    )


@router.get("/dashboard", response_model=DashboardSummary)
async def dashboard(
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummary:
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    week_ahead = now + timedelta(days=7)

    active_patients = (await db.execute(
        select(func.count()).select_from(Patient).where(
            Patient.org_id == p.org_id, Patient.deleted_at.is_(None),
        )
    )).scalar_one()
    upcoming = (await db.execute(
        select(func.count()).select_from(Appointment).where(
            Appointment.org_id == p.org_id,
            Appointment.deleted_at.is_(None),
            Appointment.start_at >= now,
            Appointment.start_at < week_ahead,
            Appointment.status.in_(("scheduled", "confirmed", "checked_in")),
        )
    )).scalar_one()
    canceled = (await db.execute(
        select(func.count()).select_from(Appointment).where(
            Appointment.org_id == p.org_id,
            Appointment.status == "canceled",
            Appointment.updated_at >= week_ago,
        )
    )).scalar_one()
    open_wl = (await db.execute(
        select(func.count()).select_from(WaitlistEntry).where(
            WaitlistEntry.org_id == p.org_id,
            WaitlistEntry.status == "open",
            WaitlistEntry.deleted_at.is_(None),
        )
    )).scalar_one()
    return DashboardSummary(
        active_patients=active_patients,
        upcoming_appointments_7d=upcoming,
        canceled_last_7d=canceled,
        open_waitlist=open_wl,
    )


@router.get("/appointments", response_model=AppointmentSummary)
async def appointment_summary(
    range_start: date | None = Query(default=None),
    range_end: date | None = Query(default=None),
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> AppointmentSummary:
    start, end = _range_defaults(range_start, range_end)
    lo, hi = _bounds(start, end)
    base = select(Appointment).where(
        Appointment.org_id == p.org_id,
        Appointment.deleted_at.is_(None),
        Appointment.start_at >= lo,
        Appointment.start_at < hi,
    ).subquery()

    total = (await db.execute(select(func.count()).select_from(base))).scalar_one()

    by_status_rows = (await db.execute(
        select(base.c.status, func.count()).group_by(base.c.status)
    )).all()
    by_source_rows = (await db.execute(
        select(base.c.source, func.count()).group_by(base.c.source)
    )).all()
    by_provider_rows = (await db.execute(
        select(base.c.provider_id, func.count()).group_by(base.c.provider_id)
    )).all()

    return AppointmentSummary(
        range_start=start, range_end=end, total=total,
        by_status=[StatusCount(key=str(k), count=c) for k, c in by_status_rows],
        by_source=[StatusCount(key=str(k), count=c) for k, c in by_source_rows],
        by_provider=[StatusCount(key=str(k), count=c) for k, c in by_provider_rows],
    )


@router.get("/no-show", response_model=NoShowReport)
async def no_show_report(
    range_start: date | None = Query(default=None),
    range_end: date | None = Query(default=None),
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> NoShowReport:
    start, end = _range_defaults(range_start, range_end)
    lo, hi = _bounds(start, end)
    scheduled = (await db.execute(
        select(func.count()).select_from(Appointment).where(
            Appointment.org_id == p.org_id,
            Appointment.deleted_at.is_(None),
            Appointment.start_at >= lo,
            Appointment.start_at < hi,
            Appointment.status.in_(("completed", "no_show")),
        )
    )).scalar_one()
    no_shows = (await db.execute(
        select(func.count()).select_from(Appointment).where(
            Appointment.org_id == p.org_id,
            Appointment.deleted_at.is_(None),
            Appointment.start_at >= lo,
            Appointment.start_at < hi,
            Appointment.status == "no_show",
        )
    )).scalar_one()
    by_prov_rows = (await db.execute(
        select(Appointment.provider_id, func.count()).where(
            Appointment.org_id == p.org_id,
            Appointment.deleted_at.is_(None),
            Appointment.start_at >= lo,
            Appointment.start_at < hi,
            Appointment.status == "no_show",
        ).group_by(Appointment.provider_id)
    )).all()

    rate = (no_shows / scheduled) if scheduled else 0.0
    return NoShowReport(
        range_start=start, range_end=end,
        total_scheduled=scheduled, total_no_show=no_shows,
        no_show_rate=round(rate, 4),
        by_provider=[StatusCount(key=str(k), count=c) for k, c in by_prov_rows],
    )


@router.get("/notifications", response_model=NotificationReport)
async def notification_report(
    range_start: date | None = Query(default=None),
    range_end: date | None = Query(default=None),
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> NotificationReport:
    start, end = _range_defaults(range_start, range_end)
    lo, hi = _bounds(start, end)
    by_channel = (await db.execute(
        select(NotificationLog.channel, func.count()).where(
            NotificationLog.org_id == p.org_id,
            NotificationLog.created_at >= lo,
            NotificationLog.created_at < hi,
        ).group_by(NotificationLog.channel)
    )).all()
    by_status = (await db.execute(
        select(NotificationLog.status, func.count()).where(
            NotificationLog.org_id == p.org_id,
            NotificationLog.created_at >= lo,
            NotificationLog.created_at < hi,
        ).group_by(NotificationLog.status)
    )).all()
    return NotificationReport(
        range_start=start, range_end=end,
        by_channel=[StatusCount(key=k, count=c) for k, c in by_channel],
        by_status=[StatusCount(key=k, count=c) for k, c in by_status],
    )


@router.get("/waitlist", response_model=WaitlistReport)
async def waitlist_report(
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> WaitlistReport:
    open_count = (await db.execute(
        select(func.count()).select_from(WaitlistEntry).where(
            WaitlistEntry.org_id == p.org_id,
            WaitlistEntry.status == "open",
            WaitlistEntry.deleted_at.is_(None),
        )
    )).scalar_one()
    by_status = (await db.execute(
        select(WaitlistEntry.status, func.count()).where(
            WaitlistEntry.org_id == p.org_id,
            WaitlistEntry.deleted_at.is_(None),
        ).group_by(WaitlistEntry.status)
    )).all()
    return WaitlistReport(
        total_open=open_count,
        by_status=[StatusCount(key=k, count=c) for k, c in by_status],
    )
