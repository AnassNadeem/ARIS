"""Startup warmup: calendar, drivers, hot packs into RAM (no FastF1)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from backend.cache import cache, get_disk, get_memory_then_disk, put_both
from backend.main import HOT_REPLAY_PACKS, _cached_sync, warmup_startup


def test_hot_packs_include_zandvoort_and_monaco():
    assert (2025, 15, "R") in HOT_REPLAY_PACKS
    assert (2024, 8, "R") in HOT_REPLAY_PACKS
    assert 5 <= len(HOT_REPLAY_PACKS) <= 10


def test_warmup_startup_fills_calendar_drivers_and_counts_hot_packs(monkeypatch):
    from backend import calendar, live, main, standings

    years_cal: list[int] = []
    years_drv: list[int] = []
    hydrated: list[tuple[int, int, str]] = []

    def fake_calendar(year: int, as_of=None, **_k):
        years_cal.append(year)
        return SimpleNamespace(year=year, rounds=[1, 2])

    def fake_drivers(year: int):
        years_drv.append(year)
        return SimpleNamespace(drivers=["VER", "NOR"])

    def fake_key(year: int, rnd: int, stype: str) -> int:
        return year * 1000 + rnd

    def fake_hydrate(key, year, rnd, stype, log_hits=True):
        hydrated.append((year, rnd, stype))
        # Pretend disk has Zandvoort 2025 and Monaco 2024 only.
        if (year, rnd, stype) in {(2025, 15, "R"), (2024, 8, "R")}:
            return {"year": year, "laps": [1]}, False, True
        return None, False, False

    monkeypatch.setattr(calendar, "get_calendar", fake_calendar)
    monkeypatch.setattr(standings, "get_drivers", fake_drivers)
    monkeypatch.setattr(live, "synthetic_session_key", fake_key)
    monkeypatch.setattr(live, "hydrate_replay_pack_cache", fake_hydrate)
    monkeypatch.setattr(main, "put_both", lambda *a, **k: None)

    result = warmup_startup()
    assert years_cal == [2024, 2025, 2026]
    assert years_drv == [2024, 2025, 2026]
    assert hydrated == list(HOT_REPLAY_PACKS)
    assert result == {"calendars": 3, "drivers": 3, "hot_packs": 2}


def test_get_memory_then_disk_promotes_disk_into_ram():
    key = "warmup_promote_key"
    cache.delete(key)
    try:
        get_disk().pop(key, default=None)
    except Exception:
        pass
    put_both(key, {"ok": True}, 3600)
    cache.delete(key)
    assert cache.get(key, 3600) is None
    hit = get_memory_then_disk(key, 3600)
    assert hit == {"ok": True}
    assert cache.get(key, 3600) == {"ok": True}
    cache.delete(key)
    try:
        get_disk().pop(key, default=None)
    except Exception:
        pass


def test_cached_sync_uses_disk_without_calling_factory():
    key = "warmup_http_disk_key"
    cache.delete(key)
    try:
        get_disk().pop(key, default=None)
    except Exception:
        pass
    put_both(key, {"from": "disk"}, 3600)
    cache.delete(key)
    called: list[int] = []

    def factory():
        called.append(1)
        return {"from": "factory"}

    result = asyncio.run(_cached_sync(key, 3600, factory))
    assert result == {"from": "disk"}
    assert called == []
    cache.delete(key)
    try:
        get_disk().pop(key, default=None)
    except Exception:
        pass
