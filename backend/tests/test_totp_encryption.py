"""Unit tests for TOTP-secret encryption at rest (P3).

Proves the ``EncryptedString`` swap on ``User.totp_secret`` and
``PatientAccount.totp_secret`` results in ciphertext (not the raw base32 MFA
secret) actually landing in the database, while ORM reads decrypt transparently
so ``totp_service.verify`` keeps working. A leaked TOTP secret would let an
attacker mint valid MFA codes, so this must never sit in the DB as plaintext.
"""
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x/x")
os.environ.setdefault("JWT_SECRET", "test-secret-please-ignore-32-bytes-min")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "test-admin-pw")
os.environ.setdefault("PHI_ENCRYPTION_KEY", "test-phi-key-please-ignore-32-bytes-min")

import sqlalchemy as sa

from app.utils import crypto
from app.models.types import EncryptedString
from app.models.patient import PatientAccount
from app.models.user import User


def _column_type(model, name):
    return model.__table__.c[name].type


class TestColumnUsesEncryptedString:
    def test_user_totp_secret_is_encrypted(self):
        assert isinstance(_column_type(User, "totp_secret"), EncryptedString)

    def test_patient_account_totp_secret_is_encrypted(self):
        assert isinstance(_column_type(PatientAccount, "totp_secret"), EncryptedString)


class TestStoredValueIsEncrypted:
    """Round-trip a TOTP secret through a real (SQLite) column."""

    def _run_for(self, model, extra_cols):
        engine = sa.create_engine("sqlite://")
        md = sa.MetaData()
        cols = [sa.Column("id", sa.Integer, primary_key=True)]
        cols += extra_cols
        cols.append(sa.Column("totp_secret", model.__table__.c["totp_secret"].type, nullable=True))
        probe = sa.Table("probe", md, *cols)
        md.create_all(engine)

        secret = "JBSWY3DPEHPK3PXP"  # canonical base32 TOTP secret
        with engine.begin() as conn:
            conn.execute(probe.insert().values(id=1, totp_secret=secret))

            raw = conn.execute(sa.text("SELECT totp_secret FROM probe WHERE id=1")).scalar_one()
            assert raw != secret
            assert secret not in raw
            assert crypto.is_encrypted(raw)

            via_type = conn.execute(
                sa.select(probe.c.totp_secret).where(probe.c.id == 1)
            ).scalar_one()
            assert via_type == secret

    def test_user_totp_secret_encrypted_in_db(self):
        self._run_for(User, [])

    def test_patient_account_totp_secret_encrypted_in_db(self):
        self._run_for(PatientAccount, [])

    def test_null_totp_secret_stays_null(self):
        engine = sa.create_engine("sqlite://")
        md = sa.MetaData()
        probe = sa.Table(
            "probe", md,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("totp_secret", User.__table__.c["totp_secret"].type, nullable=True),
        )
        md.create_all(engine)
        with engine.begin() as conn:
            conn.execute(probe.insert().values(id=1, totp_secret=None))
            raw = conn.execute(sa.text("SELECT totp_secret FROM probe WHERE id=1")).scalar_one()
            assert raw is None
