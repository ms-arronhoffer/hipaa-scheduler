"""Tests for the IDOR / cross-tenant static check (``tools/idor_lint``).

Two jobs:
1. Guard the real tree — ``scan()`` must stay empty, so any future
   ``select(<OrgScoped>)`` that forgets its ``org_id`` predicate fails CI.
2. Prove the checker actually bites (it isn't vacuously green) and that the
   ``# idor-safe`` suppression marker works, using synthetic source files.
"""
import textwrap
from pathlib import Path

from tools import idor_lint


def test_codebase_has_no_unscoped_org_queries():
    findings = idor_lint.scan()
    assert findings == [], "IDOR check failed:\n" + "\n".join(str(f) for f in findings)


def test_org_scoped_models_discovered():
    models = idor_lint.org_scoped_models()
    # Sanity: the discovery actually found the well-known org-scoped tables.
    assert {"Patient", "Appointment", "User"} <= models


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "sample_router.py"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_flags_select_without_org_filter(tmp_path):
    path = _write(tmp_path, """
        async def handler(p, db):
            return (await db.execute(select(Patient))).scalars().all()
    """)
    findings = idor_lint.scan_file(path, {"Patient"})
    assert len(findings) == 1
    assert findings[0].model == "Patient"
    assert findings[0].function == "handler"


def test_org_filtered_select_is_clean(tmp_path):
    path = _write(tmp_path, """
        async def handler(p, db):
            stmt = select(Patient).where(Patient.org_id == p.org_id)
            return (await db.execute(stmt)).scalars().all()
    """)
    assert idor_lint.scan_file(path, {"Patient"}) == []


def test_idor_safe_marker_suppresses(tmp_path):
    path = _write(tmp_path, """
        async def handler(p, db):
            # idor-safe: scoped by signed token, not org
            stmt = select(Patient).where(Patient.id == p.subject_id)
            return (await db.execute(stmt)).scalars().all()
    """)
    assert idor_lint.scan_file(path, {"Patient"}) == []


def test_non_org_scoped_model_ignored(tmp_path):
    path = _write(tmp_path, """
        async def handler(p, db):
            return (await db.execute(select(AuthLockout))).scalars().all()
    """)
    # AuthLockout is not org-scoped, so it is never a cross-tenant concern.
    assert idor_lint.scan_file(path, {"Patient"}) == []
