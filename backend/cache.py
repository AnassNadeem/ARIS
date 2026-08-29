"""Application cache, in-memory TTL cache, and FastF1 filesystem cache.

Cache inventory (three separate layers — do not treat them as one):

1. FastF1 native filesystem cache
   Path: ``fastf1_cache/`` if present, else ``cache/fastf1/``.
   Owner: FastF1 (HTTP + session pickles). Not an ARIS key/value store.
   Local: persists across process restarts on a real disk.
   Production (Heroku): **intentionally ephemeral**. The dyno filesystem is
   discarded on restart. Postgres does **not** persist this cache. A miss
   rebuilds from FastF1; that must not crash the process.
   No object-storage design is in place for beta prod.

2. ARIS application / replay-pack cache (this module's CacheBackend)
   Keys: HTTP catalog responses, OpenF1/Jolpica payloads, replay packs.
   Selected with ``ARIS_CACHE_BACKEND=disk|postgres``. If unset, auto-detects
   ``postgres`` when ``DATABASE_URL`` is present (Heroku), otherwise ``disk``.
   Explicit ``ARIS_CACHE_BACKEND=disk`` always wins, even with ``DATABASE_URL``.
   - disk: ``cache/disk/`` via diskcache. Durable on a laptop; **ephemeral
     on Heroku**. Use only for local development.
   - postgres: table ``aris_cache``. **This is the durable production layer.**
     Survives dyno restart. Does not silently fall back to disk.

3. In-memory TTLCache (``cache`` singleton)
   Process-local. Always ephemeral. Hydrated from layer 2 on a miss
   (``get_memory_then_disk``). Never a source of production durability.

Interface: get / set / delete / healthcheck. ``get_disk()`` is a compatibility
wrapper so existing callers keep using ``.get`` / ``.set(..., expire=)`` /
``.pop``.
"""

from __future__ import annotations

import logging
import os
import pickle
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, Protocol, TypeVar

from backend.paths import ROOT

T = TypeVar("T")
_log = logging.getLogger("aris.cache")

TTL_STANDINGS = 60 * 60
TTL_LIVE = 15
TTL_SCHEDULE = 60 * 60 * 24
TTL_METADATA = 60 * 60 * 24
TTL_WEATHER_LIVE = 60
TTL_RAINFALL = 30
TTL_FORECAST = 60 * 15
TTL_OPENF1 = 60 * 30
TTL_CALENDAR = 3600
TTL_NEXT_RACE = 20
TTL_DRIVERS = 3600
TTL_SESSION = 86400
TTL_CIRCUIT = 86400
TTL_STATS = 60
# Completed races do not change. Replay packs and race analytics stay warm
# across uvicorn restarts so /replay does not re-hit OpenF1 / FastF1.
TTL_REPLAY = 30 * 24 * 3600
TTL_COMPLETED = 7 * 24 * 3600

_APP_CACHE = None
_DISK_STORE = None

FASTF1_CACHE_DIR = ROOT / "cache" / "fastf1"
try:
    os.makedirs(FASTF1_CACHE_DIR, exist_ok=True)
except OSError:
    pass


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

    def peek(self, key: str) -> Optional[Any]:
        """Return a cached value even if its TTL has expired."""
        if key not in self._store:
            return None
        value, _ts = self._store[key]
        return value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def delete_prefix(self, prefix: str) -> int:
        keys = [k for k in self._store if str(k).startswith(prefix)]
        for k in keys:
            del self._store[k]
        return len(keys)


cache = TTLCache()


class CacheBackend(Protocol):
    name: str

    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None: ...
    def delete(self, key: str) -> None: ...
    def healthcheck(self) -> dict[str, Any]: ...


def cache_dir() -> Path:
    try:
        FASTF1_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    existing = ROOT / "fastf1_cache"
    if existing.exists():
        return existing
    return FASTF1_CACHE_DIR


def disk_dir() -> Path:
    path = ROOT / "cache" / "disk"
    path.mkdir(parents=True, exist_ok=True)
    return path


def selected_cache_backend_name() -> str:
    raw = (os.getenv("ARIS_CACHE_BACKEND") or "").strip().lower()
    if raw:
        if raw not in {"disk", "postgres"}:
            raise ValueError(f"ARIS_CACHE_BACKEND must be disk or postgres, got {raw!r}")
        return raw
    if (os.getenv("DATABASE_URL") or "").strip():
        return "postgres"
    return "disk"


