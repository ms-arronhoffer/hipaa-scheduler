"""Calendar incremental pull worker task.

Every 10 minutes: refresh OAuth access tokens that are near expiry so connected
Google/O365 calendars keep valid credentials, then reconcile events per
connection (mirror appointments out + repair remote drift — see
:func:`app.services.calendar_service.reconcile_events`).
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.calendar_connection import CalendarConnection
from app.services import calendar_service
from app.tasks import heartbeat

log = logging.getLogger(__name__)


async def run_calendar_pull() -> dict[str, int]:
    refreshed = 0
    scanned = 0
    reconciled = 0
    try:
        async with AsyncSessionLocal() as db:
            conns = (await db.execute(
                select(CalendarConnection).where(
                    CalendarConnection.active.is_(True),
                    CalendarConnection.deleted_at.is_(None),
                )
            )).scalars().all()
            for conn in conns:
                scanned += 1
                if calendar_service.needs_refresh(conn):
                    if await calendar_service.refresh_token(db, conn):
                        refreshed += 1
                reconciled += await calendar_service.reconcile_events(db, conn)
            await db.commit()
        heartbeat.beat(
            "calendar_pull", ok=True,
            detail={"scanned": scanned, "refreshed": refreshed, "reconciled": reconciled},
        )
        return {"scanned": scanned, "refreshed": refreshed, "reconciled": reconciled}
    except Exception as exc:  # noqa: BLE001
        log.exception("calendar_pull_failed")
        heartbeat.beat("calendar_pull", ok=False, detail={"error": type(exc).__name__})
        raise


if __name__ == "__main__":  # pragma: no cover
    import asyncio

    from app.utils.logging import configure_logging

    configure_logging()
    asyncio.run(run_calendar_pull())
