"""Serialize native FastF1 work. Concurrent sess.load() crashes uvicorn on Windows."""

from __future__ import annotations

import threading

FASTF1_LOCK = threading.Lock()
