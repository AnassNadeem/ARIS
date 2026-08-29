"""Hybrid search: dense cosine + BM25, RRF fusion, heuristic re-rank, query rewrite."""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer

TOKEN_RE = re.compile(r"[a-z0-9]+")
RRF_K = 60
DENSE_DIM = 384
DEFAULT_K = 10
DEFAULT_TOP_N = 5

_VECTORIZER = HashingVectorizer(
    n_features=DENSE_DIM,
    ngram_range=(1, 2),
    alternate_sign=False,
    norm=None,
    lowercase=True,
    stop_words=None,
)


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall((text or "").lower())


class BM25:
    """Okapi BM25 over tokenised documents."""

    def __init__(self, corpus: list[list[str]], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.n = len(corpus)
        self.doc_len = [len(doc) for doc in corpus]
        self.avgdl = (sum(self.doc_len) / self.n) if self.n else 0.0
        df: dict[str, int] = {}
        self.tf: list[dict[str, int]] = []
        for doc in corpus:
            counts: dict[str, int] = {}
            for tok in doc:
                counts[tok] = counts.get(tok, 0) + 1
            self.tf.append(counts)
            for tok in counts:
                df[tok] = df.get(tok, 0) + 1
        self.idf = {
            tok: math.log((self.n - n_t + 0.5) / (n_t + 0.5) + 1.0) for tok, n_t in df.items()
        }

    def scores(self, query_tokens: list[str]) -> np.ndarray:
        out = np.zeros(self.n, dtype=np.float64)
        if not self.n:
            return out
        for i, counts in enumerate(self.tf):
            dl = self.doc_len[i] or 1
            total = 0.0
            for tok in query_tokens:
                if tok not in counts:
                    continue
                freq = counts[tok]
                idf = self.idf.get(tok, 0.0)
                denom = freq + self.k1 * (1.0 - self.b + self.b * dl / max(self.avgdl, 1e-9))
                total += idf * (freq * (self.k1 + 1.0) / denom)
            out[i] = total
        return out


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    if matrix.size == 0:
        return matrix
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (matrix / norms).astype(np.float32)


def embed_texts(texts: list[str]) -> np.ndarray:
    """Dense embeddings. sentence-transformers if opted in; else hashing vectors."""
    if not texts:
        return np.zeros((0, DENSE_DIM), dtype=np.float32)
    if os.getenv("ARIS_COPILOT_ST", "") == "1":
        try:
            from sentence_transformers import SentenceTransformer

            model = _st_model()
            if model is not None:
                vecs = model.encode(
                    texts,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                return np.asarray(vecs, dtype=np.float32)
        except Exception:
            pass
    matrix = _VECTORIZER.transform(texts).astype(np.float32).toarray()
    return _l2_normalize(matrix)


@lru_cache(maxsize=1)
def _st_model():
    from sentence_transformers import SentenceTransformer

    name = os.getenv("ARIS_EMBED_MODEL", "all-MiniLM-L6-v2")
    return SentenceTransformer(name)


@dataclass
class Chunk:
    chunk_id: str
    text: str
    source: str
    title: str
    section: str = ""
    year: int | None = None
    path: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "source": self.source,
            "title": self.title,
            "section": self.section,
            "year": self.year,
            "path": self.path,
            "score": self.score,
        }


def _chunk_from_dict(raw: dict[str, Any]) -> Chunk:
    return Chunk(
        chunk_id=str(raw.get("chunk_id") or raw.get("id") or ""),
        text=str(raw.get("text") or ""),
        source=str(raw.get("source") or ""),
        title=str(raw.get("title") or ""),
        section=str(raw.get("section") or ""),
        year=raw.get("year"),
        path=str(raw.get("path") or ""),
        metadata={k: v for k, v in raw.items() if k not in {"chunk_id", "id", "text", "source", "title", "section", "year", "path"}},
    )


@dataclass
class CorpusIndex:
    chunks: list[Chunk]
    dense: np.ndarray
    bm25: BM25

    @classmethod
    def build(cls, raw_chunks: list[dict[str, Any]]) -> CorpusIndex:
        chunks = [_chunk_from_dict(c) for c in raw_chunks if str(c.get("text") or "").strip()]
        texts = [f"{c.title} {c.section} {c.text}" for c in chunks]
        dense = embed_texts(texts)
        bm25 = BM25([tokenize(t) for t in texts])
        return cls(chunks=chunks, dense=dense, bm25=bm25)


_INDEX: CorpusIndex | None = None


def reset_index() -> None:
    global _INDEX
    _INDEX = None


def index_corpus(chunks: list[dict[str, Any]] | None = None) -> CorpusIndex:
    """Compute dense embeddings and a BM25 index over chunk text."""
    global _INDEX
    if chunks is None:
        from aris.copilot.corpus import load_chunks

        chunks = load_chunks()
    _INDEX = CorpusIndex.build(chunks)
    return _INDEX


def get_index() -> CorpusIndex:
    global _INDEX
    if _INDEX is None:
        index_corpus()
    assert _INDEX is not None
    return _INDEX


def _top_indices(scores: np.ndarray, k: int) -> list[int]:
    if scores.size == 0:
        return []
    k = min(int(k), int(scores.size))
    if k <= 0:
        return []
    part = np.argpartition(scores, -k)[-k:]
    ordered = part[np.argsort(scores[part])[::-1]]
    return [int(i) for i in ordered if scores[i] > 0 or True]


def hybrid_search(query: str, k: int = DEFAULT_K) -> list[Chunk]:
    """Dense cosine top-k + BM25 top-k, fused with reciprocal rank fusion."""
    store = get_index()
    if not store.chunks:
        return []
    k = max(int(k), 1)
    q_vec = embed_texts([query])
    dense_scores = (store.dense @ q_vec[0]).astype(np.float64) if len(store.dense) else np.zeros(0)
    sparse_scores = store.bm25.scores(tokenize(query))
    dense_rank = {idx: rank for rank, idx in enumerate(_top_indices(dense_scores, k), start=1)}
    sparse_rank = {idx: rank for rank, idx in enumerate(_top_indices(sparse_scores, k), start=1)}
    fused: dict[int, float] = {}
    for idx, rank in dense_rank.items():
        fused[idx] = fused.get(idx, 0.0) + 1.0 / (RRF_K + rank)
    for idx, rank in sparse_rank.items():
        fused[idx] = fused.get(idx, 0.0) + 1.0 / (RRF_K + rank)
    ordered = sorted(fused, key=lambda i: fused[i], reverse=True)[:k]
    out: list[Chunk] = []
    for idx in ordered:
        ch = store.chunks[idx]
        out.append(
            Chunk(
                chunk_id=ch.chunk_id,
                text=ch.text,
                source=ch.source,
                title=ch.title,
                section=ch.section,
                year=ch.year,
                path=ch.path,
                score=float(fused[idx]),
                metadata=dict(ch.metadata),
            )
        )
    return out


def rerank(query: str, chunks: list[Chunk], top_n: int = DEFAULT_TOP_N) -> list[Chunk]:
    """Heuristic re-rank: exact-term overlap, source boosts, optional cross-encoder."""
    if not chunks:
        return []
    q = (query or "").lower()
    q_terms = set(tokenize(query))
    scored: list[tuple[float, Chunk]] = []
    use_ce = os.getenv("ARIS_COPILOT_CE", "") == "1"
    ce_scores: list[float] | None = None
    if use_ce:
        try:
            from sentence_transformers import CrossEncoder

            model = CrossEncoder(os.getenv("ARIS_CE_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"))
            pairs = [(query, c.text[:1500]) for c in chunks]
            ce_scores = [float(x) for x in model.predict(pairs)]
        except Exception:
            ce_scores = None
    for i, ch in enumerate(chunks):
        blob = f"{ch.title} {ch.section} {ch.text}".lower()
        terms = set(tokenize(blob))
        overlap = len(q_terms & terms) / max(len(q_terms), 1)
        boost = 0.0
        if ch.source == "fia_reg" and any(
            w in q for w in ("rule", "fia", "compound", "vsc", "safety", "pit", "red flag", "tyre", "tire")
        ):
            boost += 0.25
        if ch.source == "circuit_prior" and any(
            w in q for w in ("spa", "deg", "circuit", "track", "zandvoort", "monaco", "high-deg")
        ):
            boost += 0.25
        if ch.source == "driver_prior" and any(
            w in q for w in ("hamilton", "verstappen", "norris", "tyre", "tire", "easy on")
        ):
            boost += 0.25
        if ch.source == "aris_doc" and any(
            w in q
            for w in (
                "aris",
                "recommend",
                "auc",
                "conformal",
                "sc risk",
                "monte carlo",
                "wet classifier",
                "limit",
            )
        ):
            boost += 0.2
        for phrase in (
            "two different specifications",
            "high-deg",
            "easy on tyres",
            "virtual safety car",
            "safety car",
            "red flag",
            "compound accuracy",
            "recall@",
        ):
            if phrase in q and phrase in blob:
                boost += 0.4
        base = float(ch.score or 0.0) + (len(chunks) - i) * 0.01
        ce = ce_scores[i] if ce_scores is not None else 0.0
        score = base + 4.0 * overlap + boost + 0.15 * ce
        scored.append((score, ch))
    scored.sort(key=lambda item: item[0], reverse=True)
    out: list[Chunk] = []
    for score, ch in scored[: max(int(top_n), 1)]:
        ch.score = float(score)
        out.append(ch)
    return out


_REWRITE_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\bvsc\b|virtual safety", re.I),
        "VSC pit lane rules FIA sporting regulations tyre change",
    ),
    (
        re.compile(r"two compounds?|two specifications|must use two", re.I),
        "FIA dry-weather tyre two different specifications race requirement Article 30.5",
    ),
    (
        re.compile(r"hamilton|easy on tyr", re.I),
        "Hamilton tyre wear style prior easy on tyres",
    ),
    (
        re.compile(r"\bspa\b|francorchamps|high-?deg", re.I),
        "Spa-Francorchamps high-deg circuit prior degradation",
    ),
    (
        re.compile(r"safety car|\bsc\b risk|sc/vsc", re.I),
        "FIA safety car procedure pit lane SC VSC ARIS sc risk",
    ),
    (
        re.compile(r"red flag", re.I),
        "FIA red flag suspended race tyre change sporting regulations",
    ),
    (
        re.compile(r"undercut", re.I),
        "undercut window ARIS gap 22 seconds pit now vs rival",
    ),
    (
        re.compile(r"conformal|coverage", re.I),
        "ARIS conformal prediction coverage 2025 q_hat known limits",
    ),
]


