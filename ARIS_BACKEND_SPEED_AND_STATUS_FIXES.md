# ARIS backend speed and connection-status fixes

Date: 2026-08-27

Replay of **completed** sessions stays on FastF1 only. Live stays on OpenF1 only. Frame JSON is unchanged. `recommend()` / `simulate()` are untouched.

Restart the backend so these Python changes load (`scripts/run-backend.ps1`). The Next.js dev server picks up the frontend files on refresh.

## What changed

### 1. FastF1 replay wiring and logs

- Completed sessions still go through FastF1 (`backend/sessions.py` `load_session` / `build_ff1_replay_assets`, `backend/live.py` pack job). Live/open sessions skip FastF1 (`session_status != COMPLETED`).
- Logs now include:
  - `Loading replay session {year} R{round} {type} via FastF1`
  - `Metadata loaded in … s` / `Basic laps loaded in … s` / `GPS loaded in … s`
  - `Replay pack stage = metadata|minimal|full`
  - `key=replay_pack_v1:{year}:{round}:{type} memory_hit=… disk_hit=…`
- `scripts/test_fastf1_load.py` times a heavy session (default: 2025 Netherlands Race) without OpenF1.

### 2. Second-race load (cache keys)

The same helper is used for FastF1 session objects and replay-pack disk keys:

```python
def _pack_cache_key(year, round_number, session_type) -> str
# "replay_pack_v1:2025:15:R"
```

**Bug:** `/api/replay/init` used to plant an empty metadata stub in `_REPLAY_PACKS`. The pack job then treated that stub as a memory hit and **skipped diskcache**, so a later visit (or a restart) rebuilt from FastF1.

**Fix:** `hydrate_replay_pack_cache()` reads memory only if stage ≥ minimal; otherwise it loads disk (new year/round/type key, then legacy `replay_pack_v1:{session_key}`). Init, peek, prewarm, session-key, and `_ensure_replay_pack` all hydrate first. Minimal and full completed packs are written to disk (`TTL_REPLAY` = 30 days).

`_SESSION_CACHE` is still process-global (survives in-app navigation). Keys are the same `_pack_cache_key` strings for read and write.

Also: FastF1 `Session.t0_date` raises if telemetry was not loaded. Minimal-stage asset builds now ignore that and use lap start times, so laps-only packs can publish without waiting for GPS.

### 3. Header “Connecting”

- `ReplayFrameFeed` sets **connecting** at `connect()`, and **connected** on the first successful `/api/live/replay-frame` body (and again in `applyPayload`).
- `LiveSseFeed` sets **connected** in `onopen` / first payload, **disconnected** in `onerror`.
- `ConnectionStatus` reads `raceStore.connectionStatus` (plus `data-connection-status` for DevTools). Replay label is `CONNECTED FastF1`; live is `CONNECTED OpenF1 · {lag}ms lag`.

## How to verify

### FastF1 vs OpenF1

```powershell
cd C:\Users\anass\ARIS
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src;.;.deps"
python scripts/test_fastf1_load.py --year 2025 --round 15 --session R
```

Expect FastF1 cache hits in the script output, lap/driver counts, and **no OpenF1 URLs**. Backend logs for a completed replay should show `source=fastf1` and must not show OpenF1 location/car polls for that `session_key` (≥ 800_000_000).

Live: open `/live`, header should say OpenF1 after SSE `onopen`.

### Replay pack + cache

After restarting the backend:

1. POST `/api/replay/init` with `{ "year": 2025, "round_number": 15, "session_type": "R" }`.
2. Poll `GET /api/replay/pack-status?session_key=…&year=2025&round_number=15&session_type=R` until `stage` is `minimal` or `full`.
3. Repeat for another year (e.g. 2024 round 1).
4. Repeat step 1–2 for 2025 R15.

Logs should show `key=replay_pack_v1:2025:15:R memory_hit=True disk_hit=False` on the second 2025 visit in the same process. After a backend restart, the second visit should show `disk_hit=True` instead of a FastF1 cold load.

### Header status (DevTools)

1. Open `/replay`, pick a completed race, enter the console.
2. Header starts **CONNECTING…**.
3. When the first `replay-frame` 200 arrives (Network tab), the node `[data-connection-status=connected]` should read **CONNECTED FastF1** within a couple of seconds of that response — not stay on Connecting while cars are moving.

## Measured times (this machine, 2026-08-27)

| Step | What | Time | Notes |
|---|---|---|---|
| FastF1 script | 2025 Netherlands Race, laps-only | **7.23 s** `load_session`; **1364 laps**, **20 drivers** | FastF1 HTTP cache on disk (`fastf1_cache/`). No OpenF1. |
| Race A | 2025 R15 (Netherlands) `/replay/init` + pack-status to `full` | **3.6 s** | Pack already warm in the running broker. `source=fastf1`. |
| Race B | 2024 R1 (Bahrain) first visit | **120.6 s** | Cold FastF1 (GPS/full). First visit of a different year is still a download/parse, not a cache bug. |
| Race A again | 2025 R15 | **5 ms** | In-memory pack hit (`stage=full`). Under the ~5 s target. |

Race B first visit is slower than Race A’s first measured call because Race A was already in `_REPLAY_PACKS`. After a selector prewarm of Race B, pack-status should return `minimal`/`full` before you enter the console.

## FastF1 vs OpenF1 (confirmed in code)

| Mode | Source |
|---|---|
| Completed replay (`session_status == COMPLETED`) | FastF1 only (`synthetic_session_key` ≥ 800M, pack `source=fastf1`) |
| Live / open session | OpenF1 (`poll_openf1_forever`, SSE `/api/live/stream`) |

Tests: `tests/test_live_session_status.py` (`test_ensure_replay_pack_miss_does_not_call_openf1`, `test_init_replay_returns_metadata_without_openf1`, `test_stub_pack_hydrates_from_disk`, `test_pack_cache_key_matches_disk_key`). Frontend: `frontend-next/lib/connectionStatus.test.ts`.
