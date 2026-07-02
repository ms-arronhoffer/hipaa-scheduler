"""Encrypt ePHI at rest (application-layer).

Revision ID: 0002_encrypt_phi_at_rest
Revises: 0001_initial
Create Date: 2026-07-02

Widens the columns now backed by ``EncryptedString`` to ``Text`` (Fernet
ciphertext is longer than plaintext) and encrypts any pre-existing plaintext in
place so nothing is left readable at the database layer.

Scope (P2, first increment): free-text / non-indexed ePHI only —
``appointments.notes``, ``insurance_policies.member_id`` /
``group_number`` — plus the already-modeled OAuth token columns on
``calendar_connections``. Indexed / unique PHI (patient email, MRN, name, DOB,
TOTP secret) is deferred; it needs blind-index/HMAC design tracked in
``docs/hipaa/backlog.md``.

Requires ``PHI_ENCRYPTION_KEY`` to be set in the environment when run.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.utils import crypto

revision = "0002_encrypt_phi_at_rest"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


# (table, column, nullable) for columns that move from plaintext String to
# encrypted Text. `nullable` reflects the existing schema so alter_column does
# not accidentally change nullability.
_ENCRYPTED_COLUMNS = [
    ("appointments", "notes", True),
    ("insurance_policies", "member_id", False),
    ("insurance_policies", "group_number", True),
    ("calendar_connections", "access_token_ct", False),
    ("calendar_connections", "refresh_token_ct", True),
]


def _transform_rows(table: str, column: str, fn) -> None:
    """Apply ``fn`` to every non-null value of ``table.column`` in place."""
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(f"SELECT id, {column} AS val FROM {table} WHERE {column} IS NOT NULL")
    ).fetchall()
    for row in rows:
        new_val = fn(row.val)
        if new_val != row.val:
            bind.execute(
                sa.text(f"UPDATE {table} SET {column} = :val WHERE id = :id"),
                {"val": new_val, "id": row.id},
            )


def upgrade() -> None:
    # 1. Widen to Text so ciphertext fits regardless of plaintext length.
    for table, column, nullable in _ENCRYPTED_COLUMNS:
        op.alter_column(table, column, type_=sa.Text(), existing_nullable=nullable)

    # 2. Encrypt existing plaintext in place (skip anything already encrypted).
    for table, column, _nullable in _ENCRYPTED_COLUMNS:
        _transform_rows(
            table,
            column,
            lambda v: v if crypto.is_encrypted(v) else crypto.encrypt(v),
        )


def downgrade() -> None:
    # 1. Decrypt back to plaintext so the narrower columns can hold the values.
    for table, column, _nullable in _ENCRYPTED_COLUMNS:
        _transform_rows(table, column, crypto.decrypt)

    # 2. Restore the original column widths.
    _original_lengths = {
        ("appointments", "notes"): 2000,
        ("insurance_policies", "member_id"): 60,
        ("insurance_policies", "group_number"): 60,
        ("calendar_connections", "access_token_ct"): 4000,
        ("calendar_connections", "refresh_token_ct"): 4000,
    }
    for table, column, nullable in _ENCRYPTED_COLUMNS:
        op.alter_column(
            table, column,
            type_=sa.String(_original_lengths[(table, column)]),
            existing_nullable=nullable,
        )
