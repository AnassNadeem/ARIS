"""Shared pytest fixtures.

Ask unit tests must index the 14-event fixture, never the live
``results/decisions/`` corpus — including when the shell has
``ARIS_ASK_DECISION_DIRS`` pointed at that corpus.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ASK_FIXTURE = _REPO_ROOT / "data" / "ask" / "fixtures" / "decisions.jsonl"

load_dotenv(_REPO_ROOT / ".env")


def pytest_configure(config: pytest.Config) -> None:
    # Override the process env before collection so a shell-set live corpus
    # cannot leak into Ask tests (module-name filters are easy to miss).
    os.environ["ARIS_ASK_DECISION_DIRS"] = str(_ASK_FIXTURE)


@pytest.fixture(autouse=True)
def _isolate_ask_decision_dirs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARIS_ASK_DECISION_DIRS", str(_ASK_FIXTURE))
