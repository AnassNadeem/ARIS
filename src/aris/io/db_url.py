"""Resolve the Postgres URL used by the app and the production cache.

Heroku injects ``DATABASE_URL`` as ``postgres://...``. Local dev uses
``ARIS_DB_URL`` as ``postgresql+psycopg://...``. This helper accepts both
and rewrites them into the SQLAlchemy+psycopg3 form the rest of the code
expects. It does not open a connection.
"""

from __future__ import annotations

import os


def normalize_database_url(raw: str) -> str:
    url = raw.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    heroku = bool(os.getenv("DYNO")) or "amazonaws.com" in url or ".heroku.com" in url
    if heroku and "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


def resolve_database_url() -> str | None:
    """``ARIS_DB_URL`` wins; Heroku ``DATABASE_URL`` is the production fallback."""
    raw = (os.getenv("ARIS_DB_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not raw:
        return None
    return normalize_database_url(raw)
