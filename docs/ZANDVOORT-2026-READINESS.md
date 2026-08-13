# Zandvoort 2026 readiness — definitive lock-in

**Event:** 2026 Dutch Grand Prix (Circuit Zandvoort), Fri 21 – Sun 23 August 2026  
**Format:** Sprint weekend (`FP1 → SQ → S → Q → R`)  
**Document role:** Supersedes “ready to demo tonight” framing from E1–E3 summaries.  
**Executed:** Phase E.4 (2026-08-13), against the **true final E3 model** (stint split + residual damp + MSE blend).

Operational companions (unchanged):
- `docs/zandvoort-weekend-runbook.md`
- `docs/zandvoort-day-of-checklist.md`

---

## Go / no-go

### **GO for the 21–23 August 2026 Zandvoort event.**

The live Strategy path, sprint ingest timing, live-write gating, SC/VSC caveat narration, and failure-mode behaviour all re-cleared against the post-E3 code. Zandvoort 2024/2025 held-out blend bars from E3 remain the accuracy baseline (both pass). Remaining gaps below are **known, evidenced, and accepted** — none should be a surprise on the day.

This is **not** a claim of perfect calendar accuracy or perfect tyre physics. It is a claim that the demo stack is locked, rehearsed, and honest about its limits.

---

## Block E4.1 — Full rehearsal (post-E3 model)

### 1. Sprint-sequence rehearsal (2024 Austria stand-in)

Runbook pattern: per-session `ingest_session.py` then `ingest_weekend.py --sprint`.  
Aimed: **≤ 120 s** cached ingest→UI-ready per session; weekend **≤ 300 s**.

| Session | Actual total (s) | Aimed (s) | Result |
|---|---:|---:|---|
| FP1 | **11.1** | ≤ 120 | **PASS** |
| SQ | **6.7** | ≤ 120 | **PASS** |
| Sprint (S) | **10.2** | ≤ 120 | **PASS** |
| Q | **9.1** | ≤ 120 | **PASS** |
| Race (R) | **11.0** | ≤ 120 | **PASS** |
| Full `--sprint` weekend | **11.7** | ≤ 300 | **PASS** |

Log: `results/e4_1_austria_rehearsal.log`. No regression vs E2.9 (still well inside the bar; cold FastF1 first load can still take minutes).

### 2. Track-specific rehearsal (2025 Zandvoort Strategy smoke)

`scripts/_e1_smoke_strategy_zandvoort.py` → **SMOKE OK**

| Check | Aimed / expected | Actual | Result |
|---|---|---|---|
| Track config | 72 laps, pit 18.5, globals | `total_laps=72` `pit_loss=18.5` slopes SOFT/MED/HARD **0.08/0.05/0.03** | PASS |
| Prewrite windows | A≈18 / B≈29 / C≈18+40 | **A:[18] B:[29] C:[18,40]** | PASS |
| Weekend form | sessions ingested | **n=20** | PASS |
| Live clock | complete to lap 72 | **287 ticks → lap 72 complete=True** | PASS |
| Mid-race state | L25 usable | L25 MEDIUM tyre_life=2 | PASS |
| What-if | finite delta + MC band | delta **−13.00 s**, MC P10/P90 **−32.62 / −13.35** | PASS |
| Ask/recommend | ≥1 rec | Pit lap 33 HARD; Pit lap 30 HARD; Stay out | PASS |
| Postrace | export written | `123_VER_postrace.json`, finish=2 | PASS |

Log: `results/e4_1_zandvoort_smoke.log`.

### 3. Live-write gating

| Condition | Flags | Aimed | Actual |
|---|---|---|---|
| Outside window (2026-08-13) | `--write` alone | allow write | **REFUSED=False** |
| Outside window | no `--write` | log only | **REFUSED=False** |
| Inside window (2026-08-22) | `--write` alone | refuse | **REFUSED=True** |
| Inside window | `--write --allow-live-write` | allow | **REFUSED=False** |
| Inside window | log only | allow (no write) | **REFUSED=False** |

**PASS** (all five paths). Log: `results/e4_1_live_write_gating.log`.

### 4. SC/VSC caveat vs residual damping

HIT unchanged: **2024 Austria, RIC, lap 66, TrackStatus=71**, `recent_sc_pace=True`.

Displayed narration (template path, post-E3 damp):

```
confidence_caveat=based on Safety Car-affected recent pace — lower confidence
recommend_evidence=... | caveat: based on Safety Car-affected recent pace — lower confidence
narrate=RIC, recommend stay out on current tyres at lap 66 — expected -1.3s vs staying out.
        Note: based on Safety Car-affected recent pace — lower confidence.
```

**No conflict:** residual damping lives in `predict.py` (physics+residual scale); the caveat is attached in `state.py` / `recommend.py` / `narrate.py` from TrackStatus on recent lag laps. Damping does not strip or mute the caveat string.

**PASS.** Log: `results/e4_1_sc_caveat.log`.

