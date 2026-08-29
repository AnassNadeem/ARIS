"""Race-day probe: time critical APIs and confirm Zandvoort 2026 wiring."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import httpx

LOCAL = "http://127.0.0.1:8765"
CF = "https://aris.anass-nadeem42.workers.dev"


def timed(client: httpx.Client, path: str, *, timeout: float = 45.0) -> dict:
    url = path if path.startswith("http") else f"{LOCAL}{path}"
    t0 = time.perf_counter()
    try:
        r = client.get(url, timeout=timeout)
        ms = (time.perf_counter() - t0) * 1000
        body: object
        try:
            body = r.json()
        except Exception:
            body = r.text[:160]
        return {"path": path, "status": r.status_code, "ms": round(ms, 1), "ok": r.is_success, "body": body}
    except Exception as extra:
        ms = (time.perf_counter() - t0) * 1000
        return {"path": path, "status": 0, "ms": round(ms, 1), "ok": False, "body": str(extra)}


def summarize(item: dict) -> dict:
    body = item.get("body")
    extra: dict = {}
    if isinstance(body, dict):
        for key in (
            "name",
            "status",
            "is_live",
            "session_ended",
            "session_name",
            "session_type",
            "next_session_name",
            "countdown_seconds",
            "is_sprint_weekend",
            "is_this_weekend",
            "circuit_key",
            "circuit_name",
            "round_number",
            "year",
            "ready",
            "source",
            "session_key",
            "ok",
            "error",
        ):
            if key in body:
                extra[key] = body[key]
        if "rounds" in body:
            extra["rounds"] = len(body["rounds"] or [])
        if "sessions" in body:
            extra["sessions"] = [
                {
                    "type": s.get("session_type") or s.get("type"),
                    "status": s.get("status"),
                    "utc": s.get("datetime_utc") or s.get("date_start"),
                }
                for s in (body.get("sessions") or [])
            ]
        if "drivers" in body:
            extra["drivers"] = len(body["drivers"] or [])
        if "standings" in body:
            extra["standings"] = len(body["standings"] or [])
        if "laps" in body:
            extra["laps"] = len(body["laps"] or [])
        if "timing" in body and isinstance(body["timing"], dict):
            extra["timing_rows"] = len((body["timing"] or {}).get("rows") or [])
        if "positions" in body and isinstance(body["positions"], dict):
            extra["cars"] = len((body["positions"] or {}).get("positions") or [])
        if "results" in body:
            extra["results"] = len(body["results"] or [])
    return {k: v for k, v in item.items() if k != "body"} | extra


def main() -> None:
    now = datetime.now(timezone.utc)
    print(f"as_of_utc={now.isoformat()}")
    rows: list[dict] = []
    with httpx.Client(follow_redirects=True) as client:
        first = [
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
            "/api/circuit/netherlands/forecast",
            "/api/circuit/2026/15/preview",
            "/api/aris/stats",
        ]
        for path in first:
            rows.append(summarize(timed(client, path)))

        cal = next((r for r in rows if r["path"] == "/api/calendar/2026"), None)
        nxt = next((r for r in rows if r["path"] == "/api/next-race"), None)
        print("NEXT", json.dumps(nxt, default=str))
        print("CAL_META", {k: cal.get(k) for k in ("ok", "ms", "status", "rounds")} if cal else None)

        raw_cal = timed(client, "/api/calendar/2026")
        nl = None
        if isinstance(raw_cal.get("body"), dict):
            nl = next((r for r in raw_cal["body"].get("rounds") or [] if r.get("round_number") == 15), None)
        print("NL_ROUND", json.dumps(nl, default=str)[:2000] if nl else None)

        for stype in ("FP1", "SQ", "S", "Q", "R"):
            rows.append(summarize(timed(client, f"/api/live/session-key?year=2026&round_number=15&session_type={stype}", timeout=30)))

        hist = [
            "/api/race/2025/15/results",
            "/api/session/2025/15/R/results",
            "/api/session/2025/15/R/laps",
            "/api/race/2025/15/tyre-strategy",
            "/api/aris/plans?year=2026&round_number=15&driver=VER",
        ]
        for path in hist:
            rows.append(summarize(timed(client, path, timeout=90)))

        # Warm replay results (second hit should be memory-cache)
        rows.append(summarize({**timed(client, "/api/race/2025/15/results", timeout=30), "path": "/api/race/2025/15/results#warm"}))

        sk = next((r.get("session_key") for r in rows if r["path"].endswith("session_type=Q") and r.get("session_key")), None)
        if sk:
            ready = timed(client, f"/api/live/replay-ready?session_key={sk}&year=2026&round_number=15", timeout=90)
            rows.append(summarize(ready))
            start = None
            if isinstance(ready.get("body"), dict):
                start = ready["body"].get("date_start")
            if start:
                frame = timed(
                    client,
                    f"/api/live/replay-frame?session_key={sk}&as_of={start}&year=2026&round_number=15",
                    timeout=90,
                )
                rows.append(summarize(frame))
                rows.append(
                    summarize(
                        {
                            **timed(
                                client,
                                f"/api/live/replay-frame?session_key={sk}&as_of={start}&year=2026&round_number=15",
                                timeout=30,
                            ),
                            "path": "/api/live/replay-frame#warm",
                        }
                    )
                )

        for path in (f"{CF}/health", f"{CF}/api/health", f"{CF}/api/next-race", f"{CF}/"):
            rows.append(summarize(timed(client, path, timeout=25)))

    print("ROWS")
    print(json.dumps(rows, default=str, indent=2))


if __name__ == "__main__":
    main()
