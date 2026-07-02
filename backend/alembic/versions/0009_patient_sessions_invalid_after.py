"""Patient portal "sign out everywhere" support.

Revision ID: 0009_patient_sessions_invalid_after
Revises: 0008_calendar_sync_links
Create Date: 2026-07-02

Adds ``patient_accounts.sessions_invalid_after`` so a patient can revoke all of
their existing portal sessions at once (mirrors ``users.sessions_invalid_after``).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_patient_sessions_invalid_after"
down_revision = "0008_calendar_sync_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patient_accounts",
        sa.Column("sessions_invalid_after", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("patient_accounts", "sessions_invalid_after")
