"""SQLAlchemy column type that transparently encrypts ePHI at rest.

Swap a plaintext ``String`` column for ``EncryptedString`` and every write is
encrypted before it hits the database while every read is decrypted back to
plaintext in the ORM — application code is unchanged.

The database column is ``Text`` because Fernet ciphertext (base64, plus IV +
HMAC framing and our version prefix) is materially longer than the plaintext;
using ``Text`` avoids per-column length bookkeeping as data grows.

Legacy fallback: :func:`app.utils.crypto.decrypt` returns un-prefixed values
unchanged, so rows written before a column was encrypted keep reading and get
re-encrypted the next time they are written.
"""
from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.utils import crypto


class EncryptedString(TypeDecorator):
    """Encrypt on write, decrypt on read. ``None`` passes through untouched."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return crypto.encrypt(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return crypto.decrypt(value)


__all__ = ["EncryptedString"]
