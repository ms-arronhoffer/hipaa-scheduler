"""Locust load profile for the public (unauthenticated) booking surface.

Run with the Locust CLI, never under pytest — see ``backend/tests/load/README.md``.
This module imports ``locust`` (a load-only dependency not in the app image), so
it is deliberately named ``locustfile.py`` (not ``test_*.py``) to stay out of
pytest collection.

Modelled on the real flow a booking widget drives:

1. resolve the org slug once per simulated user (``GET /pub/orgs/{slug}``),
2. repeatedly search availability (``POST /pub/slots``) — the hot, DB-heavy path
   we most need capacity numbers for,
3. optionally place a guest booking (``POST /pub/book/guest``) when
   ``ENABLE_GUEST_BOOKING`` is set, since that writes real rows.

All targets come from environment variables so the same file works against any
staging deployment without code edits.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

from locust import HttpUser, between, task

API_V1 = "/api/v1"

_ORG_SLUG = os.environ.get("ORG_SLUG", "demo-clinic")
_OFFICE_ID = os.environ.get("OFFICE_ID", "")
_PROVIDER_ID = os.environ.get("PROVIDER_ID", "")
_APPOINTMENT_TYPE_ID = os.environ.get("APPOINTMENT_TYPE_ID", "")
_ENABLE_GUEST_BOOKING = os.environ.get("ENABLE_GUEST_BOOKING", "").lower() in {"1", "true", "yes"}


def _slot_query_window() -> tuple[str, str]:
    """A 14-day availability window starting tomorrow, ISO-8601 / UTC."""
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(days=14)
    return start.isoformat(), end.isoformat()


class PublicBookingUser(HttpUser):
    """Simulates a visitor browsing availability on the public booking widget."""

    # Human-ish think time between actions.
    wait_time = between(1, 5)

    def on_start(self) -> None:
        # Resolve the org slug once, mirroring the widget's initial load.
        self.client.get(
            f"{API_V1}/pub/orgs/{_ORG_SLUG}",
            name="/pub/orgs/{slug}",
        )

    @task(5)
    def search_slots(self) -> None:
        range_start, range_end = _slot_query_window()
        self.client.post(
            f"{API_V1}/pub/slots",
            name="/pub/slots",
            json={
                "org_slug": _ORG_SLUG,
                "office_id": _OFFICE_ID,
                "provider_id": _PROVIDER_ID,
                "appointment_type_id": _APPOINTMENT_TYPE_ID,
                "range_start": range_start,
                "range_end": range_end,
            },
        )

    @task(1)
    def view_org(self) -> None:
        self.client.get(
            f"{API_V1}/pub/orgs/{_ORG_SLUG}",
            name="/pub/orgs/{slug}",
        )

    @task(1)
    def book_guest(self) -> None:
        # Off by default: this writes a real appointment + PatientAccount. Only
        # enable against a disposable target.
        if not _ENABLE_GUEST_BOOKING:
            return
        start_at = (datetime.now(timezone.utc) + timedelta(days=2)).replace(
            minute=0, second=0, microsecond=0
        )
        unique = uuid.uuid4().hex[:12]
        self.client.post(
            f"{API_V1}/pub/book/guest",
            name="/pub/book/guest",
            json={
                "org_slug": _ORG_SLUG,
                "office_id": _OFFICE_ID,
                "provider_id": _PROVIDER_ID,
                "appointment_type_id": _APPOINTMENT_TYPE_ID,
                "start_at": start_at.isoformat(),
                "accept_hipaa_version": "1.0",
                "patient": {
                    "first_name": "Load",
                    "last_name": f"Test-{unique}",
                    "dob": "1990-01-01",
                    "email": f"loadtest+{unique}@example.com",
                    "phone": "+15555550123",
                },
            },
        )
