"""Dump T9 weekend HARD/MEDIUM/SOFT slopes for the phase summary."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from aris.physics.fp2_calibration import calibrate_race_weekend  # noqa: E402
from aris.physics.tires import DEFAULT_COMPOUND_SLOPE  # noqa: E402

G15_HARD = float(DEFAULT_COMPOUND_SLOPE["HARD"])

EVENTS_2024 = [
    (1, "Bahrain"), (2, "Saudi Arabia"), (3, "Australia"), (4, "Japan"),
    (5, "China"), (6, "Miami"), (7, "Emilia Romagna"), (8, "Monaco"),
    (9, "Canada"), (10, "Spain"), (11, "Austria"), (12, "Britain"),
    (13, "Hungary"), (14, "Belgium"), (15, "Netherlands"), (16, "Italy"),
    (17, "Azerbaijan"), (18, "Singapore"), (19, "United States"),
    (20, "Mexico City"), (21, "Sao Paulo"), (22, "Las Vegas"),
    (23, "Qatar"), (24, "Abu Dhabi"),
]
EVENTS_2025 = [
    (1, "Australia"), (2, "China"), (3, "Japan"), (4, "Bahrain"),
    (5, "Saudi Arabia"), (6, "Miami"), (7, "Emilia Romagna"), (8, "Monaco"),
    (9, "Spain"), (10, "Canada"), (11, "Austria"), (12, "Britain"),
    (13, "Belgium"), (14, "Hungary"), (15, "Netherlands"), (16, "Italy"),
    (17, "Azerbaijan"), (18, "Singapore"), (19, "United States"),
    (20, "Mexico City"), (21, "Sao Paulo"), (22, "Las Vegas"),
    (23, "Qatar"), (24, "Abu Dhabi"),
]


def main() -> None:
    fp2_circuits: set[str] = set()
    print(
        f"{'Year':<6}{'Rd':<4}{'Circuit':<18}{'HARD':>8}{'src':<12}"
        f"{'G1.5':>8}{'dH':>8}{'MED':>8}{'SOFT':>8}"
    )
    for year, events in ((2024, EVENTS_2024), (2025, EVENTS_2025)):
        for rnd, name in events:
            cal = calibrate_race_weekend(year, rnd)
            src = (cal.get("_source") or {}).get("HARD", "?")
            hard = float(cal.get("HARD", G15_HARD))
            med = float(cal.get("MEDIUM", 0.05))
            soft = float(cal.get("SOFT", 0.08))
            if str(src).startswith("fp2"):
                fp2_circuits.add(f"{year}-{name}")
            print(
                f"{year:<6}{rnd:<4}{name:<18}{hard:8.4f}{src:<12}"
                f"{G15_HARD:8.4f}{hard - G15_HARD:8.4f}{med:8.4f}{soft:8.4f}"
            )
    print(f"\nFP2-sourced HARD weekends: {len(fp2_circuits)}")
    for key in sorted(fp2_circuits):
        print(f"  {key}")


if __name__ == "__main__":
    main()
