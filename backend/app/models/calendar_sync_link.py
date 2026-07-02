"""CalendarSyncLink — maps a local appointment to the external calendar event
created for it, so the two-way reconcile pass can update/delete the remote copy
and detect drift (a remote deletion) without re-creating duplicates.

One row per (connection, appointment). No PHI is stored here: only opaque
provider identifiers and a hash of the last pushed payload used to decide
whether an update is required.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScoped, TimestampMixin, UUIDPk


class CalendarSyncLink(Base, UUIDPk, OrgScoped, TimestampMixin):
    __tablename__ = "calendar_sync_links"
    __table_args__ = (
        UniqueConstraint("connection_id", "appointment_id", name="uq_sync_link_conn_appt"),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("calendar_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Opaque provider event id (Google eventId / Graph event id). Not PHI.
    external_event_id: Mapped[str] = mapped_column(String(512), nullable=False)
    # sha256 of the last payload pushed — lets reconcile skip unchanged events.
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_pushed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
