"""Launch Streamlit with a fast sector clock (screenshot / UI harness only).

Does not change production code. Patches SectorClock.should_tick so each
rerun advances when speed > 0, instead of waiting 25s/speed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

os.environ.setdefault(
    "ARIS_DB_URL",
    "postgresql+psycopg://aris:aris_local_dev_pw@127.0.0.1:5432/aris",
)

from aris.engine.clock import SectorClock  # noqa: E402


def _fast_should_tick(self) -> bool:
    if self.paused or self.speed <= 0:
        return False
    import time as _time

    self._last_tick = _time.monotonic()
    return True


SectorClock.should_tick = _fast_should_tick  # type: ignore[method-assign]

from streamlit.web import cli as stcli  # noqa: E402

port = os.environ.get("ARIS_STREAMLIT_PORT", "8501")
sys.argv = [
    "streamlit",
    "run",
    str(_ROOT / "apps" / "streamlit_app.py"),
    "--server.port",
    port,
    "--server.headless",
    "true",
    "--browser.gatherUsageStats",
    "false",
]
raise SystemExit(stcli.main())
