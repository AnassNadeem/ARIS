"""Health payload shape, CORS env, Sentry no-op, Heroku DATABASE_URL rewrite."""

from __future__ import annotations

from aris.io.db_url import normalize_database_url, resolve_database_url
from backend.cors_origins import cors_allow_origins
from backend.health import build_health
from backend.observability import init_sentry


def test_health_payload_shape():
    payload = build_health()
    assert "ok" in payload
    assert payload["service"] == "aris-v3-broker"
    for key in ("db", "cache", "fastf1_cache"):
        assert key in payload
        assert "ok" in payload[key]
    assert payload["cache"]["backend"] in {"disk", "postgres"}
    assert payload["fastf1_cache"]["persistent_in_production"] is False
    if payload["ok"]:
        assert payload["db"]["ok"] is True
        assert payload["cache"]["ok"] is True
        assert payload.get("reason") is None
    else:
        assert payload.get("reason")
        assert "db:" in payload["reason"] or "cache:" in payload["reason"]


def test_cors_reads_frontend_origin_env(monkeypatch):
    monkeypatch.setenv(
        "ARIS_FRONTEND_ORIGIN",
        "https://example.pages.dev, https://preview.pages.dev/",
    )
    origins = cors_allow_origins()
    assert origins == ["https://example.pages.dev", "https://preview.pages.dev"]
    assert not any("localhost" in o for o in origins)


def test_cors_local_default_when_unset(monkeypatch):
    monkeypatch.delenv("ARIS_FRONTEND_ORIGIN", raising=False)
    origins = cors_allow_origins()
    assert "http://localhost:3000" in origins
    assert "http://localhost:5173" in origins


def test_sentry_unset_dsn_is_noop(monkeypatch):
    from backend.observability import reset_sentry_for_tests

    monkeypatch.delenv("SENTRY_DSN", raising=False)
    reset_sentry_for_tests()
    assert init_sentry() is False


def test_heroku_database_url_rewritten_to_psycopg(monkeypatch):
    monkeypatch.delenv("ARIS_DB_URL", raising=False)
    monkeypatch.setenv("DYNO", "web.1")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgres://u:p@host.amazonaws.com:5432/d",
    )
    url = resolve_database_url()
    assert url is not None
    assert url.startswith("postgresql+psycopg://")
    assert "sslmode=require" in url


def test_local_database_url_not_forced_to_ssl(monkeypatch):
    monkeypatch.delenv("DYNO", raising=False)
    assert normalize_database_url("postgresql+psycopg://u:p@127.0.0.1:5432/aris") == (
        "postgresql+psycopg://u:p@127.0.0.1:5432/aris"
    )
