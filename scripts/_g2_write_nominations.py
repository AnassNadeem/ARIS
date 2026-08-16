"""One-shot writer for data/compounds/nominations.json (Phase G2.2)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "compounds" / "nominations.json"

# (year, round, event, hard, medium, soft, era, source_url)
N: list[tuple] = []

P_NL_21 = "https://press.pirelli.com/2021-dutch-grand-prix--preview/"
P_NL_22 = "https://press.pirelli.com/2022-dutch-grand-prix--preview/"
P_NL_23 = "https://press.pirelli.com/news-and-tyre-choices-for-zandvoort-and-monza/"
P_NL_24 = "https://press.pirelli.com/all-compounds-on-track-over-next-three-races/"
P_NL_25 = "https://press.pirelli.com/changes-and-status-quo-when-it-comes-to-compound-choices-for-the-rest-of-the-season0/"
P_NL_26 = "https://press.pirelli.com/tyre-compounds-selected-for-zandvoort-monza-and-madrid/"
RN365_23 = "https://racingnews365.com/pirelli-goes-full-uncertainty-for-soft-softer-softest-in-final-f1-season"

# --- Netherlands (priority a) ---
N += [
    (2021, 13, "Netherlands", "C1", "C2", "C3", "2019-2021", P_NL_21),
    (2022, 15, "Netherlands", "C1", "C2", "C3", "2022", P_NL_22),
    (2023, 13, "Netherlands", "C1", "C2", "C3", "2023-2025", P_NL_23),
    (2024, 15, "Netherlands", "C1", "C2", "C3", "2023-2025", P_NL_24),
    (2025, 15, "Netherlands", "C2", "C3", "C4", "2023-2025", P_NL_25),
    (2026, 12, "Netherlands", "C2", "C3", "C4", "2026", P_NL_26),
]

# --- 2024 (priority b) all Pirelli ---
N += [
    (2024, 1, "Bahrain", "C1", "C2", "C3", "2023-2025",
     "https://press.pirelli.com/formula-1-comes-to-japan-in-the-springtime/"),
    (2024, 2, "Saudi Arabia", "C2", "C3", "C4", "2023-2025",
     "https://press.pirelli.com/mid-range-compounds-for-the-saudi-arabian-grand-prix/"),
    (2024, 3, "Australia", "C3", "C4", "C5", "2023-2025",
     "https://press.pirelli.com/pirellis-c5-compound-tyre-makes-its-debut/"),
    (2024, 4, "Japan", "C1", "C2", "C3", "2023-2025",
     "https://press.pirelli.com/these-are-the-p-zero-compounds-for-suzuka-shanghai-and-miami/"),
    (2024, 5, "China", "C2", "C3", "C4", "2023-2025",
     "https://press.pirelli.com/these-are-the-p-zero-compounds-for-suzuka-shanghai-and-miami/"),
    (2024, 6, "Miami", "C2", "C3", "C4", "2023-2025",
     "https://press.pirelli.com/these-are-the-p-zero-compounds-for-suzuka-shanghai-and-miami/"),
    (2024, 7, "Emilia Romagna", "C3", "C4", "C5", "2023-2025",
     "https://press.pirelli.com/same-soft-trio-for-imola-monaco-and-montreal/"),
    (2024, 8, "Monaco", "C3", "C4", "C5", "2023-2025",
     "https://press.pirelli.com/same-soft-trio-for-imola-monaco-and-montreal/"),
    (2024, 9, "Canada", "C3", "C4", "C5", "2023-2025",
     "https://press.pirelli.com/same-soft-trio-for-imola-monaco-and-montreal/"),
    (2024, 10, "Spain", "C1", "C2", "C3", "2023-2025",
     "https://press.pirelli.com/no-surprises-for-the-compounds-for-spain-austria-and-great-britain/"),
    (2024, 11, "Austria", "C3", "C4", "C5", "2023-2025",
     "https://press.pirelli.com/no-surprises-for-the-compounds-for-spain-austria-and-great-britain/"),
    (2024, 12, "Britain", "C1", "C2", "C3", "2023-2025",
     "https://press.pirelli.com/no-surprises-for-the-compounds-for-spain-austria-and-great-britain/"),
    (2024, 13, "Hungary", "C3", "C4", "C5", "2023-2025", P_NL_24),
    (2024, 14, "Belgium", "C2", "C3", "C4", "2023-2025", P_NL_24),
    (2024, 16, "Italy", "C3", "C4", "C5", "2023-2025",
     "https://press.pirelli.com/a-soft-september-for-pirelli-in-f1-compounds-confirmed-for-monza-baku-and-singapore/"),
    (2024, 17, "Azerbaijan", "C3", "C4", "C5", "2023-2025",
     "https://press.pirelli.com/a-soft-september-for-pirelli-in-f1-compounds-confirmed-for-monza-baku-and-singapore/"),
    (2024, 18, "Singapore", "C3", "C4", "C5", "2023-2025",
     "https://press.pirelli.com/a-soft-september-for-pirelli-in-f1-compounds-confirmed-for-monza-baku-and-singapore/"),
    (2024, 19, "United States", "C2", "C3", "C4", "2023-2025",
     "https://press.pirelli.com/these-are-the-tyres-for-the-americas/"),
    (2024, 20, "Mexico City", "C3", "C4", "C5", "2023-2025",
     "https://press.pirelli.com/these-are-the-tyres-for-the-americas/"),
    (2024, 21, "Sao Paulo", "C3", "C4", "C5", "2023-2025",
     "https://press.pirelli.com/these-are-the-tyres-for-the-americas/"),
    (2024, 22, "Las Vegas", "C3", "C4", "C5", "2023-2025",
     "https://press.pirelli.com/all-compounds-on-track-to-end-the-season/"),
    (2024, 23, "Qatar", "C1", "C2", "C3", "2023-2025",
     "https://press.pirelli.com/all-compounds-on-track-to-end-the-season/"),
    (2024, 24, "Abu Dhabi", "C3", "C4", "C5", "2023-2025",
     "https://press.pirelli.com/all-compounds-on-track-to-end-the-season/"),
]

# --- 2025 (priority b) all Pirelli ---
N += [
    (2025, 1, "Australia", "C3", "C4", "C5", "2023-2025",
     "https://press.pirelli.com/2025-compounds-something-new-for-jeddah/"),
    (2025, 2, "China", "C2", "C3", "C4", "2023-2025",
     "https://press.pirelli.com/2025-compounds-something-new-for-jeddah/"),
    (2025, 3, "Japan", "C1", "C2", "C3", "2023-2025",
     "https://press.pirelli.com/2025-compounds-something-new-for-jeddah/"),
    (2025, 4, "Bahrain", "C1", "C2", "C3", "2023-2025",
     "https://press.pirelli.com/in-bahrain-with-prior-knowledge/"),
    (2025, 5, "Saudi Arabia", "C3", "C4", "C5", "2023-2025",
     "https://press.pirelli.com/2025-compounds-something-new-for-jeddah/"),
    (2025, 6, "Miami", "C3", "C4", "C5", "2023-2025",
     "https://press.pirelli.com/pirelli-on-the-soft-side-for-miami-and-imola/"),
    (2025, 7, "Emilia Romagna", "C4", "C5", "C6", "2023-2025",
     "https://press.pirelli.com/the-c6-to-make-its-debut-in-imola/"),
    (2025, 8, "Monaco", "C4", "C5", "C6", "2023-2025",
     "https://press.pirelli.com/from-monaco-to-montreal-all-the-compounds-in-play/"),
    (2025, 9, "Spain", "C1", "C2", "C3", "2023-2025",
     "https://press.pirelli.com/from-monaco-to-montreal-all-the-compounds-in-play/"),
    (2025, 10, "Canada", "C4", "C5", "C6", "2023-2025",
     "https://press.pirelli.com/from-monaco-to-montreal-all-the-compounds-in-play/"),
    (2025, 11, "Austria", "C3", "C4", "C5", "2023-2025",
     "https://press.pirelli.com/both-new-and-familiar-for-spielberg-to-budapest/"),
    (2025, 12, "Britain", "C2", "C3", "C4", "2023-2025",
     "https://press.pirelli.com/both-new-and-familiar-for-spielberg-to-budapest/"),
    (2025, 13, "Belgium", "C1", "C3", "C4", "2023-2025",
     "https://press.pirelli.com/sprint-with-a-jump-in-compounds-in-the-ardennes/"),
    (2025, 14, "Hungary", "C3", "C4", "C5", "2023-2025",
     "https://press.pirelli.com/both-new-and-familiar-for-spielberg-to-budapest/"),
    (2025, 16, "Italy", "C3", "C4", "C5", "2023-2025", P_NL_25),
    (2025, 17, "Azerbaijan", "C4", "C5", "C6", "2023-2025", P_NL_25),
    (2025, 18, "Singapore", "C3", "C4", "C5", "2023-2025", P_NL_25),
    (2025, 19, "United States", "C1", "C3", "C4", "2023-2025",
     "https://press.pirelli.com/a-texas-rodeo-with-a-jump-in-compounds/"),
    (2025, 20, "Mexico City", "C2", "C4", "C5", "2023-2025", P_NL_25),
    (2025, 21, "Sao Paulo", "C2", "C3", "C4", "2023-2025",
     "https://press.pirelli.com/harder-compounds-for-the-sao-paulo-sprint-weekend/"),
    (2025, 22, "Las Vegas", "C3", "C4", "C5", "2023-2025", P_NL_25),
    (2025, 23, "Qatar", "C1", "C2", "C3", "2023-2025", P_NL_25),
    (2025, 24, "Abu Dhabi", "C3", "C4", "C5", "2023-2025", P_NL_25),
]

# --- 2026 completed + announced (priority b) ---
N += [
    (2026, 1, "Australia", "C3", "C4", "C5", "2026",
     "https://press.pirelli.com/complete-f1-tyre-range-for-the-first-three-grands-prix-of-2026/"),
    (2026, 2, "China", "C2", "C3", "C4", "2026",
     "https://press.pirelli.com/complete-f1-tyre-range-for-the-first-three-grands-prix-of-2026/"),
    (2026, 3, "Japan", "C1", "C2", "C3", "2026",
     "https://press.pirelli.com/complete-f1-tyre-range-for-the-first-three-grands-prix-of-2026/"),
    (2026, 4, "Miami", "C3", "C4", "C5", "2026",
     "https://press.pirelli.com/the-softest-trio-for-the-challenges-of-miami-and-montreal/"),
    (2026, 5, "Canada", "C3", "C4", "C5", "2026",
     "https://press.pirelli.com/the-softest-trio-for-the-challenges-of-miami-and-montreal/"),
    (2026, 6, "Monaco", "C3", "C4", "C5", "2026",
     "https://press.pirelli.com/the-tyre-compound-selections-for-monte-carlo-and-barcelona/"),
    (2026, 7, "Spain", "C2", "C3", "C4", "2026",
     "https://press.pirelli.com/the-tyre-compound-selections-for-monte-carlo-and-barcelona/"),
    (2026, 8, "Austria", "C3", "C4", "C5", "2026",
     "https://press.pirelli.com/the-full-pirelli-range-for-spielberg-and-silverstone/"),
    (2026, 9, "Britain", "C1", "C2", "C3", "2026",
     "https://press.pirelli.com/the-full-pirelli-range-for-spielberg-and-silverstone/"),
    (2026, 10, "Belgium", "C2", "C3", "C4", "2026",
     "https://press.pirelli.com/the-compounds-selected-for-belgium-and-hungary/"),
    (2026, 11, "Hungary", "C3", "C4", "C5", "2026",
     "https://press.pirelli.com/the-compounds-selected-for-belgium-and-hungary/"),
    (2026, 13, "Italy", "C3", "C4", "C5", "2026", P_NL_26),
    (2026, 14, "Madrid", "C2", "C3", "C4", "2026", P_NL_26),
]

# --- 2023 (priority c) RacingNews365 season table, NL already Pirelli ---
# Table: https://racingnews365.com/pirelli-goes-full-uncertainty-for-soft-softer-softest-in-final-f1-season
# Cross-checked vs seed NL 2023 C1/C2/C3 and vs VforVitorio/F1_Strat_Manager JSON.
N += [
    (2023, 1, "Bahrain", "C1", "C2", "C3", "2023-2025", RN365_23),
    (2023, 2, "Saudi Arabia", "C2", "C3", "C4", "2023-2025", RN365_23),
    (2023, 3, "Australia", "C2", "C3", "C4", "2023-2025", RN365_23),
    (2023, 4, "Azerbaijan", "C3", "C4", "C5", "2023-2025", RN365_23),
    (2023, 5, "Miami", "C2", "C3", "C4", "2023-2025", RN365_23),
    (2023, 6, "Monaco", "C3", "C4", "C5", "2023-2025", RN365_23),
    (2023, 7, "Spain", "C1", "C2", "C3", "2023-2025", RN365_23),
    (2023, 8, "Canada", "C3", "C4", "C5", "2023-2025", RN365_23),
    (2023, 9, "Austria", "C3", "C4", "C5", "2023-2025", RN365_23),
    (2023, 10, "Britain", "C1", "C2", "C3", "2023-2025", RN365_23),
    (2023, 11, "Hungary", "C3", "C4", "C5", "2023-2025", RN365_23),
    (2023, 12, "Belgium", "C2", "C3", "C4", "2023-2025", RN365_23),
    (2023, 14, "Italy", "C3", "C4", "C5", "2023-2025",
     "https://press.pirelli.com/news-and-tyre-choices-for-zandvoort-and-monza/"),
    (2023, 15, "Singapore", "C3", "C4", "C5", "2023-2025", RN365_23),
    (2023, 16, "Japan", "C1", "C2", "C3", "2023-2025", RN365_23),
    (2023, 17, "Qatar", "C1", "C2", "C3", "2023-2025", RN365_23),
    (2023, 18, "United States", "C2", "C3", "C4", "2023-2025", RN365_23),
    (2023, 19, "Mexico City", "C3", "C4", "C5", "2023-2025", RN365_23),
    (2023, 20, "Sao Paulo", "C2", "C3", "C4", "2023-2025", RN365_23),
    (2023, 21, "Las Vegas", "C3", "C4", "C5", "2023-2025", RN365_23),
    (2023, 22, "Abu Dhabi", "C3", "C4", "C5", "2023-2025", RN365_23),
]

# --- 2022 (priority c) Pirelli preview text only; graphics-only pages left unmapped ---
N += [
    (2022, 1, "Bahrain", "C1", "C2", "C3", "2022",
     "https://press.pirelli.com/2022-bahrain-grand-prix---preview/"),
    (2022, 2, "Saudi Arabia", "C2", "C3", "C4", "2022",
     "https://press.pirelli.com/2022-saudi-arabia-grand-prix---preview/"),
    (2022, 3, "Australia", "C2", "C3", "C5", "2022",
     "https://press.pirelli.com/2022-australian-grand-prix---preview/"),
    (2022, 4, "Emilia Romagna", "C2", "C3", "C4", "2022",
     "https://press.pirelli.com/formula-1-returns-to-europe-for-an-appointment-with-history/"),
    (2022, 5, "Miami", "C2", "C3", "C4", "2022",
     "https://press.pirelli.com/2022-miami-grand-prix---preview/"),
    (2022, 6, "Spain", "C1", "C2", "C3", "2022",
     "https://press.pirelli.com/2022-spanish-grand-prix---preview/"),
    (2022, 7, "Monaco", "C3", "C4", "C5", "2022",
     "https://press.pirelli.com/2022-monaco-grand-prix--preview/"),
    (2022, 8, "Azerbaijan", "C3", "C4", "C5", "2022",
     "https://press.pirelli.com/2022-azerbaijan-grand-prix--preview/"),
    (2022, 9, "Canada", "C3", "C4", "C5", "2022",
     "https://press.pirelli.com/2022-canada-grand-prix---preview/"),
    (2022, 10, "Britain", "C1", "C2", "C3", "2022",
     "https://press.pirelli.com/2022-british-grand-prix--preview/"),
    (2022, 12, "France", "C2", "C3", "C4", "2022",
     "https://press.pirelli.com/2022-french-grand-prix--preview/"),
    (2022, 16, "Italy", "C2", "C3", "C4", "2022",
     "https://press.pirelli.com/news-and-tyre-choices-for-zandvoort-and-monza/"),
]

UNMAPPED = [
    {"year": 2018, "note": "No C-codes: FastF1 uses SUPERSOFT/ULTRASOFT/HYPERSOFT/SOFT/MEDIUM/HARD. Entire season unmapped."},
    {"year": 2019, "note": "C-codes exist but no text-parsable Pirelli season table retrieved; graphics-only pages not used. Entire season unmapped."},
    {"year": 2020, "note": "Pirelli season tables are images without extractable C-codes. Entire season unmapped."},
    {"year": 2021, "events": "all except Netherlands", "note": "Only Dutch GP sourced from Pirelli preview text. 2021 season-choice page tables are images."},
    {"year": 2022, "events": ["Austria", "Hungary", "Belgium", "Singapore", "Japan", "United States", "Mexico City", "Sao Paulo", "Abu Dhabi"],
     "note": "Pirelli 'tyre compound choices' pages for these races are graphics-only; preview URLs 404'd. Not guessed."},
    {"year": 2023, "events": ["Emilia Romagna"], "note": "Race cancelled (floods)."},
    {"year": 2026, "events": ["Azerbaijan", "Bahrain (Sepang)", "Singapore", "United States", "Mexico City", "Sao Paulo", "Las Vegas", "Qatar", "Abu Dhabi"],
     "note": "Not yet announced as of the 28 July 2026 Zandvoort/Monza/Madrid Pirelli release. Bahrain/Saudi original slots were cancelled; Bahrain later listed at Sepang."},
]


def main() -> None:
    seen: set[tuple] = set()
    nominations = []
    for year, rnd, event, hard, medium, soft, era, url in N:
        key = (year, rnd, event)
        if key in seen:
            raise SystemExit(f"duplicate {key}")
        seen.add(key)
        nominations.append(
            {
                "year": year,
                "round": rnd,
                "event": event,
                "hard": hard,
                "medium": medium,
                "soft": soft,
                "era": era,
                "source_url": url,
            }
        )
    doc = {
        "description": (
            "Pirelli dry-tyre C-code nominations per race. hard/medium/soft are "
            "the true compounds behind FastF1 HARD/MEDIUM/SOFT. Wet compounds "
            "are not listed. Races not in `nominations` are unmapped — do not guess."
        ),
        "eras": {
            "2019-2021": "13-inch C1–C5, before the 2022 18-inch construction.",
            "2022": "18-inch first generation. 2022 C1 is the compound Pirelli renamed C0 in 2023.",
            "2023-2025": "18-inch after the C0 reclassification (new C1 slotted between old C1 and C2). C6 added in 2025. C0 was homologated in 2023 but never raced.",
            "2026": "Range recalibrated for 2026 lower-downforce cars. Five slicks C1–C5; C6 not homologated.",
        },
        "nominations": nominations,
        "unmapped": UNMAPPED,
        "existing_datasets_checked": [
            {
                "name": "VforVitorio/F1_Strat_Manager data/tire_compounds_by_race.json",
                "url": "https://github.com/VforVitorio/F1_Strat_Manager",
                "years": "2023-2025",
                "verified_against_seed": {
                    "Netherlands 2023": "C1/C2/C3 match",
                    "Netherlands 2024": "C1/C2/C3 match",
                    "Netherlands 2025": "C2/C3/C4 match",
                },
                "used_as": "cross-check only; this file cites Pirelli (or RacingNews365 for 2023 rest-of-calendar) URLs directly",
            },
            {
                "name": "harningle/fia-doc tyres.json",
                "url": "https://github.com/harningle/fia-doc/blob/main/tyres.json",
                "status": "linked from FastF1 issue #332 (2019-2023 parse) but 404 on current main; not used",
            },
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"wrote {OUT} n={len(nominations)}")


if __name__ == "__main__":
    main()
