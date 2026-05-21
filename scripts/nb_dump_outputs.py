"""Dump all stderr/stream output content from a notebook to find warnings/errors."""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __name__ == "__main__":
    nb_path = Path(sys.argv[1])
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    out_lines: list[str] = []
    for i, cell in enumerate(nb["cells"]):
        if cell["cell_type"] != "code":
            continue
        for out in cell.get("outputs", []):
            t = out.get("output_type")
            if t == "stream":
                text = "".join(out.get("text", []))
                stream = out.get("name", "")
                if stream == "stderr" or "Warning" in text or "Error" in text:
                    out_lines.append(f"-- cell {i} [{stream}] --")
                    out_lines.append(text)
            elif t == "error":
                out_lines.append(f"-- cell {i} ERROR {out.get('ename')}: {out.get('evalue')} --")
    sys.stdout.buffer.write("\n".join(out_lines).encode("utf-8"))
