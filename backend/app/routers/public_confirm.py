"""Public one-click confirm/cancel via signed ConfirmToken.

Reminders emit URLs like `/pub/confirm?t=<plaintext>` and
`/pub/cancel?t=<plaintext>`. Tokens are single-use, sha256-hashed at rest,
and scoped to a specific appointment + kind. Cancels enforce the appointment
type's `cancellation_window_hours`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.activity_log import ActivityLog
from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.services import confirm_token_service, scheduling_engine, webhook_service


router = APIRouter(prefix="/pub", tags=["public_confirm"])


async def _load_appointment(db: AsyncSession, appointment_id) -> Appointment:
    row = (await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "appointment not found")
    return row


def _now_matching(dt: datetime) -> datetime:
    """Return utcnow with the same tzinfo shape as the compared datetime."""
    if dt.tzinfo is not None:
        return datetime.now(timezone.utc)
    return datetime.utcnow()


@router.get("/confirm")
async def one_click_confirm(
    t: str = Query(..., min_length=8),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        tok = await confirm_token_service.consume(db, plaintext=t, expect_kind="confirm")
    except confirm_token_service.TokenError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    if tok.appointment_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "token missing appointment")
    appt = await _load_appointment(db, tok.appointment_id)
    if appt.status in ("canceled", "no_show", "completed"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"appointment {appt.status}")
    if appt.status != "confirmed":
        appt.status = "confirmed"
    db.add(ActivityLog(
        org_id=tok.org_id, actor_type="patient", actor_id=None, actor_email=None,
        entity_type="appointment", entity_id=appt.id, action="confirmed",
        changes={"via": "one_click"}, phi_accessed=True,
    ))
    await webhook_service.dispatch_event(
        db, org_id=tok.org_id, event="appointment.updated",
        data={"appointment_id": str(appt.id), "status": "confirmed"},
    )
    return {"appointment_id": str(appt.id), "status": "confirmed"}


@router.get("/cancel")
async def one_click_cancel(
    t: str = Query(..., min_length=8),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        tok = await confirm_token_service.consume(db, plaintext=t, expect_kind="cancel")
    except confirm_token_service.TokenError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    if tok.appointment_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "token missing appointment")
    appt = await _load_appointment(db, tok.appointment_id)
    if appt.status in ("canceled", "no_show", "completed"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"appointment {appt.status}")
    apptype = (await db.execute(
        select(AppointmentType).where(AppointmentType.id == appt.appointment_type_id)
    )).scalar_one_or_none()
    window_hours = apptype.cancellation_window_hours if apptype else 24
    now = _now_matching(appt.start_at)
    if appt.start_at - now < timedelta(hours=window_hours):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "outside cancellation window")
    await scheduling_engine.cancel_appointment(
        db, appt, actor_type="patient", reason="one-click",
    )
    db.add(ActivityLog(
        org_id=tok.org_id, actor_type="patient", actor_id=None, actor_email=None,
        entity_type="appointment", entity_id=appt.id, action="canceled",
        changes={"via": "one_click", "reason": "one-click"}, phi_accessed=True,
    ))
    await webhook_service.dispatch_event(
        db, org_id=tok.org_id, event="appointment.canceled",
        data={"appointment_id": str(appt.id)},
    )
    return {"appointment_id": str(appt.id), "status": "canceled"}
