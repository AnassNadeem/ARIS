"""Postgres cache persistence across a new connection (simulates dyno restart).

Skipped when no reachable Postgres is configured. This test constructs
PostgresCacheBackend directly — it must not fall back to disk.
"""

from __future__ import annotations

import os
import time
import uuid

import pytest

from aris.io.db_url import resolve_database_url
from backend.cache import DiskCacheBackend, PostgresCacheBackend, disk_dir


def _postgres_reachable() -> bool:
    url = resolve_database_url()
    if not url:
        return False
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_reachable(),
    reason="no reachable Postgres (ARIS_DB_URL / DATABASE_URL) - postgres cache test unexecuted",
)


def test_postgres_cache_survives_new_connection_and_honours_ttl():
    url = resolve_database_url()
    assert url, "skipif should have filtered a missing URL"
    key = f"aris:test:persist:{uuid.uuid4().hex}"
    payload = {"v": 42, "note": "phase2-cache"}

    first = PostgresCacheBackend(url=url)
    assert first.name == "postgres"
    assert not isinstance(first, DiskCacheBackend)
    first.set(key, payload, ttl_seconds=30)

    # Brand-new engine/connection — same process restart as a new dyno boot.
    second = PostgresCacheBackend(url=url)
    assert second.name == "postgres"
    assert second is not first
    assert second._engine is not first._engine  # noqa: SLF001
    assert second.get(key) == payload

    disk = DiskCacheBackend(disk_dir())
    assert disk.get(key) is None, "postgres backend must not write through to disk"

    ttl_key = f"aris:test:ttl:{uuid.uuid4().hex}"
    first.set(ttl_key, "expire-me", ttl_seconds=1)
    assert second.get(ttl_key) == "expire-me"
    time.sleep(1.3)
    third = PostgresCacheBackend(url=url)
    assert third.get(ttl_key) is None

    first.delete(key)
    first.delete(ttl_key)
