"""Notification delivery-failure retry columns.

Revision ID: 0007_notification_retry
Revises: 0006_activity_hash_chain
Create Date: 2026-07-02

Adds delivery-failure retry bookkeeping to ``notification_log``:

- ``attempts`` — number of send attempts made so far.
- ``next_retry_at`` — when a failed row becomes eligible for the retry sweep
  (NULL once delivered or permanently exhausted).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_notification_retry"
down_revision = "0006_activity_hash_chain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_log",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "notification_log",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_notification_retry_due",
        "notification_log",
        ["status", "next_retry_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_notification_retry_due", table_name="notification_log")
    op.drop_column("notification_log", "next_retry_at")
    op.drop_column("notification_log", "attempts")
