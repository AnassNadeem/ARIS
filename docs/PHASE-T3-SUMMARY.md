# Phase T3 summary — field simulation and opponent awareness

Executed 2026-08-21 in the **main** tree
`C:\Users\anass\OneDrive\Desktop\ARIS`, on the Dutch GP weekend.
Scope: pre-conditions, then T3-A → D → B → C → E, with a gate after
each section. Architecture lock held: snapshot → score a fixed
shortlist → rank by delta vs stay-out. No learned policy.

Every numeric result states aimed vs actual.

Headline commit: `14d5cc7`
`feat: Tier 3 — field sim, rival pit est, overcut, field comms, wet heuristic (match-rate: 30/87)`

Related commits immediately before it (required so T3 did not sit on a
mixed T2 tree):

| Commit | What |
|---|---|
| `a8d17d5` | T2 implementation (SC pit cost, dynamic undercut, approach trigger, circuit deg flagged) |
| `ac2efd2` | T2 docs boundary — 0.345 match-rate, T2-A flagged |
| `12b3c12` | Ask grounding citation format (pre-T3 cleanup) |

Walk artefacts (gitignored, local): `results/backtest/t3/` (dry) and
`results/backtest/t3-wet/` (`--include-wet`). Re-run:

```
python scripts/backtest.py --years 2024 2025 --out-dir results/backtest/t3
python scripts/backtest.py --years 2024 2025 --include-wet --out-dir results/backtest/t3-wet
```

---

## Verdict (read this first)

**T3 shipped as infrastructure plus two flagged scorers and one
uncalibrated wet heuristic.** The locked dry 87-event match-rate did
**not** move. Field undercut and overcut are implemented and tested,
but they are **not** the default recommend path. The wet INTER/WET
heuristic fires on rain signals in live recommend, and is labelled as
heuristic on the radio; its eval slice missed the 0.340 target.

If the race started tonight, the **demo identity is the T2 default**
(G1.5 + SC pit cost + T2-D undercut + approach trigger), plus FIELD
comms and a conservative INTER card when rain is actually signalled.
It is **not** a field-aware ranking engine unless you set the flags.

| Check | Aimed | Actual | Result |
|---|---|---|---|
| Dry combined match-rate | ≥ **0.345** (30/87), floors 2024 ≥ 0.375 / 2025 ≥ 0.319 | **0.345 (30/87)** · 2024 **0.375 (15/40)** · 2025 **0.319 (15/47)** | **PASS** (identity) |
| Lights-out all / clean / disrupted | ≤ −1.70 / −1.45 / −2.30 (tiny drift vs −1.73 / −1.49 / −2.38) | **−1.73 / −1.49 / −2.38** (n=48 / 35 / 13) | **PASS** |
| Zandvoort identity | Pit 33 HARD / Pit 30 HARD / Stay out, `mc_draws=0`, field=None | same | **PASS** |
| MAE | not re-run; last **0.583 s** | not re-run | **n/a** |
| T3-A estimator | VER NL lap 20 MEDIUM age → pit in 22–30; 0 tyre_life / 2-car field do not crash | unit tests pass; **not** wired into scoring | **PASS** |
| T3-D FIELD board | lap 1, 10, 20 fire; not lap 11; ≥4 rivals; not a `DecisionQueue` propose | unit + cadence tests pass | **PASS** |
| T3-B field undercut default-on | combined ≥ **0.355** and year floors | **not defaulted**; flag-on 48-race walk **not run** | **NOT CLEARED** — stays `ARIS_FIELD_UNDERCUT` off |
| T3-C overcut default-on | combined ≥ **0.345** | **not defaulted**; extra `OVERCUT_*` labels can steal rank-1 | **flagged off** (`ARIS_FIELD_OVERCUT`) |
| T3-E `--include-wet` | new n ~110+; combined ≥ **0.340**; do not claim calibration | **0.327 (36/110)** | **MISS** on 0.340; n **PASS**; uncalibrated as specified |
| Dry 87 vs wet slice | 87 stays a separate slice | dry still 30/87; wet 36/110 | **PASS** (separation) |
| Ask grounding (pre-condition) | `pytest tests/ -k "ask or grounding"` green | 21 passed | **PASS** |

