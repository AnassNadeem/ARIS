#!/usr/bin/env python
"""End-to-end strategy smoke test — Bahrain 2024 R, VER, lap 15.

Usage:
    python scripts/smoke_strategy.py
    python scripts/smoke_strategy.py --no-llm
    python scripts/smoke_strategy.py --train-model
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import text  # noqa: E402

from aris.io import db  # noqa: E402
from aris.models.predict import reset_model_cache  # noqa: E402
from aris.models.residual import DEFAULT_MODEL_PATH, train_residual_model  # noqa: E402
from aris.narrate import narrate_result  # noqa: E402
from aris.recommend import recommend  # noqa: E402
from aris.state import build_race_state  # noqa: E402


def _resolve_bahrain_ver_lap15() -> tuple[int, int, int]:
    """Return (session_id, driver_id, lap_number) for Bahrain 2024 R VER L15."""
    with db.engine().connect() as conn:
        sess = conn.execute(
            text(
                """
                SELECT session_id FROM sessions
                WHERE year = 2024 AND round_no = 1 AND session_type = 'R'
                """
            )
        ).first()
        if not sess:
            raise RuntimeError("Bahrain 2024 R not in DB — run ingest_season.py 2024")
        session_id = int(sess[0])
        drv = conn.execute(
            text(
                """
                SELECT driver_id FROM drivers
                WHERE code = 'VER' AND year = 2024
                """
            )
        ).first()
        if not drv:
            raise RuntimeError("VER 2024 not in DB")
        driver_id = int(drv[0])
    return session_id, driver_id, 15


def main() -> None:
    parser = argparse.ArgumentParser(description="ARIS strategy end-to-end smoke test.")
    parser.add_argument("--no-llm", action="store_true", help="template narration only")
    parser.add_argument("--train-model", action="store_true", help="train XGBoost if missing")
    args = parser.parse_args()

    if args.train_model and not DEFAULT_MODEL_PATH.exists():
        print("Training residual model...")
        _, metrics = train_residual_model()
        print(f"CV MAE: {metrics['cv_mae_mean']:.3f} s")
        reset_model_cache()

    session_id, driver_id, lap = _resolve_bahrain_ver_lap15()
    print(f"Smoke: session={session_id} driver={driver_id} lap={lap}")

    state = build_race_state(session_id, driver_id, lap)
    result = recommend(state, top_k=3, mc_draws=50)
    narration = narrate_result(result, use_llm=not args.no_llm)

    print("\n=== TOP RECOMMENDATION ===")
    if result.recommendations:
        top = result.recommendations[0]
        print(f"{top.rank}. {top.label}  delta={top.delta_vs_stay_out_s:+.2f}s")
    print(f"\n=== NARRATION ===\n{narration}")
    print("\n=== JSON ===")
    print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
