# Zandvoort 2026 readiness — definitive lock-in

**Event:** 2026 Dutch Grand Prix (Circuit Zandvoort), Fri 21 – Sun 23 August 2026
**Today:** 2026-08-17, **T−4 days**
**Format:** Sprint weekend (`FP1 → SQ → S → Q → R`)
**Document role:** Definitive go / no-go for the event tree. Accuracy
numbers live in [`docs/model-status.md`](./model-status.md); this page
is what you run on Friday. Last substantively written at E4.1
(2026-08-13); refreshed in the Final Pre-Event Consolidation.

Operational companions (unchanged):
- `docs/zandvoort-weekend-runbook.md`
- `docs/zandvoort-day-of-checklist.md`

---

## Go / no-go

### **GO for the 21–23 August 2026 Zandvoort event.**

The live Strategy path, sprint ingest timing, JSONL decision-log write
safety, live-write gating, SC/VSC caveat narration, and failure-mode
behaviour all re-cleared on the post-R.2.2 stack (Final Pre-Event
rehearsal, T−4). The Zandvoort recommend identity is **exactly** the
E4.1 / G1.5 lock. Remaining gaps below are **known, evidenced, and
accepted** — none should be a surprise on the day.

This is **not** a claim of beating MA(2), of FIA points, or of a
calibrated stopwatch. It is a claim that the demo stack is locked,
rehearsed, and honest about its limits.

---

## Locked demo identity (E4.1 → now)

Unchanged on every phase since E4.1, including H.1, H.2, R.2.1, R.2.2,
and this rehearsal. Overlay env `ARIS_TRUE_COMPOUND_SLOPES` is **unset**.
G1.5 is shipped.

| Check | Aimed (E4.1 / G1.5) | Actual (T−4 smoke) | Result |
|---|---|---|---|
| Setup | session_id 123, VER | **123**, VER, driver_id **2448** | **PASS** |
| Track | 72 laps, pit_loss **18.5**, slopes **0.08 / 0.05 / 0.03** | **72 / 18.5 / 0.08, 0.05, 0.03** | **PASS** |
| Prewrite windows | A:[18] B:[29] C:[18, 40] | **same** | **PASS** |
| Weekend form | n=20 | **20** | **PASS** |
| Clock | 287 ticks → lap 72 complete | **287** ticks, lap **72**, complete | **PASS** |
| Live state L25 | MEDIUM, tyre_life=2 | **MEDIUM / 2** | **PASS** |
| Recommend | Pit lap 33 HARD; Pit lap 30 HARD; Stay out | **Pit lap 33 for HARD; Pit lap 30 for HARD; Stay out on current tyres** | **PASS** |
| Smoke exit | SMOKE OK | **SMOKE OK** | **PASS** |

What-if is G1.4 physics-delta (**−11.92 s**, MC P10/P90 **−147.55 /
+29.33**), not E4.1 **−13.00 s**. MC bands are unseeded and not a
locked identity. The recommend labels are.

Log: `results/final-pre-event/zandvoort-smoke.log`.

---

## How good is this, really

Point interview questions at [`docs/model-status.md`](./model-status.md).
Headline, aimed vs actual:

| Question | Aimed | Actual |
|---|---|---|
| One-step lap time vs MA(2) | beat baseline | E3 blend **0.583 s** vs MA(2) **0.522** — does **not** beat |
| Mid-race match-rate vs stay-out | > 0.276 | **0.322** (28/87) |
| Lights-out position-delta (all 48) | ≤ 0 | **−1.73** (clean **−1.49** n=35 / disrupted **−2.38** n=13) |
| Absolute `team_sim − actual` | a stable intercept | mean **+989 s**, std **544** — **closed**, do not subtract |
| Tyre slopes from lap time | physical C1<…<C5 | G2/G3/G4 all miss the gate — **G1.5 locked** |

Research window is **closed until after the event**. Cornering-load
(R1.4) is queued, not abandoned — see model-status.

---

## Final Pre-Event rehearsal (T−4) vs G.6 vs E4.1

G.6 (T−6) was the last full rehearsal. H.1 / R.2.1 / R.2.2 landed
since then; only smoke-level checks had run. This is the G.6-style
re-run on current code. Cached FastF1, same 2024 Austria stand-in.

