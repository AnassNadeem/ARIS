# ARIS strategy deep audit

Read-only investigation of early pitting, wet calibration, and ghost decision logic.
All formulas, names, and numbers below are from source files and a local `recommend()` /
`simulate()` run on 2026-09-03. No model or product code was changed.

Runtime races used:

- **Primary ghost / early-pit case:** 2025 Netherlands (Zandvoort) R15, 72 laps,
  `country='Netherlands'`, start `MEDIUM`. This is the locked identity circuit
  (`data/tracks/netherlands.yaml`: `total_laps: 72`, `pit_loss_s: 18.5`).
- **G1.5 isolation:** `year=2019`, `round_no=99` so `calibrate_race_weekend` cannot
  load practice data and every compound source is `g15`.
- **User 57-lap thought experiment:** same G1.5 path, `total_laps=57`, lap 9,
  `MEDIUM`, `tyre_life=9`.

---

## SECTION 1 — EARLY PIT ROOT CAUSE

### Definitive answer

ARIS does **not** start the ghost on SOFT when the real driver started on MEDIUM.
The ghost **start compound is the real driver's lap-1 compound**.

The lap-9 HARD stop is produced because **`recommend()` at lap 1 is only allowed
to pit in `{now, +1, +2, +3, +5, +8}` laps**. On a 72-lap race that set is
**laps 1, 2, 3, 4, 6, 9**. There is **no candidate for “stay on MEDIUM to lap
25–30 then pit HARD”**. Rank-1 is therefore the **latest legal candidate**:
**Pit lap 9 for HARD**.

That is a **deliberate (but miscalibrated) candidate-generation design**, not a
SOFT-start bug and not compound suppression. The physics still prefers a later
HARD stop **when that action is scored**: at lap 9, `PIT_LAP 25 HARD` beats
`PIT_NOW HARD`, but lap 25 is **not on the shortlist**.

The ghost then **freezes that lap-1 plan** and does not re-run `recommend()`
when SC / weather / field change.

### 1. Ghost starting compound (`src/aris/ghost.py`, `src/aris/ghost_pack.py`)

`compute_ghost()` (used by `scripts/prebuild_race_r2.py` → `build_ghost`) takes
the **first focus-lap compound from the race pack**, not a lights-out guess:

```269:283:src/aris/ghost_pack.py
    start_compound = normalize_compound(str(focus_laps[0].get("compound") or "MEDIUM"))
    ...
        compound=start_compound,
        tyre_life=1,
```

`recommend()` is then called on a `RaceState` that already has that compound,
at **lap 1, then lap 2 if lap 1 is `STRATEGY_RESET`**:

```297:311:src/aris/ghost_pack.py
        for decision_lap in (1, 2):
            ...
                state = template.model_copy(update={"lap_number": decision_lap})
                rec = rec_fn(state, top_k=3, mc_draws=0)
                card = pick_strategy_recommendation(rec)
```

`schedule_from_recommendation()` **keeps** `start_compound` and only records
future pit compounds from the card:

```408:427:src/aris/ghost.py
    start = normalize_compound(str(start_compound or "MEDIUM"))
    ...
        return GhostPlan(
            pit_laps=pits,
            pit_compounds=compounds,
            start_compound=start,
```

`create_ghost_from_plan()` / `score_parallel_ghost()` seed `ghost_tyre` from
`plan.start_compound`.

**Answers:**

| Question | Answer |
|---|---|
| Taken from the real driver? | **Yes** — `focus_laps[0]["compound"]`. Fallback string `"MEDIUM"` only if missing. |
| Chosen by `recommend()` at lap 1? | **No** for the *start* compound. `recommend()` chooses the *pit schedule*. |
| Can it differ from the real start? | **Only if pack data is wrong/missing**, or if `recommend()` returns `PIT_NOW` on lap 1 (ghost would then pit immediately and switch compound). It does not invent SOFT at lights-out while the pack says MEDIUM. |

Early pitting is **not** explained by “ARIS started on SOFT”.

There is a **second** pre-race planner, unused by R2 ghost bake:
`src/aris/plan/prewrite.py` `generate_strat_plans()` / `derive_pit_windows()`.
For 72 laps and `pit_loss_s=18.5` that yields **~lap 19 (Strat A) and ~lap 30
(Strat B)** — much closer to real first stops. Ghost bake **does not** use this.

### 2. What `recommend()` returns at lap 1

Candidates (`_candidate_actions`):

```893:933:src/aris/recommend.py
    actions: list[StrategyAction] = [
        StrategyAction(kind=ActionKind.STAY_OUT),
    ]
    for compound in compounds:
        actions.append(StrategyAction(kind=ActionKind.PIT_NOW, pit_compound=compound))
    for offset in (1, 2, 3, 5, 8):
        pit_lap = state.lap_number + offset
        ...
    if not _one_stop_covers_remaining(state):
        mid = state.total_laps // 2
        for pits, compounds in (
            ([mid, state.total_laps - 8], ["MEDIUM", "HARD"]),
            ([mid - 5, mid + 10], ["SOFT", "HARD"]),
        ):
```

Plus LIFT/BRAKE on corners 1, 7, 10 (not strategy).

`_one_stop_covers_remaining`:

```858:867:src/aris/recommend.py
MAX_REALISTIC_STINT_LAPS = 38
MIN_STINT_LAPS = 15
...
    current_left = max(0, MAX_REALISTIC_STINT_LAPS - tyre_life)
    return remaining <= current_left + MAX_REALISTIC_STINT_LAPS
```

