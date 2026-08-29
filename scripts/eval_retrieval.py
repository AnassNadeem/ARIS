#!/usr/bin/env python
"""Evaluate Copilot hybrid retrieval (Recall@5, Recall@10, MRR).

Usage:
    python scripts/eval_retrieval.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aris.copilot.retrieval import evaluate_retrieval, index_corpus  # noqa: E402

GATE_RECALL5 = 0.7
GATE_MRR = 0.6


def main() -> int:
    index_corpus()
    metrics = evaluate_retrieval()
    print(json.dumps({k: metrics[k] for k in ("n", "recall_at_5", "recall_at_10", "mrr")}, indent=2))
    for row in metrics.get("details") or []:
        rank = row.get("rank")
        flag = "OK" if rank and rank <= 5 else "MISS"
        print(f"  {flag} {row.get('id')} rank={rank} top={row.get('top')[:3]}")
    rec5 = float(metrics["recall_at_5"])
    mrr = float(metrics["mrr"])
    ok = rec5 >= GATE_RECALL5 and mrr >= GATE_MRR
    print(f"\nGate Recall@5>={GATE_RECALL5}: {rec5:.3f}  MRR>={GATE_MRR}: {mrr:.3f}  {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
