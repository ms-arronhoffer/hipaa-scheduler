"""Audience separation is a security-critical invariant: a patient JWT must
never decode successfully against staff-audience guards, and vice-versa.
"""
import os
import uuid

import jwt as pyjwt
import pytest

# Bare-minimum env so app.config imports without prompting.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x/x")
os.environ.setdefault("JWT_SECRET", "test-secret-please-ignore-32-bytes-min")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "test-admin-pw")

from app.auth.jwt import decode, issue_access, issue_refresh  # noqa: E402


class TestAudienceSeparation:
    def test_staff_token_decodes_as_staff(self):
        tok = issue_access(audience="staff", subject=uuid.uuid4(), org_id=uuid.uuid4())
        payload = decode(tok, audience="staff")
        assert payload["aud"] == "staff"
        assert payload["typ"] == "access"

    def test_patient_token_rejected_by_staff_audience(self):
        tok = issue_access(audience="patient", subject=uuid.uuid4(), org_id=uuid.uuid4())
        with pytest.raises(pyjwt.InvalidAudienceError):
            decode(tok, audience="staff")

    def test_staff_token_rejected_by_patient_audience(self):
        tok = issue_access(audience="staff", subject=uuid.uuid4(), org_id=uuid.uuid4())
        with pytest.raises(pyjwt.InvalidAudienceError):
            decode(tok, audience="patient")

    def test_refresh_carries_jti_and_typ(self):
        tok = issue_refresh(audience="staff", subject=uuid.uuid4(), org_id=uuid.uuid4())
        payload = decode(tok, audience="staff")
        assert payload["typ"] == "refresh"
        assert "jti" in payload and len(payload["jti"]) == 32

    def test_wrong_secret_rejected(self):
        tok = issue_access(audience="staff", subject=uuid.uuid4(), org_id=uuid.uuid4())
        with pytest.raises(pyjwt.InvalidSignatureError):
            pyjwt.decode(tok, "wrong-secret", algorithms=["HS256"],
                         audience="staff", issuer="hipaa-scheduler")

    def test_extras_included_in_payload(self):
        tok = issue_access(
            audience="staff", subject=uuid.uuid4(), org_id=uuid.uuid4(),
            extra={"roles": ["provider"], "mfa": True},
        )
        payload = decode(tok, audience="staff")
        assert payload["roles"] == ["provider"]
        assert payload["mfa"] is True
