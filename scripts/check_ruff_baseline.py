"""Fail CI when Ruff finds new violations vs the committed baseline.

The baseline is a count of (path, code) pairs from `ruff check --output-format=json`.
Counts may drop without updating the file. Counts that rise, or new (path, code)
pairs, fail the job. Regenerate with:

    uv run ruff check . --output-format=json | uv run python scripts/check_ruff_baseline.py --write
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "ruff-baseline.json"


def _counts_from_ruff_json(payload: list[dict]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for item in payload:
        path = str(item.get("filename") or "").replace("\\", "/")
        try:
            path = str(Path(path).resolve().relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            path = path.replace("\\", "/")
        code = str(item.get("code") or "UNKNOWN")
        counter[f"{path}::{code}"] += 1
    return dict(sorted(counter.items()))


def _run_ruff() -> list[dict]:
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "check", ".", "--output-format=json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    raw = proc.stdout.strip() or "[]"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("ruff did not emit JSON:\n", proc.stdout, proc.stderr, file=sys.stderr)
        sys.exit(2)
    if not isinstance(data, list):
        print("unexpected ruff JSON shape", file=sys.stderr)
        sys.exit(2)
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="overwrite ruff-baseline.json")
    args = parser.parse_args()

    current = _counts_from_ruff_json(_run_ruff())
    if args.write:
        BASELINE_PATH.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        print(
            f"wrote {len(current)} keys ({sum(current.values())} violations) "
            f"to {BASELINE_PATH.name}"
        )
        return 0

    if not BASELINE_PATH.exists():
        print(f"missing {BASELINE_PATH.name}; run with --write", file=sys.stderr)
        return 2

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    new_keys = sorted(set(current) - set(baseline))
    raised = sorted(
        key for key, n in current.items() if n > int(baseline.get(key, 0))
    )
    if new_keys or raised:
        print("New Ruff violations vs ruff-baseline.json:", file=sys.stderr)
        for key in new_keys:
            print(f"  NEW {key} x{current[key]}", file=sys.stderr)
        for key in raised:
            if key in new_keys:
                continue
            print(
                f"  +{current[key] - int(baseline[key])} {key} (was {baseline[key]})",
                file=sys.stderr,
            )
        print(
            f"baseline {sum(int(v) for v in baseline.values())} → now {sum(current.values())}. "
            "Fix the new findings, or regenerate with --write if they are intentional.",
            file=sys.stderr,
        )
        return 1

    dropped = sum(int(baseline.get(k, 0)) for k in baseline) - sum(current.values())
    print(
        f"ruff baseline ok: {sum(current.values())} violations "
        f"({len(current)} keys); {dropped} cleared since baseline"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
