# ARIS — Live / Next Race, Circuit Maps, Real-Time Data, 2026 Replay

Design note for the Live hub, GPS circuit maps, and 2026 replay filtering.
Does not change `recommend()` or `simulate()`. T12 Explain tab is unchanged.

## Live / next-race state

`GET /api/live/hub` is the single composition endpoint the Live page polls
(~15 s). It joins existing `live_status()`, `next_race()`, weekend sessions,
and YAML circuit characteristics (no FastF1 load on the hub path).

Mode is decided by `classify_hub_mode()`:

| Mode | When | UI |
|---|---|---|
| `live_session` | OpenF1/FastF1 window is live, **or** a weekend session is `LIVE` | Enter the pit-wall console; SSE + GPS |
| `waiting_for_session` | This weekend is open, next session (often Race) is still `UPCOMING` | Countdown + “race hasn’t started yet / waiting for race data” when the next session is Race; completed FP/Q/Sprint are replayable |
| `next_weekend` | Nothing live; next listed event is in the future | Countdown + circuit details/analysis |
| `session_ended` | Last session finished and the weekend has no remaining `LIVE`/`UPCOMING` sessions | Offer replay of the ended session |

Weekend state machine (sprint vs conventional) is already in
`calendar.get_round_sessions()`:

`FP1 → FP2 → FP3 → Q → Race` or `FP1 → SQ → S → Q → Race`.

A session becomes replayable when its status is `COMPLETED` (`fastf1_key` set).
Cancelled rounds (`calendar_notes.yaml` → `cancelled`) never enter `next_race`
candidates and are dropped from the Replay selector.

### Countdown

The hub returns `countdown_target` (ISO UTC of the next session) and a snapshot
`countdown_seconds`. The browser ticks locally from `countdown_target` so the
timer stays smooth without 1 Hz API traffic. `useCountdown` / the home Live
preview both use that ISO.

## Circuit maps and car positions

Track outline comes from FastF1 position telemetry
(`sessions.circuit_map` → `GET /api/circuit/{year}/{round}/map`):

- Polyline `x[]`/`y[]` (closed loop).
- Marker `kind=sf` at index 0 labelled **S/F** (start/finish).
- Pit in/out, DRS, sector marks, optional corners.

For 2026 weekends that are still open, `circuit_map_quick` copies the previous
year’s same-track outline so we never FastF1-load a live race.

Car dots use **GPS / location**, not a synthetic oval:

- **Live:** OpenF1 `location` (polled into `backend.live._STATE`, exposed on
  `GET /api/live/positions` and included on the SSE stream). Coordinates are
  normalised onto the same map bounds as the outline.
- **Replay:** `GET /api/live/replay-frame` positions (OpenF1 pack) or session
  position samples.

The map interpolates between ticks with the existing 60 fps dead-reckoner
(`CarAnimator`); it does not invent a layout.

Alias: `GET /api/circuits/{circuit_id}/layout` resolves a circuit key to the
latest non-cancelled round and returns the same `CircuitMapResponse`.

## Real-time data flow

**Not WebSocket.** `/api/live/stream` is **SSE** (`text/event-stream`), 1 s
while `is_live`, 2 s otherwise. Payload:

```json
{ "status": ..., "timing": ..., "weather": ..., "positions": ... }
```

The pit-wall EventSource applies timing + GPS into the Zustand store (timing
tower, track map). Stints and lap rows are polled at 5 s
(`/api/live/stints`, `/api/live/laps`) so strategy / lap charts are API-driven.

If SSE drops, the client falls back to HTTP polling of `/api/live/status`,
`/api/live/timing`, `/api/live/positions` (same pattern as the legacy
`frontend/` console). Mock oval feed is **demo-only** (`?demo=1` or explicit
button), not the default live path.

Replay uses `/api/live/session-key` then `/api/live/replay-frame` on the
playback clock — not the mock generator — when OpenF1 has a pack.

## 2026 replay filter

- Year list: `2018 … max(UTC year, 2026)`.
- Calendar: `GET /api/calendar/{year}` (already includes `CANCELLED`).
- Replay selector keeps rounds with status `COMPLETED` or `LIVE` (so a live
  weekend can replay finished FP/Q).
- Drops `CANCELLED` (2026 Bahrain R2, Saudi R3) and `UPCOMING`.
- Session pills: `COMPLETED` loadable; `LIVE` opens the live console;
  `UPCOMING` disabled.

Helper: `calendar.replayable_rounds(year, as_of=…)`.
