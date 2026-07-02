"""Notification delivery retry worker task.

Runs periodically. Re-attempts every email/SMS ``NotificationLog`` that is
``failed`` and whose ``next_retry_at`` has come due, using the backoff schedule
in :mod:`app.services.notification_service`. Rows that exhaust
``notification_max_attempts`` keep ``next_retry_at=None`` and are never retried
again.
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.notification import NotificationLog
from app.models.patient import Patient
from app.services import notification_service
from app.tasks import heartbeat

log = logging.getLogger(__name__)


async def run_notification_retry() -> dict[str, int]:
    try:
        async with AsyncSessionLocal() as db:
            now = datetime.utcnow()
            rows = (await db.execute(
                select(NotificationLog).where(
                    NotificationLog.status == "failed",
                    NotificationLog.next_retry_at.is_not(None),
                    NotificationLog.next_retry_at <= now,
                )
            )).scalars().all()  # idor-safe: system retry sweep spans all orgs

            resent = 0
            recovered = 0
            for row in rows:
                opted_in = False
                if row.channel == "sms" and row.patient_id is not None:
                    patient = (await db.execute(
                        select(Patient).where(Patient.id == row.patient_id)
                    )).scalar_one_or_none()
                    opted_in = patient is not None and patient.sms_opt_in_at is not None
                await notification_service.resend(db, row, patient_opted_in_sms=opted_in)
                resent += 1
                if row.status == "sent":
                    recovered += 1
            await db.commit()

        counts = {"retried": resent, "recovered": recovered}
        heartbeat.beat("notification_retry", ok=True, detail=counts)
        return counts
    except Exception as exc:  # noqa: BLE001
        log.exception("notification_retry_failed")
        heartbeat.beat("notification_retry", ok=False, detail={"error": type(exc).__name__})
        raise


if __name__ == "__main__":  # pragma: no cover
    import asyncio

    from app.utils.logging import configure_logging

    configure_logging()
    asyncio.run(run_notification_retry())