At lap 1, `tyre_life=1`, remaining=71: `current_left=37`, `37+38=75 >= 71` →
**one-stop “covers”** → **two-stop templates are not added**.

Runtime, 72-lap Netherlands, start MEDIUM, `mc_draws=0`, **no lags** (ghost bake
also has no `lag1_pace` on the template):

**G1.5 slopes (2019/R99):**

| Rank | Label | `delta_vs_stay_out_s` |
|---|---|---|
| 1 | Pit lap 9 for HARD | **−16.612** |
| 2 | Pit lap 6 for HARD | −12.111 |
| 3 | Pit lap 4 for HARD | −9.295 |
| 4 | Pit lap 3 for HARD | −7.933 |
| 5 | Stay out on current tyres | 0.000 (forced into top-k) |

**2025 R15 weekend slopes (FP2 calibration succeeded on this machine):**

| Rank | Label | `delta_vs_stay_out_s` |
|---|---|---|
| 1 | Pit lap 9 for HARD | **−51.341** |
| 2 | Pit lap 6 for HARD | −41.722 |
| 3 | Pit lap 4 for HARD | −35.763 |
| 4 | Pit lap 3 for HARD | −32.899 |
| 5 | Stay out | 0.000 |

Stay-out here means **never pit**: MEDIUM from life 1 to lap 72
(`extrapolation` ceiling `COMPOUND_EVIDENCE_TYRE_LIFE["MEDIUM"]=32`).
Every HARD window in `{2,3,4,6,9}` beats that. The **latest** of those windows
wins. That is why PIT_LAP_9 scores better than “staying out to lap 25”:
**staying out to lap 25 is not a candidate**. Among candidates, later > earlier.

Zandvoort **identity** (`scripts/backtest.py` `run_zandvoort_identity`) is a
**different state**: lap **25**, MEDIUM, `tyre_life=2`, lags 74 s. Offsets then
are **26, 27, 28, 30, 33** → rank-1 **Pit lap 33 for HARD**. Confirmed this run:

```
Pit lap 33 for HARD: delta=-30.694
Pit lap 30 for HARD: delta=-25.354
...
Stay out: 0.000
```

Ghost bake never sits at lap 25. It decides at lap 1, so it gets lap 9, not lap 33.

### 3. Tyre slopes actually used

Defaults in `src/aris/physics/tires.py`:

```19:25:src/aris/physics/tires.py
DEFAULT_COMPOUND_SLOPE: Final[dict[str, float]] = {
    "SOFT": 0.08,
    "MEDIUM": 0.05,
    "HARD": 0.03,
    "INTERMEDIATE": 0.04,
    "WET": 0.02,
}
```

`tire_pace_loss`:

```
deg = slope * max(0, lap_in_stint - 1)
out_lap = OUT_LAP_PENALTY_S if lap_in_stint == 1 else 0.0   # OUT_LAP_PENALTY_S = 1.5
return deg + out_lap + compound_pace_offset(...)
```

Fresh offsets (`COMPOUND_PACE_OFFSET`): HARD `0.0`, MEDIUM `−0.30`, SOFT `−0.40`.
Per-circuit MEDIUM overrides (`CIRCUIT_MEDIUM_OFFSET`): bahrain/austria/qatar/mexico
`−0.35`. **Netherlands is omitted on purpose** (Zandvoort identity).

`simulate()` does not call `tire_pace_loss` in isolation. `_track_for()` overlays
`get_deg_slope()` onto the bicycle track, then chained remainder uses
`predict_physics` → `tire_pace_loss(..., slopes=track.compound_slopes)`.

`get_deg_slope` priority:

1. `calibrate_race_weekend(year, round_number)` if `year` and `round_number` set
   **and** `cal["_valid"]`.
2. Else if `ARIS_USE_CIRCUIT_DEG=1`, OLS from `data/circuit_deg_priors.csv`
   (`n_obs ≥ 30`).
3. Else G1.5.

**Important:** `calibrate_race_weekend` **always** sets `"_valid": True`, even
when every compound is G1.5 fallback:

```603:604:src/aris/physics/fp2_calibration.py
    slopes["_source"] = source
    slopes["_valid"] = True
```

So with `year`+`round_no` on `RaceState` (ghost bake always sets these),
**circuit CSV priors are never reached**. YAML `compound_slopes` on the track
file are also overwritten by `_track_for()`.

FP2 long-run `valid` (per compound) requires roughly: extracted stints with
R² ≥ `_MIN_STINT_R2=0.05` and slope > 0; pooled n_obs ≥ 15; pooled r² > `_FIT_R2=0.1`;
2 stints **or** one quality stint (n ≥ 8, r² > 0.2); slope in `(0, _MAX_SLOPE=0.20]`.
Otherwise: scale HARD/MEDIUM from a valid slick, else circuit prior n_obs ≥ 30,
else G1.5. INTER/WET always G1.5.

This machine, **2025 Netherlands R15**:

```
_source: HARD=fp2, MEDIUM=fp1, SOFT=fp2_scaled, INTER/WET=g15
SOFT=0.1480, MEDIUM=0.0925, HARD=0.0555
```

(After G1.5-ratio cap: MEDIUM ≤ SOFT×0.05/0.08, HARD ≤ MEDIUM×0.03/0.05.)

