# ARIS Race-only Replay + driver-first flow

Replay and ARIS no longer offer FP, Sprint, or Qualifying. The product is **Race weekends only**, with strategies fetched **after** a driver is locked.

## What changed

### Backend
- Replay/ARIS session lists (`GET /api/calendar/{year}/{round}/sessions?replay=1`) return only `session_type == "R"`.
- `POST /api/replay/init`, replay pack load, prewarm, and FastF1 replay assets reject non-Race types with **400** and:
  `Only Race sessions are supported for Replay/ARIS`
- `scripts/prebuild_replay_packs.py` always builds **Race** packs (`R`). `--session` is ignored if it is not `R`.

Recommend / simulate core logic is unchanged. `/api/aris/quick-analysis` and `/api/aris/plans` are still the strategy endpoints.

### Frontend
- Replay setup has **no session selector**.
- Step 1: year (2024–2026) + race weekend + ARIS On/Off.
- ARIS Off → load the race immediately (data-only replay).
- ARIS On → drivers first (no strategies) → **Lock Driver** → **Get Strategies** → pick a plan → **Start Race** (disabled until a plan is selected).
- `raceStore` fields: `arisEnabled`, `selectedDriver`, `strategies`, `selectedStrategy`, plus `driverLocked`.

## How to test

### Backend
```bash
# Race-only list
curl -s "http://127.0.0.1:8000/api/calendar/2025/15/sessions?replay=1"
# expect sessions: [{"session_type":"R", ...}]

# Non-Race Replay/ARIS request
curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:8000/api/replay/init \
  -H "Content-Type: application/json" \
  -d '{"year":2025,"round_number":15,"session_type":"Q"}'
# expect 400 and the Race-only message

# Strategies (Race, after a driver is chosen)
curl -s "http://127.0.0.1:8000/api/aris/quick-analysis?year=2025&round_number=15&driver_code=VER"

python -m pytest tests/test_replay_race_only.py tests/test_prebuild_replay_packs.py -q
```

### Frontend
1. Open `/replay`.
2. Confirm there is no FP / Sprint / Quali picker — only season, grands prix, and ARIS On/Off.
3. ARIS Off + a race → Start Race loads the existing data-only console.
4. ARIS On:
   - Driver grid appears; no strategy cards yet.
   - Lock a driver → **Get Strategies** appears.
   - Fetch plans, select one.
   - **Start Race** stays disabled until a strategy is selected, then loads the race with ARIS overlays.

## Expected behavior
- Only Race sessions for Replay/ARIS.
- Driver lock before any strategy fetch.
- Start Race requires locked driver + fetched strategies + selected strategy.
