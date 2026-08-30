#!/usr/bin/env python
"""Verify race_field.json outlines across every locally built R2 race.

    python scripts/verify_r2_outlines.py

FAIL if outline_source is gps_fallback, the outline is empty, or the
closed-loop gap is more than 10% of the bounding-box diagonal.
When meta.outline_source is missing (pre-marker rebuilds), source is inferred
from map-space span (< 800 → circuit_map_quick, else gps_fallback).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPLAY = ROOT / "data" / "replay_r2" / "replay"

KNOWN_SOURCES = frozenset({"circuit_map_quick", "gps_fallback"})
MAP_SPACE_SPAN = 800.0
CLOSED_LOOP_FAIL_RATIO = 0.10


def closed_loop_distance(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(ys) < 2:
        return None
    n = min(len(xs), len(ys))
    dx = float(xs[0]) - float(xs[n - 1])
    dy = float(ys[0]) - float(ys[n - 1])
    return math.hypot(dx, dy)


def bbox_diagonal(xs: list[float], ys: list[float]) -> float | None:
    n = min(len(xs), len(ys))
    if n < 2:
        return None
    xspan = max(xs[:n]) - min(xs[:n])
    yspan = max(ys[:n]) - min(ys[:n])
    diag = math.hypot(xspan, yspan)
    return diag if diag > 0 else None


def infer_outline_source(xs: list[float]) -> str:
    if len(xs) < 2:
        return "gps_fallback"
    if (max(xs) - min(xs)) < MAP_SPACE_SPAN:
        return "circuit_map_quick"
    return "gps_fallback"


def resolve_outline_source(meta: dict[str, Any], xs: list[float]) -> tuple[str, bool]:
    marked = str(meta.get("outline_source") or "").strip()
    if marked in KNOWN_SOURCES:
        return marked, False
    return infer_outline_source(xs), True


def evaluate_field(payload: dict[str, Any]) -> dict[str, Any]:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    outline = payload.get("outline") if isinstance(payload.get("outline"), dict) else {}
    xs = [float(v) for v in (outline.get("x") or [])]
    ys = [float(v) for v in (outline.get("y") or [])]
    source, inferred = resolve_outline_source(meta, xs)
    points = min(len(xs), len(ys))
    gap = closed_loop_distance(xs, ys)
    diag = bbox_diagonal(xs, ys)
    ratio = (gap / diag) if gap is not None and diag else None

    reasons: list[str] = []
    if points < 2:
        reasons.append("empty_or_short_outline")
    if source == "gps_fallback":
        reasons.append("gps_fallback")
    if ratio is not None and ratio > CLOSED_LOOP_FAIL_RATIO:
        reasons.append("open_loop")
    elif gap is None and points >= 2:
        reasons.append("open_loop")

    return {
        "year": meta.get("year"),
        "round": meta.get("round"),
        "source": source,
        "inferred": inferred,
        "points": points,
        "closed_loop": gap,
        "bbox_diag": diag,
        "ratio": ratio,
        "ok": not reasons,
        "reasons": reasons,
    }


def iter_race_fields(replay_root: Path) -> list[Path]:
    if not replay_root.is_dir():
        return []
    return sorted(replay_root.glob("*/*/race_field.json"))


def load_field(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def year_round_from_path(path: Path) -> tuple[int | None, int | None]:
    try:
        rnd = int(path.parent.name)
        year = int(path.parent.parent.name)
        return year, rnd
    except (TypeError, ValueError):
        return None, None


def format_row(row: dict[str, Any]) -> str:
    year = row.get("year")
    rnd = row.get("round")
    source = str(row.get("source") or "?")
    if row.get("inferred"):
        source = f"{source}*"
    pts = row.get("points")
    gap = row.get("closed_loop")
    diag = row.get("bbox_diag")
    ratio = row.get("ratio")
    result = "PASS" if row.get("ok") else "FAIL"
    gap_s = "-" if gap is None else f"{gap:.4f}"
    diag_s = "-" if diag is None else f"{diag:.2f}"
    ratio_s = "-" if ratio is None else f"{100.0 * ratio:.2f}%"
    return (
        f"{year!s:>4}  {rnd!s:>5}  {source:<22}  {pts!s:>5}  "
        f"{gap_s:>10}  {diag_s:>10}  {ratio_s:>8}  {result}"
    )


HEADER = (
    "YEAR  ROUND  SOURCE                  PTS      CLOSED        DIAG     RATIO  RESULT"
)


def evaluate_all(replay_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in iter_race_fields(replay_root):
        year, rnd = year_round_from_path(path)
        try:
            row = evaluate_field(load_field(path))
        except Exception as extra:
            row = {
                "year": year,
                "round": rnd,
                "source": "?",
                "inferred": False,
                "points": 0,
                "closed_loop": None,
                "bbox_diag": None,
                "ratio": None,
                "ok": False,
                "reasons": [f"load_error:{extra}"],
            }
        if row.get("year") is None:
            row["year"] = year
        if row.get("round") is None:
            row["round"] = rnd
        row["path"] = str(path)
        rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify R2 race_field outlines")
    parser.add_argument("--replay-root", default=str(DEFAULT_REPLAY))
    args = parser.parse_args(argv)
    replay_root = Path(args.replay_root)
    rows = evaluate_all(replay_root)
    if not rows:
        print(f"no race_field.json under {replay_root}")
        return 1
    print(HEADER)
    print("-" * len(HEADER))
    for row in rows:
        print(format_row(row))
    print("-" * len(HEADER))
    fails = [r for r in rows if not r["ok"]]
    inferred = sum(1 for r in rows if r.get("inferred"))
    gps = [r for r in rows if r.get("source") == "gps_fallback"]
    print(
        f"{len(rows)} races  {len(rows) - len(fails)} PASS  {len(fails)} FAIL  "
        f"{len(gps)} gps_fallback  {inferred} source inferred (*)"
    )
    if fails:
        print("FLAGGED:")
        for row in fails:
            reasons = ",".join(row.get("reasons") or ["fail"])
            print(f"  {row.get('year')} R{row.get('round')}: {reasons}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
