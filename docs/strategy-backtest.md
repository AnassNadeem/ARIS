# Strategy backtest — 2024 walk-forward

Walk-forward of ARIS recommendations over the **full 24-race 2024 held-out
calendar** (the same set scored in Phase E), in chronological order. Not a
Zandvoort-event deliverable. Artefacts: `results/backtest/2024_summary.json`,
`results/backtest/2024_full.json`, JSONL under `results/decisions/`.

Replay architecture: [`docs/replay-architecture.md`](./replay-architecture.md).
The walker ticks `SectorClock` + `check_triggers` + `recommend()`; it does not
reimplement temporal cutoff.

---

## Verdict (read this first)

**ARIS does not beat a naive always-stay-out policy on decision match-rate.**

| Metric | Aimed | Actual | Result |
|---|---|---:|---|
| Decision match-rate (scored inflections) | **> 0.250** (always-stay-out on the same 40 scored events) | **0.125** (5/40) | **MISS** |
| Mean position-delta (ARIS pos − actual P5) | **≤ 0** (same or better) | **+2.58** | **MISS** (about 2.6 places worse) |

That is the result. It is still the most defensible strategy artefact in the
repo: a leakage-safe walk of 24 held-out races against two naive baselines,
with insufficient-information called out instead of forced into match/mismatch.

---

## Method

### Calendar and cutoff

All 24 Phase E held-out races, round 1→24. Each tick uses `FieldState.from_laps`
/ `build_race_state` (lags from laps **before** the current lap). ARIS pits are
**not** committed — the walker observes the real race.

`recommend()` ranking used deterministic `simulate()` (`mc_draws=0`). Live demo
still uses MC draws=100. Identity of the top action (pit vs stay, lap,
compound) is what this eval scores, not percentile bands.

Elapsed: **4024 s** (~67 min) for 24 races.

### Reference driver (outcome)

**Classified P5** at every race (always existed here). P5 can finish better or
worse after a counterfactual; P1 cannot finish “better.”

### Outcome comparison

Lights-out strategy = the prewrite plan `generate_strat_plans` marks
`recommended=True` (what the Strategy page would lock). Simulated from lap 1
with the same physics as the team’s actual pit schedule. Physics bias cancels:

`adjusted_time = actual_race_time + (ARIS_sim − team_sim)`

then re-rank against other drivers’ **actual** race times.

Position-delta = `aris_finish_pos − actual_finish_pos`. Negative = ARIS better.

### Decision comparison

Inflection points from the reference driver’s laps: **pit-in**, **SC/VSC period
start**, leftover compound changes. At that lap, `recommend()` using only data
up to that point.

| Class | Meaning |
|---|---|
| `match` | Top rec is a pit within ±2 laps **and** same dry compound, or explicit stay-out when the team did not box |
| `divergence_aris_hindsight` | Not a match; re-sim remaining race ≥2 s faster on ARIS’s action |
| `divergence_team_hindsight` | Not a match; team action simulates as good or better |
| `divergence_insufficient_info` | Rainfall flag, wet compound, or red-flag status — **excluded from match-rate** |

**Stay-out coding used in the 5/40 figure:** lift/brake as top rec counted as
stay (they are not a box). **Stricter reading:** only `Stay out on current tyres`
counts as a stay call. That drops two SC “matches” (Australia Brake T7, Miami
Brake T10) → **3/40 = 0.075**. Both numbers are below the 0.250 floor.

### Proposed match-rate target

**Aimed: strictly greater than always-stay-out on the same scored set.**

Always-stay-out matches every non-pit inflection and misses every pit. On this
set that is **10/40 = 0.250**. A system that never boxes cannot be a
strategist; beating that floor is the minimum evidence of pit-call skill.

Copy-last-year (same driver, 2023 pits within ±2 laps) printed **7/28 = 0.250**
but is **not trusted**: FastF1 hit a 503 on the 2023 schedule and remapped at
least Emilia Romagna→Belgium and China→Canada. 2023 is not in the local DB.
Primary baseline is always-stay-out.

---

## Rolling 5-race averages

Window = last five **calendar** races. Match-rate average skips races with
zero scored inflections (wet/rainfall flagged); position-delta uses all five.

