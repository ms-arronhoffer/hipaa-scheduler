"""Unit tests for the first-run super-admin bootstrap (app/bootstrap.py).

No DB: a tiny fake AsyncSession records added rows and replays queued query
results, so we can assert the create/promote/grant decisions in isolation.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x/x")
os.environ.setdefault("JWT_SECRET", "test-secret-please-ignore-32-bytes-min")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "BootstrapPw123!extra")
os.environ.setdefault("PHI_ENCRYPTION_KEY", "test-phi-key-please-ignore-32-bytes-min")


from app import bootstrap
from app.auth.passwords import verify_password
from app.models.organization import Organization
from app.models.user import User


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return list(self._value or [])


class _FakeSession:
    """Replays `execute` results in FIFO order; records add/flush/commit."""

    def __init__(self, results):
        self._results = list(results)
        self.added: list = []
        self.commits = 0
        self.flushes = 0

    async def execute(self, _stmt):
        return _Result(self._results.pop(0))

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1


async def test_creates_platform_org_and_super_admin_on_empty_db(monkeypatch):
    monkeypatch.setattr(bootstrap.settings, "default_admin_email", "root@platform.test")
    monkeypatch.setattr(bootstrap.settings, "super_admin_emails", "")
    # Queries in order: platform org (none), default admin lookup (none).
    db = _FakeSession(results=[None, None])

    await bootstrap.run_bootstrap(db)

    orgs = [o for o in db.added if isinstance(o, Organization)]
    users = [u for u in db.added if isinstance(u, User)]
    assert len(orgs) == 1
    assert orgs[0].slug == bootstrap.PLATFORM_ORG_SLUG
    assert len(users) == 1
    admin = users[0]
    assert admin.email == "root@platform.test"
    assert admin.is_super_admin is True
    assert admin.org_id == orgs[0].id
    assert verify_password(
        bootstrap.settings.default_admin_password.get_secret_value(),
        admin.password_hash,
    )
    assert db.commits == 1


async def test_existing_admin_password_not_overwritten_but_promoted(monkeypatch):
    monkeypatch.setattr(bootstrap.settings, "default_admin_email", "root@platform.test")
    monkeypatch.setattr(bootstrap.settings, "super_admin_emails", "")
    org = Organization(name="Platform", slug=bootstrap.PLATFORM_ORG_SLUG)
    existing = User(
        org_id=org.id,
        email="root@platform.test",
        password_hash="do-not-touch",
        roles=[],
        is_super_admin=False,
    )
    db = _FakeSession(results=[org, existing])

    await bootstrap.run_bootstrap(db)

    assert existing.password_hash == "do-not-touch"  # untouched
    assert existing.is_super_admin is True  # promoted
    assert not any(isinstance(u, User) for u in db.added)  # no new user
    assert db.commits == 1


async def test_grants_super_admin_to_configured_emails(monkeypatch):
    monkeypatch.setattr(bootstrap.settings, "default_admin_email", "root@platform.test")
    monkeypatch.setattr(bootstrap.settings, "super_admin_emails", "boss@clinic.test")
    org = Organization(name="Platform", slug=bootstrap.PLATFORM_ORG_SLUG)
    admin = User(org_id=org.id, email="root@platform.test", is_super_admin=True, roles=[])
    boss = User(org_id=org.id, email="boss@clinic.test", is_super_admin=False, roles=["practice_admin"])
    # org lookup, default-admin lookup, then the SUPER_ADMIN_EMAILS query.
    db = _FakeSession(results=[org, admin, [boss]])

    await bootstrap.run_bootstrap(db)

    assert boss.is_super_admin is True
    assert db.commits == 1
