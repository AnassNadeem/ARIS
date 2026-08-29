"""Thread-pool helpers so blocking FastF1/pandas work never stalls the uvicorn loop.

Three pools, by intent:
  - ``_executor``      general pool for most blocking work (session loads, replay
                        pack builds, analytics/history queries). Configurable via
                        ``ARIS_SYNC_POOL_WORKERS`` (default ``min(8, cpu_count())``).
                        Each worker can hold a full FastF1 session (laps/telemetry)
                        in memory while it runs — turn this down if the process OOMs.
  - ``light_executor``  small, dedicated pool for latency-sensitive endpoints
                        (recommend/simulate/copilot) so a slow cold replay load on
                        ``_executor`` can never queue-block a live recommendation.
                        Configurable via ``ARIS_LIGHT_POOL_WORKERS`` (default 2).
  - ``prewarm_executor`` dedicated pool for background prewarm work so boot-time
                        warming never competes with user-facing requests for a
                        worker on the two pools above. Configurable via
                        ``ARIS_PREWARM_POOL_WORKERS`` (default 2).
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable, TypeVar

_log = logging.getLogger("aris.pool")


def _pool_size(env_var: str, default: int) -> int:
    raw = os.environ.get(env_var)
    if raw:
        try:
            n = int(raw)
            if n > 0:
                return n
        except ValueError:
            _log.warning("ignoring invalid %s=%r, using default %d", env_var, raw, default)
    return default


_DEFAULT_SYNC_WORKERS = min(8, os.cpu_count() or 4)
_SYNC_WORKERS = _pool_size("ARIS_SYNC_POOL_WORKERS", _DEFAULT_SYNC_WORKERS)
_LIGHT_WORKERS = _pool_size("ARIS_LIGHT_POOL_WORKERS", 2)
_PREWARM_WORKERS = _pool_size("ARIS_PREWARM_POOL_WORKERS", 2)

_executor = ThreadPoolExecutor(max_workers=_SYNC_WORKERS, thread_name_prefix="aris-sync")
executor = _executor
light_executor = ThreadPoolExecutor(max_workers=_LIGHT_WORKERS, thread_name_prefix="aris-light")
prewarm_executor = ThreadPoolExecutor(max_workers=_PREWARM_WORKERS, thread_name_prefix="aris-warm")

_log.info(
    "thread pools initialised: sync=%d light=%d prewarm=%d",
    _SYNC_WORKERS,
    _LIGHT_WORKERS,
    _PREWARM_WORKERS,
)

T = TypeVar("T")

# Log a warning when a submitted task waits longer than this for a worker to pick
# it up, so pool contention (item 1 in the fix-pass diagnostic) is observable.
_SLOW_QUEUE_WAIT_S = 2.0

_inflight_lock = threading.Lock()
_inflight_by_pool: dict[str, int] = {}


def _run_with_timing(fn: Callable[..., T], pool_name: str, submitted_at: float, label: str, *args: Any, **kwargs: Any) -> T:
    started_at = time.monotonic()
    wait_s = started_at - submitted_at
    with _inflight_lock:
        depth = _inflight_by_pool.get(pool_name, 0) + 1
        _inflight_by_pool[pool_name] = depth
    if wait_s > _SLOW_QUEUE_WAIT_S:
        _log.warning(
            "pool=%s contention: %s waited %.2fs for a worker (in-flight=%d)",
            pool_name,
            label,
            wait_s,
            depth,
        )
    try:
        return fn(*args, **kwargs)
    finally:
        with _inflight_lock:
            _inflight_by_pool[pool_name] = max(0, _inflight_by_pool.get(pool_name, 1) - 1)


async def run_on(pool: ThreadPoolExecutor, pool_name: str, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run a blocking function on a specific pool without blocking the event loop."""
    loop = asyncio.get_running_loop()
    submitted_at = time.monotonic()
    label = getattr(fn, "__name__", repr(fn))
    return await loop.run_in_executor(
        pool, partial(_run_with_timing, fn, pool_name, submitted_at, label, *args, **kwargs)
    )


async def run_sync(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run blocking work on the general pool (session loads, replay packs, history)."""
    return await run_on(_executor, "sync", fn, *args, **kwargs)


async def run_light(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run blocking work on the small latency-sensitive pool (recommend/simulate/copilot)."""
    return await run_on(light_executor, "light", fn, *args, **kwargs)


async def run_prewarm(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run blocking prewarm/background-warm work on its own dedicated pool."""
    return await run_on(prewarm_executor, "prewarm", fn, *args, **kwargs)


def pool_stats() -> dict[str, int]:
    """Snapshot of in-flight task counts per pool, for a future /api/status hook."""
    with _inflight_lock:
        return dict(_inflight_by_pool)
