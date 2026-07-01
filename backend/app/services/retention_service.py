"""HIPAA 6-year retention floor.

The `retention_years` setting is the *minimum*; a nightly sweep hard-deletes
soft-deleted rows only after they've been in the `deleted_at` state for
`retention_years` or longer. Audit records (ActivityLog) are excluded — they
are immutable and retained even beyond retention window.

Tables purged here are only those with `deleted_at` semantics AND known to be
free of downstream audit references.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.appointment import Appointment, RecurringAppointmentSeries
from app.models.availability import ProviderAvailability, TimeOff
from app.models.notification import NotificationTemplate, ReminderRule
from app.models.patient import Patient, PatientAccount
from app.models.patient_records import Consent, Document, InsurancePolicy
from app.models.waitlist import WaitlistEntry
from app.models.webhook import WebhookSubscription


log = logging.getLogger(__name__)


# Tables safe to purge: soft-deletable, not the audit log itself.
PURGE_MODELS = [
    Appointment,
    RecurringAppointmentSeries,
    ProviderAvailability,
    TimeOff,
    NotificationTemplate,
    ReminderRule,
    PatientAccount,
    Patient,
    Consent,
    Document,
    InsurancePolicy,
    WaitlistEntry,
    WebhookSubscription,
]


def _retention_cutoff(now: datetime | None = None) -> datetime:
    now = now or datetime.utcnow()
    return now - timedelta(days=365 * settings.retention_years)


async def sweep(db: AsyncSession, *, now: datetime | None = None, batch: int = 1000) -> dict[str, int]:
    """Delete soft-deleted rows older than the retention floor. Returns per-table counts."""
    cutoff = _retention_cutoff(now)
    counts: dict[str, int] = {}
    for model in PURGE_MODELS:
        result = await db.execute(
            delete(model).where(
                model.deleted_at.is_not(None),
                model.deleted_at < cutoff,
            ).execution_options(synchronize_session=False)
        )
        counts[model.__tablename__] = result.rowcount or 0
    log.info("retention_sweep", extra={"cutoff": cutoff.isoformat(), "counts": counts})
    return counts
