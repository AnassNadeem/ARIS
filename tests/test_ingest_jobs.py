"""Unit tests for background Postgres ingest jobs (no FastF1 / DB)."""

from __future__ import annotations

import threading
import time

from backend.ingest_jobs import ensure_session_ingested, reset_ingest_jobs_for_tests


def test_already_ingested_returns_ingested(monkeypatch):
    reset_ingest_jobs_for_tests()
    monkeypatch.setattr("aris.io.db.fetch_race_session_id", lambda year, round_no: 42)
    assert ensure_session_ingested(2024, 15, "R") == "INGESTED"


def test_missing_starts_one_job(monkeypatch):
    reset_ingest_jobs_for_tests()
    calls: list[int] = []
    started = threading.Event()
    release = threading.Event()

    def fake_ingest(year, event, session_type, **kwargs):
        calls.append(1)
        started.set()
        release.wait(timeout=5)
        return {"sessions": 1, "drivers": 1, "laps": 1}

    monkeypatch.setattr("aris.io.db.fetch_race_session_id", lambda year, round_no: None)
    monkeypatch.setattr("aris.io.ingest.ingest_session", fake_ingest)

    assert ensure_session_ingested(2024, 15, "R") == "INGESTING"
    assert started.wait(timeout=2)
    assert ensure_session_ingested(2024, 15, "R") == "INGESTING"
    release.set()
    deadline = time.time() + 2
    while time.time() < deadline and len(calls) != 1:
        time.sleep(0.05)
    assert len(calls) == 1


def test_db_error_is_unavailable(monkeypatch):
    reset_ingest_jobs_for_tests()

    def boom(year, round_no):
        raise RuntimeError("no db")

    monkeypatch.setattr("aris.io.db.fetch_race_session_id", boom)
    assert ensure_session_ingested(2024, 15, "R") == "UNAVAILABLE"
