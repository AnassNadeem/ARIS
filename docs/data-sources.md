# ARIS data sources

Fields ARIS actually uses, traced from `src/aris/io/ingest.py` and
`src/aris/models/features.py`. **Measured** = taken from FastF1 (or a
trivial coercion of a FastF1 value). **Derived** = computed by ARIS code
on top of measured inputs.

## Ingest → Postgres (`aris.io.ingest`)

| ARIS / DB field | FastF1 source | Measured / derived | Notes |
|---|---|---|---|
| `sessions.year` | caller argument | measured | Passed into `ingest_session` |
| `sessions.round_no` | `sess.event["RoundNumber"]` | measured | |
| `sessions.country` | `sess.event["Country"]` | measured | |
| `sessions.session_type` | caller argument | measured | Validated against FP1/FP2/FP3/Q/SQ/SS/R/SR |
| `sessions.date` | `sess.date` | measured | Coerced to Python datetime |
| `drivers.code` | `laps["Driver"]` | measured | Unique abbreviations in session laps |
| `drivers.full_name` | `results["FullName"]` | measured | Falls back to code if missing from results |
| `drivers.team` | `results["TeamName"]` | measured | |
| `drivers.year` | caller argument | measured | |
| `laps.lap_number` | `LapNumber` | measured | |
| `laps.lap_time_s` | `LapTimeS` | derived | Seconds float from FastF1 lap time via `detect_stints` enrichment |
| `laps.compound` | `Compound` | measured | |
| `laps.tyre_life` | `TyreLife` | measured | |
| `laps.stint` | (not FastF1 `Stint`) | derived | `StintId` from `aris.physics.stint.detect_stints` (compound-change cumsum) |
| `laps.sector_1_s` | `Sector1Time` | measured | Timedelta → seconds |
| `laps.sector_2_s` | `Sector2Time` | measured | Timedelta → seconds |
| `laps.sector_3_s` | `Sector3Time` | measured | Timedelta → seconds |
| `laps.track_status` | `TrackStatus` | measured | |
| `laps.pit_in` | `PitInTime` | derived | `True` iff `PitInTime` is non-null |
| `laps.pit_out` | `PitOutTime` | derived | `True` iff `PitOutTime` is non-null |
| `telemetry.speed` | telemetry `Speed` | measured | Optional; `include_telemetry=True` only |
| `telemetry.throttle` | telemetry `Throttle` | measured | |
| `telemetry.brake` | telemetry `Brake` | measured | Coerced to bool |
| `telemetry.gear` | telemetry `nGear` | derived | Measured then cleaned: values outside 1..8 → NULL |
| `telemetry.drs` | telemetry `DRS` | measured | |
| `telemetry.rpm` | telemetry `RPM` | measured | |
| `telemetry.x` / `y` / `z` | telemetry `X`/`Y`/`Z` | measured | |
| `session_weather.air_temp_c` | weather `AirTemp` | derived | Session median |
| `session_weather.track_temp_c` | weather `TrackTemp` | derived | Session median |
| `session_weather.humidity_pct` | weather `Humidity` | derived | Session median |
| `session_weather.rainfall` | weather `Rainfall` | derived | `True` if any sample reports rain |
| `session_results.grid_pos` | results `GridPosition` | measured | |
| `session_results.finish_pos` | results `Position` | measured | |
| `session_results.points` | results `Points` | measured | |

`LapTimeS` itself is produced inside `detect_stints` as
`LapTime.dt.total_seconds()` (see `aris.physics.stint`) — a unit conversion
of FastF1's `LapTime`, not a model prediction.

## Feature frame → residual model (`aris.models.features`)

Built by `build_feature_frame` from a FastF1-style laps frame (or DB-backed
equivalent after stint enrichment). Target and residual are for training /
eval only.

| Feature / column | Source | Measured / derived | Notes |
|---|---|---|---|
| `race_id` | caller | derived | e.g. `2024-Bahrain` |
| `Driver` | FastF1 `Driver` | measured | |
| `LapNumber` | FastF1 `LapNumber` | measured | |
| `StintId` | `detect_stints` | derived | Same rule as ingest `stint` |
| `target` | FastF1 `LapTime` → `LapTimeS` | measured | Clean green-flag laps only (`filter_clean_laps`) |
| `residual` | `target - physics_pred` | derived | Training label for XGBoost residual |
| `compound_code` | FastF1 `Compound` | derived | Mapped Soft=0 … Wet=4 |
| `tyre_life` | FastF1 `TyreLife` | measured | Missing → 1 |
| `fuel_kg` | `estimate_fuel_kg(LapNumber)` | derived | Linear burn model: 110 kg start, 1.7 kg/lap |
| `lag1_pace` | prior lap `LapTimeS` in stint | derived | `groupby(Driver, StintId).shift(1)` — causal |
| `lag2_pace` | lap−2 `LapTimeS` in stint | derived | `shift(2)` — causal; rows without lag1 dropped |
| `stint_roll3` | prior laps in stint | derived | `shift(1).rolling(3).mean()` — causal |
| `physics_pred` | bicycle + tyre model | derived | `aris.physics.bicycle.predict_lap_time` on `StintState` |
| `pit_lap` | hardcoded `False` in frame builder | derived | Placeholder for physics row; not FastF1 |
| `compound` (string) | FastF1 `Compound` | measured | Passed into physics; missing → `"MEDIUM"` |

Constants baked into fuel estimation (`_FUEL_START_KG=110`, `_FUEL_BURN_PER_LAP=1.7`,
default `total_laps=57`) are model assumptions, not FastF1 fields.
