"""Background FastF1 → Postgres ingest so recommend/plans never block."""

from __future__ import annotations

import logging
import threading
from typing import Literal

logger = logging.getLogger(__name__)

IngestStatus = Literal["INGESTED", "INGESTING", "UNAVAILABLE"]

_lock = threading.Lock()
_in_progress: set[tuple[int, int, str]] = set()


def reset_ingest_jobs_for_tests() -> None:
    with _lock:
        _in_progress.clear()


def ensure_session_ingested(
    year: int, round_no: int, session_type: str = "R"
) -> IngestStatus:
    """Kick off ingest if needed. Never waits for FastF1/Postgres writes.

    Returns:
      INGESTED    — race session already in Postgres
      INGESTING   — a background job is running (this call or an earlier one)
      UNAVAILABLE — cannot check Postgres (no DB / error)
    """
    session_type = str(session_type).upper()
    key = (int(year), int(round_no), session_type)
    try:
        from aris.io import db

        if session_type == "R":
            sid = db.fetch_race_session_id(int(year), int(round_no))
        else:
            sid = None
            with db.engine().connect() as conn:
                from sqlalchemy import text

                row = conn.execute(
                    text(
                        "SELECT session_id FROM sessions "
                        "WHERE year = :year AND round_no = :round_no AND session_type = :st"
                    ),
                    {"year": int(year), "round_no": int(round_no), "st": session_type},
                ).fetchone()
                if row:
                    sid = int(row[0])
        if sid is not None:
            return "INGESTED"
    except Exception:
        logger.debug("ingest status check failed for %s", key, exc_info=True)
        return "UNAVAILABLE"

    with _lock:
        if key in _in_progress:
            return "INGESTING"
        _in_progress.add(key)

    worker = threading.Thread(
        target=_run_ingest,
        args=(key, int(year), int(round_no), session_type),
        name=f"aris-ingest-{year}-R{round_no}-{session_type}",
        daemon=True,
    )
    worker.start()
    return "INGESTING"


def _run_ingest(key: tuple[int, int, str], year: int, round_no: int, session_type: str) -> None:
    try:
        from aris.io.ingest import ingest_session

        ingest_session(year, round_no, session_type)
    except Exception:
        logger.exception("background ingest failed for %s", key)
    finally:
        with _lock:
            _in_progress.discard(key)
