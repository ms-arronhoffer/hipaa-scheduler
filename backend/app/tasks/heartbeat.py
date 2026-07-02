"""Worker liveness + job-queue heartbeat.

The standalone APScheduler worker has no HTTP surface of its own, so process
liveness and job-run freshness are published to a small JSON file that the API
can read for its ``/worker/health`` probe. Each task calls :func:`beat` after it
runs, recording the wall-clock time and the last outcome of that job. The file
is written atomically (temp + rename) so a concurrent reader never sees a
partial document.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Any

from app.config import settings

log = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict[str, Any]:
    try:
        with open(settings.worker_heartbeat_path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _atomic_write(payload: dict[str, Any]) -> None:
    path = settings.worker_heartbeat_path
    directory = os.path.dirname(path) or "."
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".hb-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    except OSError as exc:  # pragma: no cover - disk/permission edge
        log.warning("worker.heartbeat_write_failed", extra={"err": str(exc)})


def beat(job: str, *, ok: bool = True, detail: dict[str, Any] | None = None) -> None:
    """Record that ``job`` just ran. Merges into the shared heartbeat file."""
    doc = _load()
    doc["updated_at"] = _now_iso()
    jobs = doc.setdefault("jobs", {})
    jobs[job] = {"at": _now_iso(), "ok": bool(ok), "detail": detail or {}}
    _atomic_write(doc)


def read_status() -> dict[str, Any]:
    """Return a health summary for the API probe.

    ``healthy`` is False when the heartbeat is missing, unparseable, older than
    ``worker_heartbeat_max_age_sec``, or when any recorded job last failed.
    """
    doc = _load()
    updated_at = doc.get("updated_at")
    if not updated_at:
        return {"healthy": False, "reason": "no_heartbeat", "jobs": {}}
    try:
        ts = datetime.fromisoformat(updated_at)
    except ValueError:
        return {"healthy": False, "reason": "bad_heartbeat", "jobs": {}}
    age = (datetime.now(timezone.utc) - ts).total_seconds()
    stale = age > settings.worker_heartbeat_max_age_sec
    jobs = doc.get("jobs", {})
    any_failed = any(not j.get("ok", True) for j in jobs.values())
    healthy = not stale and not any_failed
    reason = "ok"
    if stale:
        reason = "stale"
    elif any_failed:
        reason = "job_failed"
    return {
        "healthy": healthy,
        "reason": reason,
        "age_seconds": int(age),
        "updated_at": updated_at,
        "jobs": jobs,
    }