---

## What improved (honest)

These are real, shipped improvements. They are **not** a match-rate
gain on the 87.

1. **The field is no longer invisible to the engineer.** T3-A estimates
   when the cars around the focus driver will box (compound cliff ×
   race length × 0.85, clamped). T3-D prints that as a `FIELD` board
   on lap 1, every 10 laps, or when an estimate jumps more than 3
   laps. The console no longer collapses that into generic INTEL.
2. **Undercut has a physics-delta alternative** to the T2-D −0.3/−0.8 s
   bonus: `simulate_undercut()` vs the car ahead’s estimated pit lap,
   cap −1.2 s, explicit T2-D fallback when that estimate is missing.
   It exists behind `ARIS_FIELD_UNDERCUT`. Default remains T2-D.
3. **Overcut is a named candidate**, not only “stay-out happened to
   rank.” `OVERCUT_{code}_{N}L` for N ∈ {2,4,6}, at most two cards,
   only when the rival is within 8 laps of boxing (confidence not LOW),
   gap ahead ≥ 2 s, and ≥ 15 laps remain. Window eligibility is
   physics-delta; ranking is still `simulate()` vs stay-out. Default
   off so the 87 cannot regress.
4. **Wet is no longer “out of scope / silent.”** INTER (and WET under
   heavy rain) can enter the shortlist. The radio includes
   `[HEURISTIC — reduced confidence in wet conditions]`. Eval gained
   `--include-wet` without dumping Spain-style dry `rainfall=True`
   races into the 87.
5. **Ask grounding** now copies `json.dumps` numbers and a `Cited:
   event_id=...` block after the 3-sentence clip, and looks up lap-2
   decisions by facts when hashing retrieval misses them. That was
   pre-T3 cleanup, not a strategy win.

Match-rate on the dry 87 is **the same number T2 already had**. T3 did
not beat T2 on that metric, because the pieces that could have changed
ranking were either not wired (A), not a propose (D), or flagged off
(B, C). That is the intended gate discipline, not an accident.

---

## What failed or did not clear

### T3-B — field undercut not defaulted

Aimed: if a flag-on walk-forward combined ≥ **0.355** and identity
held, turn default on (unset still T2-D). Actual: implemented **behind
the flag first**; the 48-race flag-on walk was **not run**. Default
stays T2-D. Do not claim a 0.355 field-undercut result. Evidence
string when the car ahead has no estimate:
`undercut fallback: T2-D (no rival estimate)`.

### T3-C — overcut not defaulted

Aimed: no flag if match-rate stays ≥ 0.345; add `ARIS_FIELD_OVERCUT`
default-off only on regression. Actual: default **off from the start**.
Reason: `walk_race_triggers` now passes `field` into `recommend()`.
With overcut default-on, extra `PIT_LAP` cards labelled `OVERCUT_*`
compete for rank-1 on every trigger where a rival is about to box.
That can change `matches_team_pit` even when the pit lap is close.
Protecting the locked 87 took priority over shipping overcut live.
Unit tests (negative window, no candidate when remaining < 15 or gap
< 2 s, Zandvoort field-free identity, OVERCUT ACTIVE commentary) pass
with the flag on in-process.

### T3-E — wet eval missed 0.340

Aimed: `--include-wet` combined ≥ **0.340**, new denominator ~110+,
dry 87 unchanged, no calibration claim.

| Slice | Aimed | Actual |
|---|---|---|
| Dry 87 (same walker, `include_wet=False`) | **0.345 (30/87)** | **0.345 (30/87)** |
| Wet 2024 | report | **0.367 (18/49)** |
| Wet 2025 | report | **0.295 (18/61)** |
| Wet combined | ≥ **0.340**, n ~110+ | **0.327 (36/110)** |

