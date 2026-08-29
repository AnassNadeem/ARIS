"""Compare localhost broker vs Cloudflare Worker (same JSON, same app shell)."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

LOCAL = "http://127.0.0.1:8765"
CF = "https://aris.anass-nadeem42.workers.dev"

API_PATHS = [
    "/health",
    "/api/health",
    "/api/next-race",
    "/api/calendar/2026",
    "/api/calendar/2026/15/sessions",
    "/api/live/status",
    "/api/drivers/2026",
    "/api/standings/drivers/2026",
    "/api/standings/constructors/2026",
    "/api/circuit/netherlands/characteristics?year=2026",
    "/api/circuit/netherlands/history",
    "/api/circuit/2026/15/preview",
    "/api/aris/stats",
    "/api/aris/plans?year=2026&round_number=15&driver_code=VER",
    "/api/live/session-key?year=2026&round_number=15&session_type=Q",
    "/api/live/session-key?year=2026&round_number=15&session_type=R",
    "/api/live/replay-ready?session_key=11349&year=2026&round_number=15",
    "/api/race/2025/15/results",
]

PAGES = ["/", "/live", "/replay", "/standings"]

SKIP_KEYS = {
    "as_of",
    "countdown_seconds",
    "days_until",
    "hours_until",
    "last_success_utc",
    "session_elapsed_seconds",
    "session_remaining_seconds",
}


def _drop(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _drop(v) for k, v in value.items() if k not in SKIP_KEYS}
    if isinstance(value, list):
        return [_drop(v) for v in value]
    return value


def fetch(client: httpx.Client, base: str, path: str, timeout: float) -> tuple[int, float, Any, str]:
    t0 = time.perf_counter()
    r = client.get(base + path, timeout=timeout)
    ms = (time.perf_counter() - t0) * 1000
    ctype = r.headers.get("content-type", "")
    body: Any
    if "json" in ctype or path.startswith("/api") or path in {"/health"}:
        try:
            body = r.json()
        except Exception:
            body = r.text[:200]
    else:
        body = r.text
    return r.status_code, ms, body, ctype


def main() -> None:
    rows: list[dict[str, Any]] = []
    with httpx.Client(follow_redirects=True) as client:
        for path in API_PATHS:
            timeout = 90.0 if "replay" in path or "plans" in path or "standings" in path else 25.0
            try:
                ls, lms, lb, _ = fetch(client, LOCAL, path, timeout)
            except Exception as extra:
                ls, lms, lb = 0, 0.0, str(extra)
            try:
                cs, cms, cb, _ = fetch(client, CF, path, timeout)
            except Exception as extra:
                cs, cms, cb = 0, 0.0, str(extra)
            same = False
            detail = ""
            if ls == cs == 200 and isinstance(lb, dict) and isinstance(cb, dict):
                left, right = _drop(lb), _drop(cb)
                same = left == right
                if not same:
                    detail = f"local_keys={sorted(lb)[:8]} cf_keys={sorted(cb)[:8]}"
                    if lb.get("name") != cb.get("name"):
                        detail += f" name {lb.get('name')!r} vs {cb.get('name')!r}"
                    if lb.get("session_key") != cb.get("session_key"):
                        detail += f" session_key {lb.get('session_key')} vs {cb.get('session_key')}"
                    if (lb.get("drivers") and cb.get("drivers")) and len(lb["drivers"]) != len(cb["drivers"]):
                        detail += f" drivers {len(lb['drivers'])} vs {len(cb['drivers'])}"
            elif ls == cs:
                same = True if not (isinstance(lb, dict) or isinstance(cb, dict)) else False
                detail = f"status match {ls}"
            rows.append(
                {
                    "path": path,
                    "local_status": ls,
                    "cf_status": cs,
                    "local_ms": round(lms, 1),
                    "cf_ms": round(cms, 1),
                    "match": same,
                    "detail": detail,
                }
            )

        for path in PAGES:
            try:
                ls, lms, lb, lct = fetch(client, CF, path, 20.0)
            except Exception as extra:
                ls, lms, lb, lct = 0, 0.0, str(extra), ""
            html = lb if isinstance(lb, str) else ""
            rows.append(
                {
                    "path": f"PAGE {path}",
                    "local_status": None,
                    "cf_status": ls,
                    "local_ms": None,
                    "cf_ms": round(lms, 1),
                    "match": ls == 200 and "ARIS" in html and "id=\"root\"" in html,
                    "detail": f"ctype={lct} title={('ARIS' in html)}",
                }
            )

    print(json.dumps(rows, indent=2))
    bad = [r for r in rows if not r["match"]]
    print("SUMMARY", "ok" if not bad else f"{len(bad)} mismatch", "of", len(rows))


if __name__ == "__main__":
    main()
