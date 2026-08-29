"""Serialize native FastF1 work.

Concurrent ``sess.load()`` crashes uvicorn on Windows and two GPS sessions
together blow a 512MB Heroku Basic dyno (R15). Default concurrency is 1.

``ARIS_MAX_CONCURRENT_LOADS`` raises the cap (opt-in). Keep it at 1 in production.
"""

from __future__ import annotations

import os
import threading


def max_concurrent_loads() -> int:
    raw = (os.environ.get("ARIS_MAX_CONCURRENT_LOADS") or "1").strip()
    try:
        n = int(raw)
        return max(1, n)
    except ValueError:
        return 1


# Semaphore so ARIS_MAX_CONCURRENT_LOADS can raise the cap. Default 1 is
# equivalent to the old threading.Lock() for exclusive sess.load().
FASTF1_LOCK = threading.Semaphore(max_concurrent_loads())