n=110 meets the denominator aim. Combined **0.327 misses 0.340**. 2025
wet **0.295** is **below** always-stay-out on that slice (0.311). Do
**not** quote 0.327 as a wet-strategy win. The heuristic still ships
for live rain signals, labelled as heuristic.

### T3-B flag-on / T3-C flag-on walks

Not executed. Cost: a second and third 48-race walk (~40 min each).
The dry identity walk (flags off) and the wet eval walk were the two
that ran. Turning B or C on for a demo is `ARIS_FIELD_UNDERCUT=1` /
`ARIS_FIELD_OVERCUT=1` and a new walk before calling it default.

### Ingest integration tests during the T3 pytest sweep

`tests/test_ingest.py` (3 tests) errored at setup: FastF1 season
schedule failed (`idna` has no `encode` / `IDNAError` in this venv).
Same class of FastF1 schedule failure already noted under T2 (MAE not
re-run). Not a T3 logic regression. T3 unit + identity tests were
green; Ask grounding 21 passed.

### Early overcut unit failures (fixed before commit)

First `simulate_overcut_window` cases used similar last-lap times, so
the window delta was **positive** (focus slower) and no candidate was
emitted. Commentary OVERCUT ACTIVE was also eaten because the FIELD
board overwrote `last_estimates` after the rival had already boxed.
Fixes: tests use a slow, old-SOFT rival vs a fresh HARD focus; pit
detection reads `prior_estimates` from before the board update. Both
in `14d5cc7`.

---

## Architecture (what T3 was allowed to do)

```
SectorClock.tick
  → FieldState.standings
  → rivals.py estimate_all_rivals
       ├→ FIELD board (commentary, not DecisionQueue)
       ├→ compute_field_undercut_value   [flag off]
       └→ generate_overcut_candidates    [flag off]
  → recommend() still ranks simulate() vs stay-out
  → stay-out forced into top-3
```

Rival estimates **never** change the focus driver’s `simulate()` lap
times. They only feed undercut bonus, overcut eligibility, and comms.
`physics/traffic.py` (G3.3 gaps) was **not** reused. Residual is **not**
chained on fake rival laps (G1.4).

`recommend(state, *, field=None)`. `field is None` (Zandvoort, most
unit tests) is T2-D / no overcut. Live and walk-forward pass
`session.field_state` when they have it; scoring still ignores it
unless a flag is on (estimates are not even computed if both flags
are off — that was a walk-speed fix).

---

## Pre-conditions

T2 code was still dirty on `main`. Plan: do not mix T3 into that tree.

1. T2 implementation committed separately (`a8d17d5`).
2. `docs/model-status.md` committed as the T2 boundary (`ac2efd2`).
3. Ask: `_compose` rounded delta to `+.1f`, clipped to 3 sentences, and
   never emitted `Cited:`. Tests required `json_number(...)` verbatim,
   the label substring, and `Cited: event_id=...` **after** the clip.
   Lap-2 questions also abstained because hashing retrieval prefers
   “lap 21” / “lap 32”. Fix: exact numbers + citation after clip;
   fact lookup when vector top-k + constraints yield nothing.
   `pytest tests/ -k "ask or grounding"` → 21 passed (`12b3c12`).

---

## T3-A — Rival pit-lap estimation

**Flag:** none for the estimator. Deg: G1.5 `DEFAULT_COMPOUND_SLOPE`
unless `ARIS_USE_CIRCUIT_DEG` is on. INTER/WET T2-A slopes are never
used here.

**Cliff math (shipped):**

- `race_frac = total_laps / 72`
- `cliff = {SOFT:16, MEDIUM:32, HARD:50}[compound] * race_frac`
- `estimated_pit_lap = current + int((cliff − tyre_life) * 0.85)`
- clamp `[current+1, total−2]`
- confidence: HIGH ≤8 laps to cliff, MEDIUM ≤18, else LOW
- `tyre_life == 0` treated as 1
- top 6 by position, exclude focus; fewer than 6 cars: return what
  exists
- `stint_number >= 2` → reasoning says later stint; still estimate the
  next stop from the current compound cliff (no second model)

`StandingRow.stint_number` is `1 +` prior `pit_in` count (current lap
included at sector 3).

