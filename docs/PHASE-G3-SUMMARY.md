# Phase G.3 summary — protect the demo, then constrain the fit

Executed 2026-08-14. Scope: Blocks G3.1–G3.6. Every numeric result states
aimed vs actual. G3.1 was finished and confirmed before any later block.

The constrained overlay was validated **offline, behind the opt-in flag**.
It is **not** the default. Do not switch it in without an explicit decision.

---

## Verdict (read this first)

The shipped path is G1.5 again. Zandvoort recommend identity matches the
original lock. What-if/MC match G1.4 (physics-delta kept), not G2.

`recommend()` **is** rationally biased by the slopes it is given: with G2's
inverted C-code overlay it picked the flattest fitted compound on **80.7%**
of pit/plan proposes; with G1.5 globals it picked HARD. The apparent SOFT
bias was the simulator believing SOFT degraded slowest, which in 2025 it
did, because the unconstrained fit said so.

Harder-compound stints **do** run in lower traffic pressure than SOFT.
Observed “degradation” on HARD is partly pace management.

Isotonic (PAVA) fitting is a different method, not a fifth unconstrained
guess. In the walk-forward era it compressed **every** C-code to one
number (0.0216 s/lap). That is data quality, not a shipping slope table.
Offline, the constrained overlay **beats stay-out** on the combined walk
(0.299 vs 0.276) but **does not beat G1.5** (0.322). It is **not** a
candidate to become the new default.

| Metric | Aimed | Actual | Result |
|---|---|---|---|
| Default path = G1.5 globals + G1.4 physics-delta, no C-code overlay | yes | yes (`ARIS_TRUE_COMPOUND_SLOPES` off) | **PASS** |
| Zandvoort recommend identity vs E4.1 lock | Pit lap 33 HARD / Pit lap 30 HARD / Stay out | Pit lap 33 HARD / Pit lap 30 HARD / Stay out | **PASS** |
| Zandvoort What-if delta vs E4.1 lock / vs G2 | **−13.00 s** / not G2 **−2.34 s** | **−11.92 s** (G1.4) | identity of *simulate()* is G1.4, as required; not G2 |
| Zandvoort MC P10/P90 vs E4.1 / vs G2 | **−32.62 / −13.35** / not G2 **−137.96 / +38.92** | **−147.55 / +29.33** (G1.4) | same |
| G2 overlay requires explicit opt-in | yes | env `1` / `isotonic` or `use_true_compound=` | **PASS** |
| recommend() pit compound tracks flattest G2 slope (G2 walk) | report | **0.807** (2143/2657) | hypothesis **supported** |
| HARD stints in freer air than SOFT | report | median min-gap **1.82 s** vs **1.40 s**; free-air **0.464** vs **0.376** | **holds** |
| Constrained slopes monotonic C1≤…≤C6 within era | yes | yes, all four eras | **PASS** (by construction) |
| Zandvoort event-relative SOFT>MED>HARD after constraint | yes | **no** every year 2021–2026 | **MISS** |
| Chained MAE +5/+10/+20 vs G1.1 **1.861 / 2.444 / 2.790** | improve | **1.913 / 2.383 / 2.957** | **MISS** (+10 only is slightly better) |
| Combined 2024+2025 match-rate vs stay-out **0.276** (24/87) | **> 0.276** | **0.299** (26/87) | **PASS** vs stay-out |
| Combined match-rate vs G1.5 **0.322** (28/87) | **> 0.322** | **0.299** (26/87) | **MISS** — not a default candidate |
| Mean position-delta combined vs ≤0 / vs G1.5 **+2.96** | **≤ 0** | **+2.88** | **MISS** (0.08 better than G1.5, still positive) |
| Full pytest | green | **214 passed** | **PASS** |

**Recommendation:** keep G1.5 as the shipped default. The isotonic overlay
needs more work (the walk-forward era collapsed to a single slope). Wait
for an explicit decision before touching default `simulate()` /
`recommend()` / Strategy UI.

---

## G3.1 — shipped path reverted (done first)

