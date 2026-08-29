"""Frontend origins allowed to call this API. Production reads env, not localhost."""

from __future__ import annotations

import os

_LOCAL_DEV_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def cors_allow_origins() -> list[str]:
    """Origins for CORSMiddleware.

    ``ARIS_FRONTEND_ORIGIN`` is a comma-separated list (Cloudflare Pages URL,
    optional extra preview hosts). When unset, local Vite/Next origins are
    used so ``uvicorn`` on a laptop still works without extra config.
    """
    raw = (os.getenv("ARIS_FRONTEND_ORIGIN") or "").strip()
    if not raw:
        return list(_LOCAL_DEV_ORIGINS)
    return [part.strip().rstrip("/") for part in raw.split(",") if part.strip()]
