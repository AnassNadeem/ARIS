"""E2.4 — multi-year strict pit_loss for Australia (Phase D flagged 9.0s as low)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import yaml

import importlib.util

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

import aris  # noqa: E402, F401
import fastf1  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "build_track_config", _ROOT / "scripts" / "build_track_config.py"
)
_btc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_btc)
derive_pit_loss_s = _btc.derive_pit_loss_s

_YEARS = (2018, 2019, 2022, 2023, 2024, 2025)
_YAML = _ROOT / "data" / "tracks" / "australia.yaml"
_CACHE = _ROOT / "fastf1_cache"


def main() -> None:
    fastf1.Cache.enable_cache(str(_CACHE))
    values: list[tuple[int, float]] = []
    for year in _YEARS:
        print(f"Loading {year} Australia R ...", flush=True)
        try:
            session = fastf1.get_session(year, "Australia", "R")
            session.load(laps=True, telemetry=False, weather=False, messages=False)
            pit = derive_pit_loss_s(session, strict=True)
            values.append((year, float(pit)))
            print(f"  {year}: {pit:.2f}s", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  SKIP {year}: {exc!r}", flush=True)
    if not values:
        raise SystemExit("no pit_loss samples")
    med = float(np.median([v for _, v in values]))
    print(f"\nper-year: {values}", flush=True)
    print(f"multi-year median: {med:.2f}s", flush=True)

    doc = yaml.safe_load(_YAML.read_text(encoding="utf-8")) or {}
    old = float(doc.get("pit_loss_s", float("nan")))
    print(f"current YAML pit_loss_s={old}", flush=True)
    if abs(med - old) >= 0.5:
        doc["pit_loss_s"] = round(med, 1)
        src = dict(doc.get("source") or {})
        src["pit_loss_previous_s"] = old
        src["pit_loss_method"] = (
            "E2.4 multi-year strict median "
            f"(years={[y for y, _ in values]}; values={[round(v, 2) for _, v in values]})"
        )
        src["pit_loss_year"] = "multi"
        doc["source"] = src
        _YAML.write_text(
            yaml.safe_dump(doc, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        print(f"Updated {_YAML}: {old} -> {round(med, 1)}", flush=True)
    else:
        print(f"No update (|delta|={abs(med - old):.2f} < 0.5)", flush=True)


if __name__ == "__main__":
    main()