If rebuild logs show “FP2 insufficient … using G1.5”, `_source[compound]=="g15"`
and the **numeric slopes are still 0.08 / 0.05 / 0.03**. Calibration did not
“fail open to zero”; it failed **into G1.5**. Both G1.5 and the 2025 weekend
fit still rank **Pit lap 9 HARD** at lap 1. Weekend slopes make the delta
**larger** (−51 s vs −17 s), they do not change the winner.

Per-circuit slope override: `ARIS_USE_CIRCUIT_DEG` default **off**. Netherlands
YAML stored slopes are already G1.5 (`compound_slopes_used_global_fallback: true`
after a failed SOFT>MEDIUM>HARD sanity check: fitted HARD 0.0491 > MEDIUM 0.0346).

Warm-up is **extra** on top of `OUT_LAP_PENALTY_S`: HARD +0.8 lap 1 / +0.3 lap 2
(`src/aris/physics/tyre_warmup.py`).

### 4. `simulate()`: long MEDIUM vs early HARD

Remainder (`_simulate_remainder`): for lap `L` in `[lap_number, total_laps]`:

- First lap: residual predictor with real lags (or pure physics if no lags).
- Later laps: `pred += (physics - prev_physics)` with fuel stripped
  (`physics = physics_raw - k_fuel * fuel`) so fuel burn does not masquerade
  as tyre drop.
- Pit lap: in-lap on **old** tyres + `pit_loss` (Netherlands green **18.5 s**),
  then `tyre_life_eff = 1`, compound switches. No warm-up on the in-lap.
- Green laps: `apply_warmup` then tyre aging `tyre_life_eff += deg_multiplier`.

`delta_vs_stay_out_s = pit_path_total - stay_path_total` (negative = pit faster).

**Chained tyre term ≈ `tire_pace_loss`.** G1.5 samples:

| | life 1 | life 9 | life 16 | life 25 | life 32 |
|---|---|---|---|---|---|
| MEDIUM | 1.20 (1.5 out-lap − 0.30 offset) | **0.10** | 0.45 | 0.90 | 1.25 |
| HARD | 1.50 | 0.24 | 0.45 | 0.72 | 0.93 |

`MEDIUM life k = 0.05*(k-1) - 0.30` (k>1). `HARD life k = 0.03*(k-1)` (k>1).

**72-lap, lap 9, MEDIUM life 9, G1.5, pit_loss 18.5, runtime:**

| Action | `total_race_time_s` | `delta_vs_stay_out_s` | Notes |
|---|---|---|---|
| STAY_OUT | 5769.445 | 0 | max MEDIUM life **72**, beyond ceiling **40** |
| PIT_NOW HARD | 5742.035 | **−27.410** | HARD max life 63, beyond 13 |
| PIT_LAP 25 HARD | 5724.275 | **−45.170** | **not a candidate** |

Manual G1.5 tyre-loss sums (matches the −27.4 s pit-now delta once pit_loss +
in-lap + HARD stint are included):

- Stay MEDIUM life 9…72: `sum(tire_pace_loss) = 107.20 s`
- HARD life 1…63: `60.09 s`
- MEDIUM in-lap life 9: `0.10 s`
- `0.10 + 18.5 + 60.09 = 78.69` vs stay `107.20` → **−28.5 s** before warm-up
  (simulate’s extra HARD warm-up 0.8+0.3 brings it to **−27.41 s**)

Stay MEDIUM life 9…24 only (the “hold to 25” window): `sum = 7.60 s`.
That is cheap. The disaster is **laps 25–72 still on MEDIUM**.

**57-lap thought experiment (G1.5, same lap 9 MEDIUM life 9):**

| Action | delta vs stay |
|---|---|
| STAY_OUT | 0 (MEDIUM life 57, beyond 25) |
| PIT_NOW HARD | **−8.66** |
| PIT_LAP 25 HARD | **−19.22** (not a candidate) |
| Rank-1 of actual shortlist | Pit lap **17** HARD **−16.500** |

Human intuition “stay to 25” **is what the physics wants** (−19 s vs −9 s).
The shortlist never offers it, so rank-1 is the farthest offset (17), still
early vs a real 25–30 stop.

Ranking also multiplies pit deltas by `extrapolation_weight`:
`1 / (1 + 0.05 * beyond_laps)` (`EXTRAPOLATION_DISCOUNT_K=0.05`).
Stay-out’s delta is always 0, so a catastrophic stay baseline is **not**
discounted. Long HARD stints *are* discounted, which is why at lap 9 the
**latest in-window** HARD stop outranks PIT_NOW on 72 laps.

### 5. Minimum stint length

`MIN_STINT_LAPS = 15` exists but **only** for two-stop templates:

```870:875:src/aris/recommend.py
def _two_stop_stints_realistic(state: RaceState, pits: list[int]) -> bool:
    ...
    bounds = [int(state.lap_number)] + [int(p) for p in pits] + [total + 1]
    return all(b - a >= MIN_STINT_LAPS for a, b in zip(bounds, bounds[1:]))
```

It does **not** apply to `PIT_NOW` or `PIT_LAP` offsets. Lap 1 → pit 9 is an
**8-lap first stint**, allowed. Lap 1 is not special-cased.

This is **deliberate exclusion**, not an accident: one-stop coverage uses
`MAX_REALISTIC_STINT_LAPS=38` to **drop** two-stops, and the one-stop generator
never consults `MIN_STINT_LAPS`. Comments around `_get_available_compounds` /
`pit_compound` exist to **protect Zandvoort identity at lap 25**, not to
protect a 15-lap first stint at lights-out.

