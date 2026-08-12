# Zandvoort 2026 — day-of checklist

**Print this.** Full detail: `docs/zandvoort-weekend-runbook.md`.

Prerequisite (once at start of Friday):

```powershell
cd C:\Users\anass\OneDrive\Desktop\ARIS
$env:ARIS_DB_URL = "postgresql+psycopg://aris:aris_local_dev_pw@127.0.0.1:5432/aris"
$env:PYTHONPATH = "src"
# Docker Postgres up; venv active
```

**Tyre YAML:** observe/log only. Do **not** `--write` mid-weekend unless Anas explicitly approves (`--write --allow-live-write` required Fri–Sun 21–23 Aug).

---

## After each session ends

Wait ~5–20 min for FastF1 timing, then:

| Session | Command | Then |
|---|---|---|
| **FP1** | `.\.venv\Scripts\python.exe scripts\ingest_session.py 2026 Netherlands FP1` | Optional log-only: `scripts\fit_zandvoort_tire_slopes.py` (no `--write`). Open Strategy UI → 2026 Netherlands visible. |
| **SQ** | `...\ingest_session.py 2026 Netherlands SQ` | Strategy → weekend form shows SQ pace. |
| **Sprint** | `...\ingest_session.py 2026 Netherlands S` | Optional log-only tyre fit again. |
| **Q** | `...\ingest_session.py 2026 Netherlands Q` | Strategy → Start/Reset → confirm prewrite windows ≈ **18 / 29 / 18+40**. |
| **Race** | `...\ingest_session.py 2026 Netherlands R` | Lock strat → live clock → Watch/Ask/What-if → postrace. |

Catch-up whole weekend:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_weekend.py 2026 Netherlands --sprint
```

---

## Quick sanity (after FP1 and again after Q)

1. `netherlands.yaml`: `total_laps: 72`, `pit_loss_s: 18.5`, `compound_slopes` present.
2. Strategy does **not** show Bahrain defaults (57 laps / 21 s pit).
3. Ingest errors loudly if FastF1 empty — **retry later**; do not force.

## Do not under time pressure

- Retrain residual mid-weekend  
- Rewrite tyre YAML mid-weekend  
- Re-derive pit_loss from one sprint sample  

---

*If anything looks wrong, stop and open the full runbook before improvising.*
