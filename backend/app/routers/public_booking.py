"""Public booking API (patient portal + guest).

Three surfaces:
- GET /pub/orgs/{slug} — resolve slug to org (public, safe fields only)
- POST /pub/slots — list available slots for org/office/provider/type
- POST /pub/book/patient — authenticated patient (magic or full) books
- POST /pub/book/guest — unauthenticated guest books; also creates a
  PatientAccount in `guest` mode + returns a 24h `claim_token` to upgrade

Guest bookings still hit the same scheduling engine and write ActivityLog
with `phi_accessed=True`. Rate-limiting happens at the nginx + slowapi layer.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password  # noqa: F401  (used indirectly by claim upgrade)
from app.auth.principal import Principal, current_principal
from app.database import get_db
from app.models.activity_log import ActivityLog
from app.models.appointment_type import AppointmentType
from app.models.office import Office
from app.models.organization import Organization
from app.models.patient import Patient, PatientAccount
from app.schemas.public import (
    BookingResponse,
    GuestBookingRequest,
    PatientBookingRequest,
    PublicSlotQuery,
    PublicSlotsResponse,
)
from app.schemas.appointment import AppointmentOut, SlotOut
from app.services import (
    confirm_token_service,
    scheduling_engine,
    slot_generator,
    webhook_service,
)


router = APIRouter(prefix="/pub", tags=["public"])


async def _resolve_org(db: AsyncSession, slug: str) -> Organization:
    org = (await db.execute(
        select(Organization).where(
            Organization.slug == slug,
            Organization.deleted_at.is_(None),
            Organization.status == "active",
        )
    )).scalar_one_or_none()
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "organization not found")
    return org


async def _load_type_office(
    db: AsyncSession, org_id: uuid.UUID, type_id: uuid.UUID, office_id: uuid.UUID
) -> tuple[AppointmentType, Office]:
    apptype = (await db.execute(select(AppointmentType).where(
        AppointmentType.id == type_id,
        AppointmentType.org_id == org_id,
        AppointmentType.deleted_at.is_(None),
        AppointmentType.active.is_(True),
    ))).scalar_one_or_none()
    office = (await db.execute(select(Office).where(
        Office.id == office_id,
        Office.org_id == org_id,
        Office.deleted_at.is_(None),
    ))).scalar_one_or_none()
    if apptype is None or office is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "type or office not found")
    return apptype, office


@router.get("/orgs/{slug}")
async def public_org(slug: str, db: AsyncSession = Depends(get_db)) -> dict:
    org = await _resolve_org(db, slug)
    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "settings": {k: v for k, v in (org.settings or {}).items() if k.startswith("public_")},
    }


@router.post("/slots", response_model=PublicSlotsResponse)
async def public_slots(body: PublicSlotQuery, db: AsyncSession = Depends(get_db)) -> PublicSlotsResponse:
    org = await _resolve_org(db, body.org_slug)
    apptype, office = await _load_type_office(db, org.id, body.appointment_type_id, body.office_id)
    if body.range_end <= body.range_start:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "range_end must be after range_start")
    if body.range_end - body.range_start > timedelta(days=60):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "range too wide (60d max)")
    slots = await slot_generator.generate_slots(
        db, org_id=org.id, office=office, provider_id=body.provider_id,
        appointment_type=apptype, range_start=body.range_start, range_end=body.range_end,
    )
    return PublicSlotsResponse(slots=[SlotOut(start_at=s.start_at, end_at=s.end_at) for s in slots])


@router.post("/book/patient", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def book_as_patient(
    body: PatientBookingRequest,
    p: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_db),
) -> BookingResponse:
    if p.kind != "patient":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "patient session required")
    account = (await db.execute(
        select(PatientAccount).where(PatientAccount.id == p.subject_id)
    )).scalar_one_or_none()
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found")
    patient = (await db.execute(
        select(Patient).where(
            Patient.id == account.patient_id,
            Patient.org_id == p.org_id,
            Patient.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "patient not found")
    apptype, _office = await _load_type_office(db, p.org_id, body.appointment_type_id, body.office_id)
    end_at = body.start_at + timedelta(minutes=apptype.duration_min)
    try:
        appt = await scheduling_engine.book_appointment(db, scheduling_engine.BookRequest(
            org_id=p.org_id,
            office_id=body.office_id,
            provider_id=body.provider_id,
            patient_id=patient.id,
            appointment_type=apptype,
            start_at=body.start_at,
            end_at=end_at,
            source="magic" if account.auth_mode != "full" else "portal",
            notes=body.notes,
        ))
    except scheduling_engine.SlotConflict as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    except scheduling_engine.InvalidBooking as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="patient", actor_id=account.id, actor_email=account.email,
        entity_type="appointment", entity_id=appt.id, action="created",
        changes={"start_at": body.start_at.isoformat(), "source": appt.source},
        phi_accessed=True,
    ))
    await webhook_service.dispatch_event(
        db, org_id=p.org_id, event="appointment.created",
        data={"appointment_id": str(appt.id), "start_at": appt.start_at.isoformat()},
    )
    return BookingResponse(appointment=AppointmentOut.model_validate(appt), claim_token=None)


async def _resolve_or_create_guest_patient(
    db: AsyncSession, *, org_id: uuid.UUID, body: GuestBookingRequest
) -> tuple[Patient, PatientAccount, bool]:
    """Match on (org, email, dob, last_name); create if not found."""
    details = body.patient
    email = details.email.lower()
    patient = (await db.execute(
        select(Patient).where(
            Patient.org_id == org_id,
            Patient.email == email,
            Patient.dob == details.dob,
            Patient.last_name == details.last_name,
            Patient.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    created = False
    if patient is None:
        mrn = f"G-{uuid.uuid4().hex[:12].upper()}"
        patient = Patient(
            org_id=org_id,
            mrn=mrn,
            first_name=details.first_name,
            last_name=details.last_name,
            dob=details.dob,
            email=email,
            phone=details.phone,
        )
        db.add(patient)
        await db.flush()
        created = True

    account = (await db.execute(
        select(PatientAccount).where(PatientAccount.patient_id == patient.id)
    )).scalar_one_or_none()
    if account is None:
        account = PatientAccount(
            patient_id=patient.id,
            email=email,
            auth_mode="guest",
        )
        db.add(account)
        await db.flush()
    return patient, account, created


@router.post("/book/guest", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def book_as_guest(body: GuestBookingRequest, db: AsyncSession = Depends(get_db)) -> BookingResponse:
    org = await _resolve_org(db, body.org_slug)
    apptype, _office = await _load_type_office(db, org.id, body.appointment_type_id, body.office_id)

    if body.patient.dob >= date.today():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid date of birth")

    patient, account, _created = await _resolve_or_create_guest_patient(db, org_id=org.id, body=body)

    end_at = body.start_at + timedelta(minutes=apptype.duration_min)
    try:
        appt = await scheduling_engine.book_appointment(db, scheduling_engine.BookRequest(
            org_id=org.id,
            office_id=body.office_id,
            provider_id=body.provider_id,
            patient_id=patient.id,
            appointment_type=apptype,
            start_at=body.start_at,
            end_at=end_at,
            source="guest",
            notes=body.notes,
        ))
    except scheduling_engine.SlotConflict as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    except scheduling_engine.InvalidBooking as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    claim_plain, _tok = await confirm_token_service.issue(
        db, org_id=org.id, kind="claim_account",
        patient_id=patient.id, ttl=timedelta(hours=24),
    )

    db.add(ActivityLog(
        org_id=org.id, actor_type="patient", actor_id=account.id, actor_email=account.email,
        entity_type="appointment", entity_id=appt.id, action="created",
        changes={
            "source": "guest",
            "hipaa_version": body.accept_hipaa_version,
            "start_at": body.start_at.isoformat(),
        },
        phi_accessed=True,
    ))
    await webhook_service.dispatch_event(
        db, org_id=org.id, event="appointment.created",
        data={"appointment_id": str(appt.id), "start_at": appt.start_at.isoformat(), "source": "guest"},
    )
    return BookingResponse(
        appointment=AppointmentOut.model_validate(appt),
        claim_token=claim_plain,
    )


@router.get("/me/appointments", response_model=list[AppointmentOut])
async def patient_appointments(
    p: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[AppointmentOut]:
    if p.kind != "patient":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "patient session required")
    account = (await db.execute(
        select(PatientAccount).where(PatientAccount.id == p.subject_id)
    )).scalar_one_or_none()
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found")
    from app.models.appointment import Appointment
    rows = (await db.execute(
        select(Appointment).where(
            Appointment.patient_id == account.patient_id,
            Appointment.org_id == p.org_id,
            Appointment.deleted_at.is_(None),
        ).order_by(Appointment.start_at.desc())
    )).scalars().all()
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="patient", actor_id=account.id, actor_email=account.email,
        entity_type="appointment", entity_id=account.patient_id, action="listed",
        changes={"count": len(rows)}, phi_accessed=True,
    ))
    return [AppointmentOut.model_validate(r) for r in rows]


@router.post("/me/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
async def patient_cancel(
    appointment_id: uuid.UUID,
    p: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_db),
) -> AppointmentOut:
    if p.kind != "patient":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "patient session required")
    account = (await db.execute(
        select(PatientAccount).where(PatientAccount.id == p.subject_id)
    )).scalar_one_or_none()
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found")
    from app.models.appointment import Appointment
    row = (await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.org_id == p.org_id,
            Appointment.patient_id == account.patient_id,
            Appointment.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    apptype = (await db.execute(
        select(AppointmentType).where(AppointmentType.id == row.appointment_type_id)
    )).scalar_one_or_none()
    window_hours = apptype.cancellation_window_hours if apptype else 24
    if row.start_at - datetime.utcnow().replace(tzinfo=row.start_at.tzinfo) < timedelta(hours=window_hours):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "outside cancellation window")
    await scheduling_engine.cancel_appointment(db, row, actor_type="patient", reason="patient-canceled")
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="patient", actor_id=account.id, actor_email=account.email,
        entity_type="appointment", entity_id=row.id, action="canceled",
        changes={"reason": "patient-canceled"}, phi_accessed=True,
    ))
    await webhook_service.dispatch_event(
        db, org_id=p.org_id, event="appointment.canceled",
        data={"appointment_id": str(row.id)},
    )
    return AppointmentOut.model_validate(row)
