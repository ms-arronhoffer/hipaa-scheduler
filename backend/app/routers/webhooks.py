"""WebhookSubscription CRUD + delivery log.

Secret is generated server-side, sha256-hashed at rest, and returned ONCE
in the creation response. Receivers verify HMAC using X-HS-Signature.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import require_role
from app.models.activity_log import ActivityLog
from app.models.webhook import WebhookDelivery, WebhookSubscription
from app.schemas.integrations import (
    WebhookDeliveryOut,
    WebhookSubscriptionCreate,
    WebhookSubscriptionCreated,
    WebhookSubscriptionOut,
    WebhookSubscriptionUpdate,
)


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


VALID_EVENTS = {
    "appointment.created", "appointment.updated", "appointment.canceled",
    "appointment.no_show", "appointment.checked_in",
    "patient.created", "patient.updated",
    "intake.submitted", "waitlist.filled",
    "*",  # subscribe-all
}


def _validate_events(events: list[str] | None) -> None:
    if events is None:
        return
    for e in events:
        if e not in VALID_EVENTS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unsupported event {e}")


def _generate_secret() -> tuple[str, str]:
    plain = f"whsec_{secrets.token_urlsafe(32)}"
    digest = hashlib.sha256(plain.encode()).hexdigest()
    return plain, digest


@router.get("", response_model=list[WebhookSubscriptionOut])
async def list_subscriptions(
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookSubscription]:
    rows = (await db.execute(
        select(WebhookSubscription).where(
            WebhookSubscription.org_id == p.org_id,
            WebhookSubscription.deleted_at.is_(None),
        ).order_by(WebhookSubscription.created_at.desc())
    )).scalars().all()
    return list(rows)


@router.post("", response_model=WebhookSubscriptionCreated, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    body: WebhookSubscriptionCreate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> WebhookSubscriptionCreated:
    _validate_events(body.events)
    plain, digest = _generate_secret()
    row = WebhookSubscription(
        org_id=p.org_id,
        name=body.name,
        target_url=str(body.target_url),
        events=body.events,
        secret_hash=digest,
        active=body.active,
    )
    db.add(row)
    await db.flush()
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="webhook_subscription", entity_id=row.id, action="created",
        changes={"target_url": str(body.target_url), "events": body.events},
    ))
    return WebhookSubscriptionCreated(
        id=row.id, secret=plain, target_url=str(body.target_url), events=body.events,
    )


@router.patch("/{sub_id}", response_model=WebhookSubscriptionOut)
async def update_subscription(
    sub_id: uuid.UUID,
    body: WebhookSubscriptionUpdate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> WebhookSubscription:
    row = (await db.execute(
        select(WebhookSubscription).where(
            WebhookSubscription.id == sub_id,
            WebhookSubscription.org_id == p.org_id,
            WebhookSubscription.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    data = body.model_dump(exclude_unset=True)
    _validate_events(data.get("events"))
    if "target_url" in data and data["target_url"] is not None:
        data["target_url"] = str(data["target_url"])
    for k, v in data.items():
        setattr(row, k, v)
    return row


@router.post("/{sub_id}/rotate-secret", response_model=WebhookSubscriptionCreated)
async def rotate_secret(
    sub_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> WebhookSubscriptionCreated:
    row = (await db.execute(
        select(WebhookSubscription).where(
            WebhookSubscription.id == sub_id,
            WebhookSubscription.org_id == p.org_id,
            WebhookSubscription.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    plain, digest = _generate_secret()
    row.secret_hash = digest
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="webhook_subscription", entity_id=row.id, action="secret_rotated",
        changes={},
    ))
    return WebhookSubscriptionCreated(
        id=row.id, secret=plain, target_url=row.target_url, events=row.events,
    )


@router.delete("/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    sub_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(
        select(WebhookSubscription).where(
            WebhookSubscription.id == sub_id,
            WebhookSubscription.org_id == p.org_id,
            WebhookSubscription.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    row.deleted_at = datetime.utcnow()
    row.active = False


@router.get("/{sub_id}/deliveries", response_model=list[WebhookDeliveryOut])
async def list_deliveries(
    sub_id: uuid.UUID,
    status_filter: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookDelivery]:
    sub = (await db.execute(
        select(WebhookSubscription.id).where(
            WebhookSubscription.id == sub_id,
            WebhookSubscription.org_id == p.org_id,
        )
    )).scalar_one_or_none()
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    stmt = select(WebhookDelivery).where(
        WebhookDelivery.subscription_id == sub_id,
        WebhookDelivery.org_id == p.org_id,
    )
    if status_filter is not None:
        stmt = stmt.where(WebhookDelivery.status == status_filter)
    stmt = stmt.order_by(WebhookDelivery.created_at.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


@router.post("/deliveries/{delivery_id}/retry", response_model=WebhookDeliveryOut)
async def retry_delivery(
    delivery_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> WebhookDelivery:
    row = (await db.execute(
        select(WebhookDelivery).where(
            WebhookDelivery.id == delivery_id,
            WebhookDelivery.org_id == p.org_id,
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    # Reschedule immediately; worker picks it up.
    row.status = "pending"
    row.next_attempt_at = datetime.utcnow()
    return row
