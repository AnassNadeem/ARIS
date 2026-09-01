"""In-memory per-IP quotas for compute endpoints.

Heroku is a single web dyno (see Procfile). This is not a distributed limiter.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request

# path -> (max requests, window seconds)
COMPUTE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/aris/ghost-recompute": (10, 60),
    "/api/aris/recommend": (20, 60),
    "/api/aris/simulate": (20, 60),
    "/api/aris/plans": (20, 60),
    "/api/ask": (30, 60),
    "/api/copilot/chat": (20, 60),
}

_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_lock = Lock()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def reset_for_tests() -> None:
    with _lock:
        _hits.clear()


def _allowed(ip: str, path: str, now: float) -> bool:
    limit = COMPUTE_LIMITS.get(path)
    if limit is None:
        return True
    max_n, window_s = limit
    key = (ip, path)
    with _lock:
        bucket = _hits[key]
        cutoff = now - window_s
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= max_n:
            return False
        bucket.append(now)
        return True


def enforce_compute_quota(request: Request) -> None:
    path = request.url.path.rstrip("/") or "/"
    # FastAPI routes are registered without a trailing slash.
    if path not in COMPUTE_LIMITS and request.url.path in COMPUTE_LIMITS:
        path = request.url.path
    if path not in COMPUTE_LIMITS:
        return
    if not _allowed(client_ip(request), path, time.monotonic()):
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate limit exceeded",
                "code": "rate_limited",
                "path": path,
            },
        )