### 6. Compound suppression (verbatim)

```795:844:src/aris/recommend.py
def _get_available_compounds(state: RaceState) -> list[str]:
    """Pit compounds the simulator scores as genuine candidates.
    ...
    """
    alloc = getattr(state, "pirelli_allocation", None)
    base = list(alloc) if alloc else list(PIT_COMPOUNDS)
    order = list(PIT_COMPOUNDS)
    dry = [normalize_compound(c) for c in base]
    dry = [c for c in dry in order if c in dry]
    ...
    if current == "SOFT" and remaining >= 15:
        if track_temp is None or float(track_temp) >= 20.0:
            dry_part = [c for c in dry_part if c != "SOFT"]
    if current == "MEDIUM" and remaining >= 25:
        if "HARD" in dry_part and track_temp is not None and float(track_temp) > 25.0:
            dry_part = [c for c in dry_part if c != "MEDIUM"]
```

(`PIT_COMPOUNDS = ("SOFT", "MEDIUM", "HARD")`.)

This removes a compound from **pit-to** options, not from the car’s current
tyres. At lap 9, remaining 63:

- MEDIUM suppression needs `track_temp_c is not None` **and** `> 25`. Ghost
  bake / the diagnostic state leave `track_temp_c=None` → **MEDIUM stays**.
- SOFT suppression only fires if **current** compound is SOFT.
- Runtime `_get_available_compounds` at lap 1 and lap 9: `['SOFT', 'MEDIUM', 'HARD']`.

**HARD is not the only candidate.** HARD wins because slope + offset + the
stay-out-to-the-flag baseline, not because SOFT/MEDIUM were dropped.

### 7. Live diagnostic (executed)

User snippet omitted required `RaceState` fields (`session_id`, `driver_id`,
`driver_name`). Equivalent call was run.

**Do not use 2026 R15 blindly:** this environment’s 2025 R15 FP2 fit loaded and
**steepened** slopes. For a G1.5-comparable number, also run `year=2019,
round_no=99` or inspect `calibrate_race_weekend(year, round)["_source"]`.

Recommended command (Zandvoort, matches identity circuit):

```python
from aris.state import RaceState
from aris.recommend import recommend, _candidate_actions, _get_available_compounds
from aris.simulate import simulate, ActionKind, StrategyAction
from aris.physics.fp2_calibration import calibrate_race_weekend
from aris.models.features import estimate_fuel_kg

print(calibrate_race_weekend(2025, 15).get("_source"))

state = RaceState(
    session_id=1, driver_id=1, driver_code="NOR", driver_name="Norris",
    year=2025, round_no=15, country="Netherlands",
    compound="MEDIUM", tyre_life=9, lap_number=9, total_laps=72,
    laps_remaining=63, fuel_kg=estimate_fuel_kg(9, total_laps=72),
    lag1_pace=90.5, lag2_pace=90.3, stint_roll3=90.4,
)
print(_get_available_compounds(state))
result = recommend(state, top_k=5, mc_draws=0)
for r in result.recommendations:
    print(f"{r.label}: delta={r.delta_vs_stay_out_s:.2f}s")
print("PIT_25 (not a candidate)",
      simulate(state, StrategyAction(kind=ActionKind.PIT_LAP, pit_lap=25, pit_compound="HARD")).delta_vs_stay_out_s)
```

Lap-9 **shortlist** rank-1 here was **Pit lap 17 for HARD**, not PIT_NOW.
**Lap-9 on the ghost JSON is the lap-1 plan** (`offset 8`). If the UI shows
an in-race call at lap 9, check whether that tick is `aris_action` from the
**frozen plan** (`r2_ghost_tick`) vs a live `recommend()`.

### What would need to change (not done in this session)

1. **Generate realistic one-stop windows from lights-out**, e.g. pit laps at
   `MIN_STINT_LAPS`, 20, 25, 30, and `MAX_REALISTIC_STINT_LAPS - tyre_life`,
   or reuse `derive_pit_windows()` (Strat A/B already ~19 / ~30 on 72 laps).
2. **Score stay-out as “current stint then a later pit”**, not “never box”.
3. Optionally enforce `MIN_STINT_LAPS` on first stop so lap 1 cannot pick lap 9.
4. **Re-plan the ghost** when SC / rain / the live top card changes
   (`recompute_ghost_from_plan` already exists for a *supplied* new schedule).

This is a **model/search-space choice**, not a SOFT/MEDIUM mix-up. The physics
already likes lap 25 HARD more than lap 9 HARD when asked.

---

## SECTION 2 — WET CALIBRATION

### 8. Wet / rain detection pipeline

**FastF1 field:** `weather_data['Rainfall']` — **boolean**, ~1 sample/minute.
**Not** track status `4` (SC). Documented at top of `src/aris/physics/wet.py`.

Three different rain bits exist on `RaceState` (`src/aris/state.py`):

```149:154:src/aris/state.py
    rainfall_mm_per_lap: float | None = None
    weather_rainfall: bool | None = None
    # Per-lap FastF1 weather_data['Rainfall'] (boolean). Session-level
    # session_weather.rainfall (any-sample) stays on weather_rainfall for
    # walk-forward exclusion; it is not a live rain signal.
    rainfall: bool = False
```

`build_race_state()`:

- `weather_rainfall` = session weather dict `rainfall` (any-sample / session bit).
- `rainfall` = `_lap_rainfall()`: `laps.rainfall` if present, else nearest
  `weather_samples` row.
