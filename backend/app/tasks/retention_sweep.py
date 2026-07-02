"""Retention sweep worker task.

Thin worker wrapper around :func:`app.services.retention_service.sweep`, which
hard-deletes soft-deleted rows older than the HIPAA retention floor. Scheduled
nightly by the worker.
"""
from __future__ import annotations

import logging

from app.database import AsyncSessionLocal
from app.services import retention_service
from app.tasks import heartbeat

log = logging.getLogger(__name__)


async def run_retention_sweep() -> dict[str, int]:
    try:
        async with AsyncSessionLocal() as db:
            counts = await retention_service.sweep(db)
            await db.commit()
        heartbeat.beat("retention_sweep", ok=True, detail={"total": sum(counts.values())})
        return counts
    except Exception as exc:  # noqa: BLE001
        log.exception("retention_sweep_failed")
        heartbeat.beat("retention_sweep", ok=False, detail={"error": type(exc).__name__})
        raise


if __name__ == "__main__":  # pragma: no cover
    import asyncio

    from app.utils.logging import configure_logging

    configure_logging()
    asyncio.run(run_retention_sweep())
