"""API key generation and hashing.

Key format: `hs_<24-byte-urlsafe>`; only sha256 hash is persisted.
"""
from __future__ import annotations

import hashlib
import secrets


PREFIX = "hs_"


def generate() -> tuple[str, str, str]:
    """Return (plaintext_key, short_prefix, sha256_hash)."""
    raw = secrets.token_urlsafe(24)
    plaintext = f"{PREFIX}{raw}"
    short_prefix = plaintext[:11]  # "hs_" + 8 chars, for UI display
    digest = hashlib.sha256(plaintext.encode()).hexdigest()
    return plaintext, short_prefix, digest


def hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()