def rewrite_query(query: str, *, use_llm: bool = False) -> list[str]:
    """Return the original query plus 1–2 recall-oriented rewrites."""
    seen: set[str] = set()
    out: list[str] = []

    def _add(text: str) -> None:
        t = " ".join((text or "").split())
        key = t.lower()
        if not t or key in seen:
            return
        seen.add(key)
        out.append(t)

    _add(query)
    for pattern, alt in _REWRITE_RULES:
        if pattern.search(query or ""):
            _add(alt)
    if use_llm:
        for alt in _llm_rewrites(query):
            _add(alt)
    return out[:3] or [query]


def _llm_rewrites(query: str) -> list[str]:
    try:
        from aris.narrate import call_llm_with_fallback
    except Exception:
        return []
    prompt = (
        "Given this question, generate 1-2 alternative search queries that would "
        "help retrieve relevant FIA regulations, driver priors, or ARIS docs. "
        "Return each alternative on its own line, no numbering.\n\n"
        f"Question: {query}"
    )
    text = call_llm_with_fallback(prompt, fallback="")
    if not text:
        return []
    lines = [ln.strip(" -•\t") for ln in text.splitlines() if ln.strip()]
    return [ln for ln in lines if ln.lower() != (query or "").lower()][:2]


def retrieve(
    query: str,
    *,
    k: int = DEFAULT_K,
    top_n: int = DEFAULT_TOP_N,
    use_llm_rewrite: bool = False,
) -> list[Chunk]:
    """Rewrite → hybrid search per rewrite → fuse → re-rank."""
    queries = rewrite_query(query, use_llm=use_llm_rewrite)
    rrf: dict[str, float] = {}
    by_id: dict[str, Chunk] = {}
    for q in queries:
        hits = hybrid_search(q, k=k)
        for rank, hit in enumerate(hits, start=1):
            rrf[hit.chunk_id] = rrf.get(hit.chunk_id, 0.0) + 1.0 / (RRF_K + rank)
            by_id[hit.chunk_id] = hit
    fused = sorted(by_id.values(), key=lambda c: rrf.get(c.chunk_id, 0.0), reverse=True)
    for ch in fused:
        ch.score = float(rrf.get(ch.chunk_id, 0.0))
    return rerank(query, fused[:k], top_n=top_n)


