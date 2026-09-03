# Cloudflare hosting notes

Canonical production is **not** this Worker:

- **UI:** Cloudflare Pages, `frontend-next/` static export, custom domain `https://arisf1.tech`
- **API:** Heroku (`Procfile` → `uvicorn backend.main:app`)
- **Replay packs:** Cloudflare R2 (`prebuild_race.yml`)
- **Postgres:** Neon, via Heroku `DATABASE_URL`

See [`DEPLOY.md`](../../DEPLOY.md) for the runbook.

## What this folder is for

`worker.ts` + `../cloudflare-worker/wrangler.jsonc` can still publish the Next
static export as Workers assets (`frontend-next/out`) if you want a Worker URL.
`/api` on that Worker is a proxy: in production it is unused (the browser calls
Heroku via `NEXT_PUBLIC_API_BASE`). `API_ORIGIN` is only for **local-dev
tunneling**.

## Local-dev tunnel (not production)

`powershell -File scripts/aris-home-tunnel.ps1` is a laptop convenience. It is
not the production API. Production FastAPI runs on Heroku.

Local UI: `npm run dev` in `frontend-next/`. Vite is gone from this tree
(`legacy-vite-frontend` branch). uvicorn on 8765; Next rewrites `/api` there.

## Future option — Workers Paid + Container

`../cloudflare-worker/wrangler.containers.jsonc` + `worker.container.ts` +
`npm run deploy:container` (from `deploy/cloudflare-worker/`) would run FastAPI
inside a Cloudflare Container. That needs the **Workers Paid** plan. It is
**not** the current host. Keep the files; do not treat them as live.
