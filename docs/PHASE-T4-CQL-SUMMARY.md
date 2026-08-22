# Phase T4 summary — conservative Q-learning (CQL)

Executed 2026-08-23 in the **main** tree `C:\Users\anass\ARIS`.
Scope: pre-checks, then T4-A → T4-E → T4-B → T4-C → T4-D, with a
gate after each section. Locked decisions D1–D9 held. Default
`recommend()` scoring stays **physics**.

Every numeric result states aimed vs actual.

Headline commit (this page): T4-D + this summary.

| Commit | What |
|---|---|
| `884dd9a` | T4-A CQL dataset builder |
| `53c2cc7` | T4-E residual auto-train CLI + README setup |
| `69abab4` | T4-B CQL Q-network + training script |
| `663ee79` | T4-C CQL scoring in `recommend()` (default physics) |
| (this) | T4-D `--scoring` / `--cql-weight` walks + promotion decision |

Walk artefacts (gitignored, local): `results/backtest/t4d-cql/`,
`results/backtest/t4d-blend-w{0.2,0.4,0.5,0.6,0.8}/`, and the
`t4d-alpha05-*` / `t4d-alpha20-*` alpha retries.

```
python scripts/backtest.py --years 2024 2025 --scoring physics
python scripts/backtest.py --years 2024 2025 --scoring cql --out-dir results/backtest/t4d-cql
python scripts/backtest.py --years 2024 2025 --scoring blend --cql-weight 0.2 --out-dir results/backtest/t4d-blend-w0.2
```

---

## Verdict (read this first)

**T4 shipped as opt-in research scoring. It did not beat physics on
the dry 87.** Pure CQL is **6/87**. The best blend is a **tie** at
**30/87** (`w=0.2`, α=1.0). The gate to make blend the default is
**strictly greater than 30/87**. That gate **failed**. Default
`recommend(..., scoring="physics")` is unchanged.

If the race started tonight, the demo identity is still the T2
default (G1.5 + SC pit cost + T2-D undercut + approach trigger).
CQL is available as `scoring="cql"` or `scoring="blend"` when
`models/cql_q_network.pt` and `models/cql_normalisation.json` exist.
Missing weights fall back to physics silently. Torch is an optional
extra (`uv sync --extra cql`). Physics and CI do not import it.

| Check | Aimed | Actual | Result |
|---|---|---|---|
| Physics dry 87 | **30/87** (no regress) | **30/87** (15/40 + 15/47) | **PASS** |
| CQL dry 87 | report | **6/87** (−24 vs physics) | miss |
| Blend dry 87 | **> 30/87** to promote | best **30/87 @ w=0.2** | **GATE FAILED** |
| Alpha 0.5 / 2.0 retry | beat 30/87 | best still **30/87** (ties) | **GATE FAILED** |
| Default scoring | physics until gate | **physics** | **held** |
| Lights-out all 48 | ≤ −1.70 (only if blend promoted) | **−1.73** (unchanged; no promotion) | n/a for promotion |
| Wet 38/110 | only if blend promoted | not re-walked (default unchanged) | n/a |
| Zandvoort physics | Pit 33 HARD / Pit 30 HARD / Stay out | same | **PASS** |
| `pytest tests/` | 0 failures | **PASS** (exit 0) | **PASS** |
| Dataset N | honest; no wet padding | **62,711** | **PASS** (D9) |

---

## Results table (dry 87, α=1.0 unless noted)

| Mode | Match | Delta vs physics | Notes |
|---|---|---|---|
| Physics (baseline) | **30/87** | 0 | propose-cache path; 2024 15/40, 2025 15/47 |
| CQL | **6/87** | −24 | 2024 4/40, 2025 2/47 |
| Blend w=0.2 | **30/87** | 0 | best α=1.0 blend; **tie, not promote** |
| Blend w=0.4 | **29/87** | −1 | |
| Blend w=0.5 | **29/87** | −1 | |
| Blend w=0.6 | **28/87** | −2 | |
| Blend w=0.8 | **27/87** | −3 | |
| CQL α=0.5 | **5/87** | −25 | worse than α=1.0 |
| Blend α=0.5 w=0.2 | **30/87** | 0 | tie |
| Blend α=0.5 w=0.5 | **30/87** | 0 | 2024 16/40, 2025 14/47; still a tie |
| CQL α=2.0 | **6/87** | −24 | same as α=1.0 CQL |
| Blend α=2.0 w=0.2 | **30/87** | 0 | tie |
| Blend α=2.0 w=0.4 | **30/87** | 0 | 2024 16/40; still a tie |
| Best alpha retry | **30/87** | 0 | no configuration > 30/87 |

