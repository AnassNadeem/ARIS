# ARIS — production deploy

Canonical production is:

| Piece | Host |
|---|---|
| Strategy / Replay UI | Cloudflare Pages (`frontend-next/` static export) at **https://arisf1.tech** |
| FastAPI broker | **Heroku** (`Procfile` → `uvicorn backend.main:app`) |
| Replay / ghost JSON | Cloudflare **R2** (GitHub Action `prebuild_race.yml`) |
| Postgres | **Neon**, connected as Heroku `DATABASE_URL` |

The older Streamlit lap explorer runbook is in
[`docs/legacy-streamlit-deploy.md`](./docs/legacy-streamlit-deploy.md).

---

## Architecture

```
browser  →  https://arisf1.tech          (Cloudflare Pages, Next static export)
              ├── static UI
              ├── /r2replay/*  or NEXT_PUBLIC_R2_BASE_URL  →  R2 public bucket
              └── NEXT_PUBLIC_API_BASE   →  https://<heroku-app>.herokuapp.com
                                              └── DATABASE_URL → Neon
```

The optional Worker UI host lives under `deploy/cloudflare-worker/`
(`wrangler.jsonc`). It is **not** the production API. Cloudflare Containers
(`deploy/cloudflare-worker/wrangler.containers.jsonc`) are a **future option**
on the Workers Paid plan, not the current backend.

`scripts/aris-home-tunnel.ps1` is **local-dev only**.

---

## Dependency manifests

| File | Used for |
|---|---|
| `requirements.txt` | Heroku Python buildpack slug (see `.slugignore`) and the plain-pip local fallback; also what older Streamlit Cloud setups read at repo root. Includes FastAPI + uvicorn for the web process. |
| `requirements-scripts.txt` | Offline replay prebuild + R2 upload jobs. **Not** installed on the Heroku API dyno. |
| `apps/requirements.txt` | Streamlit Community Cloud deploy of the Phase 2 lap explorer (runtime subset the app actually imports). |
| `deploy/requirements-api.txt` | Slim FastAPI broker image (`Dockerfile` / future Cloudflare Container) — no Streamlit. |
| `pyproject.toml` | Canonical project metadata and deps for local `uv sync` / editable install; also houses Ruff, pytest, and mypy tool config (`[tool.*]`). Optional extras: `dev`, `cql`. |

---

## 1. Neon Postgres

Same project as local/dev. Connection string shape:

```
postgresql+psycopg://USER:PASSWORD@ep-xxxx.region.aws.neon.tech/aris?sslmode=require
```

