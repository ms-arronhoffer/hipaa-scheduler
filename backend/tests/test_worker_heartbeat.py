"""Worker heartbeat / liveness status logic (unit-tier, tmp-file backed)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.tasks import heartbeat


@pytest.fixture
def hb_path(tmp_path, monkeypatch):
    path = tmp_path / "hb.json"
    monkeypatch.setattr(heartbeat.settings, "worker_heartbeat_path", str(path))
    monkeypatch.setattr(heartbeat.settings, "worker_heartbeat_max_age_sec", 900)
    return path


class TestHeartbeat:
    def test_missing_file_is_unhealthy(self, hb_path):
        status = heartbeat.read_status()
        assert status["healthy"] is False
        assert status["reason"] == "no_heartbeat"

    def test_beat_then_healthy(self, hb_path):
        heartbeat.beat("reminder_sweep", ok=True, detail={"created": 3})
        status = heartbeat.read_status()
        assert status["healthy"] is True
        assert status["reason"] == "ok"
        assert status["jobs"]["reminder_sweep"]["ok"] is True
        assert status["jobs"]["reminder_sweep"]["detail"] == {"created": 3}

    def test_failed_job_is_unhealthy(self, hb_path):
        heartbeat.beat("webhook_retry", ok=False, detail={"error": "Boom"})
        status = heartbeat.read_status()
        assert status["healthy"] is False
        assert status["reason"] == "job_failed"

    def test_stale_heartbeat_is_unhealthy(self, hb_path, monkeypatch):
        heartbeat.beat("scheduler", ok=True)
        monkeypatch.setattr(heartbeat.settings, "worker_heartbeat_max_age_sec", 0)
        # age > 0 immediately -> stale
        status = heartbeat.read_status()
        assert status["healthy"] is False
        assert status["reason"] == "stale"

    def test_multiple_jobs_merge(self, hb_path):
        heartbeat.beat("reminder_sweep", ok=True)
        heartbeat.beat("webhook_retry", ok=True)
        status = heartbeat.read_status()
        assert set(status["jobs"]) == {"reminder_sweep", "webhook_retry"}
