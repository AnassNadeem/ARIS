"""Synthetic Zandvoort 2025 VER fixture — no FastF1 required."""

from __future__ import annotations

import pandas as pd

from aris.explain.session import ExplainBundle, format_session_id
from aris.physics.tires import DEFAULT_COMPOUND_SLOPE

DRIVERS = ("VER", "NOR", "PIA")
TOTAL_LAPS = 32
PIT_LAP = 20  # in-lap; stint 2 starts lap 21
SC_LAPS = (8, 9, 10)


def zandvoort_2025_bundle() -> ExplainBundle:
    """VER stint 1 = MEDIUM laps 1–20; SC on laps 8–10; NOR/PIA slightly slower."""
    rows: list[dict] = []
    base = 74.0
    offsets = {"VER": 0.0, "NOR": 0.18, "PIA": 0.35}
    for code in DRIVERS:
        for lap in range(1, TOTAL_LAPS + 1):
            if lap <= PIT_LAP:
                compound = "MEDIUM"
                stint = 1
                age = lap
            else:
                compound = "HARD"
                stint = 2
                age = lap - PIT_LAP
            slope = DEFAULT_COMPOUND_SLOPE[compound]
            lap_s = base + offsets[code] + slope * max(0, age - 1)
            if lap in SC_LAPS:
                lap_s += 12.0
            if lap == PIT_LAP:
                lap_s += 18.5
            status = "4" if lap in SC_LAPS else "1"
            rows.append(
                {
                    "Driver": code,
                    "LapNumber": lap,
                    "LapTimeS": lap_s,
                    "Compound": compound,
                    "TyreLife": age,
                    "Stint": stint,
                    "StintId": stint,
                    "PitInTime": 1.0 if lap == PIT_LAP else None,
                    "PitOutTime": 1.0 if lap == PIT_LAP + 1 else None,
                    "TrackStatus": status,
                    "Position": DRIVERS.index(code) + 1,
                    "Team": {"VER": "Red Bull", "NOR": "McLaren", "PIA": "McLaren"}[code],
                }
            )
    weather = pd.DataFrame(
        {
            "timestamp": [f"2025-08-31T13:{i:02d}:00" for i in range(8)],
            "Rainfall": [False, False, True, True, False, False, False, False],
            "AirTemp": [22.0] * 8,
            "TrackTemp": [32.0] * 8,
        }
    )
    messages = pd.DataFrame(
        [
            {"Lap": 8, "Flag": None, "Category": "SafetyCar", "Message": "SAFETY CAR DEPLOYED"},
            {"Lap": 11, "Flag": "GREEN", "Category": "Flag", "Message": "TRACK CLEAR"},
        ]
    )
    return ExplainBundle(
        year=2025,
        round_number=15,
        session_type="R",
        circuit="Netherlands",
        total_laps=TOTAL_LAPS,
        laps=pd.DataFrame(rows),
        weather=weather,
        messages=messages,
        session_id=format_session_id(2025, 15, "R"),
    )
