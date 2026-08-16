"""H.3 — FAISS top-k retrieval over the three sources."""

from aris.ask.retrieve import AskIndex
from aris.ask.sources import collect_documents


def _index() -> AskIndex:
    return AskIndex.from_documents(collect_documents())


def test_index_contains_three_sources():
    docs = collect_documents()
    sources = {d.source for d in docs}
    # Aimed: decision + race + concept. Actual set below.
    assert sources >= {"decision", "race", "concept"}, f"aimed three sources, actual {sources}"


def test_top_k_finds_logged_decision():
    index = _index()
    hits = index.search("ARIS recommend SAI 2024 Netherlands lap 21 Pit now HARD", k=5)
    assert hits, "aimed >=1 hit, actual 0"
    top = hits[0].doc
    assert top.source == "decision", f"aimed source=decision, actual {top.source}"
    assert top.facts.get("driver_code") == "SAI", f"aimed SAI, actual {top.facts.get('driver_code')}"
    assert top.facts.get("lap") == 21, f"aimed lap=21, actual {top.facts.get('lap')}"
    assert top.facts.get("delta_vs_stay_out_s") == -72.72805747985858, (
        f"aimed -72.72805747985858, actual {top.facts.get('delta_vs_stay_out_s')}"
    )


def test_top_k_finds_race_result():
    index = _index()
    hits = index.search("classified finish result SAI 2024 Netherlands round 15 grid points", k=8)
    races = [
        h
        for h in hits
        if h.doc.source == "race"
        and h.doc.facts.get("driver_code") == "SAI"
        and h.doc.facts.get("year") == 2024
        and h.doc.facts.get("round_no") == 15
    ]
    assert races, f"aimed 2024 R15 SAI race hit in top-8, actual {[ (h.doc.source, h.doc.facts.get('year'), h.doc.facts.get('driver_code'), h.doc.facts.get('finish_pos')) for h in hits ]}"
    doc = races[0].doc
    assert doc.facts.get("finish_pos") == 5, f"aimed finish_pos=5, actual {doc.facts.get('finish_pos')}"


def test_top_k_finds_concept():
    index = _index()
    hits = index.search("FIA virtual safety car VSC DEPLOYED minimum time Article 56", k=5)
    concepts = [h for h in hits if h.doc.source == "concept"]
    assert concepts, f"aimed a concept hit, actual {[h.doc.source for h in hits]}"
    assert "56" in concepts[0].doc.text or "VSC" in concepts[0].doc.text
