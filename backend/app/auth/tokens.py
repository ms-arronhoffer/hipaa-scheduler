"""Short-lived token helpers: magic link + one-click confirm/cancel.

Plaintext token is emailed to the patient; only sha256(token) is persisted.
The consume path re-hashes the presented token and looks it up.
"""
from __future__ import annotations

import hashlib
import secrets


def new_token() -> tuple[str, str]:
    """Return (plaintext_url_token, sha256_hash)."""
    tok = secrets.token_urlsafe(32)
    return tok, hashlib.sha256(tok.encode()).hexdigest()


def hash_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()
