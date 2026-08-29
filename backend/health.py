"""Process health: Postgres reachability + ARIS cache-backend reachability."""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import create_engine, text

from aris.io.db_url import resolve_database_url
from backend.cache import fastf1_cache_healthcheck, get_app_cache


def check_database() -> dict[str, Any]:
    url = resolve_database_url()
    if not url:
        return {
            "ok": False,
            "backend": "postgres",
            "reason": "ARIS_DB_URL unset (and DATABASE_URL unset)",
        }
    t0 = time.perf_counter()
    engine = None
    try:
        connect_args = {"connect_timeout": 3} if "postgres" in url else {}
        engine = create_engine(url, pool_pre_ping=True, future=True, connect_args=connect_args)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        ms = (time.perf_counter() - t0) * 1000
        return {"ok": True, "backend": "postgres", "latency_ms": round(ms, 1)}
    except Exception as extra:
        return {
            "ok": False,
            "backend": "postgres",
            "reason": f"database unreachable: {type(extra).__name__}: {extra}",
        }
    finally:
        if engine is not None:
            engine.dispose()


def build_health() -> dict[str, Any]:
    db = check_database()
    cache_status = get_app_cache().healthcheck()
    fastf1 = fastf1_cache_healthcheck()
    ok = bool(db.get("ok") and cache_status.get("ok"))
    reasons = []
    if not db.get("ok"):
        reasons.append(f"db: {db.get('reason') or 'unhealthy'}")
    if not cache_status.get("ok"):
        reasons.append(f"cache: {cache_status.get('reason') or 'unhealthy'}")
    payload: dict[str, Any] = {
        "ok": ok,
        "service": "aris-v3-broker",
        "db": db,
        "cache": cache_status,
        "fastf1_cache": fastf1,
    }
    if not ok:
        payload["reason"] = "; ".join(reasons)
    return payload
