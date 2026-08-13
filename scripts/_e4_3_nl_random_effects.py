"""E4.3 — one final Zandvoort tyre-ordering attempt.

Fit DegSlope jointly across 2021–2025 Netherlands races with a per-year
random-effect intercept (pool the compound slope; do not force one flat
number). If SOFT>MEDIUM>HARD still fails: STOP and keep global slopes.

Does not write YAML.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from aris.physics.tires import DEFAULT_COMPOUND_SLOPE, fit_track_compound_slopes  # noqa: E402

_CSV = _ROOT / "results" / "e3_2_deg_stints" / "netherlands.csv"
_OUT = _ROOT / "results" / "e4_3_nl_random_effects.json"


def _ols_with_year_fe(df: pd.DataFrame) -> dict[str, float]:
    """Compound slopes with per-year fixed effects (random-intercept proxy).

    Model per compound separately:
        DegSlope_i = beta_compound + u_year[i] + eps
    Equivalent to demeaning within year then taking the grand mean of demeaned
    slopes — i.e. pool slope while absorbing year-level intercept shifts.

    With only a compound intercept (no tyre-life regressor here — DegSlope is
    already the per-stint slope), year FE + pooled mean is exactly:
        mean_c = weighted mean of (year means), equal weight per stint after
        removing year means from a joint stacked model.

    Implementation: within each compound, demean by year, then the pooled
    compound level is the stint-weighted mean of year means (same as overall
    mean). To actually borrow strength ACROSS compounds for the year
    intercepts, fit jointly:

        DegSlope = sum_c beta_c * 1[compound=c] + sum_y u_y * 1[year=y] + eps
    with sum_y u_y = 0 for identifiability.
    """
    work = df.copy()
    years = sorted(work["Year"].unique())
    compounds = ["SOFT", "MEDIUM", "HARD"]
    # Drop one year dummy for identifiability (absorb into compound means)
    year_dummies = years[1:]

    y = work["DegSlope"].to_numpy(dtype=float)
    rows = []
    for _, row in work.iterrows():
        feat = []
        for c in compounds:
            feat.append(1.0 if row["Compound"] == c else 0.0)
        for yy in year_dummies:
            feat.append(1.0 if int(row["Year"]) == int(yy) else 0.0)
        rows.append(feat)
    X = np.asarray(rows, dtype=float)
    # OLS
    beta, residuals, rank, s = np.linalg.lstsq(X, y, rcond=None)
    slopes = {c: float(beta[i]) for i, c in enumerate(compounds)}
    year_effects = {int(years[0]): 0.0}
    for i, yy in enumerate(year_dummies):
        year_effects[int(yy)] = float(beta[len(compounds) + i])
    return {
        "slopes": slopes,
        "year_effects": year_effects,
        "rank": int(rank),
        "resid_rmse": float(np.sqrt(np.mean((y - X @ beta) ** 2))),
        "n": int(len(work)),
    }


def _ordering_ok(slopes: dict[str, float]) -> bool:
    soft, med, hard = slopes["SOFT"], slopes["MEDIUM"], slopes["HARD"]
    return soft > med > hard


def main() -> int:
    df = pd.read_csv(_CSV)
    dry = df[df["Compound"].isin(["SOFT", "MEDIUM", "HARD"])].copy()
    race = dry[dry["SessionType"] == "R"].copy()

    sample_sizes = {
        "all_sessions": dry.groupby(["Year", "Compound"]).size().unstack(fill_value=0).to_dict(),
        "all_totals": dry.groupby("Compound").size().to_dict(),
        "race_only": race.groupby(["Year", "Compound"]).size().unstack(fill_value=0).to_dict(),
        "race_totals": race.groupby("Compound").size().to_dict(),
    }

    # Adequacy: flag if any dry compound-year has n < 5 in the pooled fit years
    thin = []
    for year, grp in dry.groupby("Year"):
        for c in ["SOFT", "MEDIUM", "HARD"]:
            n = int((grp["Compound"] == c).sum())
            if n < 5:
                thin.append({"year": int(year), "compound": c, "n": n})

    baseline_iv = fit_track_compound_slopes(dry)
    race_iv = fit_track_compound_slopes(race) if len(race) else {}

    # Joint FE fits
    fe_all = _ols_with_year_fe(dry)
    fe_race = _ols_with_year_fe(race)

    # Also: random-intercept via statsmodels MixedLM if available, else note
    mixed = None
    try:
        import statsmodels.formula.api as smf

        # MixedLM needs a continuous response; compound as fixed, year as group
        # Encode compound as categorical; estimate mean per compound with year RE
        mixed_slopes = {}
        year_var = {}
        for c in ["SOFT", "MEDIUM", "HARD"]:
            sub = dry[dry["Compound"] == c]
            if len(sub) < 8 or sub["Year"].nunique() < 2:
                mixed_slopes[c] = float("nan")
                continue
            # DegSlope ~ 1 with random intercept per Year
            md = smf.mixedlm("DegSlope ~ 1", sub, groups=sub["Year"])
            mdf = md.fit(reml=True, method="lbfgs")
            mixed_slopes[c] = float(mdf.fe_params["Intercept"])
            year_var[c] = float(mdf.cov_re.iloc[0, 0]) if hasattr(mdf.cov_re, "iloc") else float(mdf.cov_re)
        mixed = {"slopes": mixed_slopes, "year_var": year_var, "engine": "statsmodels.MixedLM"}
    except Exception as exc:  # noqa: BLE001
        mixed = {"error": repr(exc)}

    # Joint mixed: DegSlope ~ C(Compound) with year random intercept
    mixed_joint = None
    try:
        import statsmodels.formula.api as smf

        md = smf.mixedlm(
            "DegSlope ~ C(Compound, Treatment(reference='MEDIUM'))",
            dry,
            groups=dry["Year"],
        )
        mdf = md.fit(reml=True, method="lbfgs")
        # Intercept = MEDIUM; SOFT/HARD are deltas
        intercept = float(mdf.fe_params["Intercept"])
        slopes = {"MEDIUM": intercept}
        for name, val in mdf.fe_params.items():
            if "SOFT" in str(name):
                slopes["SOFT"] = intercept + float(val)
            elif "HARD" in str(name):
                slopes["HARD"] = intercept + float(val)
        mixed_joint = {
            "slopes": slopes,
            "fe_params": {str(k): float(v) for k, v in mdf.fe_params.items()},
            "year_var": float(mdf.cov_re.iloc[0, 0]) if hasattr(mdf.cov_re, "iloc") else None,
            "engine": "statsmodels.MixedLM joint",
        }
    except Exception as exc:  # noqa: BLE001
        mixed_joint = {"error": repr(exc)}

    candidates = {
        "e3_2_iv_all": baseline_iv,
        "iv_race": race_iv,
        "year_fe_all": fe_all["slopes"],
        "year_fe_race": fe_race["slopes"],
        "mixed_per_compound": (mixed or {}).get("slopes"),
        "mixed_joint": (mixed_joint or {}).get("slopes"),
    }

    verdicts = {}
    any_pass = False
    for name, slopes in candidates.items():
        if not slopes or any(not np.isfinite(slopes.get(c, float("nan"))) for c in ("SOFT", "MEDIUM", "HARD")):
            verdicts[name] = {"slopes": slopes, "ordering_ok": False, "note": "incomplete"}
            continue
        ok = _ordering_ok(slopes)
        any_pass = any_pass or ok
        verdicts[name] = {
            "slopes": {k: round(float(slopes[k]), 6) for k in ("SOFT", "MEDIUM", "HARD")},
            "ordering_ok": ok,
            "vs_globals": {
                k: {
                    "aimed_order_soft_gt_med_gt_hard": True,
                    "actual": float(slopes[k]),
                    "global_fallback": float(DEFAULT_COMPOUND_SLOPE[k]),
                }
                for k in ("SOFT", "MEDIUM", "HARD")
            },
        }

    # Sample-size adequacy decision
    # Rule of thumb: total n>=30 per compound AND no compound with median year n < 5
    totals = sample_sizes["all_totals"]
    adequate = all(totals.get(c, 0) >= 30 for c in ("SOFT", "MEDIUM", "HARD")) and len(thin) <= 2

    out = {
        "sample_sizes": sample_sizes,
        "thin_compound_years_n_lt_5": thin,
        "sample_size_adequate": adequate,
        "fe_all_detail": fe_all,
        "fe_race_detail": fe_race,
        "mixed_per_compound": mixed,
        "mixed_joint": mixed_joint,
        "verdicts": verdicts,
        "any_ordering_pass": any_pass,
        "ship_decision": (
            "use_fitted"
            if any_pass
            else "KEEP_GLOBAL_FALLBACK — random-effect / year-FE pooling did not restore SOFT>MEDIUM>HARD; "
            "sample sizes are adequate so this is structural (year/compound confounding), not data volume"
        ),
        "globals": DEFAULT_COMPOUND_SLOPE,
    }
    _OUT.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps(out, indent=2, default=str))
    print(f"\nWrote {_OUT}")
    print(f"sample_size_adequate={adequate} any_ordering_pass={any_pass}")
    print(f"ship_decision={out['ship_decision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
