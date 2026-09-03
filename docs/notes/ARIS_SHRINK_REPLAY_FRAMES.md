# Shrink replay frames

Replay frames (`GET /api/live/replay-frame`) no longer carry the static circuit outline on every 250 ms tick. Subsequent ticks can be **deltas** (changed cars/rows only). API responses larger than 1 KB are **gzipped**.

## What changed

### Outline once
- `POST /api/replay/init` now includes `circuit_path`, pit-lane polylines, `markers`, and `drs_segments` when the pack already has a map.
- `GET /api/replay/pack-status?outline=1` (and `/api/live/replay-pack-status`) returns the same geometry so the client can store it as soon as FastF1 fills the pack.
- Replay-frame payloads omit `circuit_path`, pit lane, markers, and DRS segments. The frontend keeps the outline in `raceStore.circuitOutline` for the session.

### Deltas after the first frame
- Wire frames include `is_delta: true|false`.
- The client sends `prev_as_of` from the last **applied** frame. The server diffs timing rows and car positions against that snapshot.
- Seeks and lookahead prefetch pass `full=1` so they never consume or poison another client’s delta base.
- If the driver set changes, the server falls back to a full snapshot (still without the outline).

### Gzip
- `GZipMiddleware` is registered in `backend/main.py` with `minimum_size=1000`. Browsers send `Accept-Encoding: gzip` and decompress automatically.

## How to verify (Network tab)

1. Open a completed replay session and start playback.
2. Filter for `replay-frame`.
3. First applied tick: `is_delta` is false, body is larger, **no** `positions.circuit_path` polyline.
4. Later ticks: `is_delta` is true, `timing.rows` often empty or a handful of cars, `positions.positions` only cars that moved.
5. Response headers: `Content-Encoding: gzip` on bodies over ~1 KB (DevTools may show the decoded size; check the Headers pane).
6. Confirm the track map outline stays put and the timing tower / car dots still update.

Also check `replay/init` or a `pack-status?outline=1` call for the one-time outline payload.

## Expected speed improvement

- Outline polylines are thousands of floats; dropping them every 250 ms cuts tens of KB per tick.
- Unchanged timing rows (most cars, most ticks) are omitted on deltas.
- Gzip shrinks remaining JSON further on the wire.
- The browser parses less JSON per tick, which is the main CPU win during playback.

ARIS `recommend` / `simulate` logic is unchanged.
