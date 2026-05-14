"""One-shot refactor: replace inline stint/baseline defs in wk2 notebooks with imports."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

NB04 = ROOT / "notebooks" / "04-stint-analysis.ipynb"
NB05 = ROOT / "notebooks" / "05-sector-baseline.ipynb"

NB04_CELL3 = (
    "# Stint detection helpers now live in src/aris/physics/stint.py.\n"
    "from aris.physics.stint import detect_stints, summarise_stints\n"
)

NB04_CELL8 = (
    "# Per-stint metrics live in src/aris/physics/stint.py.\n"
    "from aris.physics.stint import compute_stint_metrics\n"
    "\n"
    "metrics = compute_stint_metrics(enriched)\n"
    "metrics[metrics[\"Driver\"] == \"VER\"]\n"
)

NB05_CELL3 = (
    "# Stint + baseline helpers now live in src/aris/.\n"
    "from aris.physics.stint import detect_stints, filter_clean_laps\n"
    "from aris.eval.baseline import moving_average_baseline\n"
)

NB05_CELL6 = (
    "from aris.eval.scoring import mae, per_race_mae, rmse\n"
    "\n"
    "scored_mae = mae(y_true, y_pred)\n"
    "scored_rmse = rmse(y_true, y_pred)\n"
    "print(f\"inline single_race_mae: {single_race_mae:.6f}\")\n"
    "print(f\"aris.eval.scoring.mae: {scored_mae:.6f}\")\n"
    "print(f\"aris.eval.scoring.rmse: {scored_rmse:.6f}\")\n"
)


def _set_cell_source(nb: dict, cell_idx: int, new_src: str) -> None:
    cell = nb["cells"][cell_idx]
    assert cell["cell_type"] == "code", f"cell {cell_idx} is not code"
    cell["source"] = new_src.splitlines(keepends=True)
    cell["outputs"] = []
    cell["execution_count"] = None


def _save(nb_path: Path, nb: dict) -> None:
    nb_path.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def refactor_04() -> None:
    nb = json.loads(NB04.read_text(encoding="utf-8"))
    _set_cell_source(nb, 3, NB04_CELL3)
    _set_cell_source(nb, 8, NB04_CELL8)
    _save(NB04, nb)
    print(f"refactored {NB04.name}")


def refactor_05() -> None:
    nb = json.loads(NB05.read_text(encoding="utf-8"))
    _set_cell_source(nb, 3, NB05_CELL3)
    _set_cell_source(nb, 6, NB05_CELL6)
    _save(NB05, nb)
    print(f"refactored {NB05.name}")


if __name__ == "__main__":
    refactor_04()
    refactor_05()
