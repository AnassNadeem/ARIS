"""G6.6 — confirm day-of checklist env/yaml/windows match current code."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from aris.decisions.persist import decision_log_enabled
from aris.engine.clock import fast_clock_enabled
from aris.physics.compounds import parse_true_compound_mode
from aris.plan.prewrite import derive_pit_windows
from aris.tracks import clear_track_config_cache, load_track_config


def main() -> int:
    clear_track_config_cache()
    cfg = load_track_config("Netherlands")
    windows = derive_pit_windows(cfg.total_laps, cfg.pit_loss_s)
    print(
        f"yaml total_laps={cfg.total_laps} pit_loss={cfg.pit_loss_s} slopes={cfg.compound_slopes}",
        flush=True,
    )
    print(f"prewrite A/B/C={windows}", flush=True)
    print(
        f"ARIS_FAST_CLOCK env={os.getenv('ARIS_FAST_CLOCK')!r} enabled={fast_clock_enabled()}",
        flush=True,
    )
    print(
        f"ARIS_TRUE_COMPOUND_SLOPES env={os.getenv('ARIS_TRUE_COMPOUND_SLOPES')!r} "
        f"mode={parse_true_compound_mode()}",
        flush=True,
    )
    print(
        f"ARIS_DECISION_LOG env={os.getenv('ARIS_DECISION_LOG')!r} enabled={decision_log_enabled()}",
        flush=True,
    )
    failed = False
    if cfg.total_laps != 72 or cfg.pit_loss_s != 18.5:
        print("FAIL: yaml laps/pit_loss", flush=True)
        failed = True
    if windows.get("A") != [18] or windows.get("B") != [29] or windows.get("C") != [18, 40]:
        print(f"FAIL: prewrite windows {windows}", flush=True)
        failed = True
    if fast_clock_enabled() is not False:
        print("FAIL: ARIS_FAST_CLOCK should be unset/off", flush=True)
        failed = True
    if parse_true_compound_mode() != "off":
        print("FAIL: overlay should be off", flush=True)
        failed = True
    if decision_log_enabled() is not True:
        print("FAIL: ARIS_DECISION_LOG default should be on", flush=True)
        failed = True
    print("G6.6 " + ("FAIL" if failed else "OK"), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
