"""Outbound webhooks with HMAC-SHA256 signing + exponential backoff retry.

Envelope shape:
    {"id": uuid, "event": "appointment.created", "org_id": uuid,
     "occurred_at": iso8601, "data": {...}}

Signature header (Stripe-style):
    X-HS-Signature: t=<unix-ts>,v1=<hex-hmac-sha256>
Signed payload = f"{t}.{raw_body_bytes}". Receivers reject if `t` skew > 5 min.

Retry schedule (attempts 1..6):
    30s, 2m, 10m, 1h, 6h, 24h
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.webhook import WebhookDelivery, WebhookSubscription


# Backoff schedule for the first attempts. When ``webhook_max_attempts`` exceeds
# the length of this list, the last (longest) delay is reused for the remaining
# attempts.
RETRY_DELAYS = [
    timedelta(seconds=30),
    timedelta(minutes=2),
    timedelta(minutes=10),
    timedelta(hours=1),
    timedelta(hours=6),
    timedelta(hours=24),
]


def max_attempts() -> int:
    """Total delivery attempts before a delivery is dead-lettered (config-driven)."""
    return max(1, int(settings.webhook_max_attempts))


def _retry_delay(attempt: int) -> timedelta:
    """Backoff before the next attempt after ``attempt`` failed (1-indexed)."""
    idx = min(max(attempt - 1, 0), len(RETRY_DELAYS) - 1)
    return RETRY_DELAYS[idx]


def timeout_seconds() -> float:
    return float(settings.webhook_timeout_sec)


def sign_payload(secret: str, body: bytes, ts: int) -> str:
    signed = f"{ts}.".encode() + body
    mac = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


def verify_signature(secret: str, body: bytes, header: str, *, max_skew_seconds: int = 300) -> bool:
    """Used by tests and any inbound receiver we author; safe against timing attacks."""
    parts = dict(kv.split("=", 1) for kv in header.split(",") if "=" in kv)
    try:
        ts = int(parts["t"])
        sig = parts["v1"]
    except (KeyError, ValueError):
        return False
    if abs(int(datetime.utcnow().timestamp()) - ts) > max_skew_seconds:
        return False
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def build_envelope(event: str, org_id: uuid.UUID, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "event": event,
        "org_id": str(org_id),
        "occurred_at": datetime.utcnow().isoformat() + "Z",
        "data": data,
    }


async def enqueue(
    db: AsyncSession, *, subscription: WebhookSubscription, event: str, data: dict[str, Any]
) -> WebhookDelivery:
    envelope = build_envelope(event, subscription.org_id, data)
    delivery = WebhookDelivery(
        org_id=subscription.org_id,
        subscription_id=subscription.id,
        event=event,
        payload=envelope,
        attempt=0,
        status="pending",
        next_attempt_at=datetime.utcnow(),
    )
    db.add(delivery)
    await db.flush()
    return delivery


async def deliver_once(
    db: AsyncSession, delivery: WebhookDelivery, *, subscription_secret: str, target_url: str
) -> WebhookDelivery:
    """Attempt a single POST. Updates delivery row with outcome + next_attempt_at."""
    body = json.dumps(delivery.payload, separators=(",", ":")).encode()
    ts = int(datetime.utcnow().timestamp())
    headers = {
        "Content-Type": "application/json",
        "X-HS-Signature": sign_payload(subscription_secret, body, ts),
        "X-HS-Event": delivery.event,
        "X-HS-Delivery-Id": str(delivery.id),
    }
    delivery.attempt = (delivery.attempt or 0) + 1
    delivery.last_attempt_at = datetime.utcnow()
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds()) as client:
            resp = await client.post(target_url, content=body, headers=headers)
        delivery.response_status = resp.status_code
        delivery.response_body_snippet = resp.text[:500] if resp.text else None
        if 200 <= resp.status_code < 300:
            delivery.status = "delivered"
            delivery.delivered_at = datetime.utcnow()
            delivery.next_attempt_at = None
            return delivery
    except httpx.HTTPError as e:
        delivery.response_status = None
        delivery.response_body_snippet = f"transport: {type(e).__name__}"[:500]

    if delivery.attempt >= max_attempts():
        # Exhausted the retry budget — move to the dead-letter state so it is
        # visible to operators and never retried again by the sweep.
        delivery.status = "dead_letter"
        delivery.next_attempt_at = None
    else:
        delivery.status = "pending"
        delivery.next_attempt_at = datetime.utcnow() + _retry_delay(delivery.attempt)
    return delivery


async def dispatch_event(
    db: AsyncSession, *, org_id: uuid.UUID, event: str, data: dict[str, Any]
) -> list[WebhookDelivery]:
    """Enqueue a delivery row for every active subscription that opted into `event`."""
    subs = (await db.execute(
        select(WebhookSubscription).where(
            WebhookSubscription.org_id == org_id,
            WebhookSubscription.active.is_(True),
            WebhookSubscription.deleted_at.is_(None),
        )
    )).scalars().all()
    out: list[WebhookDelivery] = []
    for s in subs:
        events = s.events or []
        if event not in events and "*" not in events:
            continue
        out.append(await enqueue(db, subscription=s, event=event, data=data))
    return out


async def retry_due(db: AsyncSession, *, now: datetime | None = None, limit: int = 100) -> dict[str, int]:
    """Deliver every ``pending`` delivery whose ``next_attempt_at`` is due.

    Joins each delivery to its subscription to recover the encrypted signing
    secret (``secret_ct``) so the payload can be re-signed. Deliveries whose
    subscription no longer has a recoverable secret (created before this
    feature, or already disconnected) are dead-lettered rather than retried
    forever. Returns per-outcome counts.
    """
    now = now or datetime.utcnow()
    rows = (await db.execute(
        select(WebhookDelivery, WebhookSubscription)
        .join(WebhookSubscription, WebhookSubscription.id == WebhookDelivery.subscription_id)
        .where(
            WebhookDelivery.status == "pending",
            WebhookDelivery.next_attempt_at.is_not(None),
            WebhookDelivery.next_attempt_at <= now,
        )
        .order_by(WebhookDelivery.next_attempt_at)
        .limit(limit)
    )).all()

    counts = {"delivered": 0, "pending": 0, "dead_letter": 0}
    for delivery, sub in rows:
        secret = sub.secret_ct
        if not secret or not sub.active or sub.deleted_at is not None:
            delivery.status = "dead_letter"
            delivery.next_attempt_at = None
            delivery.response_body_snippet = "no signing secret / subscription inactive"
            counts["dead_letter"] += 1
            _update_sub_counters(sub, delivered=False, now=now)
            continue
        await deliver_once(db, delivery, subscription_secret=secret, target_url=sub.target_url)
        counts[delivery.status] = counts.get(delivery.status, 0) + 1
        _update_sub_counters(sub, delivered=delivery.status == "delivered", now=now)
    return counts


def _update_sub_counters(sub: WebhookSubscription, *, delivered: bool, now: datetime) -> None:
    if delivered:
        sub.last_success_at = now
        sub.failure_count = 0
    else:
        sub.last_failure_at = now
        sub.failure_count = (sub.failure_count or 0) + 1