G2 applied `event_relative_slopes` inside `load_track_config` whenever
`year` was passed. That is the `simulate()` / `recommend()` / Strategy UI
path, and it regressed the walk below stay-out.

**Change:** YAML / global 0.08 / 0.05 / 0.03 is the default again, even
when `year` is passed. G2 mapping + unconstrained fits stay in the repo.
Opt-in is `ARIS_TRUE_COMPOUND_SLOPES=1` (unconstrained G2) or
`isotonic` (G3 constrained), or `load_track_config(..., use_true_compound=...)`.
Unknown / unset / `0` / `off` → no overlay (fail closed).

Zandvoort smoke (`scripts/_e1_smoke_strategy_zandvoort.py`), **SMOKE OK**:

| Check | Aimed / locked (E4.1) | G3.1 actual | vs lock | vs G2 |
|---|---|---|---|---|
| Track laps / pit | 72 / 18.5 | 72 / 18.5 | **PASS** | same |
| Track slopes H/M/S | **0.08 / 0.05 / 0.03** | **0.08 / 0.05 / 0.03** | **PASS** | G2 was 0.0359 / 0.0461 / 0.0283 |
| Prewrite windows | A:[18] B:[29] C:[18,40] | same | **PASS** | same |
| Weekend form | n=20 | n=20 | **PASS** | same |
| Clock | 287 ticks → lap 72 | 287 → 72 | **PASS** | same |
| L25 state | MEDIUM tyre_life=2 | same | **PASS** | same |
| Ask/recommend identity | Pit lap 33 HARD; Pit lap 30 HARD; Stay out | **Pit lap 33 HARD; Pit lap 30 HARD; Stay out** | **PASS** | G2 had moved to Plan L31→SOFT, L46→HARD |
| What-if delta | **−13.00 s** | **−11.92 s** | G1.4, not E4.1 | G2 was **−2.34 s** |
| What-if MC P10/P90 | **−32.62 / −13.35** | **−147.55 / +29.33** | G1.4, not E4.1 | G2 was **−137.96 / +38.92** |

Recommend **identity** matches the original lock exactly. What-if/MC are
G1.4's numbers because G3.1 keeps G1.4 physics-delta (that is what beat
stay-out). They are **not** G2's numbers. Restoring E4.1 −13.00 s would
mean dropping physics-delta, which this phase does not do.

CHECKPOINT after G3.1: pytest **211 passed** (then 213 / 214 as later
tests landed). Log: `results/g3/zandvoort_smoke.log`.

---

## G3.2 — what `recommend()` actually chose

Source: `results/decisions/*.jsonl`, 48 files, **11 865** `propose` events.
G2 appended onto G1's files. Split at 2026-08-13 20:00 UTC.

**Caveat:** the pre-G2 (`g1`) 2024 slice is **two** 2024 walks (original
Phase G + G1.5), n=4670 = 2× G2's 2024 n=2335. The **2025 g1** slice
(n=2430) matches G2's 2025 count and is a clean G1.5 walk. G2 (n=4765)
is one clean overlay walk. Headline hypothesis test uses those two clean
slices plus G2 overall.

### Stay-out vs pit

| Walk | n propose | Stay-out | Pit+plan | Line |
|---|---:|---:|---:|---:|
| G1.5 2025 (clean) | 2430 | **0.422** (1026) | **0.536** (1302) | 0.042 (102) |
| G2 2024+2025 | 4765 | **0.392** (1870) | **0.558** (2657) | 0.050 (238) |

Stay-out is ~40% either way. The change is **which compound** a pit is for.

### Compound among pit/plan

| Walk | HARD | MEDIUM | SOFT | Most often |
|---|---:|---:|---:|---|
| G1.5 2025 (globals 0.08/0.05/0.03) | **1200** | 0 | 102 | **HARD** |
| G2 2024+2025 (unconstrained C-code overlay) | 487 | 365 | **1805** | **SOFT** |