| End | GP | Rolling match-rate | Rolling pos-delta | Scored races in window |
|---|---|---:|---:|---:|
| R01 | Bahrain | 0.000 | −2.00 | 1/1 |
| R02 | Saudi Arabia | 0.000 | −0.50 | 2/2 |
| R03 | Australia | 0.083 | +2.67 | 3/3 |
| R04 | Japan | 0.062 | +1.25 | 4/4 |
| R05 | China | 0.050 | +1.60 | 5/5 |
| R06 | Miami | 0.117 | +2.20 | 5/5 |
| R07 | Emilia Romagna | 0.117 | +2.40 | 5/5 |
| R08 | Monaco | 0.083 | −0.20 | 4/5 |
| R09 | Canada | 0.111 | +0.60 | 3/5 |
| R10 | Spain | 0.167 | +3.00 | 2/5 |
| R11 | Austria | 0.000 | +3.60 | 1/5 |
| R12 | Britain | n/a | +2.60 | 0/5 |
| R13 | Hungary | 0.000 | +3.20 | 1/5 |
| R14 | Belgium | 0.250 | +2.40 | 2/5 |
| R15 | Netherlands | 0.167 | +0.60 | 3/5 |
| R16 | Italy | 0.125 | −0.20 | 4/5 |
| R17 | Azerbaijan | **0.233** | +0.40 | 5/5 |
| R18 | Singapore | 0.233 | +2.20 | 5/5 |
| R19 | United States | 0.133 | +4.20 | 5/5 |
| R20 | Mexico City | 0.133 | +4.40 | 5/5 |
| R21 | Sao Paulo | 0.167 | +4.20 | 4/5 |
| R22 | Las Vegas | 0.000 | +4.40 | 4/5 |
| R23 | Qatar | 0.000 | +4.00 | 4/5 |
| R24 | Abu Dhabi | **0.000** | **+4.20** | 4/5 |

Peak rolling match-rate is **0.250** at Belgium (equals the naive floor, does
not beat it). The walk **ends** at 0.000 match and **+4.2** positions.

---

## Decision-level counts (all 24 races)

61 inflections (42 pit, 19 SC/VSC starts).

| Class | n | Share of 61 |
|---|---:|---:|
| match | 5 | 8% |
| divergence_aris_hindsight | 33 | 54% |
| divergence_team_hindsight | 2 | 3% |
| divergence_insufficient_info | 21 | 34% |

Scored (ex-info-gap): **5 match / 33 ARIS-hindsight / 2 team-hindsight**.

The five matches: Belgium NOR pit-now HARD; Azerbaijan VER pit-now HARD;
Azerbaijan VER stay-out at SC L50; Australia PER Brake T7 at SC (line-action
counted as stay); Miami SAI Brake T10 at SC (same).

The 33/2 hindsight split is **one-sided**. Re-sim often prefers ARIS’s later
SOFT/MEDIUM stop over the team’s HARD by tens of seconds of remaining-race
time. That is as likely the known physics/tyre-slope bias as genuine missed
undercuts. It is **not** evidence that ARIS would have scored more points.

Insufficient-info races were mostly `session_weather.rainfall=True` (Canada,
Spain, Austria, Britain, São Paulo). Spain 2024’s race was dry — FastF1’s
rainfall bit can fire on any session moisture. Monaco was `rainfall=False` but
still unscored (red-flag / status-5 path).

---

## Outcome-level (P5, physics-cancelled re-rank)

Mean delta **+2.58** places (aimed ≤ 0). ARIS’s locked prewrite plan would have
put the P5 car **worse** more often than better.

Better (negative delta): Bahrain −2, Japan −3, Monaco −4, Britain −3, Hungary
−1, Belgium −3, São Paulo −1. Worse examples: Australia +9, Spain +15,
Singapore +8, Abu Dhabi +8. Italy and Azerbaijan were 0.

Spain +15 is exactly why the metric is a rolling 5-race average, not a single
headline race.

---

## What this does and does not claim

Does: ARIS can walk 24 held-out races with the live cutoff, log every
propose/resolve, and compare calls to what the team did.

Does not: beat stay-out, copy last year, or improve classified P5. The
recommender’s top action at real pit/SC moments is usually not the team’s
call, and the lights-out prewrite plan does not rank the P5 car ahead of
reality after bias-cancelling.

---

## How to re-run

```powershell
docker compose up -d
python scripts\backtest.py          # all 24; --limit N is debug-only
```
