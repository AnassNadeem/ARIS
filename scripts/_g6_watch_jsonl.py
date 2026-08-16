"""G6.2 — Watch-mode JSONL I/O under load (2025 Netherlands, locked scenario)."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from aris.decisions.persist import JsonlDecisionLog
from aris.decisions.queue import DecisionKind, DecisionQueue
from aris.engine.session import RaceEngineSession, SessionPhase
from aris.eval.backtest import walk_race_triggers
from aris.io import db
from aris.plan.prewrite import generate_strat_plans
from aris.state import RaceState
from aris.tracks import clear_track_config_cache, load_track_config

# Live 1x sector cadence. JSONL append must stay far below this.
LIVE_TICK_INTERVAL_S = 25.0
NOTICEABLE_WRITE_S = 0.05  # 50 ms would be felt against a 25 s tick; aimed << this


class TimedJsonlDecisionLog(JsonlDecisionLog):
    def __init__(self, path: Path, *, source: str = "live") -> None:
        super().__init__(path, source=source)
        self.write_times_s: list[float] = []

    def append(self, event: str, payload: dict) -> None:
        t0 = time.perf_counter()
        super().append(event, payload)
        self.write_times_s.append(time.perf_counter() - t0)


def _state() -> RaceState:
    return RaceState(
        session_id=1,
        driver_id=1,
        driver_code="VER",
        driver_name="Max",
        year=2025,
        round_no=15,
        country="Netherlands",
        lap_number=10,
        compound="MEDIUM",
        tyre_life=10,
        fuel_kg=80.0,
        laps_remaining=62,
        lag1_pace=75.0,
        lag2_pace=75.1,
        stint_roll3=75.0,
    )


def _find_nl_2025() -> dict:
    races = db.fetch_races(2025)
    nl = races[races["country"].astype(str).str.lower().str.contains("nether")]
    if nl.empty:
        raise RuntimeError("2025 Netherlands race not in DB")
    row = nl.iloc[0]
    drivers = db.fetch_drivers(int(row["session_id"]))
    drv = drivers[drivers["code"] == "VER"]
    if drv.empty:
        drv = drivers.iloc[[0]]
    d = drv.iloc[0]
    return {
        "session_id": int(row["session_id"]),
        "year": 2025,
        "round_no": int(row["round_no"]),
        "country": str(row["country"]),
        "driver_id": int(d["driver_id"]),
        "driver_code": str(d["code"]),
        "team": str(d.get("team") or ""),
    }


def _unwritable_check() -> None:
    blocked = _ROOT / "results" / "g6" / "not_a_directory"
    blocked.parent.mkdir(parents=True, exist_ok=True)
    blocked.write_text("file not dir\n", encoding="utf-8")
    log = JsonlDecisionLog(blocked / "events.jsonl", source="test")
    q = DecisionQueue()
    q.bind_log(log)
    try:
        q.propose(_state(), kind=DecisionKind.PIT, use_llm=False, mc_draws=0)
        raise RuntimeError("FAIL: unwritable log was swallowed (propose returned)")
    except RuntimeError as exc:
        if "decision log write failed" not in str(exc):
            raise
        print(f"unwritable: LOUD fail as aimed — {exc}", flush=True)


def main() -> int:
    os.environ.pop("ARIS_TRUE_COMPOUND_SLOPES", None)
    os.environ.pop("ARIS_FAST_CLOCK", None)
    # Default-on logging, isolated dir so we do not mix with prior backtests.
    os.environ.pop("ARIS_DECISION_LOG", None)
    log_dir = _ROOT / "results" / "g6" / "decisions"
    log_dir.mkdir(parents=True, exist_ok=True)
    os.environ["ARIS_DECISION_LOG_DIR"] = str(log_dir)

    print("=== G6.2 Watch-mode JSONL I/O (2025 Netherlands VER) ===", flush=True)
    print(
        f"aimed: every propose/resolve written in order; write << {LIVE_TICK_INTERVAL_S:.0f}s live tick "
        f"(noticeable threshold {NOTICEABLE_WRITE_S*1000:.0f} ms); unwritable fails loudly",
        flush=True,
    )

    print("\n-- unwritable results/decisions stand-in --", flush=True)
    _unwritable_check()

    clear_track_config_cache()
    setup = _find_nl_2025()
    track = load_track_config(setup["country"], year=setup["year"], round_no=setup["round_no"])
    print(
        f"[setup] session_id={setup['session_id']} driver={setup['driver_code']} "
        f"laps={track.total_laps} slopes={track.compound_slopes}",
        flush=True,
    )

    session = RaceEngineSession(
        session_id=setup["session_id"],
        driver_id=setup["driver_id"],
        driver_code=setup["driver_code"],
        team=setup["team"],
        year=setup["year"],
        round_no=setup["round_no"],
        country=setup["country"],
        total_laps=track.total_laps,
        phase=SessionPhase.LIVE,
    )
    timed = TimedJsonlDecisionLog(
        log_dir / f"{setup['year']}_r{setup['round_no']}_{setup['driver_code']}_{setup['session_id']}.jsonl",
        source="live",
    )
    timed.meta = {
        "session_id": setup["session_id"],
        "driver_id": setup["driver_id"],
        "driver_code": setup["driver_code"],
        "year": setup["year"],
        "round_no": setup["round_no"],
        "country": setup["country"],
    }
    session.decision_queue.bind_log(timed)

    plans = generate_strat_plans(
        setup["session_id"],
        setup["driver_id"],
        year=setup["year"],
        round_no=setup["round_no"],
        country=setup["country"],
        driver_code=setup["driver_code"],
    )
    if plans.plans:
        session.active_strat = plans.plans[0]

    all_laps = db.fetch_all_laps(setup["session_id"])
    t0 = time.perf_counter()
    # mc_draws=0: same ranking identity as the G1–G5 backtest walker. JSONL I/O
    # is after recommend(); live Watch still uses DEFAULT_DRAWS for scoring.
    ticks, _recs = walk_race_triggers(session, all_laps, mc_draws=0)
    walk_s = time.perf_counter() - t0

    path = timed.path
    if not path.exists():
        print(f"FAIL: JSONL not created at {path}", flush=True)
        return 1
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    events = [json.loads(line) for line in lines]
    n_prop = sum(1 for e in events if e.get("event") == "propose")
    n_res = sum(1 for e in events if e.get("event") == "resolve")
    order_ok = all(
        events[i]["event"] == "propose" and events[i + 1]["event"] == "resolve"
        for i in range(0, len(events) - 1, 2)
    ) and n_prop == n_res
    ts = [e.get("ts") for e in events]
    ts_ok = ts == sorted(ts)
    kinds = [e.get("kind") for e in events if e.get("event") == "propose"]

    writes = timed.write_times_s
    max_w = max(writes) if writes else float("nan")
    mean_w = (sum(writes) / len(writes)) if writes else float("nan")
    mean_tick = walk_s / ticks if ticks else float("nan")

    print(f"[walk] ticks={ticks} elapsed={walk_s:.2f}s mean_tick={mean_tick*1000:.2f}ms", flush=True)
    print(
        f"[jsonl] path={path.name} lines={len(events)} propose={n_prop} resolve={n_res} "
        f"order_ok={order_ok} ts_monotonic={ts_ok}",
        flush=True,
    )
    print(
        f"[write] n={len(writes)} mean={mean_w*1000:.3f}ms max={max_w*1000:.3f}ms "
        f"aimed << {NOTICEABLE_WRITE_S*1000:.0f}ms (live tick {LIVE_TICK_INTERVAL_S:.0f}s)",
        flush=True,
    )
    print(f"[kinds] first10={kinds[:10]} last5={kinds[-5:]}", flush=True)

    # One live-default propose to show write is negligible vs recommend().
    from aris.montecarlo import DEFAULT_DRAWS

    mid = session.build_state(min(25, track.total_laps - 5))
    q2 = DecisionQueue()
    q2.bind_log(timed)
    t_rec = time.perf_counter()
    q2.propose(mid, kind=DecisionKind.PIT, use_llm=False)  # DEFAULT_DRAWS
    rec_s = time.perf_counter() - t_rec
    last_write = timed.write_times_s[-1]
    print(
        f"[live-default propose] mc_draws={DEFAULT_DRAWS} actual {rec_s:.3f}s  "
        f"JSONL write {last_write*1000:.3f}ms  "
        f"(write is {last_write / rec_s * 100:.4f}% of propose)",
        flush=True,
    )

    failed = False
    if not order_ok or n_prop != n_res or n_prop < 1:
        print("FAIL: propose/resolve not written in order or empty", flush=True)
        failed = True
    if not ts_ok:
        print("FAIL: timestamps not monotonic", flush=True)
        failed = True
    if max_w >= NOTICEABLE_WRITE_S:
        print(
            f"FAIL: JSONL write max {max_w:.3f}s >= noticeable {NOTICEABLE_WRITE_S:.3f}s",
            flush=True,
        )
        failed = True
    if ticks < 200:
        print(f"FAIL: expected full-race ticks (~287), got {ticks}", flush=True)
        failed = True

    print(
        "\nG6.2 " + ("FAIL" if failed else "OK") + f"  propose={n_prop} resolve={n_res} "
        f"max_write_ms={max_w*1000:.3f}",
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
