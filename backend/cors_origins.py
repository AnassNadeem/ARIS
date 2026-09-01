"""Frontend origins allowed to call this API. Production reads env, not localhost."""

from __future__ import annotations

import os

# Canonical production UI (Cloudflare Pages custom domain).
PRODUCTION_FRONTEND_ORIGIN = "https://arisf1.tech"
PRODUCTION_PAGES_ORIGIN = "https://aris-frontend-590.pages.dev"

_LOCAL_DEV_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def cors_allow_origins() -> list[str]:
    """Origins for CORSMiddleware.

    ``ARIS_FRONTEND_ORIGIN`` is a comma-separated list (canonical:
    ``https://arisf1.tech``, plus optional Pages preview hosts). When unset
    on a Heroku dyno, the production UI origins are used. When unset locally,
    Vite/Next localhost origins are used so laptop ``uvicorn`` still works.
    """
    raw = (os.getenv("ARIS_FRONTEND_ORIGIN") or "").strip()
    if raw:
        return [part.strip().rstrip("/") for part in raw.split(",") if part.strip()]
    if os.getenv("DYNO"):
        return [PRODUCTION_FRONTEND_ORIGIN, PRODUCTION_PAGES_ORIGIN]
    return list(_LOCAL_DEV_ORIGINS)
