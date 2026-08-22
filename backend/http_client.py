"""Shared HTTP helpers for OpenF1, Jolpica, and Open-Meteo.

OpenF1 live REST requires a Bearer token (public access is 401 during a
session). Paid accounts are also capped at 6 req/s and 60 req/min — every
caller goes through the limiter below.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any
from urllib.parse import quote

import httpx

from backend.paths import ROOT

OPENF1 = "https://api.openf1.org/v1"
OPENF1_TOKEN_URL = "https://api.openf1.org/token"
JOLPICA = "https://api.jolpi.ca/ergast/f1"
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 12.0

# Stay under OpenF1's 6/s and 60/min paid caps.
_MAX_PER_SEC = 5
_MAX_PER_MIN = 50

_token_lock = threading.Lock()
_rate_lock = threading.Lock()
_access_token: str | None = None
_token_expires_at = 0.0
_hits_sec: list[float] = []
_hits_min: list[float] = []


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except Exception:
        pass


def _wait_rate() -> None:
    global _hits_sec, _hits_min
    while True:
        with _rate_lock:
            now = time.monotonic()
            _hits_sec = [t for t in _hits_sec if now - t < 1.0]
            _hits_min = [t for t in _hits_min if now - t < 60.0]
            if len(_hits_sec) < _MAX_PER_SEC and len(_hits_min) < _MAX_PER_MIN:
                _hits_sec.append(now)
                _hits_min.append(now)
                return
            wait_s = 0.12
            if _hits_sec:
                wait_s = max(wait_s, 1.05 - (now - _hits_sec[0]))
            if len(_hits_min) >= _MAX_PER_MIN and _hits_min:
                wait_s = max(wait_s, 60.05 - (now - _hits_min[0]))
        time.sleep(min(2.0, max(0.05, wait_s)))


def _static_bearer() -> str | None:
    """Paid OpenF1 key pasted as a bearer token (Streamlit secrets or .env)."""
    _load_env()
    for key in ("OPENF1_API_KEY", "OPENF1_TOKEN", "OPENF1_ACCESS_TOKEN", "OPENF1_KEY"):
        val = (os.getenv(key) or "").strip()
        if val:
            return val.removeprefix("Bearer ").strip()
    return None


def _refresh_token() -> str | None:
    global _access_token, _token_expires_at
    static = _static_bearer()
    if static:
        _access_token = static
        _token_expires_at = time.time() + 24 * 3600
        return static
    user = (os.getenv("OPENF1_USERNAME") or "").strip()
    password = (os.getenv("OPENF1_PASSWORD") or "").strip()
    if not user or not password:
        return None
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        resp = client.post(
            OPENF1_TOKEN_URL,
            data={"username": user, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        )
        resp.raise_for_status()
        payload = resp.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("OpenF1 token response missing access_token")
    expires = float(payload.get("expires_in") or 3600)
    _access_token = str(token)
    _token_expires_at = time.time() + max(60.0, expires)
    return _access_token


def openf1_headers() -> dict[str, str]:
    global _access_token, _token_expires_at
    with _token_lock:
        if _access_token and time.time() < _token_expires_at - 90:
            token = _access_token
        else:
            token = _refresh_token()
    headers = {"Accept": "application/json", "User-Agent": "ARIS/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _encode_params(params: dict[str, Any] | None) -> str:
    """Keep OpenF1 operators (`date>`, `lap_number>=`) in the query string."""
    if not params:
        return ""
    parts: list[str] = []
    for key, value in params.items():
        if value is None:
            continue
        raw = str(value)
        if any(op in key for op in (">", "<", "=")):
            parts.append(f"{key}{quote(raw, safe=':+-')}")
        else:
            parts.append(f"{quote(str(key), safe='')}={quote(raw, safe=':+-')}")
    return "&".join(parts)


def openf1_url(path: str, params: dict[str, Any] | None = None) -> str:
    url = f"{OPENF1}/{path.lstrip('/')}"
    qs = _encode_params(params)
    return f"{url}?{qs}" if qs else url


def get_json(url: str, params: dict[str, Any] | None = None, *, headers: dict[str, str] | None = None) -> Any:
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        resp = client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def aget_json(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> Any:
    async with httpx.AsyncClient(timeout=timeout or TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()


def openf1(path: str, params: dict[str, Any] | None = None) -> Any:
    _wait_rate()
    return get_json(openf1_url(path, params), headers=openf1_headers())


async def aopenf1(path: str, params: dict[str, Any] | None = None, *, timeout: float | None = None) -> Any:
    _wait_rate()
    try:
        return await aget_json(openf1_url(path, params), headers=openf1_headers(), timeout=timeout)
    except httpx.HTTPStatusError as extra:
        if extra.response is not None and extra.response.status_code == 401:
            with _token_lock:
                global _access_token, _token_expires_at
                _access_token = None
                _token_expires_at = 0.0
            _wait_rate()
            return await aget_json(openf1_url(path, params), headers=openf1_headers(), timeout=timeout)
        raise


def jolpica(path: str) -> Any:
    url = f"{JOLPICA}/{path.lstrip('/')}"
    if not url.endswith(".json"):
        url = url.rstrip("/") + ".json"
    return get_json(url)
