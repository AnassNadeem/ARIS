# Scratch / implementation notes

Working notes moved out of the repo root so the top level stays clean.
These are not the canonical product docs (see `docs/` siblings and the
root `README.md`); they preserve implementation history and one-off
design decisions.

| File | Covers |
|---|---|
| [`ARIS_WARMUP_ON_STARTUP.md`](./ARIS_WARMUP_ON_STARTUP.md) | FastAPI lifespan warmup: preload diskcache packs into RAM after uvicorn restart |
| [`ARIS_REPLAY_YEAR_LIMIT.md`](./ARIS_REPLAY_YEAR_LIMIT.md) | Replay session packs restricted to 2024–2026 |
| [`ARIS_SHRINK_REPLAY_FRAMES.md`](./ARIS_SHRINK_REPLAY_FRAMES.md) | Smaller replay-frame payloads: outline once, deltas, gzip |
| [`ARIS_BACKEND_SPEED_AND_STATUS_FIXES.md`](./ARIS_BACKEND_SPEED_AND_STATUS_FIXES.md) | Backend speed and connection-status fixes (FastF1 replay / OpenF1 live split) |
| [`ARIS_PREBUILD_REPLAY_PACKS.md`](./ARIS_PREBUILD_REPLAY_PACKS.md) | Offline prebuild of FastF1 replay packs into diskcache |
| [`ARIS_RACE_ONLY_FLOW.md`](./ARIS_RACE_ONLY_FLOW.md) | Race-weekend-only replay and driver-first strategy fetch |
| [`ARIS_REPLAY_LOADING_AND_UX_FIXES.md`](./ARIS_REPLAY_LOADING_AND_UX_FIXES.md) | Staged FastF1 load, header Start, post-race debrief |
| [`ARIS_STANDINGS_AND_CIRCUITS_PAGES.md`](./ARIS_STANDINGS_AND_CIRCUITS_PAGES.md) | Standings page; Circuits catalogue removed |
| [`BACKEND_PERF_NOTES.md`](./BACKEND_PERF_NOTES.md) | Warm-path FastAPI broker performance notes |
| [`NOTES.md`](./NOTES.md) | Short pointer: V3 UI is `frontend-next/`; local run commands |
