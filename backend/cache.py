"""Disk cache (OpenF1 / Jolpica TTLs), in-memory TTL cache, and FastF1 pickle cache."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional, TypeVar

from backend.paths import ROOT

T = TypeVar("T")

TTL_STANDINGS = 60 * 60
TTL_LIVE = 15
TTL_SCHEDULE = 60 * 60 * 24
TTL_METADATA = 60 * 60 * 24
TTL_WEATHER_LIVE = 60
TTL_FORECAST = 60 * 15
TTL_OPENF1 = 60 * 30
TTL_CALENDAR = 3600
TTL_NEXT_RACE = 300
TTL_DRIVERS = 3600
TTL_SESSION = 86400
TTL_CIRCUIT = 86400

_CACHE = None

# Create the FastF1 cache directory at import time so FastF1 never hangs
# trying to write into a missing folder.
FASTF1_CACHE_DIR = ROOT / "cache" / "fastf1"
os.makedirs(FASTF1_CACHE_DIR, exist_ok=True)


class TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str, ttl_seconds: int) -> Optional[Any]:
        if key not in self._store:
            return None
        value, ts = self._store[key]
        if time.time() - ts > ttl_seconds:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (value, time.time())


cache = TTLCache()


def cache_dir() -> Path:
    FASTF1_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    existing = ROOT / "fastf1_cache"
    if existing.exists():
        return existing
    return FASTF1_CACHE_DIR


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
