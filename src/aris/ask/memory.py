"""In-session Ask ARIS conversation memory.

Scope is one Streamlit/runtime session. Nothing is written to disk, and a new
browser session starts empty. Cross-session memory is out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aris.ask.retrieve import AskDocument


@dataclass
class ConversationMemory:
    max_turns: int = 8
    turns: list[tuple[str, str]] = field(default_factory=list)
    last_decision_docs: list[AskDocument] = field(default_factory=list)

    @classmethod
    def from_turns(cls, turns: list[tuple[str, str]], *, max_turns: int = 8) -> ConversationMemory:
        mem = cls(max_turns=max_turns)
        for role, text in turns[-max_turns:]:
            mem.turns.append((role, text))
        return mem

    def add(self, role: str, text: str) -> None:
        self.turns.append((role, text))
        overflow = len(self.turns) - self.max_turns
        if overflow > 0:
            self.turns = self.turns[overflow:]

    def query_with_context(self, question: str) -> str:
        """Prepend recent user turns so follow-ups can retrieve the same docs."""
        prior = [text for role, text in self.turns if role in ("user", "engineer")]
        if not prior:
            return question
        joined = " | ".join(prior[-3:])
        return f"{joined} || follow-up: {question}"

    def memory_documents(self) -> list[AskDocument]:
        if not self.last_decision_docs:
            return []
        docs: list[AskDocument] = []
        for doc in self.last_decision_docs:
            docs.append(
                AskDocument(
                    doc_id=f"memory:{doc.doc_id}",
                    source="memory",
                    title=f"Earlier in this session: {doc.title}",
                    text=f"Previously cited in this conversation. {doc.text}",
                    citation=f"session-memory of {doc.citation}",
                    facts=dict(doc.facts),
                )
            )
        return docs

    def remember_decision_hits(self, docs: list[AskDocument]) -> None:
        decisions = [d for d in docs if d.source == "decision"]
        if decisions:
            self.last_decision_docs = decisions[:3]
