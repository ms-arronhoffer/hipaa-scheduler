"""NotificationTemplate CRUD + NotificationLog read.

Templates are Jinja2 sandbox-rendered by notification_service. Whitelisted
variables only — PHI (name, dob, MRN) is never interpolated into subject/body.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import ensure_patient_in_org, require_role
from app.models.activity_log import ActivityLog
from app.models.notification import (
    NOTIFICATION_CHANNELS,
    NotificationLog,
    NotificationTemplate,
)
from app.models.patient import Patient
from app.schemas.common import ORMModel
from app.schemas.notification import (
    NotificationLogOut,
    TemplateCreate,
    TemplateOut,
    TemplateUpdate,
)


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/templates", response_model=list[TemplateOut])
async def list_templates(
    channel: str | None = None,
    event: str | None = None,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationTemplate]:
    stmt = select(NotificationTemplate).where(
        NotificationTemplate.org_id == p.org_id,
        NotificationTemplate.deleted_at.is_(None),
    )
    if channel is not None:
        stmt = stmt.where(NotificationTemplate.channel == channel)
    if event is not None:
        stmt = stmt.where(NotificationTemplate.event == event)
    stmt = stmt.order_by(NotificationTemplate.event, NotificationTemplate.name)
    return list((await db.execute(stmt)).scalars().all())


@router.post("/templates", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: TemplateCreate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> NotificationTemplate:
    if body.channel not in NOTIFICATION_CHANNELS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"channel must be one of {NOTIFICATION_CHANNELS}")
    row = NotificationTemplate(org_id=p.org_id, **body.model_dump())
    db.add(row)
    await db.flush()
    return row


@router.patch("/templates/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: uuid.UUID,
    body: TemplateUpdate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> NotificationTemplate:
    row = (await db.execute(
        select(NotificationTemplate).where(
            NotificationTemplate.id == template_id,
            NotificationTemplate.org_id == p.org_id,
            NotificationTemplate.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    return row


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(
        select(NotificationTemplate).where(
            NotificationTemplate.id == template_id,
            NotificationTemplate.org_id == p.org_id,
            NotificationTemplate.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    row.deleted_at = datetime.utcnow()


class SMSConsentOut(ORMModel):
    patient_id: uuid.UUID
    sms_opt_in_at: datetime | None


@router.post("/sms/opt-in/{patient_id}", response_model=SMSConsentOut)
async def sms_opt_in(
    patient_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider")),
    db: AsyncSession = Depends(get_db),
) -> SMSConsentOut:
    """Record affirmative SMS consent for a patient (double opt-in confirmation)."""
    await ensure_patient_in_org(db, patient_id, p.org_id)
    patient = (await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.org_id == p.org_id)
    )).scalar_one()
    if patient.sms_opt_in_at is None:
        patient.sms_opt_in_at = datetime.now(timezone.utc)
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="patient", entity_id=patient_id, action="sms_opt_in",
        changes={"sms_opt_in_at": patient.sms_opt_in_at.isoformat()},
    ))
    return SMSConsentOut(patient_id=patient_id, sms_opt_in_at=patient.sms_opt_in_at)


@router.post("/sms/opt-out/{patient_id}", response_model=SMSConsentOut)
async def sms_opt_out(
    patient_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider")),
    db: AsyncSession = Depends(get_db),
) -> SMSConsentOut:
    """Revoke SMS consent for a patient (clears the opt-in timestamp)."""
    await ensure_patient_in_org(db, patient_id, p.org_id)
    patient = (await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.org_id == p.org_id)
    )).scalar_one()
    patient.sms_opt_in_at = None
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="patient", entity_id=patient_id, action="sms_opt_out",
        changes={},
    ))
    return SMSConsentOut(patient_id=patient_id, sms_opt_in_at=None)


@router.get("/log", response_model=list[NotificationLogOut])
async def list_notification_log(
    channel: str | None = None,
    status_filter: str | None = None,
    patient_id: uuid.UUID | None = None,
    appointment_id: uuid.UUID | None = None,
    limit: int = 200,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationLog]:
    stmt = select(NotificationLog).where(NotificationLog.org_id == p.org_id)
    if channel is not None:
        stmt = stmt.where(NotificationLog.channel == channel)
    if status_filter is not None:
        stmt = stmt.where(NotificationLog.status == status_filter)
    if patient_id is not None:
        await ensure_patient_in_org(db, patient_id, p.org_id)
        stmt = stmt.where(NotificationLog.patient_id == patient_id)
    if appointment_id is not None:
        stmt = stmt.where(NotificationLog.appointment_id == appointment_id)
    stmt = stmt.order_by(NotificationLog.created_at.desc()).limit(min(limit, 500))
    return list((await db.execute(stmt)).scalars().all())
