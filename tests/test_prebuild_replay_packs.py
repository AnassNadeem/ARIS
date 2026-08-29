"""Prebuild CLI listing — no FastF1."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prebuild_replay_packs.py"


def _load_prebuild():
    spec = importlib.util.spec_from_file_location("prebuild_replay_packs", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_prebuild_script_exists():
    assert _SCRIPT.is_file()


def test_iter_prebuild_jobs_marks_completed_and_upcoming(monkeypatch):
    mod = _load_prebuild()
    rounds = [
        SimpleNamespace(round_number=1, name="Bahrain", circuit_name="BIC", status="COMPLETED"),
        SimpleNamespace(round_number=16, name="Italy", circuit_name="Monza", status="UPCOMING"),
        SimpleNamespace(round_number=24, name="Abu Dhabi", circuit_name="Yas", status="CANCELLED"),
    ]

    monkeypatch.setattr(
        "backend.calendar.get_calendar",
        lambda year, *a, **k: SimpleNamespace(rounds=rounds if year == 2026 else []),
    )

    def _sessions(year, rnd, as_of=None):
        status = "COMPLETED" if rnd == 1 else "UPCOMING"
        return SimpleNamespace(sessions=[SimpleNamespace(session_type="R", status=status)])

    monkeypatch.setattr("backend.calendar.get_round_sessions", _sessions)

    jobs = mod.iter_prebuild_jobs((2026,))
    by_round = {j.round_number: j.status for j in jobs}
    assert by_round[1] == "COMPLETED"
    assert by_round[16] == "UPCOMING"
    assert by_round[24] == "CANCELLED"


def test_dry_run_lists_without_building(monkeypatch):
    import asyncio

    mod = _load_prebuild()
    monkeypatch.setattr(
        mod,
        "iter_prebuild_jobs",
        lambda *a, **k: [
            mod.PrebuildJob(2025, 15, "R", "Netherlands", "COMPLETED"),
            mod.PrebuildJob(2026, 16, "R", "Italy", "UPCOMING"),
        ],
    )

    async def boom(*_a, **_k):
        raise AssertionError("dry-run must not build packs")

    monkeypatch.setattr(mod, "prebuild_one", boom)
    jobs = mod.iter_prebuild_jobs()
    code = asyncio.run(mod.run_prebuild(jobs, force=False, dry_run=True))
    assert code == 0
