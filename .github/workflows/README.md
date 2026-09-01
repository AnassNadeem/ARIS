# GitHub Actions

## `ci.yml`

Runs ruff + pytest on push/PR to `main`.

## `prebuild_race.yml`

Builds static FastF1 replay JSON (`race_field.json` + `ghost_{DRIVER}.json`) and
uploads it to Cloudflare R2. Triggered manually, every Monday 18:00 UTC, or when
`scripts/prebuild_race_r2.py` changes on `main`.

A single-race FastF1 failure is logged and skipped — the job continues so a
partial calendar is better than a full abort.

### Secrets (repo Settings → Secrets and variables → Actions)

| Secret | Purpose |
|---|---|
| `R2_ACCOUNT_ID` | Cloudflare account id (R2 S3 endpoint) |
| `R2_ACCESS_KEY_ID` | R2 API token access key |
| `R2_SECRET_ACCESS_KEY` | R2 API token secret |
| `R2_BUCKET_NAME` | R2 bucket (e.g. `aris-replay`) |
| `DATABASE_URL` | Postgres URL for ARIS state / recommend() at lap 1 |

Also set `NEXT_PUBLIC_R2_BASE_URL` on the Cloudflare Pages project to the
bucket's public URL (e.g. `https://pub-xxxx.r2.dev`). Leave it blank for local
dev — the frontend falls back to the Heroku pack-status path.

Canonical production: Pages (`frontend-next`) + Heroku (`Procfile`) + R2 + Neon.
See [`DEPLOY.md`](../../DEPLOY.md).
