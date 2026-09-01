# Legacy — Streamlit Cloud + Neon (Phase 2 lap explorer)

This is the Phase 2 runbook. The canonical production app is the Next.js
console + Heroku API; see [`DEPLOY.md`](../DEPLOY.md). Keep this file if the
Streamlit lap explorer should stay live somewhere.

What this doc covers: provisioning the managed Postgres, pushing the schema
and ingest to it, then deploying `apps/streamlit_app.py` to Streamlit
Community Cloud. Everything that has to be done in a browser is called out
explicitly — every CLI step is copy-pasteable on Windows PowerShell.

The path of least friction: **Neon free tier** (managed Postgres, 0.5 GB,
always-on branch) + **Streamlit Community Cloud** (free, GitHub-linked, reads
this repo on push to `main`). Static-parquet fallback is documented at the
bottom for the eviction case.

---

## Pre-reqs

- Neon account (free, GitHub login): https://neon.tech
- Streamlit Community Cloud account (free, GitHub login): https://share.streamlit.io
- This repo pushed to GitHub on `main` (already true)
- Local Postgres running (`docker compose up -d`) so the same ingest path can
  fall back to local if Neon misbehaves

---

## Step 1 — Provision Neon Postgres (5 min, **browser, you**)

1. Sign in at https://console.neon.tech.
2. **New project** → name `aris`, region pick the one nearest you (eu-west-2
   if UK), Postgres 16.
3. After provisioning Neon shows a connection string of the shape
   `postgresql://USER:PASSWORD@ep-xxxx.eu-west-2.aws.neon.tech/aris`.
   - Click **Show password** and copy the full string.
   - Replace the leading `postgresql://` with `postgresql+psycopg://` so
     SQLAlchemy uses the psycopg3 driver this repo depends on.
   - Append `?sslmode=require` (Neon requires TLS).
   - Save the final string to your password manager. This is the value that
     goes into both `.env.cloud` (next step) and Streamlit Cloud's secrets.

Final string shape:

```
postgresql+psycopg://USER:PASSWORD@ep-xxxx.eu-west-2.aws.neon.tech/aris?sslmode=require
```

---

## Step 2 — Push schema + ingest to Neon (15 min, **PowerShell, me/you**)

Create a separate env file so the cloud creds never collide with local dev:

```powershell
# in the repo root
Copy-Item .env.example .env.cloud
# then edit .env.cloud and replace ARIS_DB_URL with the Neon string from Step 1
notepad .env.cloud
```

Apply the schema. Neon doesn't ship `psql` access by default, but the same
SQLAlchemy engine we use everywhere can run the file:

```powershell
$env:ARIS_DB_URL = (Select-String -Path .env.cloud -Pattern '^ARIS_DB_URL=' -SimpleMatch).Line -replace '^ARIS_DB_URL=', ''
python -c "from sqlalchemy import create_engine, text; import os; e=create_engine(os.environ['ARIS_DB_URL']); sql=open('db/schema.sql').read();
import re
# psycopg can't run a multi-statement DDL blob in one execute; split on `;` boundaries that end a line.
stmts=[s.strip() for s in re.split(r';\s*\n', sql) if s.strip()]
with e.begin() as c:
    for s in stmts:
        c.execute(text(s))
print('schema applied:', len(stmts), 'statements')"
```

Run the season ingest against Neon (this is the same script that ran for the
local DB on Day 3, just pointed at a different `ARIS_DB_URL`):

```powershell
python scripts/ingest_season.py 2024
```

Expect: 24 rounds, +25,475 laps, ~5–10 min depending on FastF1 cache state
and Neon round-trip latency. Telemetry stays out (size constraint on the free
tier — the table exists, but population is Wk 4 work).

Sanity check from the same shell:

```powershell
python -c "from sqlalchemy import create_engine, text; import os; e=create_engine(os.environ['ARIS_DB_URL']);
with e.connect() as c:
    print('sessions:', c.execute(text('select count(*) from sessions')).scalar())
    print('drivers :', c.execute(text('select count(*) from drivers')).scalar())
    print('laps    :', c.execute(text('select count(*) from laps')).scalar())"
```

Expect roughly `sessions: 24, drivers: ~24, laps: ~25500`.

---

## Step 3 — Configure Streamlit Cloud secrets (3 min, **browser, you**)

1. https://share.streamlit.io → **New app**.
2. Repo `AnassNadeem/ARIS`, branch `main`, main file path
   `apps/streamlit_app.py`.
3. Click **Advanced settings** before deploying.
   - **Python version:** 3.11.
   - **Secrets:** paste exactly one line, using the Neon URL from Step 1:

     ```toml
     ARIS_DB_URL = "postgresql+psycopg://USER:PASSWORD@ep-xxxx.eu-west-2.aws.neon.tech/aris?sslmode=require"
     ```

4. **Deploy**.

The shape of `apps/streamlit_app.py` already reads `st.secrets["ARIS_DB_URL"]`
into `os.environ` before importing `aris.io.db` — no app-side code changes
needed.

---

## Step 4 — Watch the build, fix the first failure (5–20 min, **browser**)

Streamlit Cloud streams a build log. The two failures we expect from
experience:

- **Missing system lib for `psycopg[binary]`** — `psycopg[binary]` ships its
  own wheel, so this is rare. If you see `Error: pg_config executable not
  found`, the wheel didn't resolve; switch the line in `apps/requirements.txt`
  to `psycopg[binary]==3.2.3` (pin) and redeploy.
- **`ModuleNotFoundError: aris`** — `apps/streamlit_app.py` puts `src/` on
  `sys.path` already, so this means the working directory isn't repo-root.
  Streamlit Cloud's working dir IS repo-root, but if the error shows up
  anyway, add `src/aris -> apps/aris` symlink or change the path
  computation. Hasn't bitten us yet.

When the build is green, the URL is `https://<random-slug>-aris.streamlit.app`.
Rename the slug under **Settings → General → Custom subdomain** to something
clean, e.g. `aris-f1`.

---

## Step 5 — Verify in incognito (2 min, **browser, you**)

Open the URL in an incognito window:

- Three dropdowns render: Season, Race, Driver.
- Selecting 2024 → R1 Bahrain → VER renders a lap-time chart.
- The MA(2) MAE caption shows a number between 0.2 and 2.5 s.

If all three pass, the deploy is real and Phase 2's "someone outside the
laptop can verify the data pipeline" criterion is met.

---

## Fallback — static parquet snapshot (only if Neon eats >2 hr)

If Step 2 hits a Neon-side blocker that can't be untangled in two hours, fall
back to a static-parquet demo:

```powershell
python -c "from aris.io import db; import pandas as pd;
with db.engine().connect() as c:
    pd.read_sql('select * from sessions', c).to_parquet('data/processed/sessions.parquet')
    pd.read_sql('select * from drivers', c).to_parquet('data/processed/drivers.parquet')
    pd.read_sql('select session_id, driver_id, lap_number, lap_time_s, compound, tyre_life, stint, pit_in, pit_out from laps', c).to_parquet('data/processed/laps.parquet')"
```

Then patch `apps/streamlit_app.py` to read parquet via `pd.read_parquet`
instead of going through `aris.io.db`. Flag that "live ingest" reverts to
"static snapshot" for the week.

---

## Manual steps summary (what only you can do)

1. Create the Neon project and copy the connection string.
2. Paste that string into Streamlit Cloud → Settings → Secrets as
   `ARIS_DB_URL = "..."`.
3. Click **Deploy** and watch the first build go green.
4. Open the URL in incognito and confirm the chart renders.
5. (Optional) Set a clean custom subdomain.
