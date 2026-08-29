# ARIS data loading, ghost, and UX fixes

## 1. Race data loading (FastF1 vs cache)

**Replay is FastF1 only.** `/api/live/session-key` always returns a FastF1 key (`800000000+year*1000+round*10+kind`). The pack is built from FastF1 laps, GPS, weather, stints, and race control — OpenF1 is not called on the replay path.

OpenF1 is used for **live** polling, SSE, and live recommend rainfall only.

Circuit matching for live OpenF1 sessions ignores accents (`São Paulo` vs `Sao Paulo`) and does not treat the country name as a unique circuit (Italy/Monza vs Imola).

`?refresh=1` on `/replay` drops FastF1 session cache, HTTP TTL cache, and the replay pack.

**Verify:** pick a 2025 race that is not the default Netherlands round. Lights-out should enable once the first GPS/timing frame arrives. Broker log: `session-key FastF1` and `replay pack MISS … FastF1 only` (never `OpenF1 bootstrap`).

## 2. Ghost on map, tower, analytics

Replay frames apply `ghost`. If the DB ghost is empty, the **last recommendation** still draws a synthetic `[A]` car (including after Auto-approve, which clears the pending card). Ghost sits slightly off the real car so it is visible.

**Verify:** ARIS on → lights out. After Get strategy (or Auto’s first call), dashed `[A]` on the map and an `[A]` row on the tower.

## 3. Auto / Assisted lock

Mode is chosen on the **race selector** before the console. The header shows `Mode: Auto` / `Mode: Assisted` as a label only — no lock icon, no toggle. `setARISMode` is a no-op once locked (set when ARIS loads into the console).

## 4. Race ended / debrief

When the replay clock passes `date_end`, `RaceEndedView` overlays ghost vs real and **Open Race Debrief**.

## 5. Get strategy per driver

**Get strategy** POSTs `/api/aris/recommend` with `force_refresh`. Changing driver forces a recompute. Main Comms keys are unique (`rec.id-e{epoch}` + render index) so React no longer warns about duplicate children.

## 6. Main Comms narration

SC/VSC/red, rain, fastest lap, DNF, undercut/overcut, sector loss, periodic gaps.

## 7. ARIS for {driver}

Header chip while strategy is on.

## 8. Speed widget

~1 Hz from GPS. Click toggles km/h ↔ mph.

## 9. 30 s lookahead (not a UI delay)

There is **no** spinner, skip button, or “Smooth start” checkbox. While lights-out is up (and during play), the feed prefetches **playhead + 30 s** so a late FastF1 point can still land. If a current frame misses, playback does not jump forward.

## Flags

| Flag | Where |
| --- | --- |
| `?refresh=1` | Replay URL — bypass caches |
| `force_refresh` | Recommend POST body |

Restart the FastAPI broker after backend changes.
