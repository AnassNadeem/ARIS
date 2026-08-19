"""Shared HTTP helpers for OpenF1, Jolpica, and Open-Meteo."""

from __future__ import annotations

from typing import Any

import httpx

OPENF1 = "https://api.openf1.org/v1"
JOLPICA = "https://api.jolpi.ca/ergast/f1"
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 10.0


def get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


async def aget_json(url: str, params: dict[str, Any] | None = None) -> Any:
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def openf1(path: str, params: dict[str, Any] | None = None) -> Any:
    return get_json(f"{OPENF1}/{path.lstrip('/')}", params)


async def aopenf1(path: str, params: dict[str, Any] | None = None) -> Any:
    return await aget_json(f"{OPENF1}/{path.lstrip('/')}", params)


def jolpica(path: str) -> Any:
    url = f"{JOLPICA}/{path.lstrip('/')}"
    if not url.endswith(".json"):
        url = url.rstrip("/") + ".json"
    return get_json(url)
