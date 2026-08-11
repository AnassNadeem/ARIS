"""Held-out lap-time MAE evaluation harness."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from aris.eval.baseline import moving_average_baseline
from aris.eval.scoring import mae
from aris.models.features import build_from_fastf1
from aris.models.predict import (
    predict_blended_frame,
    predict_from_lap_row,
    reset_model_cache,
)
from aris.models.residual import DEFAULT_MODEL_PATH, REFERENCE_RACES, train_residual_model
from aris.physics.stint import detect_stints, filter_clean_laps
from aris.tracks import clear_track_config_cache, load_track_config

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BASELINE_FLOOR_S = 0.460
_RESULTS_DIR = _REPO_ROOT / "results"
_CSV_PATH = _RESULTS_DIR / "heldout-laptime-mae.csv"

HELD_OUT_RACES: list[tuple[int, str]] = [
    # Must stay disjoint from aris.models.residual.REFERENCE_RACES
    # (2018–2023). Phase D expands beyond the original five 2024 races to
    # cover newly configured circuits across the full 2024 calendar.
    (2024, "Bahrain"),
    (2024, "Saudi Arabia"),
    (2024, "Australia"),
    (2024, "Japan"),
    (2024, "China"),
    (2024, "Miami"),
    (2024, "Emilia Romagna"),
    (2024, "Monaco"),
    (2024, "Canada"),
    (2024, "Spain"),
    (2024, "Austria"),
    (2024, "Britain"),
    (2024, "Hungary"),
    (2024, "Belgium"),
    (2024, "Netherlands"),
    (2024, "Italy"),
    (2024, "Azerbaijan"),
    (2024, "Singapore"),
    (2024, "United States"),
    (2024, "Mexico City"),
    (2024, "Sao Paulo"),
    (2024, "Las Vegas"),
    (2024, "Qatar"),
    (2024, "Abu Dhabi"),
]


def _race_id(year: int, gp: str) -> str:
    return f"{year}-{gp.replace(' ', '_')}"


def _score_baseline(year: int, gp: str, window: int = 2) -> tuple[np.ndarray, np.ndarray, str]:
    import fastf1

    session = fastf1.get_session(year, gp, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    clean = filter_clean_laps(detect_stints(session.laps))
    preds = moving_average_baseline(clean, window=window).reindex(clean.index)
    mask = preds.notna()
    return clean.loc[mask, "LapTimeS"].to_numpy(), preds.loc[mask].to_numpy(), _race_id(year, gp)


def _score_predictor(year: int, gp: str) -> tuple[np.ndarray, np.ndarray, str]:
    rid = _race_id(year, gp)
    frame = build_from_fastf1(year, gp)
    if frame.empty:
        return np.array([]), np.array([]), rid
    y_true = frame["target"].to_numpy()
    y_pred = np.array([predict_from_lap_row(row) for _, row in frame.iterrows()])
    return y_true, y_pred, rid


def _score_physics_only(year: int, gp: str) -> tuple[np.ndarray, np.ndarray, str]:
    rid = _race_id(year, gp)
    frame = build_from_fastf1(year, gp)
    if frame.empty:
        return np.array([]), np.array([]), rid
    return frame["target"].to_numpy(), frame["physics_pred"].to_numpy(), rid


def _score_blended(year: int, gp: str) -> tuple[np.ndarray, np.ndarray, str]:
    rid = _race_id(year, gp)
    frame = build_from_fastf1(year, gp)
    if frame.empty:
        return np.array([]), np.array([]), rid
    y_pred = predict_blended_frame(frame)
    return frame["target"].to_numpy(), y_pred, rid


def report_track_config_coverage() -> list[dict[str, object]]:
    """Factually report whether each held-out race has a YAML track config."""
    from aris.tracks import _match_track_file

    rows: list[dict[str, object]] = []
    for year, gp in HELD_OUT_RACES:
        cfg = load_track_config(gp)
        path = _match_track_file(gp)
        using_fallback = path is None
        rows.append(
            {
                "race": f"{year} {gp}",
                "race_id": _race_id(year, gp),
                "yaml_path": str(path) if path else None,
                "using_bahrain_fallback": using_fallback,
                "total_laps": cfg.total_laps,
                "pit_loss_s": cfg.pit_loss_s,
                "physics_profile": cfg.physics_profile,
            }
        )
    return rows


def _load_or_init_results() -> pd.DataFrame:
    if _CSV_PATH.exists():
        df = pd.read_csv(_CSV_PATH)
        # Drop comment/footer rows if any slipped in.
        df = df[df["race_id"].astype(str).str.match(r"^(20\d{2}-|OVERALL$)")].copy()
        return df
    return pd.DataFrame(columns=["race_id", "mae_s", "n_laps"])


def _upsert_columns(df: pd.DataFrame, per_race: dict[str, dict[str, float | int]]) -> pd.DataFrame:
    """Merge new per-race metrics into the results frame; keep existing columns."""
    race_ids = [_race_id(y, g) for y, g in HELD_OUT_RACES] + ["OVERALL"]
    if df.empty:
        df = pd.DataFrame({"race_id": race_ids})
    else:
        missing = [r for r in race_ids if r not in set(df["race_id"])]
        if missing:
            df = pd.concat([df, pd.DataFrame({"race_id": missing})], ignore_index=True)

    for rid, metrics in per_race.items():
        mask = df["race_id"] == rid
        for col, val in metrics.items():
            if col not in df.columns:
                df[col] = np.nan
            df.loc[mask, col] = val
    # Stable row order.
    order = {r: i for i, r in enumerate(race_ids)}
    df["_ord"] = df["race_id"].map(lambda r: order.get(r, 999))
    df = df.sort_values("_ord").drop(columns=["_ord"]).reset_index(drop=True)
    return df


def run_eval(
    *,
    train_if_missing: bool = True,
    modes: tuple[str, ...] = ("baseline", "physics_only", "physics_residual"),
    column_prefix: str = "b1",
) -> dict[str, dict[str, float]]:
    """Run held-out MAE for requested modes and extend the results CSV.

    ``column_prefix`` namespaces new columns (e.g. b1_physics_only_mae_s) so
    Block 1/2/3 passes can sit side-by-side without overwriting each other.
    The Phase A ``mae_s`` column is preserved; when physics_residual is scored
    it is also written to ``{prefix}_physics_residual_mae_s`` and mirrored into
    ``mae_s`` only when prefix == \"b1\" (first reproduction of shipped model).
    """
    import fastf1

    overlap = set(HELD_OUT_RACES) & set(REFERENCE_RACES)
    if overlap:
        raise RuntimeError(
            f"HELD_OUT_RACES overlaps REFERENCE_RACES: {sorted(overlap)!r}. "
            "Held-out MAE is meaningless if training races leak into the holdout."
        )

    cache = _REPO_ROOT / "fastf1_cache"
    cache.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache))
    clear_track_config_cache()

    reset_model_cache()
    need_residual = "physics_residual" in modes
    if need_residual and train_if_missing and not DEFAULT_MODEL_PATH.exists():
        print("No residual model found — training now...")
        _, metrics = train_residual_model()
        print(f"Training CV MAE: {metrics['cv_mae_mean']:.3f} +/- {metrics['cv_mae_std']:.3f} s")
        reset_model_cache()

    print("Train races (REFERENCE_RACES):")
    for year, gp in REFERENCE_RACES:
        print(f"  {year} {gp}")
    print("Held-out races (HELD_OUT_RACES):")
    for year, gp in HELD_OUT_RACES:
        print(f"  {year} {gp}")

    print("\n=== Track config coverage (held-out) ===")
    for row in report_track_config_coverage():
        status = (
            "FALLBACK->Bahrain defaults"
            if row["using_bahrain_fallback"]
            else f"YAML {row['yaml_path']}"
        )
        print(
            f"{row['race']:18s}  {status}  "
            f"(laps={row['total_laps']}, pit_loss={row['pit_loss_s']}, "
            f"physics={row['physics_profile']})"
        )

    per_race_out: dict[str, dict[str, float | int]] = {
        _race_id(y, g): {} for y, g in HELD_OUT_RACES
    }
    per_race_out["OVERALL"] = {}
    summary: dict[str, dict[str, float]] = {}

    if "baseline" in modes:
        print("\n=== MA(2) baseline (held-out) ===")
        all_t: list[np.ndarray] = []
        all_p: list[np.ndarray] = []
        for year, gp in HELD_OUT_RACES:
            yt, yp, rid = _score_baseline(year, gp, window=2)
            m = mae(yt, yp)
            per_race_out[rid]["baseline_mae_s"] = float(m)
            per_race_out[rid]["n_laps_baseline"] = int(len(yt))
            all_t.append(yt)
            all_p.append(yp)
            print(f"{rid:22s} n={len(yt):4d}  MAE={m:.3f} s")
        overall = mae(np.concatenate(all_t), np.concatenate(all_p))
        per_race_out["OVERALL"]["baseline_mae_s"] = float(overall)
        per_race_out["OVERALL"]["n_laps_baseline"] = int(sum(len(a) for a in all_t))
        summary["baseline"] = {"overall": float(overall)}
        print(f"OVERALL                n={sum(len(a) for a in all_t):4d}  MAE={overall:.3f} s")

    if "physics_only" in modes:
        print("\n=== Physics-only (no residual) ===")
        all_t = []
        all_p = []
        col = f"{column_prefix}_physics_only_mae_s"
        for year, gp in HELD_OUT_RACES:
            yt, yp, rid = _score_physics_only(year, gp)
            if len(yt) == 0:
                print(f"{rid:22s} SKIP (no scored laps)")
                continue
            m = mae(yt, yp)
            per_race_out[rid][col] = float(m)
            per_race_out[rid]["n_laps"] = int(len(yt))
            all_t.append(yt)
            all_p.append(yp)
            print(f"{rid:22s} n={len(yt):4d}  MAE={m:.3f} s")
        overall = mae(np.concatenate(all_t), np.concatenate(all_p))
        per_race_out["OVERALL"][col] = float(overall)
        per_race_out["OVERALL"]["n_laps"] = int(sum(len(a) for a in all_t))
        summary["physics_only"] = {"overall": float(overall)}
        print(f"OVERALL                n={sum(len(a) for a in all_t):4d}  MAE={overall:.3f} s")

    if "physics_residual" in modes:
        print("\n=== Physics + residual (shipped stack) ===")
        reset_model_cache()
        all_t = []
        all_p = []
        col = f"{column_prefix}_physics_residual_mae_s"
        for year, gp in HELD_OUT_RACES:
            yt, yp, rid = _score_predictor(year, gp)
            if len(yt) == 0:
                print(f"{rid:22s} SKIP (no scored laps)")
                continue
            m = mae(yt, yp)
            per_race_out[rid][col] = float(m)
            per_race_out[rid]["n_laps"] = int(len(yt))
            if column_prefix == "b1":
                # Keep Phase-A column name as the Block-1 reproduction of shipped MAE.
                per_race_out[rid]["mae_s"] = float(m)
            all_t.append(yt)
            all_p.append(yp)
            print(f"{rid:22s} n={len(yt):4d}  MAE={m:.3f} s")
        overall = mae(np.concatenate(all_t), np.concatenate(all_p))
        per_race_out["OVERALL"][col] = float(overall)
        per_race_out["OVERALL"]["n_laps"] = int(sum(len(a) for a in all_t))
        if column_prefix == "b1":
            per_race_out["OVERALL"]["mae_s"] = float(overall)
        summary["physics_residual"] = {"overall": float(overall)}
        print(f"OVERALL                n={sum(len(a) for a in all_t):4d}  MAE={overall:.3f} s")
        print(f"(baseline floor = {_BASELINE_FLOOR_S:.3f} s)")
        if overall < _BASELINE_FLOOR_S:
            print("PASS — beats MA(2) baseline floor.")
        else:
            print("NOTE — does not beat MA(2) floor yet.")

    if "blended" in modes:
        print("\n=== Blended physics+residual + MA(2) (inverse-variance) ===")
        reset_model_cache()
        all_t = []
        all_p = []
        col = f"{column_prefix}_blended_mae_s"
        for year, gp in HELD_OUT_RACES:
            yt, yp, rid = _score_blended(year, gp)
            if len(yt) == 0:
                print(f"{rid:22s} SKIP (no scored laps)")
                continue
            m = mae(yt, yp)
            per_race_out[rid][col] = float(m)
            per_race_out[rid]["n_laps"] = int(len(yt))
            all_t.append(yt)
            all_p.append(yp)
            print(f"{rid:22s} n={len(yt):4d}  MAE={m:.3f} s")
        overall = mae(np.concatenate(all_t), np.concatenate(all_p))
        per_race_out["OVERALL"][col] = float(overall)
        per_race_out["OVERALL"]["n_laps"] = int(sum(len(a) for a in all_t))
        summary["blended"] = {"overall": float(overall)}
        print(f"OVERALL                n={sum(len(a) for a in all_t):4d}  MAE={overall:.3f} s")
        print(f"(baseline floor = {_BASELINE_FLOOR_S:.3f} s)")
        if overall < _BASELINE_FLOOR_S:
            print("PASS — beats MA(2) baseline floor.")
        else:
            print("NOTE — does not beat MA(2) floor yet.")

    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df = _load_or_init_results()
    df = _upsert_columns(df, per_race_out)
    df.to_csv(_CSV_PATH, index=False, float_format="%.6f")
    print(f"\nWrote {_CSV_PATH}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Held-out lap-time MAE evaluation.")
    parser.add_argument("--no-train", action="store_true", help="fail if model artefact missing")
    parser.add_argument(
        "--prefix",
        default="b1",
        help="column namespace for this pass (b1/b2/b3)",
    )
    parser.add_argument(
        "--modes",
        default="baseline,physics_only,physics_residual",
        help="comma-separated: baseline,physics_only,physics_residual,blended",
    )
    args = parser.parse_args()
    modes = tuple(m.strip() for m in args.modes.split(",") if m.strip())
    run_eval(train_if_missing=not args.no_train, modes=modes, column_prefix=args.prefix)


if __name__ == "__main__":
    main()