### Sprint-sequence timing (2024 Austria)

Aimed: **≤ 120 s** per session, **≤ 300 s** weekend — **and** no real
slowdown vs G.6's actuals.

| Session | Aimed (s) | E4.1 | G.6 | T−4 actual (s) | vs G.6 | Ceiling |
|---|---:|---:|---:|---:|---:|---|
| FP1 | ≤ 120 | 11.1 | 7.1 | **12.1** (ingest 10.2 + ui-ready 1.9) | **+5.0** | **PASS** |
| SQ | ≤ 120 | 6.7 | 3.9 | **3.5** (2.1 + 1.4) | **−0.4** | **PASS** |
| Sprint (S) | ≤ 120 | 10.2 | 5.1 | **7.4** (6.1 + 1.3) | **+2.3** | **PASS** |
| Q | ≤ 120 | 9.1 | 5.4 | **5.7** (4.3 + 1.3) | **+0.3** | **PASS** |
| Race (R) | ≤ 120 | 11.0 | 5.5 | **5.8** (4.5 + 1.3) | **+0.3** | **PASS** |
| Full `--sprint` weekend | ≤ 300 | 11.7 | 4.2 | **3.7** | **−0.5** | **PASS** |

FP1 is slower than G.6's 7.1 s and **+1.0 s** vs E4.1 11.1 s — first
cached load of the run, still an order of magnitude under the 120 s
ceiling. Weekend catch-up is **faster** than G.6. Cold FastF1 (first
load of a session) can still take minutes; these numbers are cached.

Log: `results/final-pre-event/austria_rehearsal.log`. Weekend types
`['FP1','SQ','S','Q','R']`, form n=20, all sessions `+0` rows
(idempotent).

### JSONL decision-log under Watch (2025 NL VER)

| Check | Aimed | G.6 | T−4 actual | Result |
|---|---|---|---|---|
| Clock | ~287 ticks → lap 72 | 287 / 26.28 s | **287** ticks, **23.66 s** | **PASS** |
| Propose / resolve | every trigger, in order | 107 / 107, `order_ok=True` | **107 / 107**, `order_ok=True` | **PASS** |
| JSONL write vs 25 s tick | << 50 ms noticeable | max **1.609 ms** | mean **0.950 ms**, max **1.858 ms** | **PASS** |
| Write vs live-default propose | negligible | 4.880 s / 0.862 ms | **4.056 s** / **0.847 ms** (0.0209%) | **PASS** |
| Unwritable dir | loud `RuntimeError`, no silent drop | same | same | **PASS** |

Log: `results/final-pre-event/watch_jsonl.log`. JSONL is safe under
the live clock.

### Live-write gating (real 21–23 Aug window)

`_EVENT_WINDOW = (date(2026, 8, 21), date(2026, 8, 23))` in
`scripts/fit_zandvoort_tire_slopes.py`. Independent of
`ARIS_TRUE_COMPOUND_SLOPES`.

| Date | Aimed inside? | Actual | Result |
|---|---|---|---|
| 2026-08-17 (T−4, this rehearsal) | no | no | **PASS** |
| 2026-08-20 (Thu) | no | no | **PASS** |
| 2026-08-21 (Fri) | yes | yes | **PASS** |
| 2026-08-22 (Sat) | yes | yes | **PASS** |
| 2026-08-23 (Sun) | yes | yes | **PASS** |
| 2026-08-24 (Mon) | no | no | **PASS** |

Five E4.1 flag paths still match (YAML not touched). Overlay=pooled
does not change `_in_event_window(2026-08-22)`. Log:
`results/final-pre-event/live_write_gating.log`.

### Failure-mode drill (same three as E2.13 / E4.1 / G.6)

| Scenario | Aimed | E4.1 | G.6 | T−4 actual | Result |
|---|---|---|---|---|---|
| FastF1 rate limit | raise immediately, no hang | 0.01 s | 0.00 s | **0.00 s** `RateLimitExceededError` | **PASS** |
| Empty/missing laps | refuse before DB write | 0.00 s | 0.00 s | **0.00 s** `RuntimeError: … session.laps is None` | **PASS** |
| Bad session type CLI | loud ValueError, no hang | 2.23 s | 1.49 s | **1.58 s** exit 1 | **PASS** |

