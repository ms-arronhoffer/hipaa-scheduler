"""Appointment CRUD + availability."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import ensure_patient_in_org, phi_log, require_role
from app.models.activity_log import ActivityLog
from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.models.office import Office
from app.schemas.appointment import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentListOut,
    AppointmentOut,
    AppointmentReschedule,
    SlotOut,
)
from app.services import scheduling_engine, slot_generator, waitlist_service, webhook_service
from app.services import ical_service


router = APIRouter(prefix="/appointments", tags=["appointments"])


async def _load_type_and_office(
    db: AsyncSession, org_id: uuid.UUID, type_id: uuid.UUID, office_id: uuid.UUID
) -> tuple[AppointmentType, Office]:
    apptype = (await db.execute(select(AppointmentType).where(
        AppointmentType.id == type_id, AppointmentType.org_id == org_id
    ))).scalar_one_or_none()
    office = (await db.execute(select(Office).where(
        Office.id == office_id, Office.org_id == org_id
    ))).scalar_one_or_none()
    if apptype is None or office is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "type or office not found")
    return apptype, office


@router.get("/slots", response_model=list[SlotOut])
async def list_slots(
    office_id: uuid.UUID,
    provider_id: uuid.UUID,
    appointment_type_id: uuid.UUID,
    range_start: datetime,
    range_end: datetime,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider")),
    db: AsyncSession = Depends(get_db),
) -> list[SlotOut]:
    apptype, office = await _load_type_and_office(db, p.org_id, appointment_type_id, office_id)
    slots = await slot_generator.generate_slots(
        db, org_id=p.org_id, office=office, provider_id=provider_id,
        appointment_type=apptype, range_start=range_start, range_end=range_end,
    )
    return [SlotOut(start_at=s.start_at, end_at=s.end_at) for s in slots]


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    body: AppointmentCreate,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider")),
    db: AsyncSession = Depends(get_db),
) -> Appointment:
    apptype, _office = await _load_type_and_office(db, p.org_id, body.appointment_type_id, body.office_id)
    await ensure_patient_in_org(db, body.patient_id, p.org_id)
    end_at = body.start_at + timedelta(minutes=apptype.duration_min)
    try:
        appt = await scheduling_engine.book_appointment(db, scheduling_engine.BookRequest(
            org_id=p.org_id,
            office_id=body.office_id,
            provider_id=body.provider_id,
            patient_id=body.patient_id,
            appointment_type=apptype,
            start_at=body.start_at,
            end_at=end_at,
            resource_id=body.resource_id,
            source="staff",
            notes=body.notes,
        ))
    except scheduling_engine.SlotConflict as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    except scheduling_engine.InvalidBooking as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="appointment", entity_id=appt.id, action="created",
        changes={"start_at": body.start_at.isoformat()}, phi_accessed=True,
    ))
    await webhook_service.dispatch_event(
        db, org_id=p.org_id, event="appointment.created",
        data={"appointment_id": str(appt.id), "start_at": appt.start_at.isoformat()},
    )
    return appt


@router.get("", response_model=AppointmentListOut)
async def list_appointments(
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    provider_id: uuid.UUID | None = None,
    office_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = Query(default=500, le=1000),
    offset: int = 0,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> AppointmentListOut:
    """List appointments for the org, filtered by date range/provider/office/status.

    Backs the calendar, appointments, dashboard, and patient-detail screens. The
    ``start_at`` window is half-open ``[from_ts, to_ts)`` so day/week grids don't
    double-count the boundary.
    """
    filters = [Appointment.org_id == p.org_id, Appointment.deleted_at.is_(None)]
    if from_ts is not None:
        filters.append(Appointment.start_at >= from_ts)
    if to_ts is not None:
        filters.append(Appointment.start_at < to_ts)
    if provider_id is not None:
        filters.append(Appointment.provider_id == provider_id)
    if office_id is not None:
        filters.append(Appointment.office_id == office_id)
    if status is not None:
        filters.append(Appointment.status == status)

    total = (await db.execute(
        select(func.count()).select_from(Appointment).where(*filters)
    )).scalar_one()
    rows = (await db.execute(
        select(Appointment).where(*filters)
        .order_by(Appointment.start_at.asc())
        .limit(limit)
        .offset(offset)
    )).scalars().all()
    return AppointmentListOut(
        items=[AppointmentOut.model_validate(r) for r in rows],
        total=total,
    )


@router.get("/{appointment_id}", response_model=AppointmentOut)
async def get_appointment(
    appointment_id: uuid.UUID,
    p: Principal = Depends(phi_log("appointment", "viewed")),
    db: AsyncSession = Depends(get_db),
) -> Appointment:
    row = (await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id, Appointment.org_id == p.org_id, Appointment.deleted_at.is_(None)
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return row


@router.patch("/{appointment_id}/reschedule", response_model=AppointmentOut)
async def reschedule(
    appointment_id: uuid.UUID,
    body: AppointmentReschedule,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider")),
    db: AsyncSession = Depends(get_db),
) -> Appointment:
    row = (await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id, Appointment.org_id == p.org_id, Appointment.deleted_at.is_(None)
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    new_end = body.start_at + timedelta(minutes=row.duration_min)
    try:
        await scheduling_engine.reschedule_appointment(db, row, new_start=body.start_at, new_end=new_end)
    except scheduling_engine.SlotConflict as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="appointment", entity_id=row.id, action="rescheduled",
        changes={"new_start_at": body.start_at.isoformat()}, phi_accessed=True,
    ))
    await webhook_service.dispatch_event(
        db, org_id=p.org_id, event="appointment.updated",
        data={"appointment_id": str(row.id), "start_at": row.start_at.isoformat()},
    )
    return row


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
async def cancel(
    appointment_id: uuid.UUID,
    body: AppointmentCancel,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider")),
    db: AsyncSession = Depends(get_db),
) -> Appointment:
    row = (await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id, Appointment.org_id == p.org_id, Appointment.deleted_at.is_(None)
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    await scheduling_engine.cancel_appointment(db, row, actor_type="user", reason=body.reason)
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="appointment", entity_id=row.id, action="canceled",
        changes={"reason": body.reason or ""}, phi_accessed=True,
    ))
    await webhook_service.dispatch_event(
        db, org_id=p.org_id, event="appointment.canceled",
        data={"appointment_id": str(row.id)},
    )
    # Waitlist candidates are handled asynchronously by the worker on this event.
    return row


@router.get("/calendar.ics")
async def export_ics(
    provider_id: uuid.UUID | None = None,
    range_start: datetime | None = None,
    range_end: datetime | None = None,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export the org's appointments as an iCalendar (.ics) feed.

    The feed is intentionally PHI-free — event summaries carry the appointment
    type and status only (no patient identifiers) — so it is safe to subscribe
    to from external calendar clients (Google/Apple/Outlook). Defaults to the
    next 60 days when no range is given.
    """
    now = datetime.utcnow()
    start = range_start or now
    end = range_end or (now + timedelta(days=60))

    stmt = select(Appointment).where(
        Appointment.org_id == p.org_id,
        Appointment.deleted_at.is_(None),
        Appointment.start_at >= start,
        Appointment.start_at <= end,
    )
    if provider_id is not None:
        stmt = stmt.where(Appointment.provider_id == provider_id)
    elif "practice_admin" not in p.roles and "front_desk" not in p.roles:
        # Providers without admin/front-desk scope only see their own calendar.
        stmt = stmt.where(Appointment.provider_id == p.subject_id)
    rows = (await db.execute(stmt.order_by(Appointment.start_at))).scalars().all()

    # Batch-load appointment type names (non-PHI) for readable summaries.
    type_ids = {r.appointment_type_id for r in rows}
    type_names: dict[uuid.UUID, str] = {}
    if type_ids:
        trows = (await db.execute(
            select(AppointmentType.id, AppointmentType.name).where(
                AppointmentType.org_id == p.org_id,
                AppointmentType.id.in_(type_ids),
            )
        )).all()
        type_names = {tid: name for tid, name in trows}

    events = [{
        "uid": f"{r.id}@hipaa-scheduler",
        "start": r.start_at,
        "end": r.end_at,
        "summary": type_names.get(r.appointment_type_id, "Appointment"),
        "status": r.status,
        "created": r.created_at,
        "updated": getattr(r, "updated_at", None),
    } for r in rows]

    ics = ical_service.build_calendar(events, cal_name="Appointments")
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="appointments.ics"'},
    )
