# Zandvoort 2026 weekend runbook

**Event:** 2026 Dutch Grand Prix — Circuit Zandvoort  
**Dates:** Friday 21 – Sunday 23 August 2026  
**Format:** **Sprint weekend** — `FP1 → Sprint Qualifying (SQ) → Sprint (S) → Qualifying (Q) → Race (R)`.  
There is **no FP2 and no FP3**.

Prerequisite: Docker Postgres up, `ARIS_DB_URL` set, venv active, `PYTHONPATH=src`.

```powershell
cd C:\Users\anass\OneDrive\Desktop\ARIS
$env:ARIS_DB_URL = "postgresql+psycopg://aris:aris_local_dev_pw@127.0.0.1:5432/aris"
$env:PYTHONPATH = "src"
```

---

## Live tyre-slope write policy (read this)

**Default during the weekend: observe / log only — never auto-write YAML.**

`scripts/fit_zandvoort_tire_slopes.py` prints blended slopes and writes
`results/e1_zandvoort_deg_stints.csv`. It does **not** touch
`data/tracks/netherlands.yaml` unless you pass `--write`.

During the event window (**2026-08-21 … 2026-08-23**), `--write` alone is
**refused**. An explicit `--allow-live-write` is also required:

```powershell
# Normal weekend ops — log only (safe default):
.\.venv\Scripts\python.exe scripts\fit_zandvoort_tire_slopes.py

# Deliberate mid-weekend YAML overwrite (rare; restart Streamlit after):
.\.venv\Scripts\python.exe scripts\fit_zandvoort_tire_slopes.py --write --allow-live-write
```

Under normal circumstances the runbook does **not** instruct writing live.
Keep the pre-weekend `compound_slopes` in YAML; compare session blends against
them via `blend_slope_prior` / the CSV, and only overwrite if Anas explicitly
accepts a large, coherent shift.

---

## FastF1 timing expectations

| After session ends | Typical FastF1 availability |
|---|---|
| Timing / lap data | Often **5–20 minutes** (sometimes longer if F1 API is slow) |
| Weather | Usually with the same load |
| Telemetry | Can lag further; **not required** for Strategy UI / tyre prior refresh |

If `ingest_session` fails with empty/missing data, wait 10 minutes and retry — ingest is idempotent (`ON CONFLICT DO NOTHING`).

---

## Exact command sequence (run after each session)

### 1. After FP1 (Friday)

```powershell
.\.venv\Scripts\python.exe scripts\ingest_session.py 2026 Netherlands FP1
```

Optional — **log** Zandvoort tyre slopes using FP1 long runs against the track prior
(**do not** pass `--write` under normal ops):

```powershell
.\.venv\Scripts\python.exe scripts\fit_zandvoort_tire_slopes.py
# Inspect results/e1_zandvoort_deg_stints.csv; live blend helper is
# aris.physics.tires.blend_slope_prior(prior_mean, prior_var, obs_mean, obs_var)
```

**Fallback note:** tyre degradation for this weekend uses **FP1 + Sprint (S)** long runs — there is no FP2. The historical Zandvoort prior in `data/tracks/netherlands.yaml` (`compound_slopes`) remains the baseline; do not overwrite it mid-weekend unless explicitly approved (see write policy above).

Confirm Strategy UI can see the session: start Streamlit → Strategy page → season 2026 → Netherlands weekend sessions listed.

```powershell
.\.venv\Scripts\streamlit.exe run apps/pages/01_Strategy.py
```

### 2. After Sprint Qualifying (SQ)

```powershell
.\.venv\Scripts\python.exe scripts\ingest_session.py 2026 Netherlands SQ
```

Open Strategy → weekend form should pick up SQ pace if Q is not yet in (see `weekend_form` fallback).

### 3. After Sprint (S)

```powershell
.\.venv\Scripts\python.exe scripts\ingest_session.py 2026 Netherlands S
```

Sprint long runs are the best same-weekend degradation sample. Re-run the fit script in **log-only** mode if you want a same-weekend comparison before race day — still no YAML write by default.

### 4. After Qualifying (Q)

```powershell
.\.venv\Scripts\python.exe scripts\ingest_session.py 2026 Netherlands Q
```

Refresh Strategy UI (Start / Reset session) so prewrite strat cards and weekend form use Q.

### 5. After Race (R) — or full weekend catch-up

Single session:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_session.py 2026 Netherlands R
```

Or ingest the **entire sprint weekend** in one go (skips FP2/FP3 by design):

```powershell
.\.venv\Scripts\python.exe scripts\ingest_weekend.py 2026 Netherlands --sprint
# or auto-detect (probes FP2; if missing → sprint list):
.\.venv\Scripts\python.exe scripts\ingest_weekend.py 2026 Netherlands --auto
```

Then in Strategy UI: Start / Reset → lock a strat → live clock → Watch / Ask / What-if → postrace.

---

## Sanity checks (do these once after FP1 and again after Q)

1. `netherlands.yaml` still has `total_laps: 72`, `pit_loss_s: 18.5`, and `compound_slopes`.
2. Prewrite windows for 72 laps should look like **A≈18 / B≈29 / C≈18+40** (pit-loss nudge can move these by a lap).
3. Headless smoke (optional):

```powershell
.\.venv\Scripts\python.exe scripts\_e1_smoke_strategy_zandvoort.py
```

(Update the script’s year to 2026 once that race is in the DB, or point it at the new session_id.)

---

## Do **not** do live under time pressure

- Do not retrain the residual XGBoost mid-weekend unless Phase E.2 work is explicitly approved.
- Do not re-derive pit_loss from a single sprint-session sample — keep the multi-year 18.5 s figure unless Race data clearly disagrees after the event.
- Do not fall back to Bahrain defaults: if `load_track_config("Netherlands")` ever returns 57 laps / 21 s pit, stop and fix YAML matching before demoing.
- Do not `--write` tyre slopes into `netherlands.yaml` mid-weekend under normal ops (see live-write policy).
