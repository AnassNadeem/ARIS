# T10-B Summary — Conformal Prediction

Date: 2026-08-26  Commit: e404a59 (working tree; T10-B not committed)  Status: **PARTIAL**

Residuals: 87 scored dry inflections (2024 = 40, 2025 = 47) from `results/backtest/2024_full.json` + `results/backtest/t92/2025_full.json`. For each inflection the current simulator is re-run (stay-out, team action, `recommend()` top action). `error = actual_delta - predicted_delta` with `actual_delta = team_remaining - stay_out_remaining` and `predicted_delta` = ARIS top-action delta vs stay-out. Split conformal, α = 0.10, calibration = 2024 only.

## Conformal results

| Subset | q_hat (s) | n_cal | 2025 empirical coverage |
|---|---:|---:|---:|
| All dry | 16.54 | 40 | **78.7%** (37/47) |
| Short stints (< 20 laps remaining) | 16.43 | 5 | 100% (8/8) |
| Long stints (≥ 20 laps remaining) | 18.25 | 35 | 79.5% (31/39) |

Runtime uses the short/long payload when that subset has calibration rows, else the all-dry `q_hat`. Wired as `p10` / `p90` / `confidence_note` on each recommendation. Ranking is unchanged.

## Honest assessment

Coverage on 2025 is **78.7%, below the 85% target**. Causes:

1. **Small calibration set** (n=40). The split-conformal quantile is the 0.925 quantile of 2024 |error| (`ceil((n+1)×0.90)/n`).
2. **Year shift, not exchangeable.** 2025 |error| is heavier (mean 8.4 s vs 4.6 s in 2024; 2025 p90 = 31.7 s). Hitting 85% on 2025 would need q_hat ≈ 22.6 s (the 2025 85th percentile) — using that would leak the test set into the band.
3. One 2025 outlier is +101 s; a 90% band cannot cover that without becoming unusable.

Short-stint q_hat is estimated on **n=5** (noisy). Long q_hat is still larger (18.25 > 16.43), so the “wider for long remainders” check holds, but the short subset is too small to trust.

The ±16.5 s 90% band is an honest statement of remaining-race delta error on public data. It is wide relative to a +2 s pit call; that is the simulator, not a bug in the quantile.

`tests/test_conformal.py::test_coverage_on_2025` **fails** on this gate (0.787 < 0.85). The other three conformal tests pass.

## Example output

`q_hat = 16.5 s`, n_cal = 40:

> Pit now MEDIUM: expected +2.4s, 90% band [−14.1s, +18.9s] (±16.5s, 90% conformal band, n=40)

## Gate check

- Zandvoort identity: **PASS**
- Tests: **3/4** passing (`test_coverage_on_2025` FAIL; p10≤p90, long>short, deterministic PASS)
