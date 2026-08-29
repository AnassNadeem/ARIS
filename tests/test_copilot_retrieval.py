"""T11 — hybrid retrieval quality gate."""

from aris.copilot.retrieval import (
    evaluate_retrieval,
    hybrid_search,
    index_corpus,
    reset_index,
    rewrite_query,
)


def test_rewrite_query_adds_recall_oriented_alts():
    alts = rewrite_query("What are the rules about pitting under VSC?")
    assert alts[0].startswith("What are the rules")
    blob = " ".join(alts).lower()
    assert "vsc" in blob or "virtual safety" in blob
    assert "fia" in blob or "sporting" in blob


def test_hybrid_search_finds_two_compound_reg():
    reset_index()
    index_corpus()
    hits = hybrid_search("two different specifications of dry-weather tyres", k=10)
    ids = [h.chunk_id for h in hits]
    assert any(i.startswith("fia_reg:two-compounds-dry") for i in ids), ids


def test_retrieval_gate_recall5_and_mrr():
    reset_index()
    index_corpus()
    metrics = evaluate_retrieval()
    assert metrics["n"] >= 20
    assert metrics["recall_at_5"] >= 0.7, metrics
    assert metrics["mrr"] >= 0.6, metrics
