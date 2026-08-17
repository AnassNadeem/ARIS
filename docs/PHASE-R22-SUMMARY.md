# Phase R.2.2 summary — SC-contamination, clean/disrupted split, closed threads

Executed 2026-08-17 in the **main** tree `C:\Users\anass\OneDrive\Desktop\ARIS`,
not a worktree. Scope: Blocks R22.1–R22.5. Bounded evidenced fix, not open
research. Eval scoring only: `simulate()` / `recommend()` / `tires.py`
were not edited.

Every numeric result states aimed vs actual.

---

## Verdict (read this first)

**21 of 85 team pit events (0.247) on the 48 lights-out comparisons
occurred under SC/VSC.** 12 of 48 races have at least one such pit.
R21.3's major-disruption flag still marks **13 / 48**. The two sets
overlap on 8 races; 4 races have SC/VSC pits without meeting red-or-
SC-run-≥-5 (including 2025 Canada LEC, scRun **4**).

Position-delta is now reported both ways, same discipline as walk-
forward insufficient-info. Aimed: both numbers visible. Actual:

| Slice | Aimed | Actual | Better / same / worse |
|---|---|---|---|
| All 48 | −1.73 (R.2) | **−1.73** | 27 / 21 / 0 |
| Clean (not major) | report, don't hide | **−1.49** (n=35) | 17 / 18 / 0 |
| Disrupted | report, don't hide | **−2.38** (n=13) | 10 / 3 / 0 |

Disrupted is *more* negative. Dropping those 13 would make ARIS look
worse, not better. Austria 2024 VER **−6** stays clean (0 red, SC run
0, no SC/VSC pits). Classification unchanged.

Physics-offset calibration and the single model-status page are written
in this tree's `docs/`. Zandvoort identity is unchanged. **SMOKE OK.**

| Metric | Aimed | Actual | Result |
|---|---|---|---|
| SC/VSC team pits / all team pits | report across 48 | **21 / 85 = 0.247**; 12 races | **reported** |
| Major-disruption races | 13 (R21.3) | **13 / 48**, 0 flag mismatches | **PASS** |
| Position-delta all / clean / disrupted | both numbers + excluded list | **−1.73 / −1.49 / −2.38**; 13 named | **PASS** |
| Austria 2024 −6 under this flag | confirm not SC-driven | major=False, still clean | **unchanged** |
| `docs/physics-calibration-research.md` | this tree's `docs/` | written | **PASS** |
| `docs/model-status.md` | this tree's `docs/` | written | **PASS** |
| Full pytest after scoring change | green | **266 passed**, 0 failed | **PASS** |
| Zandvoort smoke | G1.5 identity | **SMOKE OK**; same recommend / clock / L25 | **PASS** |

---

## R22.1 — SC-contamination across all 48 races

Reuse of R21.3 only: major disruption = any red lap **or** longest SC
run ≥ 5. Pit-level contamination = `pit_in` lap whose FastF1
`track_status` is SC/VSC (codes 4 / 6 / 7, same as
`track_status_is_sc_vsc`). No new threshold.

Source: R.2's 48 lights-out rows (`results/r2/r24_distribution.json`)
plus Postgres laps. Artefact:
`results/r22/r221_sc_contamination.json`. Re-run:
`python scripts/_r22_sc_contamination.py`.

| Check | Aimed | Actual |
|---|---|---|
| Races scored | 48 | **48** |
| Team pit events | report | **85** |
| Of those under SC/VSC | report | **21 (0.247)** |
| Races with ≥1 SC/VSC team pit | report | **12 / 48** |
| Major-disruption races | 13 | **13 / 48** |
| Major **and** ≥1 SC/VSC pit | report | **8** |
| SC/VSC pit but **not** major | report | **4** |
| Flag match vs R21.3 | 0 mismatches | **0** |

Among the 12 contaminated races, mean fraction of team pits under
SC/VSC is **0.73** (min 0.33, max 1.00). Extra team stops vs ARIS:
raw mean **+0.73**; after dropping SC/VSC pits **+0.29**.

