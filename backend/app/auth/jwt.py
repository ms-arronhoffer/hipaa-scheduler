"""JWT issue/verify for staff and patient audiences.

Two audiences: `staff` and `patient`. Guards check the audience so a patient JWT
can never satisfy a staff endpoint and vice-versa.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt

from app.config import get_settings

Audience = Literal["staff", "patient"]

ALG = "HS256"
ACCESS_TTL_MIN = 15
REFRESH_TTL_DAYS = 7


def _now() -> datetime:
    return datetime.now(timezone.utc)


def issue_access(
    *,
    audience: Audience,
    subject: uuid.UUID,
    org_id: uuid.UUID | None,
    extra: dict[str, Any] | None = None,
    ttl_min: int = ACCESS_TTL_MIN,
) -> str:
    s = get_settings()
    now = _now()
    payload: dict[str, Any] = {
        "iss": s.jwt_issuer,
        "aud": audience,
        "sub": str(subject),
        "org_id": str(org_id) if org_id else None,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_min)).timestamp()),
        "typ": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, s.jwt_secret.get_secret_value(), algorithm=ALG)


def issue_refresh(
    *,
    audience: Audience,
    subject: uuid.UUID,
    org_id: uuid.UUID | None,
    extra: dict[str, Any] | None = None,
) -> str:
    s = get_settings()
    now = _now()
    payload = {
        "iss": s.jwt_issuer,
        "aud": audience,
        "sub": str(subject),
        "org_id": str(org_id) if org_id else None,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=REFRESH_TTL_DAYS)).timestamp()),
        "typ": "refresh",
        "jti": uuid.uuid4().hex,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, s.jwt_secret.get_secret_value(), algorithm=ALG)


def decode(token: str, audience: Audience) -> dict[str, Any]:
    s = get_settings()
    return jwt.decode(
        token,
        s.jwt_secret.get_secret_value(),
        algorithms=[ALG],
        audience=audience,
        issuer=s.jwt_issuer,
    )
