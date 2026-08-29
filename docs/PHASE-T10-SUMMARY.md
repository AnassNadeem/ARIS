# T10 Summary — Uncertainty, Events, Wet, and Monte Carlo

Date: 2026-08-26  Commit: e404a59 (working tree; T10 not committed)  Status: **PARTIAL**

## Components delivered

| Component | Status | Key metric |
|---|---|---|
| SC/VSC risk model | COMPLETE | AUC 0.549 / 0.515 (5/10 lap); Brier 0.226 / 0.261 |
| Conformal prediction | PARTIAL | 2025 coverage **78.7%** (target 85%); q_hat = 16.5 s |
| Wet classifier | PARTIAL | Rule-based (5 wet races < 8); combined wet **0.336** |
| Monte Carlo sampler | COMPLETE | 200 scenarios × 50 laps in **0.5 ms**; 3-action compare **0.8 ms** |

## Gate results

| Gate | Threshold | T9.2 | T10 | Pass? |
|---|---|---|---|---|
| Zandvoort identity | PASS | PASS | **PASS** (MC flag on and off) | YES |
| Lights-out | ≤ −1.70 | −1.229 | not re-run (ranking path unchanged unless `ARIS_USE_MC=1`) | — |
| Dry 87 | ≥ 28/87 (honest floor) | 28/87 | not re-walked; DRY default + MC flag off | — |
| Combined wet | ≥ 0.340 | 0.373 (T9) | **37/110 = 0.336** | **NO** (one match short) |

## What ARIS is after T10

ARIS is still a physics remainder with a shortlist of pit/stay actions, not a black-box race winner. It uses FastF1 laps, weather `Rainfall` (boolean), Pirelli allocation, G1.5 / FP2 slopes, and the team’s actual stop as the scoring target. T10 adds three overlays that **do not rank by default**: a circuit-prior SC probability (barely above chance lap-to-lap, useful as “this track crashes”), a split-conformal ±16.5 s band that does not cover 85% of 2025 because 2025 errors are heavier than 2024, and an opt-in vectorised MC that re-ranks the top three with tyre-age noise and SC draws. The wet classifier is a five-class rule file, not a model — there are only five wet races in 2024–2025 with enough rain laps, so INTER availability is gated by those rules. Combined wet is 37/110, one match under the 0.340 floor; INTER was not leaking onto dry-compound cards (the one INTER rank-1 on slicks was Britain 2024 L26, a match). What it cannot do: predict the next SC, call a drying window with a fitted INTER-vs-slick crossover, or treat MC expected time as a substitute for the physics remainder.

## Readiness for T11 (Copilot + UI completion)

- [x] All four T10 components shipped (SC + conformal + wet rules + MC)
- [ ] No regressions in core gates — wet combined is **0.336 < 0.340**; dry 87 / lights-out not re-run
- [x] `ARIS_USE_MC=1` path tested end-to-end (Zandvoort identity PASS, p_best 0.92 / 0.08 / 0.00)
