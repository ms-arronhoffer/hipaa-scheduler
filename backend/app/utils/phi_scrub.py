"""Redact PHI-like fields from log payloads and error contexts.

Used as Sentry `before_send` hook and by structured logging when payloads may
contain patient data.
"""
from copy import deepcopy
from typing import Any

PHI_KEYS = {
    "first_name", "last_name", "middle_name", "dob", "date_of_birth",
    "ssn", "phone", "email", "address", "street", "city", "postal_code",
    "member_id", "insurance_id", "policy_number", "mrn", "medical_history",
    "medications", "allergies", "diagnosis", "notes", "note",
}


def scrub(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in PHI_KEYS:
                out[k] = "***REDACTED***"
            else:
                out[k] = scrub(v)
        return out
    if isinstance(obj, list):
        return [scrub(i) for i in obj]
    return obj


def sentry_before_send(event: dict, _hint: dict) -> dict:
    return scrub(deepcopy(event))