On Heroku, paste the Neon URL as `DATABASE_URL` (Heroku's conventional name).
The app rewrites `postgres://` → `postgresql+psycopg://` and adds `sslmode=require`
when `DYNO` is set. You can also set `ARIS_DB_URL` explicitly; it wins.

Apply schema once (from a laptop pointed at Neon):

```powershell
$env:ARIS_DB_URL = "postgresql+psycopg://USER:PASSWORD@ep-xxxx.region.aws.neon.tech/aris?sslmode=require"
python -c "from sqlalchemy import create_engine, text; import os, re; e=create_engine(os.environ['ARIS_DB_URL']); sql=open('db/schema.sql', encoding='utf-8').read(); stmts=[s.strip() for s in re.split(r';\s*\n', sql) if s.strip()];
with e.begin() as c:
    for s in stmts:
        c.execute(text(s))
print('schema applied:', len(stmts))"
```

Ingest is optional for the Replay UI (R2 serves race packs). It is required for
Streamlit / SQL-backed eval.

```powershell
python scripts/ingest_season.py 2024
```

---

## 2. Heroku FastAPI

`Procfile` already declares a single web dyno. Do not scale a second dyno
(telemetry load is in-process).

```powershell
heroku create   # once; note the app URL
heroku stack:set heroku-24
git push heroku main
```

Or connect the GitHub repo in the Heroku dashboard and deploy from `main`.

### Config vars (Heroku dashboard → Settings → Config Vars)

| Var | Value |
|---|---|
| `DATABASE_URL` | Neon URL (Heroku may set this if you attach a Postgres add-on; otherwise paste Neon) |
| `ARIS_FRONTEND_ORIGIN` | **`https://arisf1.tech`** (comma-separate extra Pages preview URLs if needed) |
| `ARIS_CACHE_BACKEND` | `postgres` |
| `OPENF1_USERNAME` / `OPENF1_PASSWORD` | OpenF1 account (live timing) |
| `OPENF1_API_KEY` | if you use the token path |
| `SENTRY_DSN` | optional |
| `ARIS_ENABLE_PREWARM` | leave **unset** (a 512MB Basic dyno OOMs if GPS loads at boot) |

If `ARIS_FRONTEND_ORIGIN` is unset, a dyno still allows `https://arisf1.tech` and
the Pages project origin. Set it anyway so preview hosts are explicit.

Python version: `runtime.txt` → `python-3.11`.

Smoke:

```powershell
curl -sS https://YOUR-APP.herokuapp.com/health
```

Expect JSON with `"ok": true` once Neon is reachable.

---

## 3. Cloudflare Pages (`frontend-next`)

Dashboard: Workers & Pages → the existing project (`aris-frontend-590`).

| Setting | Value |
|---|---|
| Root directory | `frontend-next` |
| Build command | `npm ci && npm run build` (`CF_PAGES` is set by Pages → static export to `out/`) |
| Build output | `out` |
| Node | 20 |

### Pages environment variables (build-time)

| Var | Value |
|---|---|
| `NEXT_PUBLIC_API_BASE` | `https://YOUR-APP.herokuapp.com` (no trailing slash) |
| `NEXT_PUBLIC_R2_BASE_URL` | R2 public URL, e.g. `https://pub-9429cde26be84c4c8034f0b5873b9a7d.r2.dev` |
| `NEXT_PUBLIC_WS_BASE` | optional; derived from `NEXT_PUBLIC_API_BASE` if unset (`https` → `wss`) |
| `NEXT_PUBLIC_ARIS_COPILOT` | `1` only if Copilot should ship; default is Ask ARIS |

`NEXT_PUBLIC_*` is inlined at **build** time. Changing Heroku's URL requires a
Pages rebuild.

---

## 4. Domain / DNS / SSL (`arisf1.tech`)

In the Pages project → Custom domains → `arisf1.tech`.

Cloudflare DNS (same account):

- `CNAME arisf1.tech` → the Pages target Cloudflare shows (or a proxied apex
  CNAME/ALIAS as the dashboard instructs)
- SSL/TLS: **Full (strict)**; Pages provisions the certificate

Wait until the custom domain shows Active. Then confirm:

1. `https://arisf1.tech` loads the Next console (replay selector, ARIS toggle)
2. Browser Network: `/api/health` or `/api/live/hub` hits **Heroku**, not 8765
3. Replay of a 2024/2025 race loads R2 JSON (`race_field.json` / `ghost_*.json`)

---

## 5. R2 replay packs

GitHub Actions workflow `.github/workflows/prebuild_race.yml` builds
`race_field.json` + `ghost_{DRIVER}.json` and uploads them to R2.

Repo secrets: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
`R2_BUCKET_NAME`, plus `DATABASE_URL` if the job scores ghosts against Postgres.

The bucket must be publicly readable at `NEXT_PUBLIC_R2_BASE_URL`.

---

## 6. Optional Worker UI / future Container

Root `wrangler.jsonc` must stay at the repo root so Cloudflare Workers Builds
(`npx wrangler deploy` after `cd frontend-next && npm run dev`) can find
`frontend-next/out`. Local / package scripts still live under
`deploy/cloudflare-worker/`:

```powershell
cd deploy/cloudflare-worker
npm install
npm run deploy              # Workers assets from frontend-next/out (not the live domain)
npm run deploy:container    # future: FastAPI in a Cloudflare Container (Workers Paid)
```

Do not point `arisf1.tech` at the Worker while Pages is canonical.

---

## Manual steps only you can do

1. Confirm Heroku app URL and set `ARIS_FRONTEND_ORIGIN=https://arisf1.tech`.
2. Set Pages `NEXT_PUBLIC_API_BASE` to that Heroku origin and rebuild.
3. Confirm DNS for `arisf1.tech` is the Pages custom domain, TLS active.
4. Incognito: replay a race, toggle ARIS on, confirm ghost + Heroku `/api`.
