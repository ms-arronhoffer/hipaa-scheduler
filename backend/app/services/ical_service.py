"""iCalendar (.ics) feed generation for appointments.

:func:`build_calendar` turns plain event dicts into an RFC 5545 VCALENDAR byte
string using the ``icalendar`` library. It is deliberately decoupled from the
ORM (takes dicts, not model rows) so it can be unit-tested without a database
and reused by both the staff export and any patient-portal subscription feed.

PHI note: the caller decides what goes in ``summary``/``description``. Staff
exports run under an authenticated staff principal (who may already see patient
identifiers); public/patient feeds should pass PHI-free summaries.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from icalendar import Calendar, Event

PRODID = "-//hipaa-scheduler//appointments//EN"

# Map internal appointment statuses to iCal STATUS values.
_ICAL_STATUS = {
    "scheduled": "TENTATIVE",
    "confirmed": "CONFIRMED",
    "checked_in": "CONFIRMED",
    "completed": "CONFIRMED",
    "canceled": "CANCELLED",
    "no_show": "CANCELLED",
}


def build_calendar(events: Iterable[dict[str, Any]], *, cal_name: str = "Appointments") -> bytes:
    """Build a VCALENDAR from event dicts.

    Each event dict supports: ``uid`` (required), ``start`` (datetime, required),
    ``end`` (datetime, required), ``summary``, ``description``, ``location``,
    ``status`` (internal appointment status), ``created``, ``updated``.
    """
    cal = Calendar()
    cal.add("prodid", PRODID)
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", cal_name)

    for ev in events:
        item = Event()
        item.add("uid", str(ev["uid"]))
        item.add("dtstart", ev["start"])
        item.add("dtend", ev["end"])
        item.add("summary", ev.get("summary") or "Appointment")
        if ev.get("description"):
            item.add("description", ev["description"])
        if ev.get("location"):
            item.add("location", ev["location"])
        status = ev.get("status")
        if status in _ICAL_STATUS:
            item.add("status", _ICAL_STATUS[status])
        item.add("dtstamp", ev.get("updated") or ev.get("created") or datetime.utcnow())
        if ev.get("created"):
            item.add("created", ev["created"])
        if ev.get("updated"):
            item.add("last-modified", ev["updated"])
        cal.add_component(item)

    return cal.to_ical()