- `rainfall_mm_per_lap` is **not** filled from FastF1 (`None`).

`backend/sessions.py`:

- Session summary: `rainfall=bool(rain.any())` — **session-level any-rain**.
- Per-lap live/replay: `rainfall_at_session_lap()` → `nearest_rainfall(weather, LapStartTime)`.
- Field snapshot uses the same per-lap helper.

**Classification:**

| Layer | Wet vs dry | Granularity |
|---|---|---|
| Walk-forward dry 87 | `weather.get("rainfall")` session bit | Session: any rain → wet inflections excluded unless `--include-wet` |
| Live INTER card | `state.rainfall` (per-lap boolean) and/or `rainfall_mm_per_lap > 0.5` | Lap |
| Already on INTER stay-lock | `state.rainfall` **or** `state.weather_rainfall` | Lap with session fallback |

`BOOLEAN_RAIN_MM = 1.2` when only the boolean is set (`effective_rainfall_mm`).

INTER vs dry pit: `should_recommend_inter` **and** `_inter_rain_confirmed`.
Confirmed if mm > 0.5, or `track_state in {WET, CROSSOVER}`, or
(`rainfall` and `weather_rainfall` and track not `DAMP`/`DRYING`).

### 9. INTER/WET heuristic (labelled uncalibrated)

Module docstring: *“Wet / intermediate heuristic — uncalibrated, not a fitted
deg model.”* Cards set `wet_heuristic=True` and evidence
`"wet heuristic (uncalibrated — reduced confidence)"`.

**`should_recommend_inter` fires when all of:**

- Compound is a slick (`SOFT`/`MEDIUM`/`HARD`), not already INTER/WET.
- `remaining >= MIN_LAPS_FOR_INTER` (8); remaining repaired with `max(remaining, total-lap)`.
- Not red (`track_status` contains `'5'`).
- Rain: `state.rainfall` **or** `rainfall_mm_per_lap > INTER_RAIN_THRESHOLD_MM` (0.5).
- VSC `'6'` is explicitly **not** sufficient. SC `'4'` is **not** rain.

**INTER delta** (`wet_candidate_delta`):

```
INTER_VS_SLICK_ADV_LOW = -1.5   # conservative default INTER_VS_SLICK_ADV
WET_VS_SLICK_ADV = -4.0
delta = per_lap * laps_remaining + pit_loss_s
```

Yes: **−1.5 s/lap × remaining + pit_loss** for INTER (hardcoded). WET uses −4.0
s/lap. The mm argument is **deleted**; boolean rain still gets the empirical
constant. `rainfall_mm_per_lap` is unused in the score.

On slicks in rain, `recommend()` **appends** these PIT_NOW INTER/WET cards
**on top of** the dry shortlist, then **forces the best wet card to rank 1**:

```1439:1443:src/aris/recommend.py
    if wet_on:
        wet_recs = [r for r in scored if r.wet_heuristic]
        if wet_recs:
            best_wet = min(wet_recs, key=lambda r: r.delta_vs_stay_out_s)
            scored = [best_wet] + [r for r in scored if r is not best_wet]
```

Example: remaining=63, pit_loss=18.5 → INTER delta `−1.5*63 + 18.5 = −76.0 s`,
which outranks typical dry pits.

**`should_stay_on_wet`:** already INTER/WET, (`rainfall` or `weather_rainfall`),
≥5 laps left, not red. Then dry shortlist is **replaced** by
`_generate_wet_stay_candidates`: stay, hold 3/5/8, optional INTER→WET if
`effective_rainfall_mm >= WET_RAIN_THRESHOLD_MM` (2.0) — boolean proxy 1.2
**does not** qualify — and DRY_WINDOW slick only if `remaining <= 10` **and**
`not rainfall`.

**Drying-to-slick:** partial, gated, **not a forecast**. Comment in code:

```1031:1032:src/aris/recommend.py
    # INTER→WET only for standing water. Boolean rain (1.2 mm proxy) is not that.
    # WET→INTER (drying) is out of scope until a forecast exists.
```

`docs/model-status.md`: drying-track heuristic **not shipped** (threshold was
≥3 2025 misses of INTER + `rainfall=True` + team slick; only Belgium RUS L12,
and that miss was ARIS-hindsight).

**DRY/DAMP/CROSSOVER/WET/DRYING** (`src/aris/risk/wet_classifier.py`) —
rule-based, `track_temp_c` **accepted and unused**:

| State | Rules (`classify_track_state_rules`) |
|---|---|
| DRY | `not rain_flag` and `rain_laps_last_5==0` and not `inter_on_track` (conf 0.95); default fallback 0.80 |
| DRYING | `inter_on_track` and `n_rain==0` (0.80) |
| DAMP | `n_rain >= 4` without INTER pace advantage > 1.5; or `1..3` rain laps without CROSSOVER |
| WET | `n_rain >= 4` and INTER on track and `inter_pace_advantage_s > 1.5` |
| CROSSOVER | `1 <= n_rain <= 3` and INTER on track and `abs(advantage) < 1.0` |

Reads: per-lap `rainfall`, count of rain laps in `[lap-4, lap]`, whether any car
is on INTER/WET this lap, slick−INTER median pace. Module comment: 2024–2025
FastF1 has only **five** races with Rainfall=True on ≥5 laps, none with ≥50 wet
laps — **below ML threshold**.

### 10. Wet match-rate — what it tests

