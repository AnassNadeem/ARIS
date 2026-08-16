# Phase G.5 summary — close the tyre-degradation thread

Executed 2026-08-15. Scope: Blocks G5.1–G5.4. Confirm G4 did not regress
the demo, write the interview account of G1–G4, scope (do not build) the
cornering-load proxy, lock G1.5 explicitly. No fifth unconstrained fit
on lap time. No default-path change beyond the lock note.

---

## Verdict (read this first)

G4's production edits did **not** move the Zandvoort smoke. Recommend
identity still matches the original E4.1 lock exactly. What-if/MC remain
G1.4 (physics-delta kept), not G2 and not a restore of E4.1 −13.00 s.

G1.5 (global slopes SOFT 0.08 / MEDIUM 0.05 / HARD 0.03 + G1.4
physics-delta) is now an **explicit lock**, not a default-by-omission.
The investigation is closed for the event. The one different idea
(estimated cornering load) is a design doc for later.

| Metric | Aimed | Actual | Result |
|---|---|---|---|
| Zandvoort smoke vs E4.1 recommend identity | Pit lap 33 HARD / Pit lap 30 HARD / Stay out | Pit lap 33 HARD / Pit lap 30 HARD / Stay out | **PASS** |
| Track slopes H/M/S (no overlay) | 0.08 / 0.05 / 0.03 | 0.08 / 0.05 / 0.03 | **PASS** |
| What-if / MC vs G2 | not G2 −2.34 / −137.96/+38.92 | **−11.92 s**, P10/P90 **−147.55 / +29.33** (G1.4) | **PASS** |
| `docs/tyre-degradation-research.md` | G1–G4 arc + AWS/sensor vs lap-time ceiling | written | **PASS** |
| `docs/future-research-cornering-load.md` | design only, not code | written; no implementation | **PASS** |
| G1.5 locked in README + `load_track_config` | explicit, not provisional | both | **PASS** |
| Cornering-load proxy built | **no** | not built | **PASS** |
| Full pytest | green | **230 passed**, 0 failed | **PASS** |

---

## G5.1 — Zandvoort smoke (non-negotiable)

G4 touched `traffic.py`, residual/pooled features, and overlay wiring
even though `ARIS_TRUE_COMPOUND_SLOPES=pooled` is off by default. Same
discipline as G3.1: re-run `scripts/_e1_smoke_strategy_zandvoort.py`
with the overlay unset.

**SMOKE OK.** Log: `results/g5/zandvoort_smoke.log`. Driver VER,
session_id 123, 2025 Netherlands.

| Check | Aimed / locked (E4.1) | G5.1 actual | vs lock | vs G2 |
|---|---|---|---|---|
| Track laps / pit | 72 / 18.5 | 72 / 18.5 | **PASS** | same |
| Track slopes H/M/S | **0.08 / 0.05 / 0.03** | **0.08 / 0.05 / 0.03** | **PASS** | G2 was 0.0359 / 0.0461 / 0.0283 |
| Prewrite windows | A:[18] B:[29] C:[18,40] | same | **PASS** | same |
| Weekend form | n=20 | n=20 | **PASS** | same |
| Clock | 287 ticks → lap 72 | 287 → 72 | **PASS** | same |
| L25 state | MEDIUM tyre_life=2 | same | **PASS** | same |
| Ask/recommend identity | Pit lap 33 HARD; Pit lap 30 HARD; Stay out | **Pit lap 33 HARD; Pit lap 30 HARD; Stay out** | **PASS** | G2 had moved to Plan L31→SOFT, L46→HARD |
| What-if delta | **−13.00 s** | **−11.92 s** | G1.4, not E4.1 | G2 was **−2.34 s** |
| What-if MC P10/P90 | **−32.62 / −13.35** | **−147.55 / +29.33** | G1.4, not E4.1 | G2 was **−137.96 / +38.92** |
| Postrace | export, finish=2 | `123_VER_postrace.json`, finish=2 | **PASS** | same |

Recommend **identity** matches the original lock exactly. What-if/MC are
G1.4 because physics-delta stays — same reading as G3.1. Restoring
E4.1 −13.00 s would mean dropping that rollout, which this phase does
not do.

CHECKPOINT: this block is the one non-negotiable. It passed before any
doc or lock-note edit.

---

## G5.2 — definitive research summary

[`docs/tyre-degradation-research.md`](./tyre-degradation-research.md) —
single interview account of G1–G4:

- G1: chained residual was the walk loss; physics-delta + globals beat
  stay-out (combined match-rate **0.322** vs **0.276**).
- G2: C-code mapping is real; fitted slopes still not ordered; overlay
  **0.195**, below stay-out.
- G3: `recommend()` follows the slope table (80.7% flattest-compound);
  HARD stints run in freer air; isotonic collapses 2023–2025 to one
  number; **0.299** beats stay-out, loses to G1.5.
- G4: context restores C1<…<C6 at median; overlay slopes too steep;
  **0.264** loses to both.
- AWS / real-team comparison: onboard tyre energy (temp, pressure,
  load) vs public lap-time inference. FastF1 has no C-codes and no tyre
  sensors. That is the ceiling G1–G4 mapped.

Conclusion in that doc: G1.5 remains the shipped default because every
more sophisticated attempt, evaluated on the same gate, did not beat it.

---

## G5.3 — cornering-load proxy (scoped, not built)

[`docs/future-research-cornering-load.md`](./future-research-cornering-load.md)
— design only. Outline of \(v^2/R\) lateral load from existing YAML
corners + FastF1 speed traces, use as a covariate independent of lap
time, what data already exists (G4.1 coverage, telemetry schema,
Mugello hole), and a **1.5–3 week** post-event estimate. Same
default-candidate rule as G3.5.11 / G4.4 if it is ever fitted.

No code. No ingest. No new flag.

---

## G5.4 — G1.5 locked explicitly

Not just "overlay off unless env is set." The lock is written down:

- `README.md` — Status table row **Shipped tyre model | G1.5 locked**,
  plus a paragraph under the v1 strategy demo.
- `src/aris/tracks.py` `load_track_config` docstring — "permanent
  shipped default as of Phase G.5, after the full G1–G4 investigation —
  not a placeholder pending a better fit."

Overlays remain loadable: `ARIS_TRUE_COMPOUND_SLOPES=1` / `isotonic` /
`pooled`. Unset / `off` / unknown → G1.5. Year alone still does not
overlay.

---

## Tests

Docker/Postgres up (`aris-postgres` healthy), `ARIS_DB_URL` set,
overlay env unset.

Full pytest after the docstring/README lock: **230 passed**, 0 failed
(same count as G4 close). Log: `results/g5/pytest.log`.

A first pytest pass in this session hit 3 ingest **errors** (not
failures) from a locally emptied `requests_cache` / `urllib3` after a
failed `uv run` sync on OneDrive-locked `licenses/` dirs. Packages
restored with `uv pip install --no-deps`; re-run green. Not a product
change.

---

## What this does and does not claim

Does: confirm G4 did not regress the E4.1 recommend identity; write the
G1–G4 research close; scope the only remaining different idea; lock
G1.5 in README and the track loader.

Does not: switch any overlay on; restore E4.1 What-if −13.00 s; start a
fifth lap-time fit; implement cornering load.

**STOP.** Tyre-degradation research thread closed for the event.