Highest contamination (stop-count is not a green strategy claim):

| Race | Delta | Major? | SC run | Team pits | SC/VSC pits | Extra → extra ex-SC |
|---|---:|---|---:|---:|---|---|
| 2025 Australia ALB | −1 | yes | 9 | 5 | 4 (L2,3,4,33) | +4 → **+0** |
| 2025 Canada LEC | −6 | **no** | **4** | 5 | 3 (L67,68,69) | +4 → **+1** |
| 2024 Qatar GAS | −2 | yes | 8 | 3 | 3 (L35–37) | +2 → −1 |
| 2025 Emilia Romagna ALB | −4 | yes | 8 | 2 | 2 | +1 → −1 |
| 2025 Netherlands ALB | −4 | yes | 5 | 2 | 2 | +1 → −1 |

The other seven of the twelve: 2025 Bahrain HAM, 2024 Canada PIA, 2025
Qatar ANT, 2024 São Paulo LEC, 2025 Spain HUL, 2024 Monaco RUS (L1),
2024 Saudi Arabia ALO (L7).

**Canada 2025 is the R21.5 case.** Three consecutive SC pits at the
end, extra stops +4 → +1 once those are removed. Longest SC run is
**4**, so the reused major-disruption flag does **not** mark it.
Widening the flag to catch it would be a new test; this phase does not.

---

## R22.2 — Position-delta, both numbers visible

`OutcomeScore.major_disruption` is tagged in `_score_outcome` from the
same R21.3 helper. `position_delta_split()` reports all / clean /
disrupted plus the excluded list. `scripts/backtest.py` prints both
means; it does not drop disrupted from `mean_position_delta`.

Numbers below are the existing 48-row lights-out table (no new 48-race
walk) joined to a live recompute of the flag. Aimed all-sample **−1.73**;
actual **−1.729**.

| Slice | n | Mean | Median | Better / same / worse |
|---|---:|---:|---:|---|
| All | 48 | **−1.73** | −1.00 | 27 / 21 / 0 |
| Clean | 35 | **−1.49** | 0.00 | 17 / 18 / 0 |
| Disrupted | 13 | **−2.38** | −3.00 | 10 / 3 / 0 |

### Excluded (disrupted) race list

2024 Japan NOR **−4**, China SAI **0**, Miami SAI **0**, Monaco RUS
**−4**, Canada PIA **−3**, Mexico City RUS **0**, São Paulo LEC **−3**,
Qatar GAS **−2**; 2025 Australia ALB **−1**, Emilia Romagna ALB **−4**,
Spain HUL **−5**, Britain VER **−1**, Netherlands ALB **−4**.

Canada 2025 LEC **−6** is **not** on this list (scRun 4). Austria 2024
VER **−6** is **not** on this list.

### Austria 2024 VER −6 re-audit

| Check | Aimed | Actual |
|---|---|---|
| SC-driven? (R21.5 said no) | confirm, don't assume | **no** |
| `major_disruption` | False | **False** |
| n_red | 0 | **0** |
| longest SC run | < 5 | **0** |
| Team pits | L23 HARD, L51 MEDIUM, L64 SOFT | **[23, 51, 64]** |
| SC/VSC of those | none | **[]** |
| Position-delta | −6 | **−6** |
| In clean set | yes | **yes** |

**Classification does not change.** The −6 remains a clean-race result:
two extra green pit-losses plus G1.5's 43-lap HARD at 0.03. It is not
an SC-counting artefact, and this flag does not move it into
insufficient-info.

### CHECKPOINT — tests green

Code change: `src/aris/eval/backtest.py`, `scripts/backtest.py`,
`tests/test_backtest.py` (flag helpers, split, three unit tests).
`simulate.py` / `recommend.py` / `tires.py` diff: **empty**.

| Suite | Aimed | Actual | Result |
|---|---|---|---|
| Full pytest | green | **266 passed**, 0 failed, 266 collected | **PASS** |