Log: `results/final-pre-event/failure_modes.log`.

### SC/VSC caveat, rendered UI

Same F1.1 stint: **2025 Zandvoort, VER, L25** (MEDIUM, tyre_life=2).
Formatters the gold callout actually renders
(`format_callout_delta`, `recommendation_caveat` →
`recommend_panel.py` `.aris-caveat`). Live strip in `01_Strategy.py`
still prefixes `Note: {live_state.confidence_caveat}`. CSS is visible
(amber border, not `display:none`).

| Layer | Aimed (F1.1 / E4.1 / G.6) | T−4 actual | Result |
|---|---|---|---|
| State caveat | `based on Safety Car-affected recent pace — lower confidence` | same | **PASS** |
| Callout strip | `Note: based on Safety Car-affected recent pace — lower confidence` | same | **PASS** |
| Recommend identity | Pit lap 33 HARD; Pit lap 30 HARD; Stay out | **same** | **PASS** |
| Headline truncation | none | full label, unescaped | **PASS** |

Engine HIT unchanged: **2024 Austria, RIC, lap 66, TrackStatus=71**,
`recent_sc_pace=True`, narration still appends the caveat. Logs:
`results/final-pre-event/sc_caveat_render.log`,
`results/final-pre-event/sc_caveat_engine.log`.

Callout delta on this stint is **−49.4 s** (15-draw MC, not seeded).
The lock for this block is the string on the rendered strip.

### Day-of checklist vs current code

`docs/zandvoort-day-of-checklist.md` read end to end as if running it
Friday. Cross-checked:

| Item | Checklist | Code | Result |
|---|---|---|---|
| Ingest commands | `ingest_session.py 2026 Netherlands {FP1,SQ,S,Q,R}` | same CLI | **PASS** |
| Weekend catch-up | `ingest_weekend.py 2026 Netherlands --sprint` | `SPRINT_SESSIONS = (FP1, SQ, S, Q, R)` | **PASS** |
| YAML | 72 laps, pit 18.5, compound_slopes | **72 / 18.5 / 0.08, 0.05, 0.03** | **PASS** |
| Prewrite windows | ≈ 18 / 29 / 18+40 | **A:[18] B:[29] C:[18, 40]** | **PASS** |
| `ARIS_FAST_CLOCK` | unset | `fast_clock_enabled()` False | **PASS** |
| `ARIS_TRUE_COMPOUND_SLOPES` | unset | mode `off` | **PASS** |
| `ARIS_DECISION_LOG` | default on | enabled True | **PASS** |
| Live-write | `--write --allow-live-write` Fri–Sun 21–23 Aug | `_EVENT_WINDOW` 2026-08-21…23 | **PASS** |

Log: `results/final-pre-event/checklist_sanity.log`.

---

## What landed since E4.1 (does not change the demo path)

| Phase | What it did | Demo identity |
|---|---|---|
| F / F.1 | Strategy UI, rendered callout, SC caveat CSS | untouched |
| G / G.1–G.5 | Walk-forward match-rate; G2–G4 overlays **opt-in**; G1.5 locked | untouched |
| G.6 | First full post-E4.1 rehearsal; loud JSONL write fail | untouched |
| H / H.1 / H.2 | Grounded Ask; isolate tests from live JSONL; prefer G1.5 over overlay duplicates | untouched |
| R.1 | Cornering-load cheap check in a worktree; **not merged** | n/a |
| R.2 / R.2.1 | Position-delta on the time-rank field; offset diagnosis; intercept **not shipped** | untouched |
| R.2.2 | SC/VSC pit count; clean/disrupted split; `docs/model-status.md` | untouched |

`simulate()` / `recommend()` / `tires.py` were not edited after G1.4 /
G1.5 for these phases.

---

## Remaining caveats for race weekend (explicit)

Nothing below should surprise anyone on 21–23 August:

