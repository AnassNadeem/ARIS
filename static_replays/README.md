# static_replays/

Local output of `scripts/build_replay_pack.py` (FastF1 GPS resampled into
60-second JSON chunks). FastAPI mounts this directory at `/static_replays`.

**Production replay does not use this path.** The console loads
`race_field.json` / `ghost_*.json` from Cloudflare R2 (`NEXT_PUBLIC_R2_BASE_URL`).
The Next `/test-replay` page is the only consumer of these chunks, as a
buffered-GPS experiment.

Do not commit generated packs. A 2024 Zandvoort dump used to live here
(~18 MB, 91 JSON files) as a leftover from before the R2 migration; it was
removed because nothing in the shipped Replay / ghost path reads it.

To rebuild locally:

```powershell
python scripts/build_replay_pack.py
```
