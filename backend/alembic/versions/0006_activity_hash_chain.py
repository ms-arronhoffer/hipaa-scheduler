"""Tamper-evident audit chain columns on activity_log.

Revision ID: 0006_activity_hash_chain
Revises: 0005_password_lifecycle
Create Date: 2026-07-02

Adds the per-org hash-chain columns populated by app.services.audit_chain:

- ``seq`` — monotonically increasing per-org sequence number.
- ``prev_hash`` — entry_hash of the previous row in the org's chain (GENESIS
  for the first row).
- ``entry_hash`` — sha256(prev_hash + canonical(row)); linking these makes any
  post-hoc edit or deletion detectable by re-walking the chain.

Existing rows keep NULL chain columns (they predate chaining and are excluded
from verification via ``entry_hash IS NOT NULL``).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_activity_hash_chain"
down_revision = "0005_password_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("activity_log", sa.Column("seq", sa.BigInteger(), nullable=True))
    op.add_column("activity_log", sa.Column("prev_hash", sa.String(length=64), nullable=True))
    op.add_column("activity_log", sa.Column("entry_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_activity_org_seq", "activity_log", ["org_id", "seq"])


def downgrade() -> None:
    op.drop_index("ix_activity_org_seq", table_name="activity_log")
    op.drop_column("activity_log", "entry_hash")
    op.drop_column("activity_log", "prev_hash")
    op.drop_column("activity_log", "seq")