`gap_to_focus = focus.gap_to_leader_s − rival.gap_to_leader_s`
(positive = rival ahead). `gap_trend` from last 3 completed-lap gaps
if `all_laps` is passed; else 0.

**Gate:** unit tests in `tests/test_rivals.py`. Dry walk with A **not**
wired into scoring: 0.345 held. Zandvoort field-free: unchanged.

---

## T3-D — FIELD comms (after A, before B)

**Flag:** none. Informational only.

Cadence: lap 1, every 10 laps, or any rival `estimated_pit_lap` shift
> 3. Type `FIELD`. Format:

```
FIELD: VER box ~L28 (MED 18L) · PIA box L31 (MED 21L) · LEC already pitted (HARD 6L)
```

HIGH: `box L28`. MEDIUM: `box ~L28`. LOW: `est. box L28`. Stint ≥ 2:
`already pitted`.

**Must not** go through `DecisionQueue.propose()`.
`walk_race_triggers` writes `by_lap[lap] = turn.recommendation`; a
FIELD propose would overwrite PIT and Streamlit pending would block
the engineer. Implemented as `field_board_should_fire()` in
`triggers.py` (not returned from `check_triggers()`), consumed by
commentary.

ConsoleView maps `field` → `field` (previously every non-alert type
became `intel`). CommsPanel: dark `C.void` background, IBM Plex Mono
body, `FIELD` label in `C.blue`.

On a rival pit, if the focus driver is in an overcut window (prior
estimate within 8 laps, remaining ≥ 15, gap ≥ 2 s):
`OVERCUT ACTIVE — {code} pitted. Hold {N} more laps.` Else the
existing INTEL pit line.

**Gate:** `tests/test_commentary.py` — lap 10 and 20 fire, not 11;
≥4 rivals; first lap fires. Dry match-rate untouched (no propose).

Manual NL 2024 NOR 10× replay was specified as a gate; it was **not**
run as a live 10× console session in this pass. Cadence is covered by
unit tests on the same rules.

---

## T3-B — Field-aware undercut scoring

**Flag:** `ARIS_FIELD_UNDERCUT`. Unset / 0 / false = T2-D.

`simulate_undercut()`: physics-delta / `tire_pace_loss` only. Window
now → `estimated_pit_lap + 3`. Return `min(delta, 0)` (a loss is not
an undercut). Current-lap pit uses SC-reduced `get_pit_loss`; later
stops in the window pay green YAML loss.

`compute_field_undercut_value()`: car **directly ahead** (focus
position − 1). If that rival’s estimate is missing → T2-D +
`undercut_source=t2d_missing`. If they box within 3 laps → T2-D. If
the window is negative → cap **−1.2 s**, `undercut_source=field`.

`narration_context["undercut_source"]`: `field` | `t2d` | `none`.

Call sites that have field: `DecisionQueue.propose`,
`walk_race_triggers`, `_recommend_at_lap`, Streamlit
`apps/pages/01_Strategy.py`, `backend/aris_api.py`
(`FieldState.from_laps` when `fetch_all_laps` works).

**Gate:** flag off + field present = T2-D (unit). Flag on +
`field=None` = Zandvoort identity (unit). Default-on ≥ 0.355:
**not cleared**.

---

## T3-C — Overcut

**Flag:** `ARIS_FIELD_OVERCUT`. Default off.

Eligibility: rivals with `laps_until_pit ≤ 8` and confidence ≠ LOW;
skip if `gap_ahead_s < 2` or `laps_remaining < 15`; N in {2,4,6};
at most 2 candidates, soonest rival, best (most negative) window.
Label `OVERCUT_{code}_{N}L`. Ranking: existing `simulate()` vs
stay-out. Stay-out still forced into top-3. Overcut actions do **not**
get the undercut bonus.

Narration (no LLM): `Overcut window — {rival} is coming in. Stay out
{N} more laps, build the gap, then box. Net: {delta:.1f}s in our
favour.`

