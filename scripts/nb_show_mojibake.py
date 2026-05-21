"""Print repr of non-ASCII chars in nb cell sources, so we can see the mojibake exactly."""

from __future__ import annotations

import json
import sys
from pathlib import Path

NB_PATHS = [
    Path("notebooks/03-pandas-deep-dive.ipynb"),
    Path("notebooks/04-stint-analysis.ipynb"),
    Path("notebooks/05-sector-baseline.ipynb"),
]

for p in NB_PATHS:
    nb = json.loads(p.read_text(encoding="utf-8"))
    out: list[str] = []
    for i, cell in enumerate(nb["cells"]):
        src = "".join(cell["source"])
        bad = [c for c in src if ord(c) > 127]
        # Filter to chars that look like cp1252-mojibake (â € † ™ etc.)
        suspect = [c for c in bad if c in "âê€†™'`\"“”‘’†‰ˆ"]
        if not suspect:
            continue
        out.append(f"\n--- {p.name} cell {i} ({cell['cell_type']}) ---")
        seqs: list[str] = []
        cur: list[str] = []
        for ch in src:
            if ord(ch) > 127:
                cur.append(ch)
            elif cur:
                seqs.append("".join(cur))
                cur = []
        if cur:
            seqs.append("".join(cur))
        for s in seqs:
            if any(c in s for c in "âê€†™“”‘’†‰ˆ"):
                out.append(f"  seq {s!r} = " + " ".join(f"U+{ord(c):04X}" for c in s))
    sys.stdout.buffer.write(("\n".join(out)).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
