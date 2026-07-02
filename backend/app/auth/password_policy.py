"""Password strength, breach, and reuse policy.

Layered checks, cheapest first:

1. **Structural** — minimum length (``settings.password_min_length``) plus a
   character-variety / entropy floor so a long-but-trivial password
   (``aaaaaaaaaaaa``) is rejected.
2. **Blocklist** — a small embedded set of the most common passwords and
   obvious context words (the user's own email/name) that no entropy estimate
   should ever wave through.
3. **Breach (HIBP)** — optional k-anonymity check against
   ``api.pwnedpasswords.com``: only the first 5 chars of the SHA-1 are sent, the
   full hash never leaves the process. Fails **open** (network error / disabled
   / non-production) so an outage can't lock out password changes, but a
   positive hit is always fatal.

No third-party strength library (zxcvbn) is pulled in — the estimator here is
deliberately conservative and dependency-free.
"""
from __future__ import annotations

import hashlib
import logging
import math
import re

import httpx

from app.config import settings

log = logging.getLogger(__name__)


class PasswordPolicyError(ValueError):
    """Raised when a candidate password fails policy. ``reasons`` lists why."""

    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("; ".join(reasons))


# A tiny embedded blocklist. Not exhaustive — HIBP is the real breadth. These
# are the passwords common enough that they must never pass regardless of length
# padding, plus obvious app-context words.
COMMON_PASSWORDS = frozenset({
    "password", "password1", "password123", "passw0rd", "123456", "12345678",
    "123456789", "qwerty", "qwerty123", "letmein", "welcome", "welcome1",
    "admin", "administrator", "iloveyou", "monkey", "dragon", "abc123",
    "111111", "000000", "changeme", "secret", "hipaa", "scheduler",
    "hipaascheduler", "patient", "provider",
})

_CHAR_CLASSES = (
    (r"[a-z]", 26),
    (r"[A-Z]", 26),
    (r"[0-9]", 10),
    (r"[^A-Za-z0-9]", 33),
)

# Rough Shannon-style floor: pool-size ** length must clear this many bits.
MIN_ENTROPY_BITS = 40.0


def _estimate_entropy_bits(password: str) -> float:
    pool = 0
    for pattern, size in _CHAR_CLASSES:
        if re.search(pattern, password):
            pool += size
    if pool == 0:
        return 0.0
    # Penalise long runs of a single repeated character or trivially small
    # unique-character sets (e.g. "ababab...").
    unique = len(set(password))
    effective_len = min(len(password), unique * 2)
    return effective_len * math.log2(pool)


def _context_tokens(user_inputs: list[str] | None) -> set[str]:
    tokens: set[str] = set()
    for raw in user_inputs or []:
        if not raw:
            continue
        for part in re.split(r"[^a-z0-9]+", raw.lower()):
            if len(part) >= 3:
                tokens.add(part)
    return tokens


def validate_strength(password: str, *, user_inputs: list[str] | None = None) -> None:
    """Structural + blocklist checks. Raises :class:`PasswordPolicyError`."""
    reasons: list[str] = []
    if len(password) < settings.password_min_length:
        reasons.append(f"must be at least {settings.password_min_length} characters")
    lowered = password.lower()
    if lowered in COMMON_PASSWORDS:
        reasons.append("is a commonly used password")
    for token in _context_tokens(user_inputs):
        if token in lowered:
            reasons.append("must not contain your name or email")
            break
    if _estimate_entropy_bits(password) < MIN_ENTROPY_BITS:
        reasons.append("is not complex enough — mix upper/lower case, digits, and symbols")
    if reasons:
        raise PasswordPolicyError(reasons)


async def hibp_breach_count(password: str) -> int:
    """Return how many times ``password`` appears in HIBP, 0 if unknown/clean.

    k-anonymity: sends only the first 5 hex chars of the SHA-1 hash. Fails open
    (returns 0) on any error, when disabled, or outside production.
    """
    if not settings.password_hibp_enabled or settings.app_env != "production":
        return 0
    digest = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()  # noqa: S324 - HIBP protocol requires SHA-1
    prefix, suffix = digest[:5], digest[5:]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"https://api.pwnedpasswords.com/range/{prefix}",
                headers={"Add-Padding": "true"},
            )
        if resp.status_code != 200:
            return 0
        return _parse_hibp_response(resp.text, suffix)
    except httpx.HTTPError as exc:
        log.info("hibp_check_unavailable", extra={"err": type(exc).__name__})
        return 0


def _parse_hibp_response(body: str, suffix: str) -> int:
    """Parse the ``SUFFIX:COUNT`` range-API body for our suffix. Pure/testable."""
    for line in body.splitlines():
        if ":" not in line:
            continue
        hash_suffix, _, count = line.partition(":")
        if hash_suffix.strip().upper() == suffix.upper():
            try:
                return int(count.strip())
            except ValueError:
                return 0
    return 0


async def enforce(
    password: str,
    *,
    user_inputs: list[str] | None = None,
    check_breach: bool = True,
) -> None:
    """Full policy gate: structural + blocklist + (optional) breach check."""
    validate_strength(password, user_inputs=user_inputs)
    if check_breach:
        count = await hibp_breach_count(password)
        if count > 0:
            raise PasswordPolicyError(
                ["has appeared in a known data breach and cannot be used"]
            )
