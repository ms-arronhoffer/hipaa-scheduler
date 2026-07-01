"""Standalone APScheduler worker process.

Runs periodic background jobs:
- reminder_sweep: enqueue email/SMS reminders based on ReminderRule offsets
- webhook_retry: retry failed WebhookDelivery rows with backoff
- waitlist_fill: on cancellation events, notify next waitlist entries
- retention_sweep: soft-delete rows past HIPAA 6-year retention floor
- calendar_pull: incremental sync from connected Google/O365 calendars
"""
import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.utils.logging import configure_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    configure_logging()
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Reminder sweep every 5 minutes
    from app.tasks.reminder_sweep import run_reminder_sweep
    scheduler.add_job(run_reminder_sweep, "interval", minutes=5, id="reminder_sweep")

    # Webhook retry every 1 minute
    from app.tasks.webhook_retry import run_webhook_retry
    scheduler.add_job(run_webhook_retry, "interval", minutes=1, id="webhook_retry")

    # Retention sweep nightly at 03:15 UTC
    from app.tasks.retention_sweep import run_retention_sweep
    scheduler.add_job(run_retention_sweep, "cron", hour=3, minute=15, id="retention_sweep")

    # Calendar incremental pull every 10 min
    from app.tasks.calendar_pull import run_calendar_pull
    scheduler.add_job(run_calendar_pull, "interval", minutes=10, id="calendar_pull")

    scheduler.start()
    logger.info(
        "worker.started",
        extra={"jobs": [j.id for j in scheduler.get_jobs()], "env": settings.app_env},
    )

    stop = asyncio.Event()
    try:
        await stop.wait()
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
