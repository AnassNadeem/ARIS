# ARIS — Front-end UX, Real-time Data, Circuit Map, Timing Tower, Comms, User Flow, Performance

Design note for the Next.js pit-wall (`frontend-next`) and FastAPI broker. Does **not** change `recommend()` or `simulate()` in `src/aris`. T12 Explain tab behaviour is unchanged.

Live transport remains **SSE** (`text/event-stream`) on `/api/live/stream`. Replays use FastF1 (session laps, circuit outline, GPS). Live weekends use OpenF1 (timing, race control, GPS).

---

## Track map

**Outline.** `GET /api/circuit/{year}/{round}/map` (FastF1 `circuit_map` / `circuit_map_quick` for open 2026 weekends). The client also tries `/preview` first and caches `{x,y,markers,sector_paths}` in memory + `localStorage` per `(year, round)`.

**Pit lane.** The racing-line polyline is the only path rendered. Pit-lane polylines from the API are ignored in the UI.

**Sectors.** FastF1 marshal-sector markers (`s1`/`s2`/`s3`) split the outline into three coloured polylines (S1 teal, S2 blue, S3 purple). If markers are missing, the path is split at ⅓ / ⅔. A compact S1 · S2 · S3 legend sits at the top-right. Start/finish stays a tick + **S/F** at index 0.

**Car motion.** Live GPS (OpenF1 `location` on SSE `positions`) and replay GPS are projected onto the racing line as `path_frac`. The 60 fps loop interpolates **along the path** between the last two ticks (ease ~0.8–1.0 s to match ~1 Hz GPS). Cartesian dead-reckoning is not used for on-track dots, so cars do not drift off the line.

**Click → analytics.** Clicking a dot sets `raceStore.focusDriver`. Timing tower, tyre deg, sectors, gap chart, lap times, and Explain sub-views subscribe to that code. ARIS strategy driver (`arisDriver`) is unchanged.

**DNF / DNS.** Eliminated / inactive drivers are omitted from the map.

**Load budget.** Warm cache &lt; 1 s; cold recent circuits &lt; 3 s via `circuit_map_quick` + preview + localStorage.

---

## Timing tower

Rows come from SSE `timing.rows` (OpenF1 live, FastF1/OpenF1 pack on replay), mapped in `mapTimingAndPositions`.

Each row: position, driver, gap (or +N laps), last lap, best lap (★ / FL if session fastest), S1/S2/S3 of the last lap, tyre, age, stops, laps completed, status.

**Sector colours** (backend `_sector_tone`, mirrored in the client):

| Colour | Meaning |
|---|---|
| Purple | Session-best (or OpenF1 overall-fastest segment) |
| Green | Personal best, not session best |
| Yellow | Slower than personal best |
| Grey | No time yet |

**Flags.** `session_flag` from race control (VSC / SC / RED / YELLOW / GREEN) drives a banner on the tower and the existing console phase strip. SC/VSC laps can be visually dimmed.

**DNF / DNS.** Race-control retirements plus lap inactivity (no competitive lap after ~10% distance → DNS; stopped well behind the field → DNF). Rows are greyed; dots leave the map.

Updates are Zustand-selector scoped so unchanged rows do not rebuild the whole table.

---

## Analytics (real-time, not hardcoded)

Panels read `lapRows` / `stintRows` from the store (SSE + `/api/live/laps` & `/stints`, or FastF1 session laps on replay). Mock Zandvoort 72-lap history is **not** used when a session is loaded; empty states say “Waiting for lap data…”.

Degradation scatter uses stint-average deltas from incoming laps. Ghost traces use backend ghost ticks when ARIS is on — not a fixed −3.4 s/race fudge. Header **Lap X / N** uses track YAML `total_laps` for that circuit (via calendar / live status / session summary), not a hardcoded 72.

`focusDriver` highlights the selected driver’s series.

---

## ARIS Comms (two tabs)

Default tabs:

1. **Main Comms** — ARIS decisions, field messages, approve/deny/alter cards. Empty until ARIS strategy is on.
2. **Copilot** — the chat backend (tool-calling Copilot). Preferred over legacy Ask ARIS. If `NEXT_PUBLIC_ARIS_COPILOT=0`, the second tab falls back to Ask ARIS.

Users can **New chat**; each thread still hits the same Copilot (or Ask) endpoint. Explain tab is untouched.

**Mid-race rule.** Once the console is running, the strategy model cannot be switched **on**. Copilot can be added at any time (“Add Copilot”) to ask about the current or past race. Strategy ARIS is chosen in the selector **before** replay.

---

## User flow (replay)

1. Choose **year** and **race**.
2. Two actions: **Replay** (timing/map only) or **ARIS** (strategy + comms).
3. ARIS → pick a **driver**.
4. `GET /api/aris/quick-analysis` (wraps existing `plans()`, does not call into `src/aris.recommend` / `simulate` internals) returns top-3 pre-race strategies. Rank 1 is labelled **Recommended** and highlighted.
5. Confirm **Start replay**.

Live hub is unchanged: enter console when a session is live; otherwise countdown / replay chips.

---

## Performance

| Bottleneck | Change |
|---|---|
| Sequential SSE `live_status` → timing → weather → positions | `asyncio.gather` per tick; compact JSON |
| Circuit map FastF1 load on live/2026 | `circuit_map_quick` + `/preview` + localStorage |
| Cross-origin `localhost:8000` vs broker `8765` | Next.js same-origin rewrite `/api/*` → `127.0.0.1:8765` |
| Full React re-render on every GPS tick | Positions applied in the store; map dots via rAF + refs |
| Replay 1 Hz frame fetch with teleporting dots | Path-frac interpolation at 60 fps; replay poll stays 1 Hz |
| Duplicate timing payloads | Skip `setCars` when the timing fingerprint is unchanged |
| Analytics mock fallback | Only when no session laps have arrived |

---

## Tests / how to run

See **How to Run & Test — UX / Perf** in [`HOW-TO-RUN-T12.md`](./HOW-TO-RUN-T12.md).
