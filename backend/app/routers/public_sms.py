"""Public Twilio inbound SMS webhook — STOP/START keyword handling.

Twilio POSTs (form-encoded) to this endpoint when a patient texts our number.
We honor carrier-standard opt-out keywords (STOP) and opt-in keywords
(START/YES) by flipping ``Patient.sms_opt_in_at`` for *every* patient row whose
phone matches the sender — an unsubscribe applies to the phone number across all
tenants that hold it, as required for consent compliance.

The request is authenticated by validating Twilio's ``X-Twilio-Signature``
(HMAC-SHA1 over the URL + sorted params, keyed by the account auth token). In
non-production without a configured token, signature validation is skipped so
local/testing flows work; production always enforces it.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.activity_log import ActivityLog
from app.models.patient import Patient
from app.services import sms_service


router = APIRouter(prefix="/pub/sms", tags=["public_sms"])

# Empty TwiML — acknowledges receipt without sending an auto-reply.
_EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


def _require_valid_signature(request: Request, params: dict[str, str]) -> None:
    signature = request.headers.get("X-Twilio-Signature")
    # In non-production without a configured Twilio token, skip validation so
    # local testing works. Production (or any configured token) always enforces.
    if settings.app_env != "production" and not settings.twilio_token:
        return
    if not sms_service.verify_twilio_signature(str(request.url), params, signature):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid twilio signature")


@router.post("/inbound")
async def twilio_inbound(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}
    _require_valid_signature(request, params)

    from_number = (params.get("From") or "").strip()
    body = params.get("Body") or ""
    keyword = sms_service.parse_inbound_keyword(body)
    if not from_number or keyword is None:
        # Nothing actionable — acknowledge so Twilio doesn't retry.
        return _twiml_response()

    # idor-safe: inbound STOP/START is an unauthenticated carrier callback with
    # no org context; consent for a phone number spans every tenant holding it.
    patients = (await db.execute(
        select(Patient).where(Patient.phone == from_number, Patient.deleted_at.is_(None))
    )).scalars().all()

    now = datetime.now(timezone.utc)
    for patient in patients:
        if keyword == "stop":
            patient.sms_opt_in_at = None
            action = "sms_opt_out"
        else:  # "start" or "confirm"
            patient.sms_opt_in_at = now
            action = "sms_opt_in"
        db.add(ActivityLog(
            org_id=patient.org_id, actor_type="patient_account", actor_id=patient.id,
            entity_type="patient", entity_id=patient.id, action=action,
            changes={"source": "sms_inbound", "keyword": keyword},
        ))
    return _twiml_response()


def _twiml_response():
    from fastapi.responses import Response

    return Response(content=_EMPTY_TWIML, media_type="application/xml")