`src/aris/eval/backtest.py` `score_race(..., include_wet=False)`:

- Walks 2024 held-out GPs + 2025 `BACKTEST_GPS_2025` (24 names).
- Reference driver = classified **P5** (`REFERENCE_FINISH_POS = 5`).
- Inflections = pit-in laps, SC/VSC **starts**, compound changes off-pit
  (`extract_inflections`).
- `classify_decision`: red `'5'` → `divergence_insufficient_info`.
- Default (`include_wet=False`): session `rainfall` **or** wet compound
  inflection → excluded. That is the **dry 87**.
- `--include-wet`: score INTER/WET inflections (even if session rain);
  still exclude **dry-compound** events on session-rain races (Spain-style)
  so they do not pollute the 87.

**Match** = ARIS top strategy card matches the team action:
pit within `PIT_LAP_TOLERANCE=2` laps and same dry compound, or stay vs stay.
Else hindsight sim (`HINDSIGHT_MARGIN_S=2.0`) labels ARIS-better vs team-better.

Documented combined wet slice (`docs/model-status.md`, T3-final / later):

- Combined `--include-wet`: **38/110 = 0.345** (2024 19/49, 2025 19/61).
- Stay-out baseline on 2025 wet: **19/61** — **tied**.
- Dry headline remains **30/87 = 0.345**.
- Later note: combined **39/110 = 0.355** after a remaining-laps guard;
  2025 wet **20/61** vs stay-out **19/61**.

**38/110 is not “predicted rain correctly”.** It is **rank-1 strategy vs team
at pit/SC/compound inflections** on the wet-included 110, after dropping
insufficient-info (red, and dry events on session-rain races).

Why wet barely beats stay-out (from code + `docs/model-status.md`, not
re-walked here):

1. Heuristic INTER delta is a constant, not a fitted wet deg model.
2. Sparse boolean Rainfall (~1/min) vs real track water.
3. `should_stay_on_wet` session-bit fallback **locks INTER after per-lap rain
   is False** (Australia ALB L33, Britain VER L41).
4. Extra INTER→INTER stops (Australia ALB L2–4, Britain VER L11).
5. DRY_WINDOW false positive under SC (Australia ALB L47).
6. On slicks in rain, INTER is **forced rank-1** even if timing is wrong.
7. Ghost / dry `simulate()` still uses G1.5 slick slopes if the wet lock
   does not fire (`should_recommend_inter` refuses once already on INTER).

### 11. What a proper wet model would require

Stated gaps in code/docs:

- No rainfall **intensity** (`rainfall_mm_per_lap` stays `None` in `build_race_state`).
- No drying **forecast** (WET→INTER “out of scope until a forecast exists”).
- Classifier is rules, not ML (insufficient wet laps).
- INTER vs slick −1.5 s/lap is a **conservative bound**, and 2024 Britain
  even showed INTER **slower** than slicks in light rain (+10.4 s mean) —
  comment in `wet.py`. The heuristic only fires when slicks are already
  treated as the wrong tyre.
- Failure mode called out: **keep wet / INTER when the track is drying**,
  or **rank a dry HARD pit** if stay-lock does not fire; also **pit INTER
  again** while already on INTER if rain-lock is off.

Minimal fix (docs + code comments): per-lap rain without session-bit lock
after rain stops; do not ship drying until ≥3 clear INTER+rain+team-slick
misses (currently 1); stop forcing INTER rank-1 on a single DAMP tick
(`_inter_rain_confirmed` already tries this).

---

## SECTION 3 — GHOST DECISION LOGIC

### 12. Post-race / R2 strategy: computed, then frozen

**Not hardcoded pit laps.** R2 `ghost_{CODE}.json` is:

1. `start_compound` ← real lap-1 compound.
2. `recommend(state, top_k=3, mc_draws=0)` at lap 1 (lap 2 if reset).
3. `schedule_from_recommendation` → `GhostPlan.pit_laps` / `pit_compounds`.
4. `score_parallel_ghost` follows that plan **rigidly**.

`scripts/prebuild_race_r2.py` `build_ghost` is a thin wrapper around
`aris.ghost_pack.compute_ghost`.

If `recommend()` throws, plan falls back to **STAY_OUT** (no pits), not a
hindsight optimum.

**SC on lap 20 with a planned lap-33 stop:** the ghost **does not adapt**.
`score_parallel_ghost` only checks `lap_number in pit_map`. SC changes
`track_status` on `advance_state` (so **this-lap** pit_loss would be discounted
**if** the ghost pitted that lap). A future planned stop still pays **green**
YAML pit loss (`get_pit_loss` only discounts `lap == state.lap_number` unless
`pit_status_by_lap` is passed; ghost never passes it).

Live has `recompute_ghost_from_plan()` (`backend/live.py`) to splice a **new
supplied** schedule from `current_lap` — it does **not** auto-call `recommend()`
on SC.

`generate_strat_plans()` (Strat A/B/C fractional windows) is a **different**
artifact (backtest `session.active_strat`). It is not what R2 ghost JSON stores.

### 13. Lap-by-lap trace (`score_parallel_ghost` + `advance_ghost_lap`)

For each packed lap `L` (example **L = 15**):

**State constructed for the real car** (`advance_state`):

