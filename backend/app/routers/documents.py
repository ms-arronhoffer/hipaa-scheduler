"""Document metadata records (patient uploads).

Object storage upload happens out-of-band (presigned S3 URL, handled by a
future upload endpoint); this router stores only metadata + sha256 for
integrity verification.
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
from app.models.patient_records import Document
from app.schemas.patient_records import DocumentCreate, DocumentOut


router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    patient_id: uuid.UUID | None = None,
    kind: str | None = None,
    p: Principal = Depends(phi_log("document", "listed")),
    db: AsyncSession = Depends(get_db),
) -> list[Document]:
    stmt = select(Document).where(Document.org_id == p.org_id, Document.deleted_at.is_(None))
    if patient_id is not None:
        await ensure_patient_in_org(db, patient_id, p.org_id)
        stmt = stmt.where(Document.patient_id == patient_id)
    if kind is not None:
        stmt = stmt.where(Document.kind == kind)
    stmt = stmt.order_by(Document.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def create_document(
    body: DocumentCreate,
    p: Principal = Depends(require_role("practice_admin", "front_desk", "provider")),
    db: AsyncSession = Depends(get_db),
) -> Document:
    await ensure_patient_in_org(db, body.patient_id, p.org_id)
    row = Document(
        org_id=p.org_id,
        patient_id=body.patient_id,
        kind=body.kind,
        filename=body.filename,
        mime_type=body.mime_type,
        size_bytes=body.size_bytes,
        storage_key=body.storage_key,
        sha256=body.sha256,
        uploaded_by_actor_type="user",
        uploaded_by_actor_id=p.subject_id,
    )
    db.add(row)
    await db.flush()
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="document", entity_id=row.id, action="created",
        changes={"patient_id": str(body.patient_id), "kind": body.kind, "sha256": body.sha256},
        phi_accessed=True,
    ))
    return row


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    p: Principal = Depends(phi_log("document", "viewed")),
    db: AsyncSession = Depends(get_db),
) -> Document:
    row = (await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.org_id == p.org_id,
            Document.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return row


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    p: Principal = Depends(require_role("practice_admin", "front_desk")),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.org_id == p.org_id,
            Document.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    row.deleted_at = datetime.utcnow()
    db.add(ActivityLog(
        org_id=p.org_id, actor_type="user", actor_id=p.subject_id, actor_email=p.email,
        entity_type="document", entity_id=row.id, action="deleted",
        changes={"filename": row.filename}, phi_accessed=True,
    ))
