"""Reminder sweep.

Runs every 5 minutes. For each active appointment starting within the largest
configured offset window, checks whether a NotificationLog already exists for
that (appointment, offset) tuple; if not, dispatches per the associated
ReminderRule's channels.

Idempotency: we key on `context.reminder_offset_min` in NotificationLog so a
re-run after a crash never double-sends.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Iterable

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.models.notification import NotificationLog, ReminderRule
from app.models.office import Office
from app.models.patient import Patient
from app.models.user import ProviderProfile, User
from app.services import notification_service


log = logging.getLogger(__name__)

ACTIVE = ("scheduled", "confirmed")


def _target_time(start_at: datetime, offset_min: int) -> datetime:
    return start_at - timedelta(minutes=offset_min)


async def _already_sent(db: AsyncSession, appt_id, channel: str, offset_min: int) -> bool:
    row = (await db.execute(
        select(NotificationLog.id).where(
            NotificationLog.appointment_id == appt_id,
            NotificationLog.channel == channel,
            NotificationLog.event == "appointment_reminder",
            NotificationLog.context["reminder_offset_min"].astext == str(offset_min),
        )
    )).first()
    return row is not None


async def sweep(db: AsyncSession, *, now: datetime | None = None, look_ahead_min: int = 15) -> int:
    """Return the number of NotificationLog rows created."""
    now = now or datetime.utcnow()
    # Pull all active rules and appointments in a wide window; filter in Python
    rules = (await db.execute(
        select(ReminderRule).where(ReminderRule.active.is_(True), ReminderRule.deleted_at.is_(None))
    )).scalars().all()
    if not rules:
        return 0

    max_offset = max((max(r.offsets_min or [0]) for r in rules), default=0)
    horizon_end = now + timedelta(minutes=max_offset + look_ahead_min)
    appts = (await db.execute(
        select(Appointment, AppointmentType, Office, Patient, ProviderProfile, User).join(
            AppointmentType, AppointmentType.id == Appointment.appointment_type_id
        ).join(
            Office, Office.id == Appointment.office_id
        ).join(
            Patient, Patient.id == Appointment.patient_id
        ).join(
            ProviderProfile, ProviderProfile.id == Appointment.provider_id
        ).join(
            User, User.id == ProviderProfile.user_id
        ).where(
            Appointment.deleted_at.is_(None),
            Appointment.status.in_(ACTIVE),
            Appointment.start_at > now,
            Appointment.start_at <= horizon_end,
        )
    )).all()

    rules_by_id = {r.id: r for r in rules}
    created = 0
    for appt, apptype, office, patient, provider, provider_user in appts:
        rule = rules_by_id.get(apptype.reminder_rule_id) if apptype.reminder_rule_id else None
        if rule is None:
            continue
        start_local = appt.start_at  # office tz conversion handled by renderer caller if needed
        context = {
            "practice_name": "",  # filled by caller / template if needed
            "office_name": office.name,
            "office_phone": office.phone or "",
            "office_address_city": (office.address or {}).get("city", ""),
            "provider_display": f"{provider_user.first_name or ''} {provider_user.last_name or ''}".strip(),
            "appointment_type_name": apptype.name,
            "appointment_duration_min": apptype.duration_min,
            "appointment_start_local": start_local.isoformat(),
            "confirm_url": "",
            "cancel_url": "",
            "reschedule_url": "",
            "portal_url": "",
        }
        for offset_min in rule.offsets_min or []:
            target = _target_time(appt.start_at, offset_min)
            if not (now - timedelta(minutes=look_ahead_min) <= target <= now + timedelta(minutes=look_ahead_min)):
                continue
            for channel in rule.channels or []:
                if await _already_sent(db, appt.id, channel, offset_min):
                    continue
                try:
                    to = patient.email if channel == "email" else patient.phone
                    if not to:
                        continue
                    logrow = await notification_service.notify(
                        db,
                        org_id=appt.org_id,
                        event="appointment_reminder",
                        channel=channel,
                        to_address=to,
                        context=context,
                        patient_id=patient.id,
                        appointment_id=appt.id,
                        patient_opted_in_sms=patient.sms_opt_in_at is not None,
                    )
                    logrow.context = {**logrow.context, "reminder_offset_min": offset_min}
                    created += 1
                except notification_service.NotificationError as e:
                    log.warning("reminder_skip", extra={"appt": str(appt.id), "err": str(e)})
    return created


async def run_reminder_sweep() -> int:
    """Worker entrypoint: open a session, run the sweep, commit, heartbeat."""
    from app.database import AsyncSessionLocal
    from app.tasks import heartbeat

    created = 0
    try:
        async with AsyncSessionLocal() as db:
            created = await sweep(db)
            await db.commit()
        heartbeat.beat("reminder_sweep", ok=True, detail={"created": created})
    except Exception as exc:  # noqa: BLE001 - record failure, keep worker alive
        log.exception("reminder_sweep_failed")
        heartbeat.beat("reminder_sweep", ok=False, detail={"error": type(exc).__name__})
        raise
    return created


if __name__ == "__main__":  # pragma: no cover - manual/CLI invocation
    import asyncio

    from app.utils.logging import configure_logging

    configure_logging()
    asyncio.run(run_reminder_sweep())
