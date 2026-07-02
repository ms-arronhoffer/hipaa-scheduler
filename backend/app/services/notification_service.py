"""Notification orchestrator.

Given an event (`appointment_reminder`, `appointment_confirmed`, ...) and a
target, looks up the org's active template for (event, channel), renders it
with PHI-safe context, dispatches via the right adapter, and writes a
NotificationLog row. No PHI is passed into the template context — see
`template_renderer.ALLOWED_KEYS`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.notification import NotificationLog, NotificationTemplate
from app.services import email_service, sms_service, template_renderer


class NotificationError(RuntimeError):
    pass


def next_retry_at(attempts: int, now: datetime | None = None) -> datetime | None:
    """When a row that has failed ``attempts`` times may next be retried.

    Returns ``None`` once ``attempts`` reaches ``notification_max_attempts`` —
    the row is then permanently failed. The backoff schedule is clamped so
    later attempts reuse the longest configured delay.
    """
    if attempts >= settings.notification_max_attempts:
        return None
    delays = settings.notification_retry_delays_min or [5]
    idx = min(attempts, len(delays)) - 1
    if idx < 0:
        idx = 0
    minutes = delays[idx]
    return (now or datetime.utcnow()) + timedelta(minutes=minutes)


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
        # Persist the rendered (PHI-free) payload so the retry sweep can resend
        # without re-deriving context. template_renderer whitelists non-PHI keys.
        context={"template_id": str(tpl.id), "subject": subject, "body": body},
    )
    db.add(log)
    await db.flush()

    await _dispatch(log, channel=channel, subject=subject, body=body,
                    patient_opted_in_sms=patient_opted_in_sms)
    return log


async def _do_send(*, channel: str, subject: str | None, body: str,
                   to_address: str, patient_opted_in_sms: bool) -> str | None:
    if channel == "email":
        return await email_service.send(to=to_address, subject=subject or "", html_body=body)
    if channel == "sms":
        return await sms_service.send(to=to_address, body=body, patient_opted_in=patient_opted_in_sms)
    if channel == "inapp":
        return None  # persisted via NotificationLog only; UI polls
    raise NotificationError(f"unsupported channel {channel}")


async def _dispatch(log: NotificationLog, *, channel: str, subject: str | None,
                    body: str, patient_opted_in_sms: bool) -> None:
    """Attempt one delivery and record the outcome on ``log`` (with retry scheduling)."""
    log.attempts = (log.attempts or 0) + 1
    try:
        msg_id = await _do_send(
            channel=channel, subject=subject, body=body,
            to_address=log.to_address, patient_opted_in_sms=patient_opted_in_sms,
        )
        log.provider_message_id = msg_id
        log.status = "sent"
        log.error = None
        log.sent_at = datetime.utcnow()
        log.next_retry_at = None
    except (email_service.EmailSendError, sms_service.SMSSendError) as e:
        log.status = "failed"
        log.error = str(e)[:500]
        log.next_retry_at = next_retry_at(log.attempts)
    except sms_service.SMSNotOptedIn as e:
        # Opt-out is terminal, not a transient failure — never retry.
        log.status = "opted_out"
        log.error = str(e)[:500]
        log.next_retry_at = None


async def resend(db: AsyncSession, log: NotificationLog, *, patient_opted_in_sms: bool = False) -> NotificationLog:
    """Re-attempt delivery of a previously-failed NotificationLog row."""
    ctx = log.context or {}
    await _dispatch(
        log, channel=log.channel, subject=ctx.get("subject"),
        body=ctx.get("body") or "", patient_opted_in_sms=patient_opted_in_sms,
    )
    return log