266 = R.2's 258 isolated + H.2's five `test_ask_model_version` tests +
three new R22 tests. H.2 `tests/conftest.py` (uncommitted, already on
this tree) isolates Ask from live JSONL, so the five Ask failures R21.1
reported are not in this run. Log: `results/r22/pytest.log`.

---

## R22.3 — Physics-offset thread closed

Written in this main tree:

`C:\Users\anass\OneDrive\Desktop\ARIS\docs\physics-calibration-research.md`

Same structure as `docs/tyre-degradation-research.md`: what was tried
(global, street/permanent, per-circuit), why each failed or fell short,
and the R21.4 proof that a lap-constant offset cannot move bias-
cancelled position-delta. Status: **closed research thread** — a real
limitation on absolute-value display, not a blocker for decision
quality. No intercept shipped.

---

## R22.4 — One current model-status document

Written in this main tree:

`C:\Users\anass\OneDrive\Desktop\ARIS\docs\model-status.md`

Interview-ready account of held-out MAE (E3 blend **0.583** vs MA(2)
**0.522**), G.5 tyre-degradation close, match-rate **0.322** vs stay-out
**0.276**, position-delta with the R22.2 clean/disrupted split, and the
R22.3 physics-offset close. This is the page to point at for "how good
is this, really."

---

## R22.5 — Zandvoort re-verify

`python scripts/_e1_smoke_strategy_zandvoort.py` against local Postgres.
Overlay unset. Compared to G1.5 / R21.2. This phase is eval scoring,
not simulate / recommend / tires — confirmed by diff, then by smoke.

| Check | Aimed (G1.5) | Actual (this tree) | Result |
|---|---|---|---|
| Setup | session_id 123, VER | **123**, VER, driver_id **2448** | **PASS** |
| Track | 72 laps, pit_loss **18.5**, slopes **0.08 / 0.05 / 0.03** | **72 / 18.5 / 0.08, 0.05, 0.03** | **PASS** |
| Prewrite windows | A:[18] B:[29] C:[18, 40] | **same** | **PASS** |
| Weekend form | n=20 | **20** | **PASS** |
| Clock | 287 ticks → lap 72 complete | **287** ticks, lap **72**, complete | **PASS** |
| Live state L25 | MEDIUM, tyre_life=2 | **MEDIUM / 2** | **PASS** |
| Recommend identity | Pit lap 33 HARD; Pit lap 30 HARD; Stay out | **Pit lap 33 for HARD; Pit lap 30 for HARD; Stay out on current tyres** | **PASS** |
| Smoke exit | SMOKE OK | **SMOKE OK** | **PASS** |

What-if MC is unseeded and not a locked identity. This run: delta
**−11.92 s**, MC P10/P90 **−147.55 / +29.33** (same printed delta as
R21.2 / H.1 / H.2). Log: `results/r22/zandvoort-smoke.log`.

---

## What this does and does not claim

Does: count SC/VSC pits in the 48-race stop-count comparison; report
position-delta for clean and disrupted side by side with the excluded
list; confirm Austria 2024 −6 is still a clean mixed result; close the
physics-intercept thread in writing; put one current model-status page
in this tree's `docs/`.

Does not: change `simulate()` / `recommend()` / tyre slopes; widen
major-disruption to catch Canada 2025's 4-lap SC run; drop disrupted
races from the all-sample −1.73; claim −1.49 clean is FIA points;
commit H.2.

---

## Isolation / paths

All of the following are under the main ARIS repo `docs/`, not a
worktree:

- `C:\Users\anass\OneDrive\Desktop\ARIS\docs\PHASE-R22-SUMMARY.md`
- `C:\Users\anass\OneDrive\Desktop\ARIS\docs\physics-calibration-research.md`
- `C:\Users\anass\OneDrive\Desktop\ARIS\docs\model-status.md`

Also in this tree: `docs/PHASE-R21-SUMMARY.md`,
`docs/PHASE-R2-POSITION-DELTA-SUMMARY.md`,
`docs/tyre-degradation-research.md`.

H.2 files remain uncommitted on this working tree, as they were before
R21.1.

**STOP.**
