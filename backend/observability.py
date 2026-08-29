"""Optional Sentry. Unset ``SENTRY_DSN`` is a no-op so local dev needs no account."""

from __future__ import annotations

import logging
import os

_log = logging.getLogger("aris.observability")
_initialized = False


def reset_sentry_for_tests() -> None:
    global _initialized
    _initialized = False


def init_sentry() -> bool:
    """Bind Sentry if ``SENTRY_DSN`` is set. Returns True when initialized."""
    global _initialized
    if _initialized:
        return True
    dsn = (os.getenv("SENTRY_DSN") or "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        _log.warning("SENTRY_DSN is set but sentry-sdk is not installed; skipping")
        return False
    sentry_sdk.init(
        dsn=dsn,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        send_default_pii=False,
        traces_sample_rate=0.0,
    )
    _initialized = True
    _log.info("Sentry initialized")
    return True
