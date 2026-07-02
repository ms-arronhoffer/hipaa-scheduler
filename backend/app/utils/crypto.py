"""Application-layer envelope encryption for ePHI at rest.

Why this exists
---------------
Postgres TDE / encrypted volumes protect data if a disk is stolen, but they do
nothing against a compromised DB role, a leaked logical backup, or a curious
DBA — the ciphertext is transparently decrypted for anyone who can ``SELECT``.
Encrypting sensitive columns *inside the application* means the plaintext never
touches the database, only the app process holding ``PHI_ENCRYPTION_KEY`` can
read it.

Design
------
- **Primitive.** Fernet (AES-128-CBC + HMAC-SHA256, authenticated) from the
  ``cryptography`` package. Authenticated so tampering is detected on decrypt.
- **Key.** Derived from the dedicated ``PHI_ENCRYPTION_KEY`` secret via
  SHA-256 → 32 bytes → urlsafe-base64 (a valid Fernet key). This key is
  deliberately **separate from ``JWT_SECRET``** so that rotating the signing
  key does not silently make ePHI unrecoverable, and so a JWT-key leak does not
  also expose PHI.
- **Rotation.** ``PHI_ENCRYPTION_KEY`` may be a comma-separated list of secrets.
  The *first* is the primary (used for new encryptions); *all* are accepted for
  decryption via :class:`~cryptography.fernet.MultiFernet`. To rotate: prepend a
  new key, deploy, re-encrypt at rest, then drop the old key.
- **Versioning.** Every ciphertext is prefixed with ``phi:v1:`` so the storage
  format can evolve and so :func:`is_encrypted` can cheaply distinguish
  ciphertext from legacy plaintext during migration.
"""
from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.config import settings

# Bump this if the on-disk format (primitive, framing) ever changes. Old
# versions must keep decrypting until every row is re-encrypted.
_VERSION = "v1"
_PREFIX = f"phi:{_VERSION}:"


def _derive_fernet_key(secret: str) -> bytes:
    """Derive a valid 32-byte urlsafe-base64 Fernet key from an arbitrary secret."""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def _cipher() -> MultiFernet:
    """Build the (cached) MultiFernet from ``PHI_ENCRYPTION_KEY``.

    The first configured key is primary (encrypts); all are tried on decrypt to
    support zero-downtime key rotation.
    """
    raw = settings.phi_encryption_key.get_secret_value()
    secrets = [s.strip() for s in raw.split(",") if s.strip()]
    if not secrets:
        raise RuntimeError(
            "PHI_ENCRYPTION_KEY is empty — refusing to run without a key to "
            "protect ePHI at rest."
        )
    return MultiFernet([Fernet(_derive_fernet_key(s)) for s in secrets])


def is_encrypted(value: str) -> bool:
    """True if ``value`` carries our ciphertext version prefix.

    Used so migrations and the read path can treat pre-encryption rows as
    legacy plaintext instead of failing to decrypt them.
    """
    return isinstance(value, str) and value.startswith(_PREFIX)


def encrypt(plaintext: str) -> str:
    """Encrypt ``plaintext`` and return a version-prefixed ciphertext string."""
    token = _cipher().encrypt(plaintext.encode("utf-8")).decode("ascii")
    return f"{_PREFIX}{token}"


def decrypt(value: str) -> str:
    """Decrypt a version-prefixed ciphertext.

    Legacy fallback: if ``value`` is not encrypted (no prefix), it is returned
    unchanged so rows written before this feature keep reading correctly until
    they are migrated / rewritten.
    """
    if not is_encrypted(value):
        return value
    token = value[len(_PREFIX):].encode("ascii")
    try:
        return _cipher().decrypt(token).decode("utf-8")
    except InvalidToken as exc:  # pragma: no cover - key mismatch / corruption
        raise ValueError(
            "Failed to decrypt PHI value — wrong PHI_ENCRYPTION_KEY or "
            "corrupted ciphertext."
        ) from exc


def rotate(value: str) -> str:
    """Re-encrypt ``value`` under the primary key.

    Encrypted input is re-wrapped with the current primary key (used when
    retiring an old rotation key); legacy plaintext is encrypted for the first
    time. Idempotent-safe to run across a table.
    """
    if is_encrypted(value):
        token = value[len(_PREFIX):].encode("ascii")
        rewrapped = _cipher().rotate(token).decode("ascii")
        return f"{_PREFIX}{rewrapped}"
    return encrypt(value)


__all__ = ["encrypt", "decrypt", "is_encrypted", "rotate"]
