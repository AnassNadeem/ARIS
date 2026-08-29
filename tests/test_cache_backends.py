"""Disk cache backend, factory selection, FastF1 health — no Postgres required."""

from __future__ import annotations

from backend.cache import (
    DiskCacheBackend,
    PostgresCacheBackend,
    fastf1_cache_healthcheck,
    make_cache_backend,
    reset_app_cache_for_tests,
)


def test_disk_backend_roundtrip_and_ttl(tmp_path):
    backend = DiskCacheBackend(tmp_path)
    assert backend.name == "disk"
    backend.set("aris:test:disk", {"v": 7}, ttl_seconds=60)
    assert backend.get("aris:test:disk") == {"v": 7}
    status = backend.healthcheck()
    assert status["ok"] is True
    assert status["backend"] == "disk"
    assert status["persistent_in_production"] is False
    backend.delete("aris:test:disk")
    assert backend.get("aris:test:disk") is None


def test_disk_backend_ttl_expiry(tmp_path):
    backend = DiskCacheBackend(tmp_path)
    backend.set("aris:test:ttl", "gone", ttl_seconds=1)
    assert backend.get("aris:test:ttl") == "gone"
    import time

    time.sleep(1.2)
    assert backend.get("aris:test:ttl") is None


def test_default_backend_is_disk(monkeypatch):
    monkeypatch.delenv("ARIS_CACHE_BACKEND", raising=False)
    reset_app_cache_for_tests()
    backend = make_cache_backend()
    assert isinstance(backend, DiskCacheBackend)
    assert backend.name == "disk"


def test_postgres_selection_does_not_fall_back_to_disk(monkeypatch, tmp_path):
    monkeypatch.setenv("ARIS_CACHE_BACKEND", "postgres")
    monkeypatch.delenv("ARIS_DB_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    reset_app_cache_for_tests()
    backend = make_cache_backend()
    assert isinstance(backend, PostgresCacheBackend)
    assert not isinstance(backend, DiskCacheBackend)
    assert backend.name == "postgres"
    backend.set("aris:test:no-disk-fallback", {"v": 1}, ttl_seconds=60)
    disk = DiskCacheBackend(tmp_path)
    assert disk.get("aris:test:no-disk-fallback") is None
    assert backend.get("aris:test:no-disk-fallback") is None
    status = backend.healthcheck()
    assert status["ok"] is False
    assert "database URL unset" in (status.get("reason") or "")
    assert status["persistent_in_production"] is True


def test_fastf1_cache_health_is_intentionally_ephemeral_in_production():
    status = fastf1_cache_healthcheck()
    assert status["backend"] == "fastf1_filesystem"
    assert status["persistent_in_production"] is False
    assert "ephemeral" in (status.get("note") or "").lower()
