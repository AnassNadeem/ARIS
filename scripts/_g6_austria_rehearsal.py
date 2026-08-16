"""G6.1 — sprint-sequence rehearsal (2024 Austria stand-in), timed vs E4.1."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

# E4.1 actuals (cached ingest→UI-ready). Compare against these, not only 120/300.
E41 = {
    "FP1": 11.1,
    "SQ": 6.7,
    "S": 10.2,
    "Q": 9.1,
    "R": 11.0,
    "weekend": 11.7,
}
AIMED_SESSION_S = 120.0
AIMED_WEEKEND_S = 300.0
SESSIONS = ("FP1", "SQ", "S", "Q", "R")
PY = str(_ROOT / ".venv" / "Scripts" / "python.exe")
if not Path(PY).exists():
    PY = sys.executable


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault(
        "ARIS_DB_URL",
        "postgresql+psycopg://aris:aris_local_dev_pw@127.0.0.1:5432/aris",
    )
    env["PYTHONPATH"] = "src"
    env.pop("ARIS_FAST_CLOCK", None)
    env.pop("ARIS_TRUE_COMPOUND_SLOPES", None)
    env.pop("ARIS_DECISION_LOG", None)
    return env


def _run(args: list[str]) -> tuple[float, str, int]:
    t0 = time.perf_counter()
    proc = subprocess.run(
        args,
        cwd=str(_ROOT),
        env=_env(),
        capture_output=True,
        text=True,
    )
    dt = time.perf_counter() - t0
    out = (proc.stdout or "") + (proc.stderr or "")
    return dt, out, proc.returncode


def _ui_ready(year: int, gp: str, session_type: str) -> tuple[float, str]:
    t0 = time.perf_counter()
    code = f"""
from aris.io import db
from aris.plan.weekend_form import weekend_form, weekend_session_types
races = db.fetch_races({year})
hit = races[races["country"].astype(str).str.lower().str.contains({gp.lower()!r})]
assert not hit.empty, "no race row — Strategy setup cannot list this GP"
row = hit.iloc[0]
sid = int(row["session_id"])
rnd = int(row["round_no"])
wk = db.fetch_weekend_sessions({year}, rnd)
types = set(wk["session_type"].astype(str).str.upper())
assert {session_type!r} in types or {session_type!r} == "R", types
drv = db.fetch_drivers(sid)
assert not drv.empty, "no drivers — Strategy cannot start"
forms = weekend_form({year}, rnd)
stypes = weekend_session_types({year}, rnd)
print(f"ui-ready session_id={{sid}} round={{rnd}} weekend_types={{stypes}} form_n={{len(forms)}} drivers={{len(drv)}}")
"""
    proc = subprocess.run(
        [PY, "-c", code],
        cwd=str(_ROOT),
        env=_env(),
        capture_output=True,
        text=True,
    )
    dt = time.perf_counter() - t0
    if proc.returncode != 0:
        raise RuntimeError(f"UI-ready probe failed: {proc.stderr or proc.stdout}")
    return dt, (proc.stdout or "").strip()


def main() -> int:
    print("=== G6.1 2024 Austria sprint-sequence rehearsal ===", flush=True)
    print(f"aimed per session <= {AIMED_SESSION_S:.0f}s; weekend <= {AIMED_WEEKEND_S:.0f}s", flush=True)
    print("E4.1 actuals: FP1 11.1 / SQ 6.7 / S 10.2 / Q 9.1 / R 11.0 / weekend 11.7", flush=True)
    results: dict[str, float] = {}
    failed = False

    for stype in SESSIONS:
        print(f"\n-- ingest_session.py 2024 Austria {stype} --", flush=True)
        dt, out, rc = _run([PY, "scripts/ingest_session.py", "2024", "Austria", stype])
        print(out[-800:] if len(out) > 800 else out, flush=True)
        if rc != 0:
            print(f"FAIL ingest {stype} exit={rc} in {dt:.2f}s", flush=True)
            failed = True
            continue
        probe_s, probe_msg = _ui_ready(2024, "Austria", stype)
        total = dt + probe_s
        results[stype] = total
        e41 = E41[stype]
        ceiling = "PASS" if total <= AIMED_SESSION_S else "FAIL"
        vs_e41 = total - e41
        print(
            f"{stype}: aimed <= {AIMED_SESSION_S:.0f}s  actual {total:.1f}s  "
            f"(ingest {dt:.1f}s + ui-ready {probe_s:.1f}s)  "
            f"E4.1 {e41:.1f}s  delta {vs_e41:+.1f}s  ceiling {ceiling}",
            flush=True,
        )
        print(f"  {probe_msg}", flush=True)

    print("\n-- ingest_weekend.py 2024 Austria --sprint --", flush=True)
    dt, out, rc = _run([PY, "scripts/ingest_weekend.py", "2024", "Austria", "--sprint"])
    print(out[-800:] if len(out) > 800 else out, flush=True)
    results["weekend"] = dt
    if rc != 0:
        print(f"FAIL weekend ingest exit={rc} in {dt:.2f}s", flush=True)
        failed = True
    else:
        e41 = E41["weekend"]
        ceiling = "PASS" if dt <= AIMED_WEEKEND_S else "FAIL"
        print(
            f"weekend: aimed <= {AIMED_WEEKEND_S:.0f}s  actual {dt:.1f}s  "
            f"E4.1 {e41:.1f}s  delta {dt - e41:+.1f}s  ceiling {ceiling}",
            flush=True,
        )

    print("\n=== G6.1 summary ===", flush=True)
    for key in (*SESSIONS, "weekend"):
        if key not in results:
            continue
        aimed = AIMED_WEEKEND_S if key == "weekend" else AIMED_SESSION_S
        print(
            f"  {key:8s} aimed <={aimed:.0f}s  actual {results[key]:.1f}s  "
            f"E4.1 {E41[key]:.1f}s",
            flush=True,
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
