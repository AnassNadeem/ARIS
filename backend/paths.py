"""Repo paths and sys.path bootstrap so `import aris` works under uvicorn."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
BACKEND = ROOT / "backend"
DEPS = ROOT / ".deps"

for extra in (SRC, DEPS):
    if extra.exists() and str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

# Apply FastF1/requests shims before any FastF1 import.
import aris  # noqa: E402, F401