---

## Per-action breakdown (α=1.0, dry 87)

Team action class vs physics recommend-at-inflection and CQL rank-1.
Physics column sums to **30/87** (same headline as the propose-cache
walk). CQL never matches a stay-out inflection.

| Action class | n | Physics correct | CQL correct |
|---|---|---|---|
| STAY_OUT | 24 | **7/24** | **0/24** |
| PIT_S | 7 | 0/7 | 0/7 |
| PIT_M | 14 | 0/14 | 1/14 |
| PIT_H | 42 | **23/42** | **5/42** |
| PIT_OTHER | 0 | — | — |
| **Total** | **87** | **30/87** | **6/87** |

Where CQL helps: one extra PIT_M match. Where it hurts: all 7 physics
stay-out hits, and 18 of the 23 physics HARD-pit hits. Higher blend
weights trade stay-out matches for a few extra HARD pits and lose
overall (w=0.8: CQL-side stay 0/24, HARD 27/42, total 27/87).

---

## Dataset (T4-A) — actual N

`data/cql_dataset.parquet` (gitignored): **62,711** transitions.

| | |
|---|---|
| Years | 2018–2023 (`REFERENCE_RACES`) |
| Filter | P1–P10 classified finishers; drop lap 1, last lap, out-laps, TrackStatus `'5'`, INTER/WET current compound |
| Keep | SC/VSC 4/6/7; session-rainfall **dry** laps |
| Action (D1) | in-lap (`PitInTime`) → `PIT_*` from **next** compound; out-laps dropped |
| Reward (D2) | `return_g = 0.95^(T − t) * finish_pos`; MSE; no bootstrap |
| Sessions skipped | **0** (load failures logged and continued) |

Action distribution:

| Action | n | pct |
|---|---|---|
| 0 STAY_OUT | 60,966 | **97.22%** |
| 1 SOFT | 465 | 0.74% |
| 2 MEDIUM | 528 | 0.84% |
| 3 HARD | 713 | 1.14% |
| 4 INTERMEDIATE | 38 | 0.06% |
| 5 WET | 1 | 0.00% |

Year distribution: 2018 10,803 · 2019 10,898 · 2020 8,513 · 2021
10,705 · 2022 10,473 · 2023 11,319.

2018–2019 smoke set (`data/cql_dataset_test.parquet`): N=21,701,
pits > 0, STAY_OUT **97.6%** — **0.6 pp above** the planned 88–97%
band. Honest rate after dropping last lap / red / wet / out-laps.
Not padded with wet laps (D9).

---

## Training (T4-B)

Architecture: 2-layer MLP 128–128, dropout 0.1, 6 actions, 18-d
state. CQL loss = MSE(Q(s,a), G_t) + α logsumexp penalty. No s'
bootstrap.

| | α=1.0 (shipped weights) | α=0.5 | α=2.0 |
|---|---|---|---|
| Train / val rows | 51,392 / 11,319 | same split | same split |
| Val years | 2023 | 2023 | 2023 |
| Best val | **0.9246 @ epoch 34** | 0.8039 @ 18 | 1.1169 @ 34 |
| Q[STAY_OUT] | [0.052, 8.324] | [0.012, 8.036] | [−0.017, 8.298] |
| Q[PIT_HARD] | [−8.825, 3.232] | [−6.752, 3.785] | [−9.646, 2.904] |
| Val argmax | 11,312 stay / 5 hard / 2 med | 11,312 stay | 11,319 stay |

Normalisation: train-set mean/std on continuous indices
`[4,5,6,7,8,9,10,14,15,16]`, then clip ±3. Saved to
`models/cql_normalisation.json` (gitignored).

