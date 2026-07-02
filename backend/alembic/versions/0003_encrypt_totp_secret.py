"""Encrypt TOTP secrets at rest (application-layer).

Revision ID: 0003_encrypt_totp_secret
Revises: 0002_encrypt_phi_at_rest
Create Date: 2026-07-02

Second encryption increment (P3). Completes the ``EncryptedString`` swap for the
MFA shared secrets that P2 deliberately deferred:

- ``users.totp_secret`` (staff MFA)
- ``patient_accounts.totp_secret`` (patient-portal MFA)

These are the backlog "do next" columns — non-indexed, read on every MFA verify,
so a plain ``EncryptedString`` swap works with no blind-index design needed. The
columns widen from ``String(64)`` to ``Text`` because Fernet ciphertext is
longer than the raw base32 secret, and any pre-existing plaintext is encrypted
in place so nothing MFA-bypassing is left readable at the database layer.

Requires ``PHI_ENCRYPTION_KEY`` to be set in the environment when run.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.utils import crypto

revision = "0003_encrypt_totp_secret"
down_revision = "0002_encrypt_phi_at_rest"
branch_labels = None
depends_on = None


# (table, column, nullable) for columns moving from plaintext String to
# encrypted Text. Both TOTP secret columns are nullable.
_ENCRYPTED_COLUMNS = [
    ("users", "totp_secret", True),
    ("patient_accounts", "totp_secret", True),
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

    # 2. Restore the original column width.
    for table, column, nullable in _ENCRYPTED_COLUMNS:
        op.alter_column(
            table, column,
            type_=sa.String(64),
            existing_nullable=nullable,
        )
