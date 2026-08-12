"""Re-derive Zandvoort pit_loss_s across 2021–2025 with Phase C/D strict matcher."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import yaml

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

import aris  # noqa: F401
import fastf1

from build_track_config import derive_pit_loss_s  # noqa: E402  — scripts/ on path

_CACHE = _ROOT / "fastf1_cache"
_YAML = _ROOT / "data" / "tracks" / "netherlands.yaml"
_YEARS = (2021, 2022, 2023, 2024, 2025)
_GP = "Netherlands"
_PHASE_D_VALUE = 16.4


def main() -> None:
    fastf1.Cache.enable_cache(str(_CACHE))
    per_year: dict[int, float] = {}
    for year in _YEARS:
        print(f"Loading {year} {_GP} R ...", flush=True)
        session = fastf1.get_session(year, _GP, "R")
        session.load(laps=True, telemetry=False, weather=False, messages=False)
        pit = derive_pit_loss_s(session, strict=True)
        per_year[year] = pit
        print(f"  pit_loss_s = {pit}", flush=True)

    vals = np.array(list(per_year.values()), dtype=float)
    multi = round(float(np.median(vals)), 1)
    spread = float(vals.max() - vals.min())
    print("\nPer-year:", per_year, flush=True)
    print(f"Median across years: {multi}", flush=True)
    print(f"Range (max-min): {spread:.1f} s", flush=True)
    print(f"Phase D single-year (2025): {_PHASE_D_VALUE}", flush=True)

    # Update if multi-year median differs by >= 0.5 s (meaningful).
    meaningful = abs(multi - _PHASE_D_VALUE) >= 0.5
    print(f"Meaningful difference (>=0.5s)? {meaningful}", flush=True)

    doc = yaml.safe_load(_YAML.read_text(encoding="utf-8")) or {}
    src = dict(doc.get("source") or {})
    src["pit_loss_per_year"] = {str(y): float(v) for y, v in per_year.items()}
    src["pit_loss_multi_year_median_s"] = multi
    src["pit_loss_phase_d_s"] = _PHASE_D_VALUE
    if meaningful:
        previous = doc.get("pit_loss_s")
        doc["pit_loss_s"] = multi
        src["pit_loss_previous_s"] = previous
        src["pit_loss_method"] = (
            "strict multi-year median 2021-2025: median(pit_lap - clean@tyre_life±1,"
            "same_compound,LapNumber±5,TrackStatus==1,free-air≤stint_med+1s)"
        )
        print(f"UPDATED pit_loss_s: {previous} -> {multi}", flush=True)
    else:
        src["pit_loss_method"] = (
            "strict Phase D 2025 single-year retained; multi-year median "
            f"{multi} within 0.5s of {_PHASE_D_VALUE}"
        )
        print(f"KEPT pit_loss_s={doc.get('pit_loss_s')} (multi-year median {multi})", flush=True)
    doc["source"] = src
    _YAML.write_text(
        yaml.safe_dump(doc, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"Wrote source notes to {_YAML}", flush=True)


if __name__ == "__main__":
    main()
