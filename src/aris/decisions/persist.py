"""Append-only JSONL persistence for propose/resolve events.

JSONL under ``results/decisions/`` rather than a new Postgres table: the
locked Zandvoort demo schema (and Neon) stays untouched, files survive
process/session end, and the backtest walker can grep/aggregate without a
migration. ``strategy_feedback`` remains the explicit post-race UI save path.

Disable with ``ARIS_DECISION_LOG=0``. Override the directory with
``ARIS_DECISION_LOG_DIR``.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DIR = _REPO_ROOT / "results" / "decisions"


def decision_log_enabled() -> bool:
    return os.getenv("ARIS_DECISION_LOG", "1") != "0"


def decision_log_dir() -> Path:
    raw = os.getenv("ARIS_DECISION_LOG_DIR")
    return Path(raw) if raw else _DEFAULT_DIR


class JsonlDecisionLog:
    """One JSON object per line. First write creates the file."""

    def __init__(self, path: Path, *, source: str = "live") -> None:
        self.path = path
        self.source = source
        self.meta: dict[str, Any] = {}

    @classmethod
    def for_session(
        cls,
        *,
        session_id: int,
        driver_code: str,
        year: int,
        round_no: int,
        source: str = "live",
    ) -> JsonlDecisionLog:
        directory = decision_log_dir()
        name = f"{year}_r{round_no}_{driver_code}_{session_id}.jsonl"
        return cls(directory / name, source=source)

    def append(self, event: str, payload: dict[str, Any]) -> None:
        record = {
            "event_id": str(uuid.uuid4()),
            "event": event,
            "ts": datetime.now(UTC).isoformat(),
            "source": self.source,
            **self.meta,
            **payload,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
                fh.flush()
        except OSError as exc:
            logger.exception(
                "decision log write failed path=%s event=%s", self.path, event
            )
            raise RuntimeError(
                f"ARIS decision log write failed for {event!r} at {self.path}: {exc}. "
                "Fix permissions on results/decisions/ or set ARIS_DECISION_LOG=0."
            ) from exc


def dump_recommendation(rec: Any) -> dict[str, Any] | None:
    if rec is None:
        return None
    if hasattr(rec, "model_dump"):
        return rec.model_dump()
    return dict(rec)
