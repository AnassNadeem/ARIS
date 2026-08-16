"""Build the Ask ARIS FAISS index from the three retrieval sources."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from aris.ask.sources import (  # noqa: E402
    DEFAULT_INDEX_DIR,
    build_index,
    load_concept_documents,
    load_decision_documents,
    load_race_documents,
    save_index,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Ask ARIS FAISS index")
    parser.add_argument("--out", type=Path, default=DEFAULT_INDEX_DIR)
    args = parser.parse_args()

    t0 = time.perf_counter()
    decisions = load_decision_documents()
    races = load_race_documents()
    concepts = load_concept_documents()
    print(
        f"sources aimed: decision JSONL + session_results dump + concept md; "
        f"actual decisions={len(decisions)} races={len(races)} concepts={len(concepts)}",
        flush=True,
    )
    index = build_index()
    path = save_index(index, args.out)
    elapsed = time.perf_counter() - t0
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    print(
        f"index aimed: IndexFlatIP n_features=4096; actual n_docs={meta['n_docs']} "
        f"by_source={meta['by_source']} wrote={path} elapsed_s={elapsed:.3f}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
