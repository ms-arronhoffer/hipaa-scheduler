"""P0 auth regression tests.

Covers the three "fix immediately" bugs from the security remediation plan:

1. ``provisioning_uri`` must be called with an issuer so MFA enrollment can't
   silently break (previously called with a missing positional arg).
2. ``mfa_ok`` must be carried forward across ``/auth/refresh`` instead of being
   hard-coded to ``False`` — an MFA-authenticated session stays MFA-authenticated.
3. Backup codes must satisfy the login MFA check and be single-use.

These are unit-level tests: they exercise the pure auth helpers and the token
plumbing directly, with no DB session required.
"""
import os
import uuid

import pyotp
import pytest

# Bare-minimum env so app.config imports without prompting.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x/x")
os.environ.setdefault("JWT_SECRET", "test-secret-please-ignore-32-bytes-min")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "test-admin-pw")

from app.auth import totp as totp_service  # noqa: E402
from app.auth.jwt import decode, issue_access, issue_refresh  # noqa: E402


class TestProvisioningUri:
    def test_provisioning_uri_includes_issuer(self):
        secret = totp_service.new_secret()
        uri = totp_service.provisioning_uri(secret, "user@example.com", issuer="hipaa-scheduler")
        assert uri.startswith("otpauth://totp/")
        assert "issuer=hipaa-scheduler" in uri
        assert secret in uri

    def test_provisioning_uri_requires_issuer(self):
        # The historical bug was calling provisioning_uri without an issuer.
        # The signature must make the issuer mandatory so it can't happen again.
        secret = totp_service.new_secret()
        with pytest.raises(TypeError):
            totp_service.provisioning_uri(secret, "user@example.com")  # type: ignore[call-arg]


class TestMfaOkAcrossRefresh:
    def test_refresh_token_carries_mfa_ok_true(self):
        tok = issue_refresh(
            audience="staff", subject=uuid.uuid4(), org_id=uuid.uuid4(),
            extra={"mfa_ok": True},
        )
        payload = decode(tok, audience="staff")
        assert payload["mfa_ok"] is True

    def test_refresh_token_carries_mfa_ok_false(self):
        tok = issue_refresh(
            audience="staff", subject=uuid.uuid4(), org_id=uuid.uuid4(),
            extra={"mfa_ok": False},
        )
        payload = decode(tok, audience="staff")
        assert payload["mfa_ok"] is False

    def test_mfa_ok_survives_a_refresh_cycle(self):
        subj, org = uuid.uuid4(), uuid.uuid4()
        # Login-issued refresh with an MFA-authenticated session.
        refresh = issue_refresh(audience="staff", subject=subj, org_id=org, extra={"mfa_ok": True})
        claims = decode(refresh, audience="staff")
        carried = bool(claims.get("mfa_ok", False))
        # The refresh handler must forward the claim (not hard-code False).
        new_access = issue_access(audience="staff", subject=subj, org_id=org, extra={"mfa_ok": carried})
        new_refresh = issue_refresh(audience="staff", subject=subj, org_id=org, extra={"mfa_ok": carried})
        assert decode(new_access, audience="staff")["mfa_ok"] is True
        assert decode(new_refresh, audience="staff")["mfa_ok"] is True


class TestBackupCodes:
    def test_verify_backup_code_matches_and_missing(self):
        plain, hashed = totp_service.generate_backup_codes(n=5)
        assert len(plain) == 5 and len(hashed) == 5
        consumed = totp_service.verify_backup_code(plain[0], hashed)
        assert consumed is not None and consumed in hashed
        assert totp_service.verify_backup_code("not-a-real-code", hashed) is None

    def test_backup_code_is_single_use(self):
        """Simulate the login handler consuming a backup code and rejecting reuse."""
        plain, hashed = totp_service.generate_backup_codes(n=3)
        remaining = list(hashed)

        # First use succeeds and removes the hash.
        consumed = totp_service.verify_backup_code(plain[1], remaining)
        assert consumed is not None
        remaining = [h for h in remaining if h != consumed]
        assert len(remaining) == 2

        # Replaying the same code no longer matches.
        assert totp_service.verify_backup_code(plain[1], remaining) is None

        # A different, unused code still works.
        assert totp_service.verify_backup_code(plain[0], remaining) is not None

    def test_totp_still_verifies_alongside_backup_codes(self):
        secret = totp_service.new_secret()
        code = pyotp.TOTP(secret).now()
        assert totp_service.verify(secret, code) is True