G1.5's 102 SOFT in 2025 are the two-stop *plan* sketch (SOFT then HARD),
not pit-now SOFT. Almost every single-stop pit was HARD — the global
flattest slope.

### Does recommended compound track the flattest fitted slope?

Flattest = smallest (most negative) G2 unconstrained event-relative slope
for that race.

| Walk | Pit/plan with a compound | Match flattest G2 slope | Aimed vs actual |
|---|---:|---:|---|
| G1.5 2025 | 1302 | **0.040** (52-ish; HARD ≠ G2's often-SOFT flattest) | G1.5 was not using G2 slopes |
| G2 2024 | 1349 | **0.792** | — |
| G2 2025 | 1308 | **0.822** | — |
| G2 combined | 2657 | **2143/2657 = 0.807** | **yes, it does** |

All 2657 G2 pit/plan proposes sat in era 2023–2025. In that era the
unconstrained table has C5=−0.1892 and C4=0.0283 (slower-degrading than
C1–C3). Mapped onto event-relative labels, SOFT is often the kindest
tyre in the simulator. `recommend()` picked that tyre **four times in
five** pit/plan calls.

**Finding:** the SOFT bias is a rational response to bad degradation
numbers, not a separate bug in candidate generation. Give it globals
(HARD kindest) and it recommends HARD. Give it G2 (SOFT kindest) and it
recommends SOFT. Artefact: `results/g3/decision_audit.json`.

---

## G3.3 — pace-management confound

48 races, 2024+2025, gaps from cumulative lap times (same construction
RaceState uses). Green, non-pit laps. Free air = min(gap ahead, gap
behind) ≥ 2.0 s.

### Event-relative

| Compound | n laps | Median min nearby (s) | Median gap ahead (s) | Free-air fraction | Battle <1.5 s |
|---|---:|---:|---:|---:|---:|
| HARD | 22307 | **1.82** | 2.93 | **0.464** | 0.428 |
| MEDIUM | 17366 | 1.35 | 2.03 | 0.358 | 0.539 |
| SOFT | 4427 | 1.40 | 2.11 | 0.376 | 0.525 |

Stint-level medians: HARD **1.82 s** (n=766) vs MEDIUM 1.29 (n=912) vs
SOFT 1.24 (n=326). HARD free-air stints **0.449** vs SOFT **0.331**.

### True C-code

| Code | n laps | Median min nearby (s) | Free-air fraction |
|---|---:|---:|---:|
| C1 | 3811 | **2.07** | **0.512** |
| C2 | 7764 | 1.61 | 0.422 |
| C3 | 18190 | 1.65 | 0.426 |
| C4 | 11693 | 1.39 | 0.369 |
| C5 | 2594 | 1.34 | 0.356 |
| C6 | 48 | 0.82 | 0.396 |

C1 median nearby > C5: **yes**. C1 free-air > C5: **yes**. HARD > SOFT
and HARD > MEDIUM on both median nearby and free-air: **yes**.

**Finding: this holds.** Stints on harder compounds systematically occur
in lower-pressure air. Observed DegSlope on those stints is partly
deliberate pace management, not pure tyre physics. That is a concrete
reason an unconstrained lap-time fit will not produce C1 < C2 < … < C5.
Artefact: `results/g3/pace_pressure.json`.

---

## G3.4 — monotonicity-constrained refit

Same E3.2/G2.3 data (`--reuse-stints-csv`): fuel-corrected race DegSlope,
clean-lap filter, Stint/pit-out split, session IV pool, keyed by
CompoundIdentity within era. **Only the last step changed:** weighted
PAVA so C1 ≤ C2 ≤ … ≤ C6 (weights = n stints).

### Constrained vs G2 unconstrained (s/lap)

| Era | n | G2 unconstrained | G3 constrained | What the constraint did |
|---|---:|---|---|---|
| 2019-2021 | 79 | C1=**0.0976**, C2=**0.0353**, C3=**0.1029** | C1=**0.0583**, C2=**0.0583**, C3=**0.1029** | C1≤C2 **inverted → compressed to equal**. C2≤C3 unchanged |
| 2022 | 890 | C1=**0.0849**, C2=**0.0381**, C3=**−0.0423**, C4=**−0.0039**, C5=**0.1368** | C1=C2=C3=**−0.0074**, C4=**−0.0039**, C5=**0.1368** | C1≤C2 and C2≤C3 **inverted → pooled**. C3≤C4 and C4≤C5 unchanged (C5 was already the steepest) |
| 2023-2025 | 4597 | C1=**0.0369**, C2=**0.0359**, C3=**0.0461**, C4=**0.0283**, C5=**−0.1892**, C6=**−0.012** | **all 0.0216** | Whole stack pooled. C1≤C2, C3≤C4, C4≤C5 **inverted → equal**. C2≤C3 and C5≤C6 compressed to equal as part of that pool. **C5=−0.1892 is the inversion that dragged every compound to one number** |
| 2026 | 740 | C1=**0.0353**, C2=**−0.0082**, C3=**0.0195**, C4=**−0.0008**, C5=**0.0101** | C1=C2=**0.0066**, C3=C4=**0.0093**, C5=**0.0101** | C1≤C2 and C3≤C4 **inverted → compressed to equal**. C2≤C3 and C4≤C5 unchanged |

The useful distinction: 2019–2021 and 2026 still have *some* spread after
the constraint (a softest compound that the data could tell apart).
2023–2025 — the walk-forward era — could **not** distinguish any C-code
once order was enforced. That is not “SOFT should equal HARD” as physics.
It is “the lap-time estimator, with C5 badly inverted, has no remaining
compound signal under a monotone constraint.”

Shipped file (opt-in only): `data/compounds/true_compound_slopes_isotonic.json`.
Unconstrained G2 file is untouched.

CHECKPOINT: pytest **214 passed**.

---

## G3.5 — offline validation (opt-in, not default)

`ARIS_TRUE_COMPOUND_SLOPES=isotonic`. Default path unchanged.

### G3.5.8 — G1.1 chained rollout

Same 477 green 2024 stretches. Aimed: improve on G1.1 **1.861 / 2.444 / 2.790** at +5/+10/+20.

| Horizon | n | G1.1 chained MAE | G3 isotonic chained MAE | vs G1.1 |
|---|---:|---:|---:|---|
| +1 | 477 | **0.861** | **0.849** | slight improve |
| +5 | 477 | **1.861** | **1.913** | **worse** |
| +10 | 477 | **2.444** | **2.383** | slight improve |
| +20 | 354 | **2.790** | **2.957** | **worse** |

Compounding is still ~3.5× from +1 to +20. A single 0.0216 slope for every
2024 dry compound does not fix chained residual error. Artefact:
`results/g3/g11_rollout.json`.

### G3.5.9 — walk-forward 2024+2025

Same walker, `mc_draws=0`, classified P5. 2024 elapsed **767 s**. 2025
elapsed **1240 s**. Not shortcut.

#### 2024 (same 40 scored events)

| Metric | Aimed | Actual | Result |
|---|---|---|---|
| Match-rate | **> 0.250** stay-out (10/40); G1.5 **0.325** (13/40) | **0.300** (12/40) | beats stay-out; **below G1.5** |
| Position-delta | **≤ 0**; G1.5 **+2.63** | **+2.29** | **MISS** (0.34 better than G1.5) |
| ARIS-hindsight / team / insufficient | — | 27 / 1 / 21 | — |
| Rolling match at R24 | — | **0.425** (G1.5 **0.300**) | — |
| Rolling pos-delta at R24 | — | **+3.8** (G1.5 **+4.4**) | — |

#### 2025 (never in residual training)

| Metric | Aimed | Actual | Result |
|---|---|---|---|
| Match-rate | **> 0.298** stay-out (14/47); G1.5 **0.319** (15/47) | **0.298** (14/47) | **equals** stay-out, not greater; **below G1.5** |
| Position-delta | **≤ 0**; G1.5 **+3.29** | **+3.46** | **MISS** (worse than G1.5) |
| ARIS-hindsight / team / insufficient | — | 29 / 4 / 27 | — |
| Rolling match at R24 | — | **0.300** (G1.5 **0.200**) | — |
| Rolling pos-delta at R24 | — | **+3.8** (G1.5 **+3.4**) | — |

#### Combined 2024+2025 (48 races, 87 scored inflections)

| Metric | Aimed | Actual | Result |
|---|---|---|---|
| Match-rate vs stay-out | **> 0.276** (24/87) | **0.299** (26/87) | **PASS** vs stay-out |
| Match-rate vs G1.5 | **> 0.322** (28/87) | **0.299** (26/87) | **MISS** |
| Position-delta | **≤ 0**; G1.5 **+2.96** | **+2.88** | **MISS** |

G2 on this set was **0.195** (17/87), below stay-out. Constrained beats
G2 and beats stay-out. It does **not** beat G1.5. Rule G3.5.11: candidate
for default only if it beats **both**. It does not.

Artefacts: `results/g3/backtest/2024_summary.json`, `2025_summary.json`,
`2024_2025_combined_summary.json`.

### G3.5.10 — Zandvoort event-relative SOFT>MEDIUM>HARD

Aimed: yes, every year, for the compounds Zandvoort actually runs.

| Year | Nomination | Constrained H / M / S | SOFT>MED>HARD |
|---|---|---|---|
| 2021 | C1/C2/C3 | 0.0583 / 0.0583 / 0.1029 | **NO** (SOFT>HARD but MED=HARD) |
| 2022 | C1/C2/C3 | −0.0074 / −0.0074 / −0.0074 | **NO** (all equal, all negative) |
| 2023 | C1/C2/C3 | 0.0216 / 0.0216 / 0.0216 | **NO** |
| 2024 | C1/C2/C3 | 0.0216 / 0.0216 / 0.0216 | **NO** |
| 2025 | C2/C3/C4 | 0.0216 / 0.0216 / 0.0216 | **NO** |
| 2026 | C2/C3/C4 | 0.0066 / 0.0093 / 0.0093 | **NO** (SOFT=MED; HARD is kindest, which is the right *direction*) |

Aimed yes. Actual **no every year**. Ties fail a strict SOFT>MED>HARD
check. 2026 is the only year with any leftover spread, and even there
SOFT is not steeper than MEDIUM.

### G3.5.11 — default-candidate flag

**Not a candidate.** Combined match-rate 0.299 beats stay-out 0.276 and
loses to G1.5 0.322. The walk-forward era's constrained table is one
number. Switching that in automatically would replace a physical prior
that differentiates SOFT/MEDIUM/HARD with a flat 0.0216 and give back
two of the eight extra matches G1.5 holds over stay-out. Leave the flag
off.

---

## G3.6 — how ARIS decides

`docs/how-recommend-works.md` — non-engineer account of the snapshot
`recommend()` sees (position, gaps, tyre state, laps remaining), the
fixed candidate menu, physics-delta scoring, and why lap-time-only
degradation is the reliability ceiling. Written for the interviews this
project is for.

---

## Tests

Full pytest after G3.1 gate, after isotonic fitter, after isotonic opt-in
test, and at close: **214 passed**, 0 failed. Final log:
`results/g3/pytest.log`.

G2 work remains loadable: `ARIS_TRUE_COMPOUND_SLOPES=1` still overlays
unconstrained C-code slopes. `isotonic` overlays the constrained file.
Neither is default.

---

## What this does and does not claim

Does: put the Zandvoort demo back on the locked recommend identity;
prove `recommend()` follows the slope table it is given; show HARD
stints are cleaner-air stints; replace a fourth unconstrained guess
with an order constraint, and report that the constraint erases
compound identity in 2023–2025.

Does not: restore E4.1 What-if −13.00 s (physics-delta stays); make
SOFT>MEDIUM>HARD true at Zandvoort; beat G1.5 match-rate; or change
the shipped default.

---

STOP — waiting for review before any default behavior changes.
