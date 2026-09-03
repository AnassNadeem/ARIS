# Prebuild replay packs (2024–2026)

Cold first load of a completed race can take ~1–2 minutes because FastF1 downloads and parses `pos_data` for the whole field. This script builds those packs offline and writes them to diskcache with the **same keys the backend already reads**, so `/replay` is a disk hit (seconds) instead of a FastF1 cold load.

Recommend / simulate logic is unchanged.

## Cache key

```
replay_pack_v1:{year}:{round}:{session}
```

Example: `replay_pack_v1:2025:15:R` (2025 Netherlands Race).

On request the backend calls `hydrate_replay_pack_cache()` first (memory, then disk). Logs:

```
key=replay_pack_v1:2025:15:R memory_hit=False disk_hit=True
key=replay_pack_v1:2025:15:R … stage=full — skip FastF1
```

If the key is missing (future 2026 race, cache cleared), the existing on-demand FastF1 build still runs.

## How to run

From the repo root, venv on:

```powershell
cd C:\Users\anass\ARIS
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src;.;.deps"
python scripts/prebuild_replay_packs.py --dry-run
python scripts/prebuild_replay_packs.py --year 2025 --round 15
python scripts/prebuild_replay_packs.py
```

| Flag | Effect |
|---|---|
| `--dry-run` | Print what would be built; no FastF1, no disk writes |
| `--year 2025` | One season (repeatable) |
| `--round 15` | One round (use with `--year`) |
| `--force` | Rebuild even if a full pack is already on disk |

A full season is slow (minutes per race the first time). Re-runs skip packs that are already `stage=full` with real GPS unless `--force`.

## Coverage

| Season | What is built |
|---|---|
| **2024** | Every completed Race (`R`) on the ARIS calendar |
| **2025** | Every completed Race |
| **2026** | Completed Races only. Upcoming / live rounds log `Skipped 2026 R16 (upcoming)`. Cancelled rounds (e.g. 2026 R2/R3) are skipped. FastF1 may fail if `pos_data` is not published yet. |

Cancelled rounds are skipped. FastF1 failures (e.g. a 2026 round the calendar marks complete but FastF1 has no `pos_data` yet) log `Failed …` and continue.

Session type defaults to **Race**. Quali/sprint are not part of this batch.

## Expected speed

| Path | Typical time |
|---|---|
| Cold FastF1 (`telemetry=True`, whole field GPS) | ~60–120+ s |
| Diskcache hit after prebuild (backend restart, empty memory) | a few seconds (`disk_hit=True`) |
| Same process, second visit | memory hit (`memory_hit=True disk_hit=False`) |

Full completed packs are stored **without a 30-day expiry** so a prebuild stays valid across restarts. Minimal (laps-only) packs still use `TTL_REPLAY` (30 days).

## Sanity check (2025 R15)

```powershell
python scripts/prebuild_replay_packs.py --year 2025 --round 15
```

Expect `Prebuilt 2025 R15 R` (or `Skipped … already cached`). Restart the backend, open that race in `/replay`, and confirm logs show `disk_hit=True` and `stage=full — skip FastF1` — not a multi-minute FastF1 GPS load.
