"""Jinja2 sandbox rendering for notification templates.

Only PHI-safe variables are exposed. If a template tries to reference PHI
(e.g., `patient.name`, `patient.dob`), the sandbox raises SecurityError and
the render fails closed — no fall-through to a partially-interpolated message.

Whitelisted context keys:
    - practice_name, office_name, office_phone, office_address_city
    - provider_display (e.g., "Dr. Smith" — first initial + last name)
    - appointment_type_name, appointment_duration_min
    - appointment_start_local (formatted string in office tz)
    - confirm_url, cancel_url, reschedule_url, portal_url
"""
from __future__ import annotations

from typing import Any

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment


ALLOWED_KEYS = frozenset({
    "practice_name",
    "office_name",
    "office_phone",
    "office_address_city",
    "provider_display",
    "appointment_type_name",
    "appointment_duration_min",
    "appointment_start_local",
    "confirm_url",
    "cancel_url",
    "reschedule_url",
    "portal_url",
})


_env = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False)


class TemplateContextError(ValueError):
    pass


def render(template: str, context: dict[str, Any]) -> str:
    extra = set(context) - ALLOWED_KEYS
    if extra:
        raise TemplateContextError(f"disallowed template variables: {sorted(extra)}")
    return _env.from_string(template).render(**context)