class DiskCacheBackend:
    """Local-dev ARIS cache. Durable on a laptop disk; ephemeral on Heroku."""

    name = "disk"

    def __init__(self, directory: Path | None = None) -> None:
        from diskcache import Cache

        self._dir = Path(directory) if directory is not None else disk_dir()
        self._dir.mkdir(parents=True, exist_ok=True)
        self._store = Cache(str(self._dir))

    def get(self, key: str) -> Any | None:
        try:
            return self._store.get(key)
        except Exception:
            _log.exception("disk cache GET failed key=%s", key)
            return None

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        if ttl_seconds is None:
            self._store.set(key, value)
        else:
            self._store.set(key, value, expire=int(ttl_seconds))

    def delete(self, key: str) -> None:
        self._store.pop(key, default=None)

    def healthcheck(self) -> dict[str, Any]:
        probe = "aris:health:disk-probe"
        t0 = time.perf_counter()
        try:
            self.set(probe, {"ok": True}, ttl_seconds=30)
            hit = self.get(probe)
            self.delete(probe)
            if hit != {"ok": True}:
                return {
                    "ok": False,
                    "backend": self.name,
                    "persistent_in_production": False,
                    "reason": "disk cache probe round-trip mismatch",
                }
            ms = (time.perf_counter() - t0) * 1000
            return {
                "ok": True,
                "backend": self.name,
                "persistent_in_production": False,
                "latency_ms": round(ms, 1),
                "path": str(self._dir),
                "note": "Durable on a local disk. Ephemeral on Heroku — use postgres in production.",
            }
        except Exception as extra:
            return {
                "ok": False,
                "backend": self.name,
                "persistent_in_production": False,
                "reason": f"disk cache unreachable: {type(extra).__name__}: {extra}",
            }


_ARIS_CACHE_DDL = """
CREATE TABLE IF NOT EXISTS aris_cache (
    cache_key  TEXT PRIMARY KEY,
    payload    BYTEA NOT NULL,
    expires_at TIMESTAMPTZ
)
"""


class PostgresCacheBackend:
    """Production ARIS cache. Entries survive process restart via Postgres.

    Never falls back to DiskCacheBackend. A connection failure is a miss on
    get, a logged no-op on set, and a failed healthcheck.
    """

    name = "postgres"

    def __init__(self, url: str | None = None) -> None:
        from sqlalchemy import create_engine

        from aris.io.db_url import resolve_database_url

        self._url = (url or resolve_database_url() or "").strip() or None
        self._engine = None
        self._table_ready = False
        if self._url:
            connect_args = {"connect_timeout": 3} if "postgres" in self._url else {}
            self._engine = create_engine(
                self._url,
                pool_pre_ping=True,
                future=True,
                connect_args=connect_args,
            )

    def _ensure_table(self) -> None:
        if self._table_ready or self._engine is None:
            return
        from sqlalchemy import text

        with self._engine.begin() as conn:
            conn.execute(text(_ARIS_CACHE_DDL))
        self._table_ready = True

    def get(self, key: str) -> Any | None:
        if self._engine is None:
            return None
        from sqlalchemy import text

        try:
            self._ensure_table()
            with self._engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT payload, expires_at FROM aris_cache WHERE cache_key = :k"
                    ),
                    {"k": key},
                ).fetchone()
                if row is None:
                    return None
                payload, expires_at = row
                if expires_at is not None:
                    exp = expires_at
                    if getattr(exp, "tzinfo", None) is None:
                        exp = exp.replace(tzinfo=timezone.utc)
                    if exp <= datetime.now(timezone.utc):
                        conn.execute(
                            text("DELETE FROM aris_cache WHERE cache_key = :k"),
                            {"k": key},
                        )
                        conn.commit()
                        return None
                return pickle.loads(bytes(payload))
        except Exception:
            _log.exception("postgres cache GET failed key=%s", key)
            return None

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        if self._engine is None:
            _log.warning("postgres cache SET skipped (no database URL) key=%s", key)
            return
        from sqlalchemy import text

        expires = None
        if ttl_seconds is not None:
            expires = datetime.now(timezone.utc) + timedelta(seconds=int(ttl_seconds))
        blob = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        try:
            self._ensure_table()
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO aris_cache (cache_key, payload, expires_at) "
                        "VALUES (:k, :p, :e) "
                        "ON CONFLICT (cache_key) DO UPDATE "
                        "SET payload = EXCLUDED.payload, expires_at = EXCLUDED.expires_at"
                    ),
                    {"k": key, "p": blob, "e": expires},
                )
        except Exception:
            _log.exception("postgres cache SET failed key=%s", key)

    def delete(self, key: str) -> None:
        if self._engine is None:
            return
        from sqlalchemy import text

        try:
            self._ensure_table()
            with self._engine.begin() as conn:
                conn.execute(text("DELETE FROM aris_cache WHERE cache_key = :k"), {"k": key})
        except Exception:
            _log.exception("postgres cache DELETE failed key=%s", key)

    def healthcheck(self) -> dict[str, Any]:
        base = {"backend": self.name, "persistent_in_production": True}
        if self._engine is None:
            return {
                **base,
                "ok": False,
                "reason": "database URL unset (set ARIS_DB_URL or DATABASE_URL) "
                "with ARIS_CACHE_BACKEND=postgres",
            }
        from sqlalchemy import text

        t0 = time.perf_counter()
        try:
            self._ensure_table()
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            ms = (time.perf_counter() - t0) * 1000
            return {**base, "ok": True, "latency_ms": round(ms, 1)}
        except Exception as extra:
            return {
                **base,
                "ok": False,
                "reason": f"postgres cache unreachable: {type(extra).__name__}: {extra}",
            }


