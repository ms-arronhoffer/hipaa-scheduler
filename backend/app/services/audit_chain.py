"""Tamper-evident hash chaining for ``ActivityLog``.

Each audit row is linked to the previous row *within the same org* by a SHA-256
hash chain::

    entry_hash = SHA256( prev_hash + "\\n" + canonical_payload(row) )

``prev_hash`` of the first row per org is the fixed ``GENESIS`` value. Because
every hash commits to the one before it, silently editing or deleting a row
breaks every subsequent ``entry_hash`` — :func:`verify_chain` re-walks the chain
and reports the first break.

Assignment happens at flush time (:func:`assign_chain`, wired from a
``before_flush`` listener in :mod:`app.database`). The listener runs inside the
flush's synchronous connection, so it can read the current chain head with a
normal ``session.execute`` even under an async engine.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Iterable

from sqlalchemy import select

from app.models.activity_log import ActivityLog

GENESIS = "0" * 64


def _norm(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def canonical_payload(row: ActivityLog) -> str:
    """Deterministic serialization of the immutable fields a row commits to."""
    payload = {
        "id": _norm(row.id),
        "org_id": _norm(row.org_id),
        "seq": row.seq,
        "actor_type": row.actor_type,
        "actor_id": _norm(row.actor_id),
        "actor_email": row.actor_email,
        "entity_type": row.entity_type,
        "entity_id": _norm(row.entity_id),
        "action": row.action,
        "changes": row.changes or {},
        "phi_accessed": bool(row.phi_accessed),
        "created_at": _norm(row.created_at),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_entry_hash(prev_hash: str, row: ActivityLog) -> str:
    material = f"{prev_hash}\n{canonical_payload(row)}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _chain_head(session, org_id: uuid.UUID) -> tuple[int, str]:
    """Return (last_seq, last_entry_hash) for an org, or (0, GENESIS) if empty."""
    row = session.execute(
        select(ActivityLog.seq, ActivityLog.entry_hash)
        .where(ActivityLog.org_id == org_id, ActivityLog.entry_hash.is_not(None))
        .order_by(ActivityLog.seq.desc())
        .limit(1)
    ).first()
    if row is None or row.seq is None:
        return 0, GENESIS
    return int(row.seq), row.entry_hash


def assign_chain(session) -> None:
    """Assign seq/prev_hash/entry_hash to all pending new ActivityLog rows.

    Called from ``before_flush``. Groups new rows by org, seeds each group from
    the org's current chain head, and links them in insertion order.
    """
    pending = [obj for obj in session.new if isinstance(obj, ActivityLog) and obj.entry_hash is None]
    if not pending:
        return
    by_org: dict[uuid.UUID, list[ActivityLog]] = {}
    for obj in pending:
        by_org.setdefault(obj.org_id, []).append(obj)

    for org_id, rows in by_org.items():
        last_seq, prev = _chain_head(session, org_id)
        for row in rows:
            last_seq += 1
            row.seq = last_seq
            row.prev_hash = prev
            row.entry_hash = compute_entry_hash(prev, row)
            prev = row.entry_hash


def verify_chain(rows: Iterable[ActivityLog]) -> dict[str, Any]:
    """Re-walk an ordered (by seq) iterable of rows and detect the first break.

    Returns ``{"ok": bool, "checked": int, "broken_at": seq|None}``.
    """
    prev = GENESIS
    checked = 0
    ordered = sorted(rows, key=lambda r: (r.seq if r.seq is not None else 0))
    for row in ordered:
        expected = compute_entry_hash(prev, row)
        checked += 1
        if row.prev_hash != prev or row.entry_hash != expected:
            return {"ok": False, "checked": checked, "broken_at": row.seq}
        prev = row.entry_hash
    return {"ok": True, "checked": checked, "broken_at": None}
