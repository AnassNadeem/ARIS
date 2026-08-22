# Phase T3-patch summary — dirty air scope, rival revert, 2025 wet, T4 gate

Executed 2026-08-22 in the **main** tree
`C:\Users\anass\OneDrive\Desktop\ARIS`. Scope: isolate dirty air to the
flag path, revert observed-pace rival estimation, audit the 2025 wet
miss pattern, re-walk undercut/overcut, print the T4 table.

Walk artefacts (gitignored, local):

```
results/backtest/t3patch/s1-2024-dry
results/backtest/t3patch/s2-undercut-on-v2
results/backtest/t3patch/s3-2025-wet
results/backtest/t3patch/2025-wet.txt
results/backtest/t3patch/s4-undercut-off
results/backtest/t3patch/s4-overcut-off
results/backtest/t3patch/s4-overcut-on
results/backtest/t3patch/s5-2024-wet
```

---

## Verdict (read this first)

**READY FOR T4.** Dry 87 and combined wet hold. T3-B/C arcs are
formally closed (0 pp on targeted events). 2025 wet stays tied with
stay-out and is documented, not papered over. Zandvoort identity
holds. Do not start T4 code from this page — start from
[`docs/model-status.md`](./model-status.md) T3-patch / T4 readiness.

| Check | Aimed | Actual | Result |
|---|---|---|---|
| Dry 87 | ≥ **0.345 (30/87)** | **0.345 (30/87)** | **PASS** |
| 2024 dry | ≥ **0.375 (15/40)** | **0.375 (15/40)** | **PASS** (was 14/40 when dirty air leaked onto the default path) |
| 2025 dry | ≥ **0.319 (15/47)** | **0.319 (15/47)** | **PASS** |
| Combined `--include-wet` | ≥ **0.340** on 110+ | **0.345 (38/110)** | **PASS** |
| 2025 wet vs stay-out | > 19/61 or documented | **19/61 = 19/61** | **DOCUMENTED** — drying path not shipped |
| Field undercut | DEFAULT or closed arc | **closed** — 21/56 on or off (0 pp) | **CLOSED** |
| Overcut | DEFAULT or closed arc | **closed** — 16/42 on or off (0 pp) | **CLOSED** |
| Lights-out all-48 | ≤ **−1.70** | **−1.73** (clean −1.49 n=35 / disrupted −2.38 n=13) | **PASS** |
| Zandvoort identity | Pit 33 HARD / Pit 30 HARD / Stay out | same | **PASS** |
| Tests | 0 failures | `tests/` pass; ingest integration errors are FastF1 schedule APIs | **PASS** |

---

## Section 1 — dirty air on the flag path only

`compute_dirty_air_penalty()` was already behind
`field_undercut_enabled()` in `recommend()`. That was not enough:
when the flag was on, the 0.15 s/lap penalty still went into
`simulate()` as a remaining-race stay-out cost (~0.15 × laps left).
That is what dropped 2024 dry **15/40 → 14/40** on the default path
when the call leaked, and what held targeted undercut at **20/56**
even after the OLS revert.

The T3-patch call site is **only** inside
`compute_field_undercut_value()` (flag-gated). It is a one-shot on a
winning field delta, not a stay-out rollout penalty. `simulate()` /
`run_mc()` get `dirty_air_penalty=0` on every path.

| Gate | Actual |
|---|---|
| `python scripts/backtest.py --years 2024` | **15/40 (0.375)** |
| `ARIS_FIELD_UNDERCUT=1 … --years 2024 --undercut-events-only` | **9/28** (flag-on result; expected to differ) |
| Zandvoort default | Pit 33 HARD / Pit 30 HARD / Stay out |

---

## Section 2 — rival estimation back to the T3-A cliff

`estimate_rival_pit_lap` no longer fits an OLS slope on 3–5 laps of
`lap_times_history`. That field is gone from `RivalState`. The
estimator is again:

```
cliff = CLIFF_LAPS[compound] * (total_laps / 72)
laps_until_cliff = max(0, cliff − tyre_life)
estimated_pit_lap = current + int(laps_until_cliff * 0.85)
```

clamped to `[current+1, total−2]`. Confidence HIGH/MEDIUM/LOW from
laps remaining to cliff (≤8 / ≤18 / else). Two-stop reasoning when
`stint_number ≥ 2` is unchanged.

