"""Unit tests for the tamper-evident audit hash chain (no DB)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models.activity_log import ActivityLog
from app.services import audit_chain


def _row(seq=None, org_id=None, action="created", created_at=None, **kw):
    r = ActivityLog(
        org_id=org_id or uuid.uuid4(),
        actor_type="user",
        actor_id=uuid.uuid4(),
        actor_email="a@example.com",
        entity_type="patient",
        entity_id=uuid.uuid4(),
        action=action,
        changes=kw.get("changes", {"k": "v"}),
        phi_accessed=kw.get("phi_accessed", False),
    )
    r.id = kw.get("id", uuid.uuid4())
    r.created_at = created_at or datetime(2026, 7, 2, 12, 0, 0, tzinfo=timezone.utc)
    r.seq = seq
    return r


def _chain(rows, org_id):
    """Link rows in order starting from GENESIS (mimics assign_chain)."""
    prev = audit_chain.GENESIS
    seq = 0
    for r in rows:
        r.org_id = org_id
        seq += 1
        r.seq = seq
        r.prev_hash = prev
        r.entry_hash = audit_chain.compute_entry_hash(prev, r)
        prev = r.entry_hash
    return rows


def test_canonical_payload_deterministic():
    r = _row(seq=1)
    assert audit_chain.canonical_payload(r) == audit_chain.canonical_payload(r)


def test_entry_hash_is_hex_sha256():
    r = _row(seq=1)
    h = audit_chain.compute_entry_hash(audit_chain.GENESIS, r)
    assert len(h) == 64
    int(h, 16)  # valid hex


def test_entry_hash_depends_on_prev():
    r = _row(seq=1)
    h1 = audit_chain.compute_entry_hash(audit_chain.GENESIS, r)
    h2 = audit_chain.compute_entry_hash("f" * 64, r)
    assert h1 != h2


def test_verify_valid_chain():
    org = uuid.uuid4()
    rows = _chain([_row() for _ in range(4)], org)
    result = audit_chain.verify_chain(rows)
    assert result == {"ok": True, "checked": 4, "broken_at": None}


def test_verify_detects_mutated_field():
    org = uuid.uuid4()
    rows = _chain([_row() for _ in range(4)], org)
    rows[2].action = "deleted"  # tamper after hashing
    result = audit_chain.verify_chain(rows)
    assert result["ok"] is False
    assert result["broken_at"] == 3


def test_verify_detects_deleted_row():
    org = uuid.uuid4()
    rows = _chain([_row() for _ in range(4)], org)
    remaining = [rows[0], rows[1], rows[3]]  # drop seq 3
    result = audit_chain.verify_chain(remaining)
    assert result["ok"] is False
    assert result["broken_at"] == 4


def test_verify_empty_chain_ok():
    assert audit_chain.verify_chain([]) == {"ok": True, "checked": 0, "broken_at": None}


def test_first_row_uses_genesis_prev():
    org = uuid.uuid4()
    rows = _chain([_row()], org)
    assert rows[0].prev_hash == audit_chain.GENESIS
