"""Twilio SMS adapter with double opt-in enforcement.

`send(...)` refuses to send to any patient whose `sms_opt_in_at` is null. STOP
handling is done at the router layer (Twilio inbound webhook) which flips
`sms_opt_in_at` back to None. Like `email_service`, non-production is stubbed.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging

import httpx

from app.config import settings


log = logging.getLogger(__name__)


class SMSSendError(RuntimeError):
    pass


class SMSNotOptedIn(RuntimeError):
    pass


async def send(*, to: str, body: str, patient_opted_in: bool) -> str | None:
    """Send an SMS. Raises SMSNotOptedIn if patient hasn't confirmed."""
    if not patient_opted_in:
        raise SMSNotOptedIn(f"patient {to} not opted in")

    sid = settings.twilio_sid
    token = settings.twilio_token
    frm = settings.twilio_from
    if not (sid and token and frm) or settings.app_env != "production":
        log.info("sms_send_stub", extra={"to": to})
        return None

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = {"To": to, "From": frm, "Body": body}
    async with httpx.AsyncClient(timeout=10.0, auth=(sid, token.get_secret_value())) as client:
        resp = await client.post(url, data=data)
    if resp.status_code >= 300:
        raise SMSSendError(f"twilio {resp.status_code}: {resp.text[:200]}")
    return resp.json().get("sid")


def parse_inbound_keyword(body: str) -> str | None:
    """Recognize STOP/START/YES keywords in an inbound SMS body (case-insensitive)."""
    b = (body or "").strip().upper()
    if b in {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"}:
        return "stop"
    if b in {"START", "UNSTOP"}:
        return "start"
    if b in {"YES", "Y", "OPT IN"}:
        return "confirm"
    return None


def verify_twilio_signature(url: str, params: dict[str, str], signature: str | None) -> bool:
    """Validate Twilio's ``X-Twilio-Signature`` header (HMAC-SHA1).

    Twilio signs the full request URL concatenated with each POST field's name
    and value, sorted by field name. See
    https://www.twilio.com/docs/usage/security#validating-requests.

    Fails closed: returns ``False`` when the auth token or signature is missing.
    """
    token = settings.twilio_token
    if not token or not signature:
        return False
    data = url
    for key in sorted(params):
        data += key + (params[key] or "")
    digest = hmac.new(
        token.get_secret_value().encode("utf-8"),
        data.encode("utf-8"),
        # SHA-1 is used inside HMAC (keyed), not as a bare hash: HMAC's security
        # does not rely on the collision resistance of the underlying hash, and
        # Twilio's signature protocol mandates HMAC-SHA1. Not password hashing.
        hashlib.sha1,  # noqa: S324 - required by the Twilio signing protocol
    ).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, signature)