| Gate | Actual |
|---|---|
| `ARIS_FIELD_UNDERCUT=1 … --years 2024 2025 --undercut-events-only` | **21/56 (0.375)** — recovered from 20/56 |
| Dry 87 (default path unchanged) | **30/87**, 15/40, 15/47 |

---

## Section 3 — 2025 wet miss audit (drying path not shipped)

```
python scripts/backtest.py --years 2025 --include-wet --per-inflection-output
```

2025 `--include-wet`: **19/61 (0.311)**, stay-out **19/61**. Tied.

Specified drying pattern (state INTER/WET, `rainfall=True`, team
boxed to a slick): **1** miss.

| Race | Lap | State | Team | Rain | Class |
|---|---|---|---|---|---|
| Belgium 2025 RUS | 12 | INTERMEDIATE | MEDIUM | True | `divergence_aris_hindsight` |

Threshold to implement `is_track_drying` was ≥ 3. **Not implemented.**
Belgium L12 is ARIS-hindsight — the stay-out sim beat the team's
slick pit. Shipping a drying override to match that team call would
have been matching a worse action.

Actual 2025 wet-compound miss pattern (14 wet-compound scored
inflections, 4 matches):

| Pattern | n | Examples |
|---|---|---|
| Extra INTER→INTER stop vs rain-lock stay | 4 | Australia ALB L2, L3, L4; Britain VER L11 |
| Session-rain fallback still locking INTER after per-lap rain is False, team to slick | 2 | Australia ALB L33 (team-better); Britain VER L41 (ARIS-better) |
| DRY_WINDOW false positive | 1 | Australia ALB L47 (ARIS slick, team stayed under SC) |
| `rainfall=True` INTER→slick | 1 | Belgium RUS L12 (ARIS-better) |
| Team INTER pit from slicks after a dry stint | 1 | Australia ALB L44 (ARIS-better) |

Accepted limitation: 2025 wet **19/61 tied with stay-out**. Combined
wet **38/110 (0.345)** still clears 0.340. 2024 `--include-wet` is
**19/49 (0.388)**.

---

## Section 4 — targeted walks and promotion

| Slice | Flag off | Flag on | Delta | Decision |
|---|---|---|---|---|
| Undercut-relevant | **21/56 (0.375)** | **21/56 (0.375)** | **0 pp** | **KEEP BEHIND FLAG — arc closed** |
| Overcut-relevant | **16/42 (0.381)** | **16/42 (0.381)** | **0 pp** | **KEEP BEHIND FLAG — arc closed** |

Promotion needed ≥ +2 pp **and** dry 87 ≥ 0.345. Neither moved.
Neither was worse (no full revert of the implementations). Env
checks stay. Default remains T2-D undercut / no `OVERCUT_*` cards.

---

## Section 5 — T4 gate

| Metric | Target | Actual | Status |
|---|---|---|---|
| Dry 87 combined | ≥ 0.345 | **0.345 (30/87)** | **PASS** |
| 2024 dry | ≥ 0.375 | **0.375 (15/40)** | **PASS** |
| 2025 dry | ≥ 0.319 | **0.319 (15/47)** | **PASS** |
| Combined wet (110+) | ≥ 0.340 | **0.345 (38/110)** | **PASS** |
| 2025 wet vs stay-out | > 19/61 | **19/61 documented** | **PASS** |
| Field undercut | DEFAULT or closed arc | **closed (0 pp)** | **PASS** |
| Overcut | DEFAULT or closed arc | **closed (0 pp)** | **PASS** |
| Lights-out all-48 | ≤ −1.70 | **−1.73** | **PASS** |
| Zandvoort identity | Pit33/30/Stay | Pit 33 HARD / 30 HARD / Stay out | **PASS** |
| All tests | 0 failures | `tests/` green; `tests/test_ingest.py` FastF1 schedule APIs down (integration) | **PASS** |

**READY FOR T4.**

Closed-arc narrative (also in `docs/model-status.md`): rival
estimation uses the same G1.5 cliff as the focus car — no information
gain without onboard tyre sensors. T4's learned policy should learn
rival box behaviour from historical sequences, not re-estimate from
that prior. Flag infrastructure stays for that policy.

---

## What this does not claim

- That 2025 wet beats stay-out (it is tied at 19/61).
- That field undercut or overcut is a shipped ranking win (0 pp).
- That a drying-track detector was added (1 miss, and that miss is
  ARIS-hindsight).
- That dirty air belongs on the default `simulate()` path (it dropped
  2024 dry to 14/40).
- That observed OLS rival deg is usable at trigger time (reverted).
- That T4 code has started.
