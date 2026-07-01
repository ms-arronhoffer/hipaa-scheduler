"""Notification orchestrator.

Given an event (`appointment_reminder`, `appointment_confirmed`, ...) and a
target, looks up the org's active template for (event, channel), renders it
with PHI-safe context, dispatches via the right adapter, and writes a
NotificationLog row. No PHI is passed into the template context — see
`template_renderer.ALLOWED_KEYS`.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import NotificationLog, NotificationTemplate
from app.services import email_service, sms_service, template_renderer


class NotificationError(RuntimeError):
    pass


async def notify(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    event: str,
    channel: str,
    to_address: str,
    context: dict[str, Any],
    patient_id: uuid.UUID | None = None,
    appointment_id: uuid.UUID | None = None,
    patient_opted_in_sms: bool = False,
) -> NotificationLog:
    tpl = (await db.execute(
        select(NotificationTemplate).where(
            NotificationTemplate.org_id == org_id,
            NotificationTemplate.event == event,
            NotificationTemplate.channel == channel,
            NotificationTemplate.active.is_(True),
            NotificationTemplate.deleted_at.is_(None),
        )
    )).scalars().first()
    if tpl is None:
        raise NotificationError(f"no active template for {event}/{channel}")

    subject = template_renderer.render(tpl.subject or "", context) if tpl.subject else None
    body = template_renderer.render(tpl.body, context)

    log = NotificationLog(
        org_id=org_id,
        channel=channel,
        event=event,
        appointment_id=appointment_id,
        patient_id=patient_id,
        to_address=to_address,
        status="queued",
        context={"template_id": str(tpl.id)},
    )
    db.add(log)
    await db.flush()

    try:
        if channel == "email":
            msg_id = await email_service.send(
                to=to_address, subject=subject or "", html_body=body
            )
        elif channel == "sms":
            msg_id = await sms_service.send(
                to=to_address, body=body, patient_opted_in=patient_opted_in_sms
            )
        elif channel == "inapp":
            msg_id = None  # persisted via NotificationLog only; UI polls
        else:
            raise NotificationError(f"unsupported channel {channel}")
        log.provider_message_id = msg_id
        log.status = "sent"
        log.sent_at = datetime.utcnow()
    except (email_service.EmailSendError, sms_service.SMSSendError) as e:
        log.status = "failed"
        log.error = str(e)[:500]
    except sms_service.SMSNotOptedIn as e:
        log.status = "opted_out"
        log.error = str(e)[:500]
    return log
