"""Backward-compatible import path.

Phase A renamed rag.py → keyword_qa.py because matching was keyword/rule based.
Phase H replaces that matching with grounded retrieval in grounded.py.
"""

from aris.ask.grounded import answer_question
from aris.ask.sources import session_documents

__all__ = ["answer_question"]


def _session_snapshot(session):  # noqa: ANN001
    docs = session_documents(session)
    return docs[0].facts if docs else {}
