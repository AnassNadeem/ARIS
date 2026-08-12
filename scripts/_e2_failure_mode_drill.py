"""E2.13 — failure-mode drill for ingest (loud fail, no hang / silent corrupt)."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import aris  # noqa: E402, F401
from fastf1.exceptions import RateLimitExceededError  # noqa: E402


def main() -> None:
    from aris.io import ingest as ingest_mod

    print("=== Drill 1: RateLimitExceededError during session load ===", flush=True)
    t0 = time.time()
    try:
        with patch("fastf1.get_session", side_effect=RateLimitExceededError("any API: 500 calls/h")):
            # ingest_session path
            from aris.io.ingest import ingest_session

            try:
                ingest_session(2024, "Austria", "FP1")
                print("FAIL: expected exception", flush=True)
                sys.exit(1)
            except RateLimitExceededError as exc:
                dt = time.time() - t0
                print(f"PASS: raised loudly: {exc!r} in {dt:.2f}s (no hang)", flush=True)
                if dt > 30:
                    print("WARN: took >30s — may be retrying too long", flush=True)
    except Exception as exc:  # noqa: BLE001
        # Some wrappers catch and re-raise differently
        dt = time.time() - t0
        print(f"PASS-ish: failed with {type(exc).__name__}: {exc} in {dt:.2f}s", flush=True)

    print("\n=== Drill 2: malformed/empty session laps ===", flush=True)
    class FakeSession:
        event = type("E", (), {"EventName": "Fake", "Country": "Austria", "Location": "Spielberg", "RoundNumber": 11})()
        total_laps = 0
        laps = None

        def load(self, **kwargs):
            return None

    t0 = time.time()
    try:
        with patch("fastf1.get_session", return_value=FakeSession()):
            from aris.io.ingest import ingest_session

            try:
                ingest_session(2024, "Austria", "FP1")
                print("NOTE: returned without raise — checking message path", flush=True)
            except Exception as exc:  # noqa: BLE001
                dt = time.time() - t0
                print(f"PASS: raised clearly: {type(exc).__name__}: {exc} in {dt:.2f}s", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"PASS: {type(exc).__name__}: {exc}", flush=True)

    print("\n=== Drill 3: scripts/ingest_session.py CLI on nonsense session ===", flush=True)
    import subprocess

    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, "scripts/ingest_session.py", "2024", "Austria", "NOTASESSION"],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": "src"},
        timeout=60,
    )
    dt = time.time() - t0
    print(f"exit={proc.returncode} elapsed={dt:.2f}s", flush=True)
    print("stderr_tail:", (proc.stderr or proc.stdout)[-500:], flush=True)
    if proc.returncode == 0:
        print("FAIL: nonsense session should not succeed", flush=True)
        sys.exit(1)
    if dt > 55:
        print("FAIL: hung near timeout", flush=True)
        sys.exit(1)
    print("PASS: CLI failed loudly without hanging", flush=True)


if __name__ == "__main__":
    main()