Ask concepts `data/ask/concepts/overcut.md` / `undercut.md` updated:
still not FIA rules. `docs/how-recommend-works.md` shortlist now
mentions optional OVERCUT / INTER tags.

**Gate:** unit tests in `tests/test_overcut.py`. Dry 0.345 protected
by leaving the flag off. Monaco “OVERCUT in top-3” is generator +
narration contract; remainder-of-race ranking can still leave the
card outside top-3.

---

## T3-E — Wet / intermediate heuristic

**Flag on the live path:** none (fires on wet signals). Eval:
`--include-wet` (default off).

`src/aris/physics/wet.py`. **No G1.5 dry slopes. No FastF1 wet-slope
fit.** Constants (uncalibrated):

| Constant | Value |
|---|---|
| INTER pace loss vs dry slick | 3.0 s/lap |
| WET pace loss vs dry slick | 8.0 s/lap |
| Slick penalty per mm rain | 2.0 s/lap |
| INTER rain threshold | 0.5 mm |
| WET rain threshold | 2.0 mm |
| Boolean rainfall stand-in | 1.2 mm |
| Min laps for INTER | 8 |

`should_recommend_inter`: current compound SOFT/MEDIUM/HARD, ≥8 laps
left, not red (`"5"` not in `track_status`), **and** (`mm > 0.5` **or**
`weather_rainfall is True` **or** a field car already on INTER/WET).
False if already INTER/WET. **Ignores** track_status `4`/`6`/`7` as
wet (`"4"` is Safety Car).

WET candidate only if `mm ≥ 2.0` or already INTER with rain still on.
**Not** when `track_status == "5"` (that is red).

When the heuristic fires, INTER is **promoted to rank 1** among the
scored list (stay-out still forced into top-3). `Recommendation.wet_heuristic
= True`. Radio includes the HEURISTIC caveat.

`RaceState`: `rainfall_mm_per_lap: float | None = None`,
`weather_rainfall: bool | None = None`. `build_race_state()` sets the
boolean from `fetch_session_weather()["rainfall"]` and leaves mm None
unless a caller passes it. DB weather is a **boolean**, not mm/lap.

`classify_decision(..., include_wet=False)` default path is **identical
to T2** (session rainfall or wet compound → exclude; red `"5"` →
exclude) so 87 and 0.345 stay locked. `include_wet=True`: do not
blanket-exclude session rainfall; **score** iff no red **and**
INTER/WET on focus compound **or** team actual compound; remaining
rainfall-bit dry events stay excluded (Spain).

Brazil unit: `weather_rainfall=True` or `rainfall_mm_per_lap=1.2`,
`track_status="1"`, INTER in shortlist, `wet_heuristic is True`, slick
not rank 1. Passes.

**Limitation (live):** session-level `rainfall=True` on a dry race
(Spain) can still fire the INTER heuristic in `recommend()`, even
though walk-forward will not **score** those inflections into the 87.
That is a false-positive rain bit, not a fitted wet model.

---

## Feature flags (complete)

| Flag | Default | Role |
|---|---|---|
| `ARIS_USE_CIRCUIT_DEG` | **off** | T2-A; rival cliffs stay G1.5 unless this is on |
| `ARIS_FIELD_UNDERCUT` | **off** | T3-B field vs T2-D |
| `ARIS_FIELD_OVERCUT` | **off** | T3-C candidates |
| `ARIS_TRUE_COMPOUND_SLOPES` | **unset** | unchanged |
| `--include-wet` | eval only | T3-E scoring; not a runtime flag |

---

## Dry vs wet walks (full numbers)

### Dry (`results/backtest/t3/`, flags off)

| Year | Match | Stay-out | Pos-delta all | Clean | Disrupted |
|---|---|---|---|---|---|
| 2024 | **0.375 (15/40)** | 0.250 (10/40) | −2.04 | −2.06 (n=16) | −2.00 (n=8) |
| 2025 | **0.319 (15/47)** | 0.298 (14/47) | −1.42 | −1.00 (n=19) | −3.00 (n=5) |
| Combined | **0.345 (30/87)** | 0.276 (24/87) | **−1.73** | **−1.49 (n=35)** | **−2.38 (n=13)** |

