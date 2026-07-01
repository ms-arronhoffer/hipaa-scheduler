"""RRULE expansion — recurring appointment series must materialize predictably
and respect the 12-month horizon cap."""
from datetime import datetime, timedelta

import pytest

from app.services.rrule_expander import MAX_HORIZON, expand


class TestExpand:
    def test_weekly_monday_wednesday_friday(self):
        # 2026-01-05 is a Monday
        start = datetime(2026, 1, 5, 9, 0)
        until = datetime(2026, 1, 26, 9, 0)  # 3 weeks — expect 9 occurrences
        out = expand("FREQ=WEEKLY;BYDAY=MO,WE,FR", start, until)
        assert len(out) == 9
        weekdays = {dt.weekday() for dt in out}
        assert weekdays == {0, 2, 4}  # Mon, Wed, Fri

    def test_daily_short_horizon(self):
        start = datetime(2026, 2, 1, 8, 0)
        out = expand("FREQ=DAILY;COUNT=5", start, start + timedelta(days=10))
        assert len(out) == 5

    def test_horizon_capped_at_max(self):
        start = datetime(2026, 1, 1)
        # request 3 years, expander should truncate to 366 days
        very_far = start + timedelta(days=365 * 3)
        out = expand("FREQ=DAILY", start, very_far)
        assert out[-1] <= start + MAX_HORIZON

    def test_exdates_removed(self):
        start = datetime(2026, 1, 5, 9, 0)
        until = datetime(2026, 1, 19, 9, 0)
        skip = datetime(2026, 1, 12, 9, 0)
        out = expand("FREQ=WEEKLY;BYDAY=MO", start, until, exdates=[skip.isoformat()])
        assert skip not in out
        assert start in out

    def test_malformed_exdate_ignored_not_raised(self):
        start = datetime(2026, 1, 5, 9, 0)
        out = expand("FREQ=WEEKLY;BYDAY=MO;COUNT=2", start, start + timedelta(days=30),
                     exdates=["not-a-date", "also-bad"])
        # Malformed exdates are dropped, real occurrences preserved.
        assert len(out) == 2

    def test_empty_when_no_occurrences_in_window(self):
        start = datetime(2026, 1, 5)
        # Window ends before dtstart — nothing to yield.
        out = expand("FREQ=DAILY", start, start - timedelta(days=1))
        assert out == []