| Field | Source |
|---|---|
| `lap_number` | row |
| `compound` / `tyre_life` | **real** pack row (not ghost) |
| `fuel_kg` | row or `estimate_fuel_kg(L, total_laps)` |
| `laps_remaining` | `total_laps - L` |
| `position`, `gap_to_leader_s`, `gap_ahead_s` | row / template |
| `track_status` | row or template `"1"` |
| `lag1_pace`, `lag2_pace`, `stint_roll3` | row if present; **ghost_pack lap_rows omit these** |
| `rainfall` | **not set on lap_rows** → remains template default `False` |

Ghost tyres are **not** in this state. `advance_ghost_lap` copies the state and
overwrites `compound`/`tyre_life` with `ghost.ghost_tyre` / `ghost.ghost_tyre_age`.

**`simulate(STAY_OUT, ghost_tyres)`:** one remainder from L to the flag on ghost
compound/age; `lap_times_out[0]` is **this lap’s** model time
(`ghost_lap_s`). Formula: first remaining lap = `predict_lap_time` (physics +
optional residual if lags exist); if this is a ghost pit lap, add
`get_pit_loss` after the fact in `advance_ghost_lap` (not inside that STAY_OUT
sim). Warm-up applies when `ghost_tyre_age` is 1–2.

**`simulate(STAY_OUT, real_tyres)`:** same with real compound/age → `real_lap_s`.

**Delta:** `lap_delta = real_lap_s - ghost_lap_s` (positive → ghost faster).
`ghost_cumulative_delta += lap_delta`.

**If L is a ghost pit lap:** `ghost_lap_s += pit_loss`; then
`ghost_tyre = pit_compound`, `ghost_tyre_age = 1`. Else `ghost_tyre_age += 1`.
If the **real** car pitted this lap, `real_lap_s +=` the same pit_loss.

**Position at L:** prefer `field_gap_by_lap` from `field_gap_snapshot_by_lap`
(classified cars’ `gap_to_leader_s`, DNFs dropped):

```
ghost_gap = max(0, real_gap_to_leader - ghost_cumulative_delta)
ghost_position = 1 + count(real gaps < ghost_gap)
```

If `cumulative_delta==0`, ghost **sits on the real driver’s classified
position**. Fallback: `field_cum_by_lap` + `_rank_ghost_in_field` (legacy;
fragile on DNF).

**Tick stored:** `ghost_to_dict` then `r2_ghost_tick`:

```
lap, position, gap_to_leader_s, compound, tyre_life, stint,
cumulative_delta_s, aris_action, aris_confidence
```

`r2_ghost_tick` sets `aris_action` to **`"PIT"` iff `lap in plan.pit_laps` else
`"STAY_OUT"`** — not the full recommend label.

### 14. What the ghost knows

| Information | Available? |
|---|---|
| Real driver’s **actual** lap time | Packed as `lap_time_s` and added into `real_cum_actual`; **lap delta uses model STAY_OUT vs model STAY_OUT**, not actual vs model |
| Safety car / red / VSC **this lap** | `track_status` on the row (pit-loss multiplier only if **this** lap is a pit) |
| Weather / rain lap-by-lap | **No** in ghost_pack `lap_rows`. Rainfall stays false unless template had it |
| Rival pits / strategies | `rivals` optional on rows; **ghost_pack does not fill it**. Position uses field gaps, not rival strategy |
| Field | Per-lap classified `gap_to_leader_s` (preferred) or cumulative lap times |

The ghost is a **physics delta vs the real tyre state**, anchored to the real
timing tower. It is not a second car with a full world model.

### 15. `advance_ghost_lap` vs `score_parallel_ghost`

**Different.**

- `advance_ghost_lap`: one lap, optional resolve (divergence ghosts).
- `score_parallel_ghost`: full race from lap 1, `resolve=False`, applies
  `plan.pit_laps`, field ranking, returns `{lap: ghost_to_dict}`.

**R2 prebuild and on-demand `compute_ghost`:** `score_parallel_ghost`.
**Live replay bake:** `precompute_ghost_for_session` → same.
**`maybe_create_ghost`:** divergence-gated, live WS path; **not** R2 JSON.
`backend/live.py` comment: `_rank_ghost_in_field` still used if gap snapshot
missing.

### 16. How `aris_action` is set

Two layers:

1. `GhostState.aris_action` = lights-out **plan label** (e.g. `"Pit lap 9 for HARD"`),
   set once in `create_ghost_from_plan`. `ghost_to_dict` keeps that string every lap.
2. R2 JSON ticks (`r2_ghost_tick`): **`PIT` / `STAY_OUT` from `plan.pit_laps` only.**

It is **not** `recommend()` at that lap. Prebuild runs `recommend()` at **lap 1
(and maybe 2)** only.

To mid-race re-plan: call `recommend()` at the SC/rain lap, convert with
`schedule_from_recommendation` (keep stint already completed), then
`recompute_ghost_from_plan` or re-run `score_parallel_ghost` from lap 1 with
the new `GhostPlan`. Nothing in the bake path does this today.

---

## SECTION 4 — DIAGNOSIS SUMMARY

Ranked by impact on the observed “pit lap 9 HARD, then a long degraded HARD stint”.

1. **Lights-out candidate set is only `{now, +1, +2, +3, +5, +8}`.** Rank-1 at
   lap 1 on a 72-lap MEDIUM start is therefore **Pit lap 9 HARD** (G1.5 Δ=−16.6 s;
   2025 FP2 Δ=−51.3 s). **Fix:** generate one-stop candidates at realistic first-stop
   laps (reuse `derive_pit_windows` / `MIN_STINT_LAPS`…`MAX_REALISTIC_STINT_LAPS`).

