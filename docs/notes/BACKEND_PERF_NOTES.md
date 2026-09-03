# Backend performance notes

Warm-path changes for the FastAPI broker (`backend/main.py`, port 8765). `recommend()` / `simulate()` are untouched.

## What changed

1. **Parallel SSE ticks** (`backend/live.py`)
   - `/api/live/stream` still emits ~1 Hz snapshots (`sleep(1)` live / `sleep(2)` idle).
   - Each tick calls `live_status()` **once**, then `asyncio.gather(timing, weather, positions)` with that status shared. The four builders used to each call `live_status()` (and FastF1 calendar scan) so wall time stacked.
   - FastF1 `_fastf1_window_live` runs only when OpenF1 has **no** attached session (it was adding ~1 s on every live tick).

2. **Delta-friendly SSE payload**
   ```
   {
     "seq": int,              # monotonic per connection; 0 = handshake stub
     "last_updated": str,     # UTC ISO-8601
     "full": bool,            # true when static metadata is included
     "status": { ... },       # LiveStatus (REST `/api/live/status`)
     "timing": { ... } | null,
     "weather": { ... } | null,
     "positions": { ... } | null
   }
   ```
   After the first full tick (until `session_key` / year / round change), `status.session` and `positions.circuit_path` / markers / pit-lane are omitted. `frontend-next/lib/liveFeed.ts` already keeps the last outline when `circuit_path` is missing.

3. **`GET /api/status`**
   - Alias of `/api/aris/stats` (same JSON, 60 s memory + disk cache).
   - Includes Hero fields used by `frontend-next/lib/api.ts` `getStatus()`: `version`, `match_rate`, `match_rate_fraction`, `last_gate`, `timestamp` (`match_rate` = `decision_match_rate`).
   - Previously this path 404’d and the Hero fell back to `LAST_KNOWN_STATUS` after a 1.5 s abort.

4. **Startup preload**
   - Calendars 2024–2026 + next race + current-season drivers + stats → memory TTL cache **and** diskcache (keys the HTTP layer already uses: `calendar_{year}_now`, `drivers_{year}`, `aris_stats`).
   - Background: next-race outline **and** last 3–5 completed races via `circuit_map_quick` → `circuit_map_v6_{year}_{round}`.
   - FastF1 session loads stay off the blocking startup path (Windows crash avoidance).

## How to verify

```powershell
cd C:\Users\anass\ARIS
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src;.;.deps"
python -m pytest tests/test_backend_perf.py tests/test_ux_perf.py -q
```

With the broker running (`python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765`):

```powershell
# Hero alias — must be 200, same body as stats, warm cache after first hit
curl.exe -s -o NUL -w "%{http_code} %{time_total}`n" http://127.0.0.1:8765/api/status
curl.exe -s http://127.0.0.1:8765/api/status
curl.exe -s http://127.0.0.1:8765/api/aris/stats

# SSE — first data line is seq=0 stub; later ticks have seq, last_updated, status, timing, weather, positions
curl.exe -N --max-time 5 http://127.0.0.1:8765/api/live/stream
```

Logs to look for:

- `[ARIS] Calendar 2026 cached OK`
- `[ARIS] Drivers 2026 cached OK`
- `[ARIS] Circuit map cached: 2026 R…`
- `[ARIS] SSE tick seq=1 NNNms` then every 10th tick. Warm ticks should be **well under 500 ms** (idle, cached calendar: tens of ms; live with OpenF1 state already in `_STATE`: typically 50–300 ms).

## Expected gains

| Path | Before | After |
|---|---|---|
| SSE tick construction | Sequential `live_status` ×4 + FastF1 window (~1–1.6 s warm) | One `live_status` + parallel timing/weather/positions; FastF1 skipped when OpenF1 attached (**&lt; 500 ms** typical warm) |
| `GET /api/status` | **404** → Hero timeout 1.5 s → mock copy | **200** from `_aris_stats()` cache (**&lt; 50 ms** warm) |
| Calendar / drivers / circuit map first paint | Cold FastF1 / OpenF1 | Preloaded into the existing TTL + disk cache |

SSE cadence stays ~1 Hz and does not add OpenF1 calls; the poller (`poll_openf1_forever`) is unchanged.
