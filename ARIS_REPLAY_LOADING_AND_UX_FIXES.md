# ARIS replay loading and UX fixes

Staged FastF1 replay load, header Start with track-only lights-out, and a post-race debrief.

## What changed

### FastF1-only replay (no OpenF1)

Completed replay sessions still load only through FastF1 (`backend/sessions.py`, `backend/live.py`). Session calendar status chooses the source: `COMPLETED` → FastF1; `LIVE` / `UPCOMING` → no FastF1 pack (live remains OpenF1). Logs include:

- `Loading replay session {year} R{round} {type} via FastF1`
- `Metadata loaded in … s`
- `Basic laps loaded in … s`
- `GPS loaded in … s`
- `Replay pack stage = metadata/minimal/full`

FastF1 cache path is logged from `backend/cache.py` (`FastF1 cache enabled path=…`).

### Staged pack: metadata → minimal → full

| Stage | Contents |
| --- | --- |
| **metadata** | Circuit, session type, dates, scheduled laps from the calendar. No FastF1 wait. |
| **minimal** | FastF1 laps (no telemetry), previous-year map outline, synthetic GPS along the outline so cars can move. |
| **full** | Real FastF1 GPS, weather, race control. Replaces synthetic GPS. |

Waiters **do not hold** the pack lock. They poll in-memory stage. The background job always continues to `full`.

New / extended APIs:

- `POST /api/replay/init` `{ year, round_number, session_type }` — metadata immediately, kicks FastF1.
- `GET /api/replay/pack-status?session_key=` (also `session_id`) and `GET /api/live/replay-pack-status` — `stage`, `progress`, `flags` (`laps_ready`, `map_ready`, `gps_ready`, `weather_ready`). `ready` means stage ≥ minimal (Start can enable). `gps_ready` is real FastF1 GPS.

`GET /api/live/replay-frame` waits for **minimal** only, then returns frames from the partial pack.

`POST /api/aris/recommend` uses laps-only FastF1 (`telemetry=False, weather=False, messages=False`) so Get strategy does not wait on GPS/weather.

### Frontend UX

- Setup: after session pick, `POST /api/replay/init` and poll pack-status. Loading copy is real (`Loading session metadata…` then `Preparing race data (laps, map)…`). Console opens at **minimal** (does not call `/summary`).
- Header **Start Race** (disabled until stage ≥ minimal). No full-screen Start overlay.
- `TrackLightsOut` plays ~3.5s five-light sequence **on the track map only**, then replay runs from lap 1. Dashboard stays usable before Start. Playback play is disabled until racing.
- Subtle toast **Data fully loaded** when stage flips to full.
- Race end (clock past `date_end`, or Finished + last lap): `RaceFinishedDebrief` banner **Race finished — View post-race debrief**. Modal compares ghost vs real (position, gap, pits, estimated delta). Dismissible; reopen from Explain → **Post-race debrief**.

## How to verify

### FastF1 timing (no ARIS pack)

```bash
python scripts/test_fastf1_load.py --year 2025 --round 15 --session R
python scripts/test_fastf1_load.py --year 2025 --round 15 --session R --full
```

Expect laps-only in seconds–tens of seconds on a warm cache; `--full` is the slow GPS path. Backend logs should show the staged messages above.

### Init + pack-status

With the API running:

```bash
curl -s -X POST http://127.0.0.1:8000/api/replay/init -H "Content-Type: application/json" -d "{\"year\":2025,\"round_number\":15,\"session_type\":\"R\"}"
curl -s "http://127.0.0.1:8000/api/replay/pack-status?session_key=<key_from_init>"
```

Watch `stage` move `metadata` → `minimal` → `full`. `ready` should become true at **minimal**, before `flags.gps_ready`.

DevTools: Network `POST /api/replay/init` returns quickly; `pack-status` polls every ~1s. `GET /api/session/.../summary` should **not** block setup.

### UI flow

1. Replay → pick a race you have not loaded recently.
2. Metadata line appears within seconds; then “Preparing race data”.
3. Console opens with **Start Race** enabled before GPS is done.
4. Rearrange dashboard; click **Start Race** — lights only on the map, then cars move.
5. Optional: Get strategy on the comms panel (spinner on that control) while stage is still minimal.
6. When GPS finishes, a brief “Data fully loaded” toast.
7. After the race clock ends, the debrief banner appears.

### Tests

```bash
python -m pytest tests/test_live_session_status.py -q
```

## Flags / settings

No new env flags. Explain/debrief still uses `NEXT_PUBLIC_ARIS_EXPLAIN`. Replay force-refresh remains `?refresh=1` on the console URL.
