"""TOTP (RFC 6238) via pyotp + backup codes."""
from __future__ import annotations

import secrets
import hashlib

import pyotp


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str, issuer: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def verify(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def generate_backup_codes(n: int = 10) -> tuple[list[str], list[str]]:
    """Return (plaintext_codes, hashed_codes). Store hashed, show plaintext once."""
    plain = [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(n)]
    hashed = [hashlib.sha256(c.encode()).hexdigest() for c in plain]
    return plain, hashed


def verify_backup_code(candidate: str, hashed: list[str]) -> str | None:
    digest = hashlib.sha256(candidate.encode()).hexdigest()
    return digest if digest in hashed else None
