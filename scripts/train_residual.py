#!/usr/bin/env python
"""Train and save the XGBoost residual model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aris.models.residual import train_residual_model  # noqa: E402


def main() -> None:
    model, metrics = train_residual_model()
    print(f"Saved model. CV MAE = {metrics['cv_mae_mean']:.3f} ± {metrics['cv_mae_std']:.3f} s")


if __name__ == "__main__":
    main()
