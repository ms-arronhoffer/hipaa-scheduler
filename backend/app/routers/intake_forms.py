"""IntakeForm builder + IntakeSubmission storage.

Forms are versioned: any schema change bumps `version`. Submissions store
`form_version` so history is stable across evolution.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.database import get_db
from app.guards.deps import ensure_patient_in_org, phi_log, require_role
from app.models.activity_log import ActivityLog
from app.models.intake_form import IntakeForm, IntakeSubmission
from app.schemas.intake_form import (
    IntakeFormCreate,
    IntakeFormOut,
    IntakeFormUpdate,
    IntakeSubmissionCreate,
    IntakeSubmissionOut,
)


router = APIRouter(prefix="/intake", tags=["intake"])


ALLOWED_FIELD_TYPES = {
    "text", "textarea", "date", "select", "multi",
    "signature", "scale", "file", "consent-block", "number", "boolean",
}


def _validate_schema(schema: dict) -> None:
    """Structural check on the form JSON — validators/showIf are opaque here."""
    if not isinstance(schema, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "schema must be object")
    pages = schema.get("pages")
    if pages is not None and not isinstance(pages, list):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "schema.pages must be list")
    for page in pages or []:
        for section in page.get("sections", []) or []:
            for field in section.get("fields", []) or []:
                if not field.get("key"):
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "field missing key")
                if field.get("type") not in ALLOWED_FIELD_TYPES:
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST,
                        f"field {field.get('key')} has unsupported type",
                    )


def _validate_submission(schema: dict, answers: dict) -> None:
    keys: dict[str, dict] = {}
    for page in schema.get("pages", []) or []:
        for section in page.get("sections", []) or []:
            for field in section.get("fields", []) or []:
                keys[field["key"]] = field
    for key, field in keys.items():
        if field.get("required") and key not in answers:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"missing required field {key}")


# ---- form definitions ---------------------------------------------------------


@router.get("/forms", response_model=list[IntakeFormOut])
async def list_forms(
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> list[IntakeForm]:
    rows = (await db.execute(
        select(IntakeForm).where(
            IntakeForm.org_id == p.org_id, IntakeForm.deleted_at.is_(None)
        ).order_by(IntakeForm.name)
    )).scalars().all()
    return list(rows)


@router.post("/forms", response_model=IntakeFormOut, status_code=status.HTTP_201_CREATED)
async def create_form(
    body: IntakeFormCreate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> IntakeForm:
    _validate_schema(body.schema_)
    row = IntakeForm(
        org_id=p.org_id,
        name=body.name,
        version=1,
        schema=body.schema_,
        active=body.active,
    )
    db.add(row)
    await db.flush()
    return row


@router.get("/forms/{form_id}", response_model=IntakeFormOut)
async def get_form(
    form_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider", "billing")),
    db: AsyncSession = Depends(get_db),
) -> IntakeForm:
    row = (await db.execute(
        select(IntakeForm).where(
            IntakeForm.id == form_id,
            IntakeForm.org_id == p.org_id,
            IntakeForm.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return row


@router.patch("/forms/{form_id}", response_model=IntakeFormOut)
async def update_form(
    form_id: uuid.UUID,
    body: IntakeFormUpdate,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> IntakeForm:
    row = (await db.execute(
        select(IntakeForm).where(
            IntakeForm.id == form_id,
            IntakeForm.org_id == p.org_id,
            IntakeForm.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    data = body.model_dump(exclude_unset=True, by_alias=False)
    if "schema_" in data and data["schema_"] is not None:
        _validate_schema(data["schema_"])
        row.schema = data.pop("schema_")
        row.version = (row.version or 1) + 1
    else:
        data.pop("schema_", None)
    for k, v in data.items():
        setattr(row, k, v)
    return row


@router.delete("/forms/{form_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_form(
    form_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(
        select(IntakeForm).where(
            IntakeForm.id == form_id,
            IntakeForm.org_id == p.org_id,
            IntakeForm.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    row.deleted_at = datetime.utcnow()


# ---- submissions --------------------------------------------------------------


@router.post("/submissions", response_model=IntakeSubmissionOut, status_code=status.HTTP_201_CREATED)
async def create_submission(
    body: IntakeSubmissionCreate,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider")),
    db: AsyncSession = Depends(get_db),
) -> IntakeSubmission:
    form = (await db.execute(
        select(IntakeForm).where(
            IntakeForm.id == body.form_id,
            IntakeForm.org_id == p.org_id,
            IntakeForm.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if form is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "form not found")
    await ensure_patient_in_org(db, body.patient_id, p.org_id)
    _validate_submission(form.schema or {}, body.answers or {})
    row = IntakeSubmission(
        org_id=p.org_id,
        form_id=form.id,
        form_version=form.version,
        patient_id=body.patient_id,
        appointment_id=body.appointment_id,
        answers=body.answers,
        signed_at=datetime.utcnow() if body.signature_name else None,
        signature_name=body.signature_name,
    )
    db.add(row)
    await db.flush()
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="intake_submission", entity_id=row.id, action="created",
        changes={"form_id": str(form.id), "patient_id": str(body.patient_id)},
        phi_accessed=True,
    ))
    return row


@router.get("/submissions", response_model=list[IntakeSubmissionOut])
async def list_submissions(
    patient_id: uuid.UUID | None = None,
    form_id: uuid.UUID | None = None,
    p: Principal = Depends(phi_log("intake_submission", "listed")),
    db: AsyncSession = Depends(get_db),
) -> list[IntakeSubmission]:
    stmt = select(IntakeSubmission).where(
        IntakeSubmission.org_id == p.org_id, IntakeSubmission.deleted_at.is_(None)
    )
    if patient_id is not None:
        await ensure_patient_in_org(db, patient_id, p.org_id)
        stmt = stmt.where(IntakeSubmission.patient_id == patient_id)
    if form_id is not None:
        stmt = stmt.where(IntakeSubmission.form_id == form_id)
    stmt = stmt.order_by(IntakeSubmission.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


@router.get("/submissions/{submission_id}", response_model=IntakeSubmissionOut)
async def get_submission(
    submission_id: uuid.UUID,
    p: Principal = Depends(phi_log("intake_submission", "viewed")),
    db: AsyncSession = Depends(get_db),
) -> IntakeSubmission:
    row = (await db.execute(
        select(IntakeSubmission).where(
            IntakeSubmission.id == submission_id,
            IntakeSubmission.org_id == p.org_id,
            IntakeSubmission.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return row
