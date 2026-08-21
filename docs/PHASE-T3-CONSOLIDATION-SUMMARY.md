# Phase T3 consolidation summary — flag walks + rainfall signal

Executed 2026-08-21 in the **main** tree
`C:\Users\anass\OneDrive\Desktop\ARIS`. Scope: targeted walks for
T3-B / T3-C, rainfall-signal fix for T3-E, wet re-eval, Zandvoort
identity after each section. Architecture lock held.

Walk artefacts (gitignored, local):

```
results/backtest/t3c-undercut-off
results/backtest/t3c-undercut-on
results/backtest/t3c-overcut-off
results/backtest/t3c-overcut-on
results/backtest/t3c-wet
```

---

## Verdict (read this first)

**Superseded for current numbers by T3-final in
[`docs/model-status.md`](./model-status.md) (2026-08-22).** This page
is the 2026-08-21 rainfall-signal / flag-walk record. T3-final wet
combined is **0.345 (38/110)**; flags still off; still not ready for T4.

**NEEDS MORE T3 WORK. Not ready for T4.**

The rainfall boolean is now the live rain signal (FastF1
`weather_data['Rainfall']`). A dry Safety Car no longer produces an
INTER card. That is a real correctness fix. It did **not** clear the
wet match-rate gate. Field undercut and overcut were walked on the
events they were designed for and did **not** move match-rate. Both
stay behind flags. Dry 87 is unchanged. Zandvoort identity holds.

| Check | Aimed | Actual | Result |
|---|---|---|---|
| Dry 87 | ≥ **0.345 (30/87)** | **0.345 (30/87)** | **PASS** (unchanged) |
| Combined `--include-wet` | ≥ **0.340** on 110+ | **0.318 (35/110)** | **MISS** (0.327 → 0.318) |
| Promote T3-B or T3-C | targeted +≥2 pp and 87 ≥ 0.345 | **0 pp** on both subsets | **MISS** — flags stay off |
| Dry SC must not recommend INTER | no INTER on `track_status=4`, `rainfall=False` | PASS | **PASS** |
| Wet `rainfall=True` recommends INTER | INTER in shortlist | PASS | **PASS** |
| Zandvoort identity | Pit 33 HARD / Pit 30 HARD / Stay out | same | **PASS** |

---

## Summary table

| Metric | Before T3-consol | After T3-consol |
|---|---|---|
| Dry match-rate (87 events) | 0.345 (30/87) | **0.345 (30/87)** |
| Combined match-rate (110+ evts) | 0.327 (36/110) | **0.318 (35/110)** |
| Field undercut | FLAGGED | **FLAGGED** |
| Overcut | FLAGGED | **FLAGGED** |
| Wet rainfall signal | WRONG if treated as SC=4; live INTER also fired on session `any()` | **FIXED** (`weather_data['Rainfall']`) |
| Zandvoort identity | PASS | **PASS** |

---

## Section 1 — targeted undercut / overcut walks

CLI: `--undercut-events-only` and `--overcut-events-only` on
`scripts/backtest.py`.

Undercut subset: `gap_ahead < 22s` and trigger kind PIT (team pit
inflection) or TACTICAL (`gap_ahead < 1s`, same threshold as
`check_triggers`). Overcut subset: a rival `pit_in` in the 3 laps
before the inflection and `gap_ahead > 2s`.

Targeted walks skip the sector clock and reconstruct `FieldState` at
each inflection so `gap_ahead` is the gap at that lap, not end-of-race.

| Slice | Flags off | Flag on | Delta | Decision |
|---|---|---|---|---|
| Undercut-relevant | **0.375 (21/56)** · 2024 10/28 · 2025 11/28 | **0.375 (21/56)** with `ARIS_FIELD_UNDERCUT=1` | **0 pp** | **KEEP BEHIND FLAG** |
| Overcut-relevant | **0.381 (16/42)** · 2024 9/20 · 2025 7/22 | **0.381 (16/42)** with `ARIS_FIELD_OVERCUT=1` | **0 pp** | **KEEP BEHIND FLAG** |

Promotion rule was ≥ +2 pp on the subset **and** combined 87 ≥ 0.345
**and** Zandvoort unchanged. Neither subset moved. The flags are a
confirmed **non-improvement** on the events they apply to, not a
confirmed worsening. Default remains T2-D undercut / no `OVERCUT_*`
cards. Env checks stay.

87-event flag-on walks were not required: promotion did not trigger.
Dry 87 was not re-walked after the rainfall fix; see Section 3
(session-dry races have zero `laps.rainfall=True` rows).

---

## Section 2 — rainfall signal

FastF1 `track_status` `4` is Safety Car. Rain is
`session.weather_data['Rainfall']` (boolean, ~60 s samples).

`RaceState.rainfall: bool = False` is the live signal. Populated from
`laps.rainfall` (nearest weather sample to elapsed lap time) or FastF1
direct (`weather=True` on the FASTF1_DIRECT path). Session-level
`session_weather.rainfall` (any sample True) stays on
`weather_rainfall` for walk-forward **exclusion** only and no longer
fires INTER in `recommend()`.