def evaluate_retrieval(
    qa_rows: list[dict[str, Any]] | None = None,
    *,
    k5: int = 5,
    k10: int = 10,
) -> dict[str, Any]:
    """Recall@k and MRR on a held-out Q/A set."""
    if qa_rows is None:
        qa_rows = load_retrieval_qa()
    get_index()
    ranks: list[int | None] = []
    hits5 = 0
    hits10 = 0
    details: list[dict[str, Any]] = []
    for row in qa_rows:
        question = str(row.get("question") or "")
        relevant = {str(x) for x in (row.get("relevant") or [])}
        hits = retrieve(question, k=k10, top_n=k10, use_llm_rewrite=False)
        first: int | None = None
        for i, ch in enumerate(hits, start=1):
            if _is_relevant(ch.chunk_id, relevant):
                first = i
                break
        ranks.append(first)
        if first is not None and first <= k5:
            hits5 += 1
        if first is not None and first <= k10:
            hits10 += 1
        details.append(
            {
                "id": row.get("id"),
                "rank": first,
                "top": [h.chunk_id for h in hits[:5]],
            }
        )
    n = max(len(qa_rows), 1)
    mrr = sum((1.0 / r) if r else 0.0 for r in ranks) / n
    return {
        "n": len(qa_rows),
        "recall_at_5": hits5 / n,
        "recall_at_10": hits10 / n,
        "mrr": mrr,
        "details": details,
    }


def _is_relevant(chunk_id: str, relevant: set[str]) -> bool:
    if chunk_id in relevant:
        return True
    return any(chunk_id == rel or chunk_id.startswith(rel + ":") for rel in relevant)


def load_retrieval_qa() -> list[dict[str, Any]]:
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "data" / "eval" / "retrieval_qa.jsonl"
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    import json

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows
