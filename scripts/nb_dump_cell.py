"""Print specific cells of a notebook to stdout (utf-8 safe)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __name__ == "__main__":
    nb_path = Path(sys.argv[1])
    indices = [int(x) for x in sys.argv[2:]] if len(sys.argv) > 2 else None
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    out_lines: list[str] = []
    for i, cell in enumerate(nb["cells"]):
        if indices is not None and i not in indices:
            continue
        out_lines.append(f"===CELL {i} {cell['cell_type']}===")
        out_lines.append("".join(cell["source"]))
        out_lines.append("")
    sys.stdout.buffer.write(("\n".join(out_lines)).encode("utf-8"))