Schema: `db/migrations/004_lap_rainfall.sql` (`laps.rainfall`,
`weather_samples`). Backfill from FastF1 cache pickles (schedule APIs
were down): **46/48** 2024–2025 races; Las Vegas date-vs-folder
mismatch skipped (dry races).

`should_recommend_inter`: rainfall True, dry slick, ≥8 laps left, not
already INTER/WET, not red (`5`). Does **not** use SC `4`. Field car
already on INTER is no longer a rain signal.

### Empirical INTER vs slick

User-specified probe: 2024 Brazil VER. Cache loaded without the
schedule API.

- Brazil 2024: **no slick laps** (INTERMEDIATE / WET / UNKNOWN only).
  Cannot compute a slick-to-inter transition.
- 2024 Britain, `Rainfall=True`: INTER mean **101.29 s** (n=50) vs
  slick **90.92 s** (n=19) → INTER **+10.4 s** (slicks still faster in
  light rain). Not used as the live advantage, because the heuristic
  only fires when slicks are already treated as the wrong tyre.

Shipped constants (conservative T3-E band, less-negative default):

```
INTER_VS_SLICK_ADV_LOW  = -1.5   # default
INTER_VS_SLICK_ADV_HIGH = -3.0
```

Gates:

```
PASS — dry SC does not recommend INTER
PASS — wet race recommends INTER
```

---

## Section 3 — wet re-eval

```
python scripts/backtest.py --years 2024 2025 --include-wet
```

| Slice | T3-E | After rainfall fix |
|---|---|---|
| 2024 | 0.367 (18/49) | **0.367 (18/49)** |
| 2025 | 0.295 (18/61) | **0.279 (17/61)** |
| Combined | 0.327 (36/110) | **0.318 (35/110)** |

n=110 still meets the denominator aim. Combined **misses 0.340**.
2025 is below always-stay-out on that slice (0.311). Do **not** claim
the wet gate passed. Dry 87 stays the headline. Wet logic stays shipped
and labelled `WET_HEURISTIC`.

Dry 87 unchanged by construction: **0** laps have `laps.rainfall=True`
on sessions where `session_weather.rainfall=False`, so INTER cannot
enter the shortlist on the 87.

### Systematic wet misses

Once the car is already on INTERMEDIATE, `should_recommend_inter`
returns False (do not double-recommend). Dry `simulate()` then ranks a
HARD pit. That is the repeating error:

| Race | Driver | What the team did | ARIS rank-1 |
|---|---|---|---|
| 2024 Sao Paulo | LEC | pit to INTER L24; stay out on INTER under SC | Pit lap 29 HARD / Pit now HARD |
| 2025 Australia | ALB | INTER pits L2–L4; stay/SC later | Pit lap 10–12 HARD; stay-out vs INTER pit L44 |
| 2025 Britain | VER | INTER under SC / pit L11 | Pit lap 10/19 HARD; Pit now HARD |
| 2025 Belgium | RUS | SC on INTER L1 | Pit now HARD |

Closing the wet gate needs a **stay-on-INTER / don't-switch-to-slick**
path when `state.rainfall` is True and the car is already on a wet
compound — not only an INTER pit from slicks.

---

## Section 4 — Zandvoort identity

Default path, all flags off, `_zandvoort_state()` (L25 MEDIUM
tyre_life 2, `mc_draws=0`):

```
pit_lap 33 HARD -14.32
pit_lap 30 HARD -11.92
stay_out - - 0.0
```

Unchanged after Sections 1–3. (The spec's lap-1 constructor would not
produce pit 33/30; the locked identity is L25.)

Lights-out from the wet walk (same 48 races): all **−1.73**, clean
**−1.49** (n=35), disrupted **−2.38** (n=13).

---

## Section 5 — T4 readiness

**NEEDS MORE T3 WORK.**

Gates that failed:

1. Combined `--include-wet` **0.318 < 0.340**. Additional work: when
   already on INTER/WET in rain, do not rank a dry HARD pit as if the
   race were green slicks.
2. Neither field undercut nor overcut promoted (0 pp on targeted
   subsets). Additional work: only promote if a later walk shows ≥ +2 pp
   on the subset **without** dropping the 87 below 0.345. The
   implementations can stay flagged; they are not a live ranking win.

Do not start T4 until dry ≥ 0.345, combined ≥ 0.340, at least one of
T3-B/C is default, and Zandvoort still PASSes. Today that table does
not show READY.

---

## What this does not claim

- That field undercut or overcut is a shipped ranking improvement.
- That the rainfall-signal fix is a wet-strategy win (combined went
  **down** 36/110 → 35/110).
- That −1.5 s/lap is a fitted INTER model. Brazil had no slicks;
  Britain light-rain INTER was slower than slicks.
- That T4 is open.
