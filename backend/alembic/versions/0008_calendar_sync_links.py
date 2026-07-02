"""Calendar sync links (appointment ↔ external event mapping).

Revision ID: 0008_calendar_sync_links
Revises: 0007_notification_retry
Create Date: 2026-07-02

Supports two-way calendar reconciliation: each row maps a local appointment to
the external Google/O365 event created for it, so the reconcile pass can update
or delete the remote copy and detect remote deletions without duplicating.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_calendar_sync_links"
down_revision = "0007_notification_retry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calendar_sync_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_event_id", sa.String(length=512), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=True),
        sa.Column("last_pushed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["calendar_connections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["appointment_id"], ["appointments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "connection_id", "appointment_id", name="uq_sync_link_conn_appt"
        ),
    )
    op.create_index(
        "ix_calendar_sync_links_org_id", "calendar_sync_links", ["org_id"]
    )
    op.create_index(
        "ix_calendar_sync_links_connection_id",
        "calendar_sync_links",
        ["connection_id"],
    )
    op.create_index(
        "ix_calendar_sync_links_appointment_id",
        "calendar_sync_links",
        ["appointment_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_calendar_sync_links_appointment_id", table_name="calendar_sync_links"
    )
    op.drop_index(
        "ix_calendar_sync_links_connection_id", table_name="calendar_sync_links"
    )
    op.drop_index("ix_calendar_sync_links_org_id", table_name="calendar_sync_links")
    op.drop_table("calendar_sync_links")