Exact combined print: match `0.3448275862068966` scored 30/87;
pos-delta all `−1.7291666666666667`; clean `−1.4857142857142858`;
disrupted `−2.3846153846153846`. Quoted as −1.73 / −1.49 / −2.38,
same as T2.

### Wet (`results/backtest/t3-wet/`, `--include-wet`)

| Year | Match | Stay-out | n scored |
|---|---|---|---|
| 2024 | 0.367 (18/49) | 0.265 (13/49) | 49 |
| 2025 | 0.295 (18/61) | 0.311 (19/61) | 61 |
| Combined | **0.327 (36/110)** | 0.291 | **110** |

2025 wet loses to stay-out. Combined 0.327 **< 0.340**. Lights-out
pos-delta on this walk is the same −1.73 / −1.49 / −2.38 (prewrite,
not mid-race wet ranking).

---

## Spec vs code (corrections that were required)

These would have broken identity or eval if copied from the brief
literally:

- Tests live in `tests/`, not `src/aris/tests/`.
- Zandvoort lock is **lap 25, MEDIUM, tyre_life 2**, via
  `_zandvoort_state()` — not a `RaceState(driver=..., lap=1)`
  constructor (invalid).
- FastF1 `track_status` `"4"` is **Safety Car**, not wet. `"5"` is
  red. Wet signals: mm, session boolean rainfall, or INTER/WET on
  track.
- DB weather is boolean `rainfall`, not mm/lap.
- FIELD board must **not** `propose()`.
- Overcut window deltas are seconds; remainder-of-race pit deltas are
  tens of seconds. Eligibility ≠ ranking.
- Dry 87 stays a **separate slice**. `--include-wet` does not dump
  Spain-style dry rainfall bits into it.

---

## Files

**Created:** `src/aris/field/rivals.py`, `src/aris/physics/wet.py`,
`tests/test_rivals.py`, `tests/test_field_undercut.py`,
`tests/test_overcut.py`, `tests/test_wet.py`,
`docs/PHASE-T3-SUMMARY.md` (this file).

**Modified (T3):** `standings.py` (`stint_number`), `field/__init__.py`,
`recommend.py`, `simulate.py`, `state.py`, `triggers.py`, `session.py`,
`queue.py`, `narrate.py`, `commentary.py`, `eval/backtest.py`,
`scripts/backtest.py`, `backend/sessions.py` (type passthrough already
lowercased FIELD), `backend/aris_api.py`, `apps/pages/01_Strategy.py`,
`CommsPanel.tsx`, `ConsoleView.tsx`, `test_commentary.py`,
`data/ask/concepts/overcut.md`, `undercut.md`,
`docs/how-recommend-works.md`, `docs/model-status.md`, `README.md`.

**Not modified for T3:** `physics/traffic.py`, postrace ranking,
R21.3 `is_major_disruption`, T2-A JSON as a default slope source,
Zandvoort YAML pit-loss.

---

## What this does not claim

- That T3 beat T2 on match-rate. Dry 87 is **the same 30/87**.
- That field undercut or overcut is the shipped ranking path.
- That `--include-wet` 0.327 is a calibrated wet model, or that it
  beats stay-out in 2025.
- That session `rainfall=True` means it is raining (Spain).
- That track_status `"4"` is rain or `"5"` is extreme wet.
- That rival pit estimates are a learned opponent policy.
- That MAE, G1.5, T2-A, or lights-out physics offset changed.
- That Strat B would have scored more FIA points.

Public headline remains: mid-race match-rate **0.345 (30/87)** vs
stay-out **0.276**, lights-out **−1.73 / −1.49 / −2.38**, Zandvoort
Pit 33 / Pit 30 / Stay out, MAE **0.583 s**, T2-A flagged.

Further reading: [`docs/model-status.md`](./model-status.md),
[`docs/how-recommend-works.md`](./how-recommend-works.md),
[`docs/strategy-backtest.md`](./strategy-backtest.md).
