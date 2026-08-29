# T10-D Summary — Monte Carlo Sampler

Date: 2026-08-26  Commit: e404a59 (working tree; T10-D not committed)  Status: **COMPLETE**

Vectorised remainder in `src/aris/simulate_mc.py`. All 200 scenarios are NumPy arrays; the only Python loop is SC duration (3 laps), not scenarios. Pit loss is applied as a **delta on the in-lap** (ARIS YAML `pit_loss_s`), not a replacement of the lap with 20 s — replacing the lap made an immediate pit always faster than staying out on fresh tyres.

Gated behind `ARIS_USE_MC=1`. Backtest default is unchanged (`mc_draws=0`, flag unset).

## Performance

- n_scenarios: 200
- Typical laps_remaining: 40–50
- Measured runtime: **0.5 ms** for 200×50 `sample_remaining_race`; **0.8 ms** for a 3-action `compare_actions_mc` (same machine as the unit tests)
- Speed test: 200×50 completes in << 2 s

`deg_sigma` = conformal `median_abs_error / sqrt(laps_remaining)` (floor 0.01). `p_sc_per_lap` = `1 - (1 - p_sc_next_5)^(1/5)`. Shared noise and SC draws across actions so `p_best` is a paired comparison.

## Example output (ARIS_USE_MC=1)

Zandvoort identity state (lap 25, MEDIUM life 2, 47 laps remaining):

> Pit lap 33 for HARD: E[time] = 3551.6s, P10-P90 = [3538.0, 3570.4], P(best) = 0.92
> Pit lap 30 for HARD: E[time] = 3555.4s, P10-P90 = [3542.0, 3574.3], P(best) = 0.08
> Stay out on current tyres: E[time] = 3597.6s, P10-P90 = [3583.4, 3616.5], P(best) = 0.00

Synthetic 40-lap, age-18, 21 s pit loss (decisive physics gap, so P(best) collapses to 1.0):

> Pit lap 8 HARD: E[time] = 3661.1s, P10-P90 = [3643.5, 3682.2], P(best) = 1.00
> Pit now MEDIUM: E[time] = 3675.6s, P10-P90 = [3657.3, 3696.1], P(best) = 0.00
> Stay out HARD: E[time] = 3691.4s, P10-P90 = [3672.8, 3711.6], P(best) = 0.00

## Honest assessment

MC **confirms the same ranking** as deterministic simulate() when the physics gap is several seconds (Zandvoort Pit 33 vs Pit 30 is ~4 s in MC expected time, 92/8 split). It does not invent a different call.

It does **not** reproduce physics deltas. Zandvoort physics stay-delta is −14.3 s / −11.9 s; MC reports −45.9 s / −42.1 s because the sampler is `base + slope×age + N(0,σ) + SC`, not the chained G1.5 / FP2 / fuel remainder. With the flag on, the displayed delta is the MC number. Leave the flag off for identity-safe radio.

## Gate check (with ARIS_USE_MC=1)

- Zandvoort identity: **PASS** (same labels: Pit 33 HARD / Pit 30 HARD / Stay)
- Tests: **5/5** passing (`tests/test_simulate_mc.py`)
- Dry 87 (MC enabled): **not re-walked**. Flag off, DRY default, and MC only re-ranks the existing top 3, so the 28/87 floor is the deterministic number. A full MC walk would be justified only if we promoted the flag to default.
