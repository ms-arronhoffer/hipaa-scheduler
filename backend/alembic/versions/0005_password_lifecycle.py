"""Password lifecycle: expiry, history, reset tokens, session revocation.

Revision ID: 0005_password_lifecycle
Revises: 0004_webhook_retry_fields
Create Date: 2026-07-02

Adds the staff password policy/lifecycle plumbing:

- ``users.password_changed_at`` / ``password_expires_at`` — rotation + expiry.
- ``users.sessions_invalid_after`` — "sign out everywhere" cutoff enforced in
  the principal resolver.
- ``password_history`` — prior bcrypt hashes for reuse prevention.
- ``password_reset_tokens`` — single-use, time-boxed reset tokens (sha256 only).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_password_lifecycle"
down_revision = "0004_webhook_retry_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("password_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("sessions_invalid_after", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "password_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_password_history_user_id", "password_history", ["user_id"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"])


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_token_hash", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_password_history_user_id", table_name="password_history")
    op.drop_table("password_history")
    op.drop_column("users", "sessions_invalid_after")
    op.drop_column("users", "password_expires_at")
    op.drop_column("users", "password_changed_at")
