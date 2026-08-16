"""G3.2 — audit what recommend() actually chose in the Phase G walks.

Reads persisted JSONL under results/decisions/ (no re-run). Files contain
both G1.5 (2026-08-13 afternoon UTC) and G2 (later the same UTC day /
2026-08-14) propose events because G2 appended. Split by timestamp.

  python scripts/_g3_audit_decisions.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from aris.physics.compounds import (  # noqa: E402
    event_relative_slopes,
    load_true_compound_slopes,
    lookup_nomination,
)

_LOG_DIR = _ROOT / "results" / "decisions"
_OUT = _ROOT / "results" / "g3" / "decision_audit.json"

# G2 walk last-write times are 2026-08-14 ~02:30–03:20 local (UTC+5) =
# 2026-08-13 21:30 UTC onward. G1.5 walk timestamps start ~14:23 UTC Aug 13.
_G2_START = datetime(2026, 8, 13, 20, 0, tzinfo=timezone.utc)


def _parse_ts(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _walk_name(ts: datetime | None) -> str:
    if ts is None:
        return "unknown"
    if ts >= _G2_START:
        return "g2"
    return "g1"


def _classify(rec: dict[str, Any] | None) -> tuple[str, str | None]:
    """Return (kind, compound) for the top recommendation."""
    if not rec:
        return "empty", None
    action = rec.get("action") or {}
    label = str(rec.get("label") or "")
    if action.get("pit_laps") and action.get("pit_compounds"):
        comps = [str(c).upper() for c in action["pit_compounds"] if c]
        return "plan", comps[0] if comps else None
    kind = str(action.get("kind") or "")
    if kind in ("pit_now", "pit_lap") or label.lower().startswith("pit"):
        return "pit", (str(action.get("pit_compound") or "").upper() or None)
    if kind in ("lift", "brake") or label.lower().startswith(("lift", "brake")):
        return "line", None
    if kind == "stay_out" or "stay out" in label.lower():
        return "stay_out", None
    return "other", None


def _flattest_relative(year: int, event: str, round_no: int) -> tuple[str | None, dict[str, float]]:
    """Event-relative compound with the smallest (flattest / most negative) G2 slope."""
    slopes, _meta = event_relative_slopes(year, event, round_no=round_no, mode="unconstrained")
    if not slopes:
        return None, {}
    dry = {k: float(v) for k, v in slopes.items() if k in ("SOFT", "MEDIUM", "HARD")}
    if not dry:
        return None, dry
    flat = min(dry, key=dry.get)
    return flat, dry


def main() -> int:
    if not _LOG_DIR.exists():
        print(f"NO LOGS at {_LOG_DIR}", flush=True)
        return 1

    by_walk: dict[str, list[dict[str, Any]]] = defaultdict(list)
    n_files = 0
    n_propose = 0
    for path in sorted(_LOG_DIR.glob("*.jsonl")):
        n_files += 1
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("event") != "propose":
                    continue
                n_propose += 1
                ts = _parse_ts(str(rec.get("ts") or ""))
                walk = _walk_name(ts)
                top = rec.get("recommendation") or {}
                kind, compound = _classify(top)
                year = int(rec.get("year") or 0)
                country = str(rec.get("country") or "")
                round_no = int(rec.get("round_no") or 0)
                flat, slopes = (
                    _flattest_relative(year, country, round_no)
                    if year and country
                    else (None, {})
                )
                matches_flat = (
                    compound is not None and flat is not None and compound == flat
                )
                by_walk[walk].append(
                    {
                        "year": year,
                        "round_no": round_no,
                        "country": country,
                        "driver": rec.get("driver_code"),
                        "lap": rec.get("lap"),
                        "kind": kind,
                        "compound": compound,
                        "label": top.get("label"),
                        "flattest": flat,
                        "slopes": slopes,
                        "matches_flattest": matches_flat,
                    }
                )

    summary: dict[str, Any] = {
        "n_files": n_files,
        "n_propose": n_propose,
        "g2_split_utc": _G2_START.isoformat(),
        "walks": {},
    }
    print(f"files={n_files} propose={n_propose}", flush=True)
    for walk in ("g1", "g2", "unknown"):
        rows = by_walk.get(walk) or []
        if not rows:
            continue
        kinds = Counter(r["kind"] for r in rows)
        n = len(rows)
        stay = kinds.get("stay_out", 0)
        pit = kinds.get("pit", 0)
        plan = kinds.get("plan", 0)
        line = kinds.get("line", 0)
        pit_like = [r for r in rows if r["kind"] in ("pit", "plan") and r["compound"]]
        compounds = Counter(r["compound"] for r in pit_like)
        n_pit_like = len(pit_like)
        n_match_flat = sum(1 for r in pit_like if r["matches_flattest"])
        by_year: dict[str, dict[str, Any]] = {}
        for year in (2024, 2025):
            yrows = [r for r in rows if r["year"] == year]
            if not yrows:
                continue
            ykinds = Counter(r["kind"] for r in yrows)
            ypit = [r for r in yrows if r["kind"] in ("pit", "plan") and r["compound"]]
            by_year[str(year)] = {
                "n": len(yrows),
                "kinds": dict(ykinds),
                "stay_out_frac": ykinds.get("stay_out", 0) / len(yrows),
                "pit_frac": (ykinds.get("pit", 0) + ykinds.get("plan", 0)) / len(yrows),
                "compounds": dict(Counter(r["compound"] for r in ypit)),
                "pit_match_flattest_frac": (
                    sum(1 for r in ypit if r["matches_flattest"]) / len(ypit)
                    if ypit
                    else None
                ),
            }
        walk_sum = {
            "n_propose": n,
            "kinds": dict(kinds),
            "stay_out_frac": stay / n,
            "pit_frac": (pit + plan) / n,
            "line_frac": line / n,
            "plan_frac": plan / n,
            "compounds_among_pit_or_plan": dict(compounds),
            "n_pit_or_plan_with_compound": n_pit_like,
            "pit_match_flattest_n": n_match_flat,
            "pit_match_flattest_frac": (n_match_flat / n_pit_like) if n_pit_like else None,
            "by_year": by_year,
        }
        summary["walks"][walk] = walk_sum
        print(f"\n=== {walk} n={n} ===", flush=True)
        print(f"  kinds={dict(kinds)}", flush=True)
        print(
            f"  stay-out {stay}/{n} = {stay/n:.3f}  "
            f"pit+plan {pit+plan}/{n} = {(pit+plan)/n:.3f}  "
            f"line {line}/{n} = {line/n:.3f}",
            flush=True,
        )
        print(f"  compounds among pit/plan: {dict(compounds)}", flush=True)
        if n_pit_like:
            print(
                f"  recommended compound == flattest G2 slope: "
                f"{n_match_flat}/{n_pit_like} = {n_match_flat/n_pit_like:.3f}",
                flush=True,
            )
        for y, payload in by_year.items():
            print(
                f"  {y}: n={payload['n']} stay={payload['stay_out_frac']:.3f} "
                f"pit={payload['pit_frac']:.3f} compounds={payload['compounds']} "
                f"match_flat={payload['pit_match_flattest_frac']}",
                flush=True,
            )

    # Era-level: did G2 prefer the C-code with the flattest unconstrained slope?
    era_slopes = load_true_compound_slopes("unconstrained")
    summary["unconstrained_era_slopes"] = era_slopes
    g2_rows = by_walk.get("g2") or []
    era_hits: dict[str, Counter] = defaultdict(Counter)
    for r in g2_rows:
        if r["kind"] not in ("pit", "plan") or not r["compound"]:
            continue
        nom = lookup_nomination(r["year"], r["country"], round_no=r["round_no"])
        if nom is None:
            continue
        fitted = era_slopes.get(nom.era) or {}
        rel_map = {"HARD": nom.hard, "MEDIUM": nom.medium, "SOFT": nom.soft}
        code = rel_map.get(r["compound"])
        if not code or code not in fitted:
            continue
        era_codes = {c: fitted[c] for c in rel_map.values() if c in fitted}
        if not era_codes:
            continue
        flattest_code = min(era_codes, key=era_codes.get)
        era_hits[nom.era]["n"] += 1
        if code == flattest_code:
            era_hits[nom.era]["match_flattest_c"] += 1
        era_hits[nom.era][f"rec_{r['compound']}"] += 1
    summary["g2_era_flattest_c_code"] = {k: dict(v) for k, v in era_hits.items()}

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {_OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
