"""Try several Neon connection variants and report which (if any) work.

Reads `.env.cloud` for the base URL, then attempts five connection shapes
in order: SQLAlchemy URL as-is, direct psycopg with kwargs, direct psycopg
with kwargs + options=endpoint=..., pooler endpoint, pooler endpoint via
SQLAlchemy. First green wins; failures print the underlying error.
"""

from __future__ import annotations

import re
import socket
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent

from dotenv import dotenv_values  # noqa: E402


def _load_url() -> str:
    env_path = ROOT / ".env.cloud"
    if not env_path.exists():
        sys.exit("ERROR: .env.cloud missing")
    url = dotenv_values(env_path).get("ARIS_DB_URL", "").strip()
    if not url:
        sys.exit("ERROR: ARIS_DB_URL empty in .env.cloud")
    return url


def _parse(url: str) -> dict:
    p = urlparse(url.replace("postgresql+psycopg://", "postgresql://"))
    qs = parse_qs(p.query)
    host = p.hostname or ""
    return {
        "host": host,
        "port": p.port or 5432,
        "user": p.username,
        "password": p.password,
        "dbname": (p.path or "/").lstrip("/"),
        "sslmode": (qs.get("sslmode") or ["require"])[0],
        "endpoint_id": host.split(".")[0] if host else "",
    }


def _pooler_host(host: str) -> str:
    # ep-sparkling-cake-ab4ivr0f.eu-west-2.aws.neon.tech
    # -> ep-sparkling-cake-ab4ivr0f-pooler.eu-west-2.aws.neon.tech
    return re.sub(r"^([^.]+)\.", r"\1-pooler.", host, count=1)


def _tcp_probe(host: str, port: int) -> str:
    """Open a TCP socket and see if it stays open for 2 seconds (no TLS yet)."""
    try:
        s = socket.create_connection((host, port), timeout=5)
        s.settimeout(2.0)
        try:
            data = s.recv(1)
            s.close()
            return f"got {len(data)} bytes back unexpectedly (server pushed data on plain TCP)"
        except TimeoutError:
            s.close()
            return "tcp open, no data (normal — waiting for TLS client hello)"
        except OSError as e:
            return f"tcp opened then closed: {e}"
    except Exception as e:
        return f"tcp connect failed: {type(e).__name__}: {e}"


def _try(label: str, fn) -> bool:
    print(f"\n--- {label}")
    try:
        fn()
        print("    OK")
        return True
    except Exception as e:
        print(f"    FAIL: {type(e).__name__}: {str(e).splitlines()[0]}")
        return False


def main() -> int:
    url = _load_url()
    info = _parse(url)
    print(f"host         = {info['host']}")
    print(f"endpoint_id  = {info['endpoint_id']}")
    print(f"user         = {info['user']}")
    print(f"db           = {info['dbname']}")
    pooler_host = _pooler_host(info["host"])
    print(f"pooler_host  = {pooler_host}")

    print(f"\n[probe] TCP only -> {info['host']}:5432")
    print(f"        {_tcp_probe(info['host'], 5432)}")
    print(f"[probe] TCP only -> {pooler_host}:5432")
    print(f"        {_tcp_probe(pooler_host, 5432)}")

    import psycopg

    base_kwargs = {
        "host": info["host"],
        "port": info["port"],
        "user": info["user"],
        "password": info["password"],
        "dbname": info["dbname"],
        "sslmode": info["sslmode"],
        "connect_timeout": 10,
    }

    # Variant 1: SQLAlchemy URL straight
    def v1():
        from sqlalchemy import create_engine
        create_engine(url).connect().close()
    _try("v1 SQLAlchemy URL (as in .env.cloud)", v1)

    # Variant 2: direct psycopg kwargs, no options
    def v2():
        with psycopg.connect(**base_kwargs) as conn:
            conn.execute("SELECT 1")
    _try("v2 psycopg kwargs (no options)", v2)

    # Variant 3: direct psycopg kwargs WITH options=endpoint=<id>
    def v3():
        kw = dict(base_kwargs, options=f"endpoint={info['endpoint_id']}")
        with psycopg.connect(**kw) as conn:
            conn.execute("SELECT 1")
    _try("v3 psycopg kwargs + options=endpoint", v3)

    # Variant 4: pooler endpoint via direct psycopg
    def v4():
        kw = dict(base_kwargs, host=pooler_host)
        with psycopg.connect(**kw) as conn:
            conn.execute("SELECT 1")
    _try("v4 psycopg kwargs + pooler host", v4)

    # Variant 5: pooler endpoint via SQLAlchemy URL
    def v5():
        from sqlalchemy import create_engine
        pooler_url = url.replace(info["host"], pooler_host)
        # strip the options=... since pooler doesn't need it
        pooler_url = re.sub(r"&?options=endpoint%3D[^&]+", "", pooler_url)
        create_engine(pooler_url).connect().close()
    _try("v5 SQLAlchemy URL + pooler host", v5)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
