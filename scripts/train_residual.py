#!/usr/bin/env python
"""Train and save the XGBoost residual model."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aris.models.residual import train_residual_model  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the XGBoost residual model")
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=None,
        help="Subset of REFERENCE_RACES years (default: all 2018–2023)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Destination JSON path (default: models/residual_xgb.json)",
    )
    args = parser.parse_args()
    model, metrics = train_residual_model(path=args.output, years=args.years)
    del model
    print(f"Saved model. CV MAE = {metrics['cv_mae_mean']:.3f} ± {metrics['cv_mae_std']:.3f} s")


if __name__ == "__main__":
    main()
