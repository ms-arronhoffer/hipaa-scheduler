"""Unit tests for application-layer ePHI encryption (P2).

Covers the round-trip, the legacy-plaintext read fallback, versioned framing,
key rotation, and the SQLAlchemy ``EncryptedString`` bind/result behaviour that
guarantees ciphertext (not plaintext) is what actually reaches the database.
"""
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x/x")
os.environ.setdefault("JWT_SECRET", "test-secret-please-ignore-32-bytes-min")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "test-admin-pw")
os.environ.setdefault("PHI_ENCRYPTION_KEY", "test-phi-key-please-ignore-32-bytes-min")

import pytest

from app.utils import crypto
from app.models.types import EncryptedString


class TestRoundTrip:
    def test_encrypt_decrypt_roundtrip(self):
        pt = "Patient reports intermittent chest pain since Tuesday."
        ct = crypto.encrypt(pt)
        assert crypto.decrypt(ct) == pt

    def test_ciphertext_differs_from_plaintext(self):
        pt = "MRN A12345"
        ct = crypto.encrypt(pt)
        assert ct != pt
        assert pt not in ct  # plaintext must not be embedded in the token

    def test_unicode_roundtrip(self):
        pt = "José — allergy: penicillin 💊"
        assert crypto.decrypt(crypto.encrypt(pt)) == pt

    def test_nondeterministic(self):
        # Fernet embeds a random IV, so two encryptions of the same plaintext
        # differ — this prevents equality-based inference on the ciphertext.
        pt = "same value"
        assert crypto.encrypt(pt) != crypto.encrypt(pt)


class TestVersioning:
    def test_ciphertext_carries_version_prefix(self):
        ct = crypto.encrypt("x")
        assert ct.startswith("phi:v1:")
        assert crypto.is_encrypted(ct) is True

    def test_plaintext_is_not_flagged_encrypted(self):
        assert crypto.is_encrypted("plain member id") is False
        assert crypto.is_encrypted("") is False


class TestLegacyFallback:
    def test_decrypt_passes_through_legacy_plaintext(self):
        # Rows written before encryption have no prefix; they must read as-is.
        assert crypto.decrypt("legacy-plaintext-mrn") == "legacy-plaintext-mrn"

    def test_rotate_encrypts_legacy_plaintext(self):
        out = crypto.rotate("legacy")
        assert crypto.is_encrypted(out)
        assert crypto.decrypt(out) == "legacy"


class TestTamperDetection:
    def test_tampered_ciphertext_rejected(self):
        ct = crypto.encrypt("sensitive")
        tampered = ct[:-2] + ("AA" if not ct.endswith("AA") else "BB")
        with pytest.raises(ValueError):
            crypto.decrypt(tampered)


class TestRotation:
    def test_multiple_keys_decrypt_old_ciphertext(self, monkeypatch):
        # Encrypt under an "old" single key.
        crypto._cipher.cache_clear()
        monkeypatch.setattr(
            crypto.settings, "phi_encryption_key",
            _Secret("old-key-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
        )
        ct = crypto.encrypt("secret")

        # Now a new primary key is prepended; the old key remains for decrypt.
        crypto._cipher.cache_clear()
        monkeypatch.setattr(
            crypto.settings, "phi_encryption_key",
            _Secret("new-key-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb,"
                    "old-key-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
        )
        assert crypto.decrypt(ct) == "secret"

        crypto._cipher.cache_clear()  # don't leak the patched cipher to other tests


class TestEncryptedStringType:
    def test_bind_param_encrypts(self):
        t = EncryptedString()
        bound = t.process_bind_param("chest pain", dialect=None)
        assert crypto.is_encrypted(bound)
        assert bound != "chest pain"

    def test_result_value_decrypts(self):
        t = EncryptedString()
        stored = t.process_bind_param("chest pain", dialect=None)
        assert t.process_result_value(stored, dialect=None) == "chest pain"

    def test_none_passthrough(self):
        t = EncryptedString()
        assert t.process_bind_param(None, dialect=None) is None
        assert t.process_result_value(None, dialect=None) is None

    def test_result_value_reads_legacy_plaintext(self):
        t = EncryptedString()
        # Simulate a pre-encryption row: raw plaintext already in the column.
        assert t.process_result_value("old-plaintext", dialect=None) == "old-plaintext"


class _Secret:
    """Minimal SecretStr stand-in for monkeypatching settings in tests."""

    def __init__(self, val: str):
        self._val = val

    def get_secret_value(self) -> str:
        return self._val


class TestDbLayerCiphertext:
    """Prove that what lands in the database is ciphertext, not plaintext.

    Uses an in-memory SQLite table (no external I/O, still a unit test) with an
    ``EncryptedString`` column. Reading the column back through the type yields
    plaintext; reading the raw bytes with a plain text() query shows the
    stored value is encrypted and does not contain the plaintext.
    """

    def _table(self):
        import sqlalchemy as sa

        md = sa.MetaData()
        return sa.Table(
            "phi_probe", md,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("secret", EncryptedString, nullable=True),
        )

    def test_stored_value_is_encrypted(self):
        import sqlalchemy as sa

        engine = sa.create_engine("sqlite://")
        t = self._table()
        t.metadata.create_all(engine)
        pt = "Member ID XYZ-99887766"
        with engine.begin() as conn:
            conn.execute(t.insert().values(id=1, secret=pt))

            # Raw read (no type processing) — must be ciphertext, not plaintext.
            raw = conn.execute(sa.text("SELECT secret FROM phi_probe WHERE id=1")).scalar_one()
            assert raw != pt
            assert pt not in raw
            assert crypto.is_encrypted(raw)

            # Typed read — decrypts transparently back to plaintext.
            via_type = conn.execute(sa.select(t.c.secret).where(t.c.id == 1)).scalar_one()
            assert via_type == pt

    def test_null_stays_null(self):
        import sqlalchemy as sa

        engine = sa.create_engine("sqlite://")
        t = self._table()
        t.metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(t.insert().values(id=1, secret=None))
            raw = conn.execute(sa.text("SELECT secret FROM phi_probe WHERE id=1")).scalar_one()
            assert raw is None
