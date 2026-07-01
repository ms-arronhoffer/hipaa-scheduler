"""RRULE expansion helpers.

We accept a canonical RRULE string ("FREQ=WEEKLY;BYDAY=MO,WE,FR;UNTIL=...") plus
a dtstart, and materialize concrete datetimes for a bounded window. `exdates`
(list of ISO strings) are removed. Consumers cap horizons (default 12 months).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from dateutil.rrule import rrulestr


MAX_HORIZON = timedelta(days=366)


def expand(rrule: str, dtstart: datetime, until: datetime, exdates: list[str] | None = None) -> list[datetime]:
    if until - dtstart > MAX_HORIZON:
        until = dtstart + MAX_HORIZON
    rule = rrulestr(rrule, dtstart=dtstart)
    excluded = set()
    if exdates:
        for s in exdates:
            try:
                excluded.add(datetime.fromisoformat(s))
            except ValueError:
                continue
    return [dt for dt in rule.between(dtstart, until, inc=True) if dt not in excluded]
