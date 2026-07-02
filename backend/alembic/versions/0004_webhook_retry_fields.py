"""Webhook delivery reconciliation + encrypted signing secret.

Revision ID: 0004_webhook_retry_fields
Revises: 0003_encrypt_totp_secret
Create Date: 2026-07-02

Wires the webhook retry/dead-letter path that the worker relies on:

- ``webhook_subscriptions.secret_ct`` — encrypted-at-rest copy of the shared
  HMAC secret so the background ``webhook_retry`` task can re-sign a payload on
  a later attempt (``secret_hash`` alone is one-way and cannot sign).
- ``webhook_deliveries.response_body_snippet`` / ``last_attempt_at`` — columns
  the delivery service already writes but that had no backing column.

No data backfill: existing subscriptions have no recoverable plaintext secret,
so their in-flight deliveries are dead-lettered by the worker rather than
retried. Rotating a subscription's secret repopulates ``secret_ct``.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_webhook_retry_fields"
down_revision = "0003_encrypt_totp_secret"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("webhook_subscriptions", sa.Column("secret_ct", sa.Text(), nullable=True))
    op.add_column(
        "webhook_deliveries",
        sa.Column("response_body_snippet", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "webhook_deliveries",
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("webhook_deliveries", "last_attempt_at")
    op.drop_column("webhook_deliveries", "response_body_snippet")
    op.drop_column("webhook_subscriptions", "secret_ct")
