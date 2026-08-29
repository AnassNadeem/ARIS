# T10-A Summary — SC/VSC Risk Model

Date: 2026-08-26  Commit: e404a59 (working tree; T10-A not committed)  Status: **COMPLETE**

A0 column check (FastF1 2024 Bahrain Race, plus `db.fetch_all_laps`):

- **laps:** `Time, Driver, DriverNumber, LapTime, LapNumber, Stint, PitOutTime, PitInTime, Sector1/2/3Time, … Compound, TyreLife, TrackStatus, Position, Deleted, …` — **20 drivers** (cross-car).
- **race_control_messages:** `Time, Category, Message, Status, Flag, Scope, Sector, RacingNumber, Lap`.
- **weather_data:** `Time, AirTemp, Humidity, Pressure, Rainfall, TrackTemp, WindDirection, WindSpeed`.
- **DB `fetch_all_laps`:** all 20 cars; `driver_id, code, lap_number, lap_time_s, compound, tyre_life, stint, sectors, track_status, pit_in, pit_out`. No `StatusNotClassified` on laps.

`field_density` is available from FastF1 `Time` (dataset) and from cumulative `lap_time_s` (runtime DB).

## Features used

Required:

- `circuit_id` (one-hot, canonical keys)
- `lap_number`, `race_frac`
- `rain_flag` (weather `Rainfall`)
- `track_temp_c` (weather `TrackTemp`)

Optional (all available, all used):

- `retirements_last_5_laps` — drivers whose last completed lap is in `[current-4, current)`
- `yellow_flags_last_3_laps` — RCM `Flag` containing YELLOW, else TrackStatus `2`
- `field_density` — fraction of cars with another car within 2.0 s
- `historical_sc_rate` — 2022–2024 fraction of races at the circuit with ≥1 SC/VSC **deployment** (`Message` contains SAFETY CAR / VIRTUAL SAFETY CAR **and** DEPLOYED; endings and infringement notes excluded)

SC/VSC labels from RCM deployment laps; `sc_in_next_5` / `sc_in_next_10` are forward windows on the current lap only (no leakage).

## Model performance

Train 2024 (n=1444 laps) / test 2025 (n=1394). 2025 Las Vegas Race failed to load (empty FastF1 session) and is absent from the test set. LogisticRegression `class_weight='balanced'`. No oversampling.

Class balance (full 2838 rows): **sc_in_next_5 = 6.3%** (180/2838), sc_in_next_10 = 10.7% (304/2838). Close to the ~7% prior.

| Metric | sc_in_next_5 | sc_in_next_10 |
|---|---|---|
| AUC-ROC | 0.549 | 0.515 |
| Brier score | 0.226 | 0.261 |
| Mean p on SC laps | 0.322 | 0.284 |
| Mean p on non-SC laps | 0.303 | 0.312 |
| Prec=rec threshold | 0.82 | 0.78 |

## Honest assessment

The 5-lap model is only barely above chance (AUC 0.55). The 10-lap model is a coin flip (AUC 0.52) and is slightly **inverted** (mean p higher on non-SC laps). Lap-level features (density, yellows, retirements, rain) do not predict the next SC well on public data — SCs are rare, bursty, and mostly circuit-driven.

What *is* useful is the circuit prior. Historical SC rate is 1.00 at Azerbaijan vs 0.33 at Italy, and the live probabilities follow that: Baku mid-race ~56% vs Monza ~2%. That is enough for the narration line (`p_sc_next_5 > 0.20`) and is an honest “this circuit crashes” flag, not a lap-by-lap detector.

## Example output

| Circuit | Lap | rain | p_sc_next_5 | p_sc_next_10 |
|---|---:|:---:|---:|---:|
| Azerbaijan (Baku) | 25 / 51 | no | 56% | 75% |
| Italy (Monza) | 25 / 53 | no | 1.7% | 2.6% |
| Bahrain | 10 / 57 | no | 8.9% | 13% |
| Azerbaijan | 20 / 51 | yes | 59% | 80% |

Narration (Baku only): *SC/VSC risk elevated: 56% in next 5 laps. Consider pitting under neutralisation if the window opens.* Ranking / match logic unchanged.

## Gate check

- Zandvoort identity: **PASS** (Pit 33 HARD / Pit 30 HARD / Stay)
- Lights-out: not re-run (T10-A does not change ranking)
- Tests: **4/4** passing (`tests/test_sc_risk.py`)

## Files

- `scripts/build_sc_risk_dataset.py`
- `src/aris/risk/sc_risk_model.py`
- `models/sc_risk_5laps.pkl`, `models/sc_risk_10laps.pkl`
- `data/sc_risk_dataset.parquet`, `data/sc_historical_rates.json`
- `src/aris/state.py`, `src/aris/recommend.py`, `src/aris/narrate.py`
