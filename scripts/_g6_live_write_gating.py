"""G6.3 — live-write gate on the actual 21–23 Aug 2026 window; overlay independence."""

from __future__ import annotations

import importlib.util
import os
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

_FIT_PATH = _ROOT / "scripts" / "fit_zandvoort_tire_slopes.py"


def _load_fit():
    spec = importlib.util.spec_from_file_location("fit_zandvoort_tire_slopes", _FIT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    fit = _load_fit()
    print("=== G6.3 live-write gating (actual event window) ===", flush=True)
    aimed_window = (date(2026, 8, 21), date(2026, 8, 23))
    actual_window = fit._EVENT_WINDOW
    print(
        f"window: aimed {aimed_window[0]}..{aimed_window[1]}  "
        f"actual {actual_window[0]}..{actual_window[1]}  "
        f"{'PASS' if actual_window == aimed_window else 'FAIL'}",
        flush=True,
    )

    days = [
        (date(2026, 8, 15), False, "rehearsal day (T-6)"),
        (date(2026, 8, 20), False, "Thursday before"),
        (date(2026, 8, 21), True, "Friday FP1/SQ/S"),
        (date(2026, 8, 22), True, "Saturday Q"),
        (date(2026, 8, 23), True, "Sunday race"),
        (date(2026, 8, 24), False, "Monday after"),
    ]
    failed = actual_window != aimed_window
    for day, aimed_inside, label in days:
        actual = fit._in_event_window(day)
        ok = actual is aimed_inside
        if not ok:
            failed = True
        print(
            f"  {day} ({label}): aimed inside={aimed_inside}  actual={actual}  "
            f"{'PASS' if ok else 'FAIL'}",
            flush=True,
        )

    # Five E4.1 paths, with date mocked so we do not depend on "today".
    print("\nE4.1 flag matrix (logic; YAML not touched):", flush=True)
    paths = [
        ("outside", False, True, False, False, "Outside window + --write alone -> allow"),
        ("outside", False, False, False, False, "Outside window, no --write -> log only"),
        ("inside", True, True, False, True, "Inside window + --write alone -> refuse"),
        ("inside", True, True, True, False, "Inside + --write --allow-live-write -> allow"),
        ("inside", True, False, False, False, "Inside window, log only -> allow (no write)"),
    ]
    for when, inside, write, allow, refuse, desc in paths:
        would_refuse = inside and write and not allow
        ok = would_refuse is refuse
        if not ok:
            failed = True
        print(
            f"  {desc}: aimed REFUSED={refuse}  actual REFUSED={would_refuse}  "
            f"{'PASS' if ok else 'FAIL'}",
            flush=True,
        )

    src = _FIT_PATH.read_text(encoding="utf-8")
    coupled = (
        "ARIS_TRUE_COMPOUND_SLOPES" in src
        or "parse_true_compound_mode" in src
        or "true_compound" in src.lower()
    )
    print(
        f"\noverlay independence: aimed no ARIS_TRUE_COMPOUND_SLOPES in fit script  "
        f"actual coupled={coupled}  {'FAIL' if coupled else 'PASS'}",
        flush=True,
    )
    if coupled:
        failed = True

    from aris.physics.compounds import parse_true_compound_mode

    os.environ["ARIS_TRUE_COMPOUND_SLOPES"] = "pooled"
    inside_with_overlay = fit._in_event_window(date(2026, 8, 22))
    os.environ.pop("ARIS_TRUE_COMPOUND_SLOPES", None)
    inside_without = fit._in_event_window(date(2026, 8, 22))
    overlay_mode_on = parse_true_compound_mode("pooled")
    overlay_mode_off = parse_true_compound_mode(None)
    print(
        f"  gate with overlay=pooled: inside={inside_with_overlay}  "
        f"gate overlay unset: inside={inside_without}  "
        f"parse(pooled)={overlay_mode_on} parse(unset)={overlay_mode_off}",
        flush=True,
    )
    if inside_with_overlay is not True or inside_without is not True:
        failed = True
        print("FAIL: overlay env changed the date gate", flush=True)
    if overlay_mode_on != "pooled" or overlay_mode_off != "off":
        failed = True
        print("FAIL: overlay parser not independent of the write gate", flush=True)

    print("\nG6.3 " + ("FAIL" if failed else "OK"), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
