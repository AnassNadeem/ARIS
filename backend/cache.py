"""Disk cache (OpenF1 / Jolpica TTLs) plus FastF1 pickle cache enable."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from backend.paths import ROOT

T = TypeVar("T")

TTL_STANDINGS = 60 * 60
TTL_LIVE = 15
TTL_SCHEDULE = 60 * 60 * 24
TTL_METADATA = 60 * 60 * 24
TTL_WEATHER_LIVE = 60
TTL_FORECAST = 60 * 15
TTL_OPENF1 = 60 * 30

_CACHE = None


def cache_dir() -> Path:
    existing = ROOT / "fastf1_cache"
    if existing.exists():
        return existing
    path = ROOT / "cache" / "fastf1"
    path.mkdir(parents=True, exist_ok=True)
    return path


def disk_dir() -> Path:
    path = ROOT / "cache" / "disk"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_disk():
    global _CACHE
    if _CACHE is None:
        from diskcache import Cache

        _CACHE = Cache(str(disk_dir()))
    return _CACHE


def enable_fastf1_cache() -> Path:
    import fastf1

    path = cache_dir()
    path.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(path))
    return path


def cached(key: str, ttl: int, factory: Callable[[], T]) -> T:
    store = get_disk()
    hit = store.get(key)
    if hit is not None:
        return hit  # type: ignore[return-value]
    value = factory()
    store.set(key, value, expire=ttl)
    return value
