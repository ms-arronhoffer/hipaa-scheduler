"""pytest config for the HIPAA scheduler backend.

Two test tiers:

- **unit** (default) — pure-function tests that hit no I/O. Run in seconds and
  are safe in CI everywhere. Import services directly and pass in ORM objects
  hand-constructed with the columns each test needs (no DB session).
- **integration** — marked `@pytest.mark.integration`. Require a live Postgres
  reachable at `TEST_DATABASE_URL`. Skipped by default; run with
  `pytest -m integration`.

Property-based tests (Hypothesis) live under `tests/property/` and count as
unit tests — no DB required.
"""
import asyncio
import os
from collections.abc import AsyncIterator

import pytest

# Ensure required secrets have test defaults before any test module imports
# app.config (which validates env on import). Individual test modules also set
# these via os.environ.setdefault; doing it here as well guarantees any test
# that touches config — including the PHI crypto path — can boot.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x/x")
os.environ.setdefault("JWT_SECRET", "test-secret-please-ignore-32-bytes-min")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "test-admin-pw")
os.environ.setdefault("PHI_ENCRYPTION_KEY", "test-phi-key-please-ignore-32-bytes-min")


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless -m integration explicitly requested."""
    if config.getoption("-m") == "integration":
        return
    skip_int = pytest.mark.skip(reason="integration test — run with -m integration")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_int)


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped loop so integration fixtures can reuse it."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_db_url() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://hs_admin:devpass@localhost:5432/hipaa_scheduler_test",
    )