class _DiskCacheCompat:
    """diskcache-shaped wrapper over the selected CacheBackend."""

    def __init__(self, backend: CacheBackend) -> None:
        self._backend = backend

    def get(self, key: str, default: Any = None) -> Any:
        hit = self._backend.get(str(key))
        return default if hit is None else hit

    def set(self, key: str, value: Any, expire: int | None = None, **_kwargs: Any) -> None:
        self._backend.set(str(key), value, ttl_seconds=expire)

    def pop(self, key: str, default: Any = None) -> Any:
        val = self._backend.get(str(key))
        self._backend.delete(str(key))
        return default if val is None else val


def make_cache_backend(name: str | None = None, *, url: str | None = None) -> CacheBackend:
    """Construct a backend. postgres is never replaced with disk."""
    kind = (name or selected_cache_backend_name()).strip().lower()
    if kind == "postgres":
        return PostgresCacheBackend(url=url)
    if kind == "disk":
        return DiskCacheBackend()
    raise ValueError(f"unknown cache backend {kind!r}")


def get_app_cache() -> CacheBackend:
    global _APP_CACHE
    if _APP_CACHE is None:
        _APP_CACHE = make_cache_backend()
        _log.info(
            "ARIS cache backend=%s persistent_in_production=%s",
            _APP_CACHE.name,
            _APP_CACHE.name == "postgres",
        )
    return _APP_CACHE


def get_disk():
    """Compatibility: historically returned diskcache.Cache."""
    global _DISK_STORE
    if _DISK_STORE is None:
        _DISK_STORE = _DiskCacheCompat(get_app_cache())
    return _DISK_STORE


def reset_app_cache_for_tests() -> None:
    global _APP_CACHE, _DISK_STORE
    _APP_CACHE = None
    _DISK_STORE = None


def enable_fastf1_cache() -> Path:
    """Enable FastF1's own disk cache. Failure must not kill the process.

    On Heroku this directory is ephemeral. A miss rebuilds from the network.
    """
    path = cache_dir()
    try:
        path.mkdir(parents=True, exist_ok=True)
        import fastf1

        fastf1.Cache.enable_cache(str(path))
        _log.info("FastF1 cache enabled path=%s (ephemeral on Heroku)", path)
    except Exception:
        _log.exception(
            "FastF1 cache enable failed path=%s; session loads will refetch",
            path,
        )
    return path


def fastf1_cache_healthcheck() -> dict[str, Any]:
    path = cache_dir()
    writable = False
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".aris_fastf1_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        writable = True
    except OSError as extra:
        return {
            "ok": False,
            "backend": "fastf1_filesystem",
            "persistent_in_production": False,
            "path": str(path),
            "reason": f"FastF1 cache dir not writable: {extra}",
            "note": "Intentionally ephemeral on Heroku. A miss must rebuild, not crash.",
        }
    return {
        "ok": writable,
        "backend": "fastf1_filesystem",
        "persistent_in_production": False,
        "path": str(path),
        "note": "Intentionally ephemeral on Heroku. Postgres does not persist this layer.",
    }


def cached(key: str, ttl: int, factory: Callable[[], T], *, refresh: bool = False) -> T:
    store = get_disk()
    if not refresh:
        hit = store.get(key)
        if hit is not None:
            _log.info("disk cache HIT key=%s", key)
            return hit  # type: ignore[return-value]
    else:
        _log.info("disk cache BYPASS key=%s", key)
    _log.info("disk cache MISS key=%s", key)
    value = factory()
    store.set(key, value, expire=ttl)
    return value


def invalidate(key: str) -> None:
    """Drop a key from the in-memory TTL cache and application cache."""
    cache.delete(key)
    try:
        get_disk().pop(key, default=None)
    except Exception:
        pass
    _log.info("cache invalidate key=%s", key)


def put_both(key: str, value: Any, disk_ttl: int | None = None) -> None:
    """Write the memory TTL cache and application cache so HTTP `_cached_sync` hits on first request."""
    cache.set(key, value)
    try:
        store = get_disk()
        if disk_ttl is None:
            store.set(key, value)
        else:
            store.set(key, value, expire=disk_ttl)
    except Exception:
        pass


def get_memory_then_disk(key: str, ttl: int) -> Optional[Any]:
    """HTTP/catalog lookup: RAM first, then application cache (hydrates RAM on a hit)."""
    hit = cache.get(key, ttl)
    if hit is not None:
        return hit
    try:
        stored = get_disk().get(key)
    except Exception:
        stored = None
    if stored is None:
        return None
    cache.set(key, stored)
    _log.debug("disk cache promoted to memory key=%s", key)
    return stored
