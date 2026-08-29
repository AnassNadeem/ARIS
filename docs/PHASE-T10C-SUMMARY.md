# T10-C Summary — Wet Classifier

Date: 2026-08-26  Commit: e404a59 (working tree; T10-C not committed)  Status: **PARTIAL**

C0 (FastF1 2024 Belgium Race + 2024–2025 SC-risk weather table): weather columns are `Time, AirTemp, Humidity, Pressure, Rainfall, TrackTemp, WindDirection, WindSpeed`. `Rainfall` is boolean. Belgium 2024 was fully dry (137/137 samples False; compounds HARD/MEDIUM/SOFT only).

## Approach used

**Rule-based** (`classify_track_state_rules`), not LogisticRegression.

Five 2024–2025 races have Rainfall=True on ≥5 laps, and none of those races has ≥50 wet laps. That is below the ML threshold (≥8 wet races × ≥50 wet laps per class). The five-class labels (DRY / DAMP / CROSSOVER / WET / DRYING) are a **heuristic**, not observed ground truth.

## Wet race data available

| Year | GP | Rain laps (of race laps) |
|---|---|---:|
| 2024 | Britain | 22 / 52 |
| 2024 | Canada | 17 / 70 |
| 2024 | Sao Paulo | 48 / 69 |
| 2025 | Australia | 16 / 57 |
| 2025 | Britain | 5 / 52 |

2025 Miami had 3 rain laps (below the ≥5 cutoff). 2024 Belgium: 0.

## Performance (if ML model)

Not trained. Rule function only.

## Example classifications

From FastF1 laps + weather, then the rule scorer:

| Race | Lap | rain_flag | rain_laps_last_5 | Notes | State | Conf. |
|---|---:|:---:|---:|---|---|---:|
| 2024 Bahrain | 10 | False | 0 | field SOFT | DRY | 0.95 |
| 2024 Britain | 20 | True | 2 | INTER on track, slicks still ~23 s faster | DAMP | 0.65 |
| 2024 Britain | 35 | True | 5 | field INTERMEDIATE, no slicks | WET | 0.85 |
| 2024 Sao Paulo | 15 | True | 5 | field INTERMEDIATE | WET | 0.85 |
| 2025 Australia | 12 | False | 0 | INTER still on track, rain stopped | DRYING | 0.80 |
| 2025 Australia | 40 | False | 0 | field HARD | DRY | 0.95 |

`compound_field_mode` and INTER vs slick pace use `fetch_all_laps` (already loaded for SC risk). Sector variance was skipped. `fetch_all_laps` has no rainfall column; `rain_laps_last_5` uses the focus driver's `laps.rainfall`.

`RaceState.track_state` / `track_state_confidence` are filled in `build_race_state()`. `_get_available_compounds()`: DRY → slicks only; WET → INTERMEDIATE+WET; DAMP/CROSSOVER/DRYING → slicks+INTER, then the existing SOFT/MEDIUM suppression.

## Gate check

- Combined wet backtest (`scripts/backtest.py --years 2024 2025 --include-wet`, out-dir `results/backtest/t10c-wet`): **37/110 = 0.336** (must hold ≥ 0.340) — **FAIL by one match**
  - 2024: 19/49 (0.388)
  - 2025: 18/61 (0.295), below stay-out 19/61
  - T9 was 41/110 (0.373). T9.2 physics (fuel strip, per-circuit MEDIUM offsets) was never re-walked on the wet set, so this is not a clean T10-C delta.
  - INTER as rank-1 on a dry-compound state happened **once**: 2024 Britain SAI L26 `Pit now for INTERMEDIATE`, which **matched** the team. Not an INTER-on-dry false positive.
- Tests: **5/5** passing (`tests/test_wet_classifier.py`)
- Zandvoort identity: **PASS** (DRY default; INTER not in the slick shortlist)