10-epoch smoke on the 2018–2019 parquet passed (Q ranges differed).

---

## Integration (T4-C / T4-D)

- `recommend(..., *, scoring="physics", cql_weight=0.5)` — keyword-only,
  return type unchanged (`RecommendationResult`).
- Wet lock still returns before any CQL scoring.
- Physics delta always computed. Rank key is
  `(rank_score, delta_vs_stay_out_s)` (D4).
- `scoring != "physics"` **must not** use `DecisionQueue.propose()`
  cache. T4-D rebuilds `FieldState` at the inflection lap and calls
  `recommend()` directly so CQL and physics numbers compare.
- Per-action table prints whenever `--scoring` is set.

---

## Why the gate failed (honest)

1. **Class imbalance.** 97% of offline transitions are STAY_OUT. The
   Q-network’s val argmax is almost always stay, but ranking uses
   `Q(s,a) − Q(s, STAY_OUT)` with **lower Q = better finish_pos**.
   At Zandvoort, both HARD cards score `cql_q_delta ≈ −4.5` vs stay
   `0.0`, so CQL prefers pit whenever a pit card exists. That wipes
   stay-out matches (0/24).
2. **Scale mismatch.** Physics `delta_vs_stay_out_s` is seconds.
   `cql_q_delta` is a Q-unit (~few). Low blend weight collapses to
   physics (30/87). High weight inherits CQL’s pit bias.
3. **α does not fix the reward.** finish_pos MC return (D2) is a
   sparse outcome shared by every lap of a driver-race. It does not
   teach *when* to box. Changing α from 0.5 to 2.0 moved pure CQL
   between 5/87 and 6/87.

This is not a walk bug. The uncached physics recommend-at-inflection
column on the CQL walk is **30/87**, matching the propose-cache
headline.

---

## Flags (no locked decision changed)

1. FastF1 live schedule backends were down at pre-check (`idna` was a
   broken namespace). Dataset/residual load uses pickle-cache
   reconstruction (`src/aris/io/fastf1_session.py`). `idna` was
   reinstalled to 3.19 during T4-D; later FastF1 schedule loads
   succeeded.
2. `ClassifiedPosition` is empty when Ergast is down. Finisher filter
   falls back to FastF1 timing `Position`.
3. Vintage 2018 compounds (ULTRASOFT/SUPERSOFT/HYPERSOFT/SUPERHARD)
   and C1–C5 are mapped onto SOFT/MEDIUM/HARD so in-laps stay `PIT_*`
   (D1).
4. Gap-ahead is **driver cumulative − car-ahead cumulative**, capped
   `[0, 22]`, P1 → 22. Spec shorthand subtracted the other way and
   would clamp every gap to 0.
5. STAY_OUT rate **97.2%** vs the planned 88–97% band on 2018–2019.
   Honest; not padded (D9).
6. T4-E trained a 2018-only residual to pass the recreate gate, then
   **restored** production `models/residual_xgb.json` so T4-D could
   not drift.
7. Official `--scoring physics` 55-minute walk was not re-run after
   the T4-D flag landed. Physics **30/87** is the pre-check
   propose-cache walk plus the uncached physics column on every
   CQL/blend walk (also 30/87).

---

## T4-E residual CLI

`scripts/train_residual.py --years` / `--output`. No-flag behaviour
unchanged. README “First-time setup” block added. Gate: 2018-only
file recreated; Zandvoort identity held; production residual
restored.

---

## Artefacts (local, gitignored)

| Path | Status |
|---|---|
| `data/cql_dataset.parquet` | **62,711** rows |
| `models/cql_q_network.pt` | exists (α=1.0, best epoch 34) |
| `models/cql_normalisation.json` | exists |
| `models/cql_q_network_test.pt` | smoke only; **not committed** |

---

## What this does not claim

- That CQL is a better ranker than physics on 2024–2025 dry inflections.
- That blend @ w=0.2 is an improvement. It is a **tie**.
- That finish_pos is the wrong reward to try later — only that **this**
  MC return, with this imbalance, did not clear the ship gate.
- That the physics 30/87 moved. It did not.
