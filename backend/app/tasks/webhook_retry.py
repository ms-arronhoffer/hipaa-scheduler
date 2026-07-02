"""Webhook retry worker task.

Runs every minute. Re-attempts delivery of every ``pending`` WebhookDelivery
whose ``next_attempt_at`` has come due, using the exponential backoff schedule
in :mod:`app.services.webhook_service`. Deliveries that exhaust
``webhook_max_attempts`` are moved to ``dead_letter`` (never retried again).
"""
from __future__ import annotations

import logging

from app.database import AsyncSessionLocal
from app.services import webhook_service
from app.tasks import heartbeat

log = logging.getLogger(__name__)


async def run_webhook_retry() -> dict[str, int]:
    try:
        async with AsyncSessionLocal() as db:
            counts = await webhook_service.retry_due(db)
            await db.commit()
        heartbeat.beat("webhook_retry", ok=True, detail=counts)
        return counts
    except Exception as exc:  # noqa: BLE001
        log.exception("webhook_retry_failed")
        heartbeat.beat("webhook_retry", ok=False, detail={"error": type(exc).__name__})
        raise


if __name__ == "__main__":  # pragma: no cover
    import asyncio

    from app.utils.logging import configure_logging

    configure_logging()
    asyncio.run(run_webhook_retry())
