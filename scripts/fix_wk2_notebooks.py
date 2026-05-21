"""One-shot fixer for wk2 notebooks 03 and 04.

- nb03 cell 22: rename `Position` -> `FinishPosition` on results before merge so the
  laps-side `Position` column survives, and use the new name in the column selection.
  Also clear the stored KeyError output.
- nb04 cells 0, 5, 9, 13: replace cp1252-double-encoded mojibake (U+00E2 U+2020 U+2019,
  U+00E2 U+20AC U+201C, U+00E2 U+2030 U+02C6) with the intended U+2192, U+2013, U+2248.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NB03 = ROOT / "notebooks" / "03-pandas-deep-dive.ipynb"
NB04 = ROOT / "notebooks" / "04-stint-analysis.ipynb"


MOJIBAKE_MAP = {
    "â†’": "→",  # â†'  -> →
    "â€“": "–",  # â€"  -> –
    "â€”": "—",  # â€"  -> —  (covered for safety; not seen in nb04)
    "â‰ˆ": "≈",  # â‰ˆ  -> ≈
}


NB03_CELL22_SOURCE = (
    "# `laps` already carries its own running-position `Position` column. Rename results' "
    "finishing-position column before merging so we don't end up with `Position_x` / `Position_y`.\n"
    "laps_full = laps_wx.merge(\n"
    "    results[[\"Abbreviation\", \"TeamName\", \"Position\"]].rename(\n"
    "        columns={\"Position\": \"FinishPosition\"}\n"
    "    ),\n"
    "    left_on=\"Driver\",\n"
    "    right_on=\"Abbreviation\",\n"
    "    how=\"left\",\n"
    ")\n"
    "\n"
    "print(\"shape after results join:\", laps_full.shape)\n"
    "laps_full[[\"Driver\", \"TeamName\", \"FinishPosition\", \"LapNumber\", \"LapTimeS\", \"TrackTemp\"]].head()\n"
)


def fix_nb03() -> None:
    nb = json.loads(NB03.read_text(encoding="utf-8"))
    cell = nb["cells"][22]
    assert cell["cell_type"] == "code", "nb03 cell 22 should be code"
    cell["source"] = NB03_CELL22_SOURCE.splitlines(keepends=True)
    cell["outputs"] = []
    cell["execution_count"] = None
    NB03.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"fixed {NB03.name}")


def fix_nb04() -> None:
    nb = json.loads(NB04.read_text(encoding="utf-8"))
    changed = 0
    for cell in nb["cells"]:
        if cell["cell_type"] != "markdown":
            continue
        new_lines: list[str] = []
        cell_changed = False
        for line in cell["source"]:
            new_line = line
            for bad, good in MOJIBAKE_MAP.items():
                if bad in new_line:
                    new_line = new_line.replace(bad, good)
                    cell_changed = True
            new_lines.append(new_line)
        if cell_changed:
            cell["source"] = new_lines
            changed += 1
    NB04.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"fixed {NB04.name} ({changed} markdown cells)")


if __name__ == "__main__":
    fix_nb03()
    fix_nb04()
