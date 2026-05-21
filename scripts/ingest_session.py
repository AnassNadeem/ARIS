"""CLI: ingest one FastF1 session into Postgres.

    python scripts/ingest_session.py 2024 1 R
    python scripts/ingest_session.py 2024 Bahrain R

Argument 2 is a round number or an event name — both work. The ingest is
idempotent, so running this twice on the same session leaves row counts
unchanged (the second run reports +0 across the board).
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

# Make `aris` importable when the package is not installed into the environment.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aris.io.ingest import ingest_session  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: ingest_session.py <year> <round-or-name> <session-type>", file=sys.stderr)
        return 2

    year = int(argv[0])
    event: int | str = argv[1]
    with contextlib.suppress(ValueError):
        event = int(event)  # a bare number is a round; anything else is a name
    session_type = argv[2]

    counts = ingest_session(year, event, session_type)
    print(
        f"ingested {year} round/name={event} {session_type.upper()}: "
        f"+{counts['sessions']} sessions, +{counts['drivers']} drivers, +{counts['laps']} laps"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