### 5. Failure-mode drill (same three as E2.13)

| Scenario | Aimed | Actual | Result |
|---|---|---|---|
| FastF1 rate limit | raise immediately, no hang | `RateLimitExceededError` in **0.01 s** | PASS |
| Empty/missing laps | refuse before DB write | `RuntimeError: ... session.laps is None` in **0.00 s** | PASS |
| Bad session type CLI | loud ValueError, no hang | exit 1 in **2.23 s**; `session_type 'NOTASESSION' not one of [...]` | PASS |

Log: `results/e4_1_failure_modes.log`.

### E4.1 checkpoint

Full pytest after rehearsal: **green** (`results/e4_1_pytest.log` / `results/e4_final_pytest.log`). No rehearsal regressions vs E2.

---

## Block E4.2 — MSE / variance semantic risk

### Call graph

| Symbol | Location | What it returns / means |
|---|---|---|
| `rolling_error_variance` | `src/aris/models/blend.py` | **MSE** of signed errors (bias²+variance), name kept for API stability |
| Sole production caller | `blend_physics_residual_with_ma2` in `src/aris/models/predict.py` | Feeds values into `inverse_variance_blend` as **relative trust weights** |
| `inverse_variance_blend` also used by | `src/aris/physics/tires.py` (`blend_slope_prior`, session IV pool) | Those paths pass **true sample variances** from `slope_mean_var` — they do **not** call `rolling_error_variance` |

### Monte Carlo / intervals

| Module | Noise model | Uses `rolling_error_variance`? |
|---|---|---|
| `src/aris/montecarlo.py` | Independent Gaussian draws with fixed `PACE_SIGMA_S` (+ small pit noise) | **No** |
| `src/aris/eval/mc_intervals.py` | Re-expresses MC p10/p90; explicitly “not calibrated conformal” | **No** |

### Verdict

**No mismatch bug.** Downstream of `rolling_error_variance`, the MSE is used only as a generic “how much do I trust this source” weight for IV combination — that is exactly why E3 switched from variance to MSE. Percentile bands do **not** treat this quantity as a Gaussian variance for interval width.

**No rename / no behaviour change in E4.2.**

---

## Block E4.3 — Tyre ordering final verdict

### Sample sizes first (post E3.2 stint split), Netherlands 2021–2025

Dry stints from `results/e3_2_deg_stints/netherlands.csv`:

| Year | SOFT (all / race) | MEDIUM (all / race) | HARD (all / race) |
|---|---:|---:|---:|
| 2021 | 33 / 15 | 29 / 17 | 17 / 14 |
| 2022 | 39 / 38 | 38 / 25 | 18 / 17 |
| 2023 | 40 / 29 | 12 / 8 | 9 / 1 |
| 2024 | 13 / 6 | 30 / 20 | 23 / 20 |
| 2025 | 17 / 15 | 23 / 19 | 25 / 20 |
| **Total** | **142 / 103** | **132 / 89** | **92 / 72** |

Thin compound-years with n&lt;5 (all-session dry): **none**.  
**Sample size is adequate** — this is **not** a data-volume limitation for Zandvoort.

### One final modelling attempt

Pooled compound slopes with **per-year intercepts** (OLS year fixed effects = classical random-intercept proxy; `statsmodels` MixedLM not installed in the venv, FE is the equivalent identification):

| Fit | SOFT | MEDIUM | HARD | Aimed order SOFT&gt;MED&gt;HARD | Result |
|---|---:|---:|---:|---|---|
| E3.2 IV pool (pre-sanity) | 0.0609 | 0.0346 | 0.0491 | yes | **FAIL** (MED &lt; HARD) |
| Year-FE, all sessions | 0.0818 | 0.0349 | 0.0704 | yes | **FAIL** |
| Year-FE, race-only | 0.0874 | 0.0639 | 0.0655 | yes | **FAIL** (MED ≈ HARD, MED &lt; HARD by **0.0016**) |

Artefact: `results/e4_3_nl_random_effects.json`, `scripts/_e4_3_nl_random_effects.py`.

### Permanent ship decision for Zandvoort

**Keep global fallback slopes permanently for Netherlands:** SOFT **0.08** / MEDIUM **0.05** / HARD **0.03**.

Why (interview-ready): after correcting the real pipeline bugs (same-compound stint merges + SC laps in DegSlope fits), Zandvoort still will not order. Sample sizes are large enough that this is **structural** — compound means overlap within year noise; pooling the slope while absorbing year intercepts does not restore SOFT&gt;MEDIUM&gt;HARD. Further confound hunts have diminishing value; globals are the honest ship choice.

**STOP here for Zandvoort tyre ordering.** No further correction attempted.

---

## Block E4.4 — China final verdict

### Baseline (accepted E3 miss)

| Metric | Aimed | Actual | Result |
|---|---:|---:|---|
| China 2024 blend MAE | ≤ **0.563** (1.5× MA2 **0.376**) | **0.596** | **MISS by 0.033 s** |