2. **Stay-out baseline is “never pit”.** `simulate(STAY_OUT)` runs current
   compound to the flag (MEDIUM life 72, beyond=40). Any early HARD stop looks
   brilliant vs that, even though **PIT_LAP 25 HARD is ~18 s better than PIT_NOW
   at lap 9 (G1.5, 72 laps)**. **Fix:** compare pits against a default later
   stop, not against a zero-stop race.

3. **Ghost freezes the lap-1 card** and never re-runs `recommend()`. An SC at
   lap 20 does not move a planned stop. **Fix:** on SC/VSC/rain/red, re-call
   `recommend()` and `recompute_ghost_from_plan`.

4. **`MIN_STINT_LAPS=15` does not apply to one-stop `PIT_LAP`.** An 8-lap first
   stint is legal. **Fix:** apply the same 15-lap floor to the first stop
   (identity test is lap 25, so it would be unchanged).

5. **Weekend FP2 slopes, when they succeed, make the early HARD call louder
   (MEDIUM 0.093 vs 0.05) but are not required for it.** Failed FP2 still uses
   G1.5 0.08/0.05/0.03 because `_valid` is always true. **Fix:** after adding
   late-stop candidates, re-fit; do not treat G1.5 fallback as the early-pit root.

6. **Extrapolation discounts long HARD stints but not the stay-out zero.** That
   shifts rank-1 to the **latest in-window** stop (lap 9 from lap 1; lap 17 from
   lap 9), still far from 25–30. **Fix:** either discount the stay baseline’s
   over-age or stop using never-pit as baseline.

7. **Wet INTER is an uncalibrated −1.5 s/lap + pit_loss card, forced to rank 1
   when the rain heuristic fires.** Combined wet match **38/110**, 2025 wet **tied
   with stay-out**. **Fix:** drop session-bit INTER lock after per-lap rain is
   false; do not force rank-1 on a single DAMP sample; drying transition still
   needs a forecast (explicitly not shipped).

8. **Compound suppression is not the lap-9 HARD-only story.** With
   `track_temp_c=None`, lap 9 still lists SOFT/MEDIUM/HARD. **Fix:** none
   required for this bug; keep suppression out of the early-pit patch.

9. **Strat A/B/C (`derive_pit_windows`) already aims ~lap 19 / ~lap 30 on 72
   laps and is unused by ghost bake.** **Fix:** optionally seed `GhostPlan`
   from Strat B instead of lap-1 `recommend()` until the candidate set is fixed.

---

## TODOs / known issues flagged in source

| Location | Text / meaning |
|---|---|
| `src/aris/physics/wet.py` L1–7 | Uncalibrated heuristic; not a fitted deg model |
| `src/aris/recommend.py` `WET_HEURISTIC_EVIDENCE` | `"wet heuristic (uncalibrated — reduced confidence)"` |
| `src/aris/recommend.py` L1032 | `WET→INTER (drying) is out of scope until a forecast exists` |
| `src/aris/risk/wet_classifier.py` L1–6 | Five-class labels are heuristics; below ML data threshold |
| `docs/model-status.md` | Drying-track heuristic **not shipped**; 2025 wet tied stay-out |
| `src/aris/simulate.py` L28–37 | `STINT_URGENCY_PENALTY = 0.0` (disabled T7) |
| `src/aris/physics/tires.py` | Netherlands omitted from `CIRCUIT_MEDIUM_OFFSET` to protect identity |
| `src/aris/state.py` L81 | SC pit-loss 0.35/0.55 napkin **UNSOURCED** unless measured flag on |
| `data/tracks/netherlands.yaml` | Track OLS failed sanity; YAML slopes are G1.5 fallback |

---

## UNKNOWN — needs runtime (not blocking the root cause)

1. **2026 Zandvoort NOR specifically:** this audit used **2025 R15** (same
   circuit file, 72 laps). 2026 FP2 `_source` / whether NOR actually started
   MEDIUM must be checked against that race pack / FastF1.
2. **Every rebuild log “FP2 failed”:** on this machine 2025 R15 FP2 **succeeded**
   (HARD fp2, MEDIUM fp1, SOFT scaled). Rebuild hosts may lack FastF1 cache.
   Root cause holds for **both** G1.5 and weekend slopes.
3. **Wet 38/110 vs 39/110:** taken from `docs/model-status.md`, not re-run
   `scripts/backtest.py --include-wet` in this session.
4. **Whether the product UI “pit lap 9” is the ghost plan or live `recommend()`
   at lap 9.** Live recommend at lap 9 ranks **Pit lap 17 HARD**, not PIT_NOW.
   Ghost JSON `aris_action` at lap 9 is `PIT` iff the **lap-1 plan** listed 9.

## Recommended diagnostic race

**2025 Formula 1 Dutch Grand Prix (Netherlands, round 15), 72 laps.**

- Ghost / “why lap 9”: `recommend()` at **lap 1**, MEDIUM, `tyre_life=1`,
  `mc_draws=0` — expect **Pit lap 9 for HARD**.
- Live shortlist: same driver at **lap 9**, MEDIUM life 9 — expect **Pit lap 17
  for HARD**, and a hidden `PIT_LAP 25 HARD` with a **better** delta.
- Identity (must not break if you later patch candidates): **lap 25**, MEDIUM
  life 2, lags 74 s, VER — **Pit lap 33 HARD**.
)
</tool_call>

The Write tool was used. Use Read to verify the file exists.