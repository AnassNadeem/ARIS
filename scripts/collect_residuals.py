"""Collect simulator residuals from existing dry-87 backtest JSON.

Does not re-walk the full backtest. Uses stored team_sim_s / aris_sim_s on
mismatches, and a stay-out / team-action resim on matches when the DB is up.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from aris.eval.backtest import Inflection, team_action_for  # noqa: E402
from aris.simulate import ActionKind, StrategyAction, simulate  # noqa: E402
from aris.tracks import load_track_config  # noqa: E402
from aris.uncertainty.conformal import (  # noqa: E402
    empirical_coverage,
    fit_conformal,
    save_conformal_result,
)

_DRY = frozenset({"SOFT", "MEDIUM", "HARD", "C1", "C2", "C3", "C4", "C5"})
_JSON_2024 = _ROOT / "results" / "backtest" / "2024_full.json"
_JSON_2025 = _ROOT / "results" / "backtest" / "t92" / "2025_full.json"
_JSON_2025_FALLBACK = _ROOT / "results" / "backtest" / "2025_full.json"
_OUT = _ROOT / "data" / "simulator_residuals.parquet"


def _load_races(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _scored_dry(decision: dict) -> bool:
    if decision.get("classification") == "divergence_insufficient_info":
        return False
    compound = str(decision.get("state_compound") or "").upper()
    if compound not in _DRY:
        return False
    if bool(decision.get("state_rainfall")):
        return False
    return True


def _inflection(decision: dict) -> Inflection:
    inf = decision.get("inflection") or {}
    return Inflection(
        kind=str(inf.get("kind") or "pit"),
        lap=int(inf.get("lap") or 0),
        compound=inf.get("compound"),
        team_pitted=bool(inf.get("team_pitted")),
        notes=str(inf.get("notes") or ""),
    )


def _resim_pair(session_id: int, driver_code: str, decision: dict) -> tuple[float, float, float] | None:
    """Current-sim stay-out, team remaining, and ARIS predicted delta vs stay-out."""
    try:
        from aris.io import db
        from aris.recommend import recommend
        from aris.state import build_race_state

        drv = db.fetch_driver_by_code(session_id, driver_code)
        if drv is None:
            return None
        driver_id = int(drv["driver_id"])
        lap = int((decision.get("inflection") or {}).get("lap") or 0)
        state = build_race_state(session_id, driver_id, lap)
        stay = simulate(state, StrategyAction(kind=ActionKind.STAY_OUT))
        team = simulate(state, team_action_for(_inflection(decision), state))
        rec = recommend(state, top_k=3, mc_draws=0)
        predicted = float(rec.recommendations[0].delta_vs_stay_out_s) if rec.recommendations else 0.0
        return float(stay.total_race_time_s), float(team.total_race_time_s), predicted
    except Exception:
        return None


def _row_from_decision(race: dict, decision: dict) -> dict | None:
    if not _scored_dry(decision):
        return None
    year = int(decision.get("year") or race.get("year"))
    gp = str(decision.get("gp") or race.get("gp"))
    lap = int((decision.get("inflection") or {}).get("lap") or 0)
    session_id = int(race.get("session_id") or 0)
    driver = str(decision.get("driver_code") or race.get("driver_code") or "")
    compound = str(decision.get("state_compound") or "")
    tyre_life = int(decision.get("state_tyre_life") or 0)
    try:
        total = int(load_track_config(gp, year=year).total_laps)
    except Exception:
        total = 57
    laps_remaining = max(0, total - lap)

    resim = _resim_pair(session_id, driver, decision)
    if resim is None:
        return None
    stay_s, team_s, predicted_delta = resim
    actual_delta = float(team_s) - float(stay_s)
    error = actual_delta - float(predicted_delta)
    inf = decision.get("inflection") or {}
    return {
        "inflection_id": f"{year}-{gp}-{driver}-{lap}-{inf.get('kind')}",
        "year": year,
        "circuit": gp,
        "compound": compound,
        "stint_length": tyre_life,
        "laps_remaining": laps_remaining,
        "predicted_delta": predicted_delta,
        "actual_delta": actual_delta,
        "error": error,
        "classification": decision.get("classification"),
    }


def collect(paths: list[Path] | None = None) -> pd.DataFrame:
    files = paths or [
        _JSON_2024,
        _JSON_2025 if _JSON_2025.is_file() else _JSON_2025_FALLBACK,
    ]
    rows: list[dict] = []
    for path in files:
        if not path.is_file():
            print(f"missing {path}", flush=True)
            continue
        races = _load_races(path)
        print(f"reading {path} ({len(races)} races)", flush=True)
        for i, race in enumerate(races, start=1):
            gp = race.get("gp")
            n_before = len(rows)
            for decision in race.get("decisions") or []:
                row = _row_from_decision(race, decision)
                if row is not None:
                    rows.append(row)
            print(
                f"  {i}/{len(races)} {race.get('year')} {gp} "
                f"+{len(rows) - n_before} scored",
                flush=True,
            )
    return pd.DataFrame(rows)


def fit_and_save(df: pd.DataFrame) -> dict:
    cal = df[df["year"] == 2024]
    test = df[df["year"] == 2025]
    all_fit = fit_conformal(cal["error"].to_numpy())
    short = fit_conformal(cal.loc[cal["laps_remaining"] < 20, "error"].to_numpy())
    long = fit_conformal(cal.loc[cal["laps_remaining"] >= 20, "error"].to_numpy())
    coverage = {
        "all": empirical_coverage(test["error"].to_numpy(), all_fit["q_hat"]),
        "short": empirical_coverage(
            test.loc[test["laps_remaining"] < 20, "error"].to_numpy(),
            short["q_hat"],
        ),
        "long": empirical_coverage(
            test.loc[test["laps_remaining"] >= 20, "error"].to_numpy(),
            long["q_hat"],
        ),
    }
    payload = {
        **all_fit,
        "short": short,
        "long": long,
        "coverage_2025": coverage,
        "n_2024": int(len(cal)),
        "n_2025": int(len(test)),
    }
    save_conformal_result(payload)
    print(json.dumps(payload, indent=2, default=str))
    return payload


def main() -> int:
    df = collect()
    if df.empty:
        print("no residuals collected")
        return 1
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(_OUT, index=False)
    print(
        f"wrote {_OUT} n={len(df)} "
        f"2024={int((df.year == 2024).sum())} 2025={int((df.year == 2025).sum())}",
        flush=True,
    )
    print(
        f"error median={df['error'].median():.2f}s  "
        f"p90_abs={np.quantile(np.abs(df['error']), 0.90):.2f}s",
        flush=True,
    )
    fit_and_save(df)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
