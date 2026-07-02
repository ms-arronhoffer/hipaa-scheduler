"""Unit tests for iCal feed generation (no DB)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from icalendar import Calendar

from app.services import ical_service


def _event(**kw):
    base = {
        "uid": f"{uuid.uuid4()}@hipaa-scheduler",
        "start": datetime(2026, 7, 3, 14, 0, tzinfo=timezone.utc),
        "end": datetime(2026, 7, 3, 14, 30, tzinfo=timezone.utc),
        "summary": "Annual Physical",
        "status": "confirmed",
    }
    base.update(kw)
    return base


def test_empty_calendar_is_valid():
    ics = ical_service.build_calendar([])
    cal = Calendar.from_ical(ics)
    assert cal.get("prodid") == ical_service.PRODID
    assert cal.get("version") == "2.0"
    assert [c for c in cal.walk("VEVENT")] == []


def test_single_event_fields():
    ev = _event()
    ics = ical_service.build_calendar([ev])
    cal = Calendar.from_ical(ics)
    vevents = list(cal.walk("VEVENT"))
    assert len(vevents) == 1
    ve = vevents[0]
    assert str(ve.get("uid")) == ev["uid"]
    assert str(ve.get("summary")) == "Annual Physical"
    assert ve.decoded("dtstart") == ev["start"]
    assert ve.decoded("dtend") == ev["end"]
    assert str(ve.get("status")) == "CONFIRMED"


def test_status_mapping():
    ics = ical_service.build_calendar([_event(status="canceled")])
    ve = list(Calendar.from_ical(ics).walk("VEVENT"))[0]
    assert str(ve.get("status")) == "CANCELLED"


def test_unknown_status_omitted():
    ics = ical_service.build_calendar([_event(status="weird")])
    ve = list(Calendar.from_ical(ics).walk("VEVENT"))[0]
    assert ve.get("status") is None


def test_summary_defaults_when_missing():
    ev = _event()
    ev.pop("summary")
    ics = ical_service.build_calendar([ev])
    ve = list(Calendar.from_ical(ics).walk("VEVENT"))[0]
    assert str(ve.get("summary")) == "Appointment"


def test_multiple_events():
    ics = ical_service.build_calendar([_event(), _event(), _event()])
    assert len(list(Calendar.from_ical(ics).walk("VEVENT"))) == 3


def test_optional_description_and_location():
    ics = ical_service.build_calendar([_event(description="Bring ID", location="Suite 200")])
    ve = list(Calendar.from_ical(ics).walk("VEVENT"))[0]
    assert str(ve.get("description")) == "Bring ID"
    assert str(ve.get("location")) == "Suite 200"
