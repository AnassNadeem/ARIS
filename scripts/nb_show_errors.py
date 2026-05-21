"""Print every error output stored in the wk2 notebooks."""

from __future__ import annotations

import json
from pathlib import Path

NBS = ["03-pandas-deep-dive.ipynb", "04-stint-analysis.ipynb", "05-sector-baseline.ipynb"]
ROOT = Path(__file__).resolve().parent.parent / "notebooks"

for name in NBS:
    nb = json.loads((ROOT / name).read_text(encoding="utf-8"))
    print(f"\n===== {name} =====")
    for i, cell in enumerate(nb["cells"]):
        if cell["cell_type"] != "code":
            continue
        for out in cell.get("outputs", []):
            if out.get("output_type") == "error":
                ename = out.get("ename")
                evalue = out.get("evalue")
                print(f"-- cell {i}: {ename}: {evalue}")
                src = "".join(cell["source"])
                print("    source first 200:", src[:200].replace("\n", " | "))
