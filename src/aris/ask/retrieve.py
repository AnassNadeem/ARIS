"""Local FAISS retrieval for Ask ARIS.

IndexFlatIP over L2-normalised hashing embeddings. File-backed under
``data/ask/index/`` — not pgvector (see docs/PHASE-H-SUMMARY.md).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer

N_FEATURES = 4096
DEFAULT_TOP_K = 5
# Cosine (IP of L2-normalised vectors). Untuned guesses go in PHASE-H as aimed vs actual.
MIN_COSINE = 0.08

_VECTORIZER = HashingVectorizer(
    n_features=N_FEATURES,
    ngram_range=(1, 2),
    alternate_sign=False,
    norm=None,
    lowercase=True,
    stop_words="english",
)


@dataclass
class AskDocument:
    doc_id: str
    source: str  # decision | race | concept | session | memory
    title: str
    text: str
    citation: str
    facts: dict[str, Any] = field(default_factory=dict)


@dataclass
class Hit:
    doc: AskDocument
    cosine: float
    score: float


def embed_texts(texts: list[str]) -> np.ndarray:
    """Dense hashing embeddings, L2-normalised for IndexFlatIP cosine search."""
    if not texts:
        return np.zeros((0, N_FEATURES), dtype=np.float32)
    matrix = _VECTORIZER.transform(texts).astype(np.float32)
    dense = matrix.toarray()
    faiss.normalize_L2(dense)
    return dense


def metadata_boost(query: str, doc: AskDocument) -> float:
    """Light hybrid prior. Does not replace vector retrieval."""
    q = query.lower()
    facts = doc.facts
    boost = 0.0
    if doc.source == "decision":
        if any(tok in q for tok in ("recommend", "delta", "proposal", "propose", "call")):
            boost += 0.08
        lap = facts.get("lap")
        if lap is not None and re.search(rf"\blap\s*{lap}\b", q):
            boost += 0.25
        code = str(facts.get("driver_code") or "")
        if code and re.search(rf"\b{re.escape(code.lower())}\b", q):
            boost += 0.15
        year = facts.get("year")
        if year is not None and str(year) in q:
            boost += 0.2
        round_no = facts.get("round_no")
        if round_no is not None and re.search(rf"\bround\s*{round_no}\b", q):
            boost += 0.15
        country = str(facts.get("country") or "").lower()
        if country and country in q:
            boost += 0.1
        label = str(facts.get("label") or "").lower()
        if "stay out" in q and "stay out" in label:
            boost += 0.12
        if "pit now" in q and "pit now" in label:
            boost += 0.12
    elif doc.source == "race":
        if any(tok in q for tok in ("finish", "grid", "classified", "points", "result")):
            boost += 0.12
        code = str(facts.get("driver_code") or "")
        if code and re.search(rf"\b{re.escape(code.lower())}\b", q):
            boost += 0.1
        year = facts.get("year")
        if year is not None and str(year) in q:
            boost += 0.2
        round_no = facts.get("round_no")
        if round_no is not None and re.search(rf"\bround\s*{round_no}\b", q):
            boost += 0.15
        country = str(facts.get("country") or "").lower()
        if country and country in q:
            boost += 0.1
    elif doc.source == "concept":
        keys = (
            "undercut",
            "overcut",
            "safety car",
            "vsc",
            "virtual safety",
            "pit lane",
            "pit loss",
            "compound",
            "tyre",
            "tire",
        )
        if any(tok in q for tok in keys):
            boost += 0.1
    return boost


class AskIndex:
    """FAISS IndexFlatIP plus the documents it ranks."""

    def __init__(self, documents: list[AskDocument], embeddings: np.ndarray) -> None:
        self.documents = documents
        self.embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)
        self._index = faiss.IndexFlatIP(N_FEATURES)
        if len(self.embeddings):
            self._index.add(self.embeddings)

    @classmethod
    def from_documents(cls, documents: list[AskDocument]) -> AskIndex:
        embeddings = embed_texts([d.text for d in documents])
        return cls(documents, embeddings)

    def search(self, query: str, *, k: int = DEFAULT_TOP_K) -> list[Hit]:
        if not self.documents:
            return []
        q = embed_texts([query])
        n_fetch = min(max(k * 6, k), len(self.documents))
        scores, ids = self._index.search(q, n_fetch)
        hits: list[Hit] = []
        for cosine, idx in zip(scores[0], ids[0], strict=False):
            if idx < 0:
                continue
            doc = self.documents[int(idx)]
            cosine_f = float(cosine)
            hits.append(
                Hit(doc=doc, cosine=cosine_f, score=cosine_f + metadata_boost(query, doc))
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        docs_path = directory / "documents.jsonl"
        with docs_path.open("w", encoding="utf-8") as fh:
            for doc in self.documents:
                fh.write(
                    json.dumps(
                        {
                            "doc_id": doc.doc_id,
                            "source": doc.source,
                            "title": doc.title,
                            "text": doc.text,
                            "citation": doc.citation,
                            "facts": doc.facts,
                        },
                        default=str,
                    )
                    + "\n"
                )
        np.savez_compressed(directory / "embeddings.npz", embeddings=self.embeddings)
        faiss.write_index(self._index, str(directory / "faiss.index"))
        (directory / "meta.json").write_text(
            json.dumps(
                {
                    "n_docs": len(self.documents),
                    "n_features": N_FEATURES,
                    "index": "IndexFlatIP",
                    "embedder": "sklearn.HashingVectorizer",
                    "by_source": _counts(self.documents),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: Path) -> AskIndex:
        docs: list[AskDocument] = []
        with (directory / "documents.jsonl").open(encoding="utf-8") as fh:
            for line in fh:
                raw = json.loads(line)
                docs.append(
                    AskDocument(
                        doc_id=raw["doc_id"],
                        source=raw["source"],
                        title=raw["title"],
                        text=raw["text"],
                        citation=raw["citation"],
                        facts=raw.get("facts") or {},
                    )
                )
        embeddings = np.load(directory / "embeddings.npz")["embeddings"]
        loaded = cls(docs, embeddings)
        index_path = directory / "faiss.index"
        if index_path.exists():
            loaded._index = faiss.read_index(str(index_path))
        return loaded


def _counts(documents: list[AskDocument]) -> dict[str, int]:
    out: dict[str, int] = {}
    for doc in documents:
        out[doc.source] = out.get(doc.source, 0) + 1
    return out