Root cause (unchanged): **57** early-stint laps with no `lag2` fall back to physics+residual alone under ~10 s physics bias; on MA2-available laps blend is **0.408** (would pass).

### One narrow attempt (no-lag2 only)

Idea: when `lag2` missing but `lag1` present, **precision-weight blend** physics+residual toward lag1, **without** writing lag1 errors into the MA error history (unlike E3’s MA(1) substitute, which poisoned later MA2 weights — Australia).

| Mode | China MAE (aimed 0.563) | Australia MAE (aimed 0.695) | Ship? |
|---|---:|---:|---|
| baseline (phys+res alone on no-lag2) | **0.596 MISS** | **0.685 PASS** | current |
| E3 MA(1) substitute + update err_m | 0.593 MISS | **0.740 MISS** | no |
| shrink_nolag2 (IV toward lag1, no err_m update) | **0.511 PASS** | **0.704 MISS** | **no** |
| shrink + disagreement inflate | 0.537 PASS | 0.735 MISS | no |

Netherlands / Italy / Spain / Belgium / US / Bahrain / São Paulo stayed PASS under shrink, but **Australia flips PASS→MISS** (aimed **0.695**, actual **0.704**, short by **0.009 s**). Japan also degrades substantially (0.660 → 0.801) though still under its looser bar.

Artefact: `results/e4_4_china_nolag2_shrink.json`, `scripts/_e4_4_china_nolag2_shrink.py`.

### Permanent ship decision for China

**Do not ship the no-lag2 shrinkage.** Accept China at **0.033 s over** its 1.5× MA(2) bar as understood:

- The miss is concentrated in early-stint no-MA2 laps under large physics bias.
- Pulling those laps toward lag1 fixes China but moves weight in a way that **fails Australia**, which only clears its bar by **~0.010 s**.
- Fabricating a China-only special case would hide a real early-stint / physics-bias interaction; leaving it documented is the honest call.

**STOP.** No further China correction in this phase. Production blend path unchanged.

---

## Remaining caveats for race weekend (explicit)

Nothing below should surprise anyone on 21–23 August:

1. **Tyre slopes for Zandvoort are globals (0.08/0.05/0.03), not fitted.** Live `fit_zandvoort_tire_slopes.py` is **log-only** by default; mid-weekend YAML write needs `--write --allow-live-write` inside the event window, and only with explicit approval.
2. **China calendar miss remains (0.033 s).** Zandvoort itself passes 2024 and 2025 bars; do not expect every other 2024 race to clear 1.5× MA(2) if you re-score the full calendar mid-demo.
3. **Physics absolute level is still ~10–26 s slow on many circuits.** Residual + MSE blend mask this for demo MAE; bicycle geometry/calibration debt is unchanged.
4. **SC/VSC What-if / recommend deltas can look extreme** because lag features inherit dirty pace — mitigated by the displayed caveat string, not by scrubbing lags.
5. **Cold FastF1** (first load of a session) can take minutes; rehearsal timings above are **cached**. After session end, wait ~5–20 min for timing before ingest; empty laps **refuse loudly** — retry, do not force.
6. **No mid-weekend residual retrain** and **no pit_loss rewrite from a single sprint sample** — keep `netherlands.yaml` `pit_loss_s: 18.5` and `total_laps: 72`.
7. **Sprint format only** — there is no FP2/FP3; weekend form and tyre log use FP1 + Sprint long runs.
8. **Monte Carlo bands are not conformal** — fixed pace sigma draws; do not present P10/P90 as calibrated coverage.

---

## Accuracy snapshot (carried from E3.6 — not re-tuned in E4)

| Scope | Blend MAE | Aimed | Result |
|---|---:|---:|---|
| 2024 calendar overall | **0.583** | ≤ **0.783** (1.5× MA2 0.522) | PASS (23/24 races) |
| Netherlands 2024 | **0.502** | ≤ **0.640** | PASS |
| Netherlands 2025 | **0.566** | ≤ **0.603** | PASS |
| China 2024 | **0.596** | ≤ **0.563** | MISS (−0.033) |

E4 did **not** chase further accuracy gains beyond the single tyre and China attempts above.

---

## Test suite

Docker Postgres up; `ARIS_DB_URL` set.

| Checkpoint | Result |
|---|---|
| After E4.1 rehearsal | green (`results/e4_1_pytest.log`) |
| After E4.2 (analysis only, no code change) | n/a — covered by E4.1 |
| After E4.3 (script-only; globals unchanged) | green |
| After E4.4 (script-only; blend unchanged) | green |
| **End of Phase E.4** | **150 passed**, 0 failed (`results/e4_final_pytest.log`) |

Production code was **not** modified in E4 (rehearsal + analysis + rejected attempts only). New scripts/artefacts under `scripts/_e4_*` and `results/e4_*`.

---

## Stop

Phase E.4 (final Zandvoort lock-in) is complete. **Dashboard / Phase F work starts only after you review this document and say so.**