1. **Tyre slopes for Zandvoort are globals (0.08/0.05/0.03), not fitted.** Live `fit_zandvoort_tire_slopes.py` is **log-only** by default; mid-weekend YAML write needs `--write --allow-live-write` inside the event window, and only with explicit approval. Overlay env does **not** bypass that refuse.
2. **China calendar miss remains (0.033 s).** Aimed ≤ **0.563**, actual **0.596**. Zandvoort itself passes 2024 (**0.502** ≤ 0.640) and 2025 (**0.566** ≤ 0.603); do not expect every other 2024 race to clear 1.5× MA(2) if you re-score the full calendar mid-demo.
3. **Physics absolute level is uncalibrated.** `team_sim − actual` mean **+989 s**, std **544**, per configured lap **+17.3 s**. A lap-constant intercept was tried and **not shipped** (`docs/physics-calibration-research.md`). Residual + MSE blend mask this for demo MAE; do not read `expected_race_time_s` as a stopwatch.
4. **Lights-out −1.73 is identity-safe ranking, not FIA points.** Clean **−1.49** (n=35) / disrupted **−2.38** (n=13). **21 of 85** team pit events (0.247) were under SC/VSC. Austria 2024 VER **−6** is a clean mixed result (G1.5 long HARD), not SC-driven.
5. **SC/VSC What-if / recommend deltas can look extreme** because lag features inherit dirty pace — mitigated by the displayed caveat string, not by scrubbing lags.
6. **Cold FastF1** (first load of a session) can take minutes; rehearsal timings above are **cached**. After session end, wait ~5–20 min for timing before ingest; empty laps **refuse loudly** — retry, do not force.
7. **No mid-weekend residual retrain** and **no pit_loss rewrite from a single sprint sample** — keep `netherlands.yaml` `pit_loss_s: 18.5` and `total_laps: 72`.
8. **Sprint format only** — there is no FP2/FP3; weekend form and tyre log use FP1 + Sprint long runs.
9. **Monte Carlo bands are not conformal** — fixed pace sigma draws; do not present P10/P90 as calibrated coverage.
10. **Ask retrieval defaults to G1.5-shipped proposes.** Overlay-walk JSONL stays in `results/decisions/` but is not indexed unless `ARIS_ASK_INCLUDE_OVERLAY_DECISIONS=1`. Leave that unset.

---

## Closed E4 decisions (still the ship choice)

### Tyre ordering (E4.3 / G.5)

**Keep global fallback slopes permanently for Netherlands:** SOFT **0.08** / MEDIUM **0.05** / HARD **0.03**. Sample sizes are adequate; fitted overlays (G2 unconstrained, G3 isotonic, G4 pooled) all missed the gate vs G1.5 **0.322**. Full write-up: `docs/tyre-degradation-research.md`.

### China (E4.4)

**Do not ship the no-lag2 shrinkage.** Accept China at **0.033 s over** its 1.5× MA(2) bar. Pulling those laps toward lag1 fixes China but fails Australia.

### MSE vs variance (E4.2)

**No mismatch bug.** `rolling_error_variance` is MSE used as an IV trust weight. MC bands do not treat it as a Gaussian variance.

---

## Accuracy snapshot (not re-tuned since E3 / G.5 / R.2.2)

| Scope | Aimed | Actual | Result |
|---|---|---|---|
| 2024 calendar blend MAE | ≤ **0.783** (1.5× MA2 0.522) | **0.583** | PASS (23/24 races) |
| Netherlands 2024 | ≤ **0.640** | **0.502** | PASS |
| Netherlands 2025 | ≤ **0.603** | **0.566** | PASS |
| China 2024 | ≤ **0.563** | **0.596** | MISS (−0.033) |
| Combined match-rate | > **0.276** stay-out | **0.322** (28/87) | PASS |
| Position-delta all 48 | ≤ 0 | **−1.73** | identity-safe |

---

## Stop

Final Pre-Event Consolidation is complete. Print
`docs/zandvoort-day-of-checklist.md`. Keep `ARIS_FAST_CLOCK` and
`ARIS_TRUE_COMPOUND_SLOPES` unset; leave `ARIS_DECISION_LOG` default-on.
Run the runbook after each session. No further model-accuracy work
before the event.
