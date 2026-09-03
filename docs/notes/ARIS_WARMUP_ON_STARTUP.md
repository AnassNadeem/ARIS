# Warmup on startup

After a uvicorn restart, RAM is empty even when diskcache still holds calendars, driver lists, and prebuilt replay packs. The FastAPI lifespan now **awaits** a warmup so the first user request is a memory hit.

Recommend / simulate are unchanged. Hot packs are copied from **disk into `_REPLAY_PACKS` only** — FastF1 is not loaded at boot (that has crashed uvicorn on Windows).

## What is preloaded

| Data | Years / keys | Where it lands |
|---|---|---|
| Calendar | 2024, 2025, 2026 | In-memory TTL cache + disk (`calendar_{year}_now`) and `calendar.get_calendar`’s `calbuild_*` RAM cache |
| Driver lists | 2024, 2025, 2026 | In-memory + disk (`drivers_{year}`) |
| Hot Race packs | 2025 R15 Zandvoort, 2024 R8 Monaco, plus Monaco/Zandvoort/Silverstone/Monza 2024–2025 (8 packs) | `_REPLAY_PACKS` if the pack is already on disk |

Background (does **not** block the first request): next-race, ARIS stats, 2018–2023 standings, live-weekend pack prewarm.

Look for:

```
[ARIS] Warmup complete: calendar, drivers, N hot packs loaded.
```

`N` is how many hot packs were found in RAM or diskcache. Missing packs are skipped (`Hot pack … skipped (not on disk)`); run `scripts/prebuild_replay_packs.py` to populate them.

## Cache order

- **Calendar / drivers HTTP:** `_cached_sync` → RAM (`cache.get`) → diskcache (promote into RAM) → factory.
- **Replay packs:** `hydrate_replay_pack_cache` → `_REPLAY_PACKS` → diskcache → (on demand) FastF1.

## How to verify

Restart uvicorn, then immediately:

```powershell
Measure-Command { Invoke-RestMethod http://127.0.0.1:8765/api/calendar/2025 }
Measure-Command { Invoke-RestMethod http://127.0.0.1:8765/api/drivers/2025 }
Invoke-RestMethod -Method POST http://127.0.0.1:8765/api/replay/init `
  -ContentType "application/json" `
  -Body '{"year":2025,"round_number":15,"session_type":"R"}'
```

Expect:

- Calendar and drivers **under 100 ms** (warm RAM).
- Hot `/api/replay/init` **under 1 s** if that pack was on disk at boot (`memory_hit=True`).
- Backend log line `Warmup complete: calendar, drivers, N hot packs loaded.`

## Expected speed

| Request | Before (cold RAM, even with disk) | After warmup |
|---|---|---|
| `GET /api/calendar/2025` | Rebuild / disk unpickle on first hit | RAM hit, typically under 100 ms |
| `GET /api/drivers/2025` | OpenF1 / FastF1 on first hit | RAM hit, typically under 100 ms |
| Hot `/api/replay/init` | Disk unpickle of a full GPS pack (seconds) or FastF1 (minutes) | Already in `_REPLAY_PACKS` when disk had the pack |
