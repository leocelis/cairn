"""Constraint tests for intents/connection_suggestion_intent.yaml (OP-36).

Cold-start link prediction: rank existing entities a NEW candidate should link
to. Content-first (TF-IDF cosine, corpus IDF); optional seed-gated Resource
Allocation structural term.

Golden values (N=3 documents A,B,C):
  common  in A,B,C -> IDF log(3/3) = 0.0  (dropped)
  rare    in A,C   -> IDF log(3/2) = 0.405465...
  niche   in A     -> IDF log(3/1) = 1.098612...
Candidate shares {rare, niche}:
  content(A) = cosine(identical vectors)                 = 1.0
  content(C) = log1.5 / sqrt(log1.5^2 + log3^2)          = 0.346285...
  content(B) = 0 (ubiquitous-only) -> dropped
Resource Allocation: seed s contributes 1/deg(s) to each neighbour of s.
"""

from __future__ import annotations

import math

from cairn_engine import Entity, Relation
from cairn_retrieval import ConnectionSuggestion, suggest_connections


def _corpus() -> list[Entity]:
    """3 documents + 3 concepts (one ubiquitous, one shared, one unique)."""
    concepts = [
        Entity(canonical_id="concept::common", label="common", entity_type="concept"),
        Entity(canonical_id="concept::rare", label="rare", entity_type="concept"),
        Entity(canonical_id="concept::niche", label="niche", entity_type="concept"),
    ]
    docs = [
        Entity(canonical_id="post::a", label="A", entity_type="document",
               relations=(Relation("mentions", "concept::common"),
                          Relation("mentions", "concept::rare"),
                          Relation("mentions", "concept::niche"))),
        Entity(canonical_id="post::b", label="B", entity_type="document",
               relations=(Relation("mentions", "concept::common"),)),
        Entity(canonical_id="post::c", label="C", entity_type="document",
               relations=(Relation("mentions", "concept::common"),
                          Relation("mentions", "concept::rare"))),
    ]
    return concepts + docs


def _candidate() -> Entity:
    """A NOT-yet-existing node that mentions the shared + unique concepts."""
    return Entity(canonical_id="post::new", label="NEW", entity_type="document",
                  relations=(Relation("mentions", "concept::rare"),
                             Relation("mentions", "concept::niche")))


# -- constraint: content_similarity_cold_start --------------------------------

def test_content_ranks_shared_rare_concept_first() -> None:
    picks = suggest_connections(_candidate(), _corpus())
    ids = [p.target_id for p in picks]
    # A shares both rare+niche (identical vector) -> content 1.0, ranked first.
    assert picks[0].target_id == "post::a"
    assert picks[0].content_score == 1.0
    assert picks[0].shared == ("concept::niche", "concept::rare")  # common (IDF 0) dropped
    # C shares only rare -> present but lower.
    c = next(p for p in picks if p.target_id == "post::c")
    expected_c = math.log(1.5) / math.hypot(math.log(1.5), math.log(3))  # 0.346242
    assert math.isclose(c.content_score, expected_c, abs_tol=1e-6)
    assert 0.0 < c.content_score < 1.0
    # B shares only the ubiquitous concept -> score 0 -> dropped entirely.
    assert "post::b" not in ids


# -- constraint: structural_signal_optional_seeds_only ------------------------

def test_structural_zero_without_seeds() -> None:
    # No seeds -> every structural_score is exactly 0 (cold node has no edges).
    for p in suggest_connections(_candidate(), _corpus()):
        assert p.structural_score == 0.0
        assert p.via == ()


def test_structural_fires_only_with_seeds() -> None:
    """Resource Allocation: seed A (deg 2) contributes 1/2 to each neighbour."""
    docs = [
        Entity(canonical_id="doc::a", label="A", entity_type="document",
               relations=(Relation("relates_to", "doc::b"),
                          Relation("relates_to", "doc::c"))),  # deg(A) = 2
        Entity(canonical_id="doc::b", label="B", entity_type="document"),
        Entity(canonical_id="doc::c", label="C", entity_type="document"),
    ]
    cand = Entity(canonical_id="doc::new", label="NEW", entity_type="document")
    # candidate provisionally relates to A; B and C share A as a neighbour.
    picks = suggest_connections(cand, docs, seeds=["doc::a"], graph_weight=0.25)
    got = {p.target_id: p for p in picks}
    assert set(got) == {"doc::b", "doc::c"}          # A is an input (seed), not a result
    for p in got.values():
        assert math.isclose(p.structural_score, 0.5)  # RA: 1/deg(A)=1/2, normalised by 1 seed
        assert p.via == ("doc::a",)                    # provenance: which seed drove it
        assert math.isclose(p.score, 0.25 * 0.5)       # content 0 -> total = weight*struct


# -- constraint: provenance_and_closed_world ----------------------------------

def test_provenance_and_empty_on_no_overlap() -> None:
    # A candidate whose only concept is novel to the corpus -> nothing to connect.
    novel = Entity(canonical_id="post::x", label="X", entity_type="document",
                   relations=(Relation("mentions", "concept::unknown"),))
    assert suggest_connections(novel, _corpus()) == []
    # An empty candidate with no seeds -> [].
    assert suggest_connections(Entity(canonical_id="post::y", label="Y",
                                      entity_type="document"), _corpus()) == []
    # Real suggestions carry their shared-concept evidence.
    for p in suggest_connections(_candidate(), _corpus()):
        assert p.shared  # non-empty provenance


# -- constraint: deterministic_pure_graph_no_engine_leak ----------------------

def test_deterministic_and_closed_world() -> None:
    corpus, cand = _corpus(), _candidate()
    ids = {e.canonical_id for e in corpus}
    r1, r2 = suggest_connections(cand, corpus), suggest_connections(cand, corpus)
    assert repr(r1) == repr(r2)                                   # byte-stable
    for p in r1:                                                  # closed world
        assert p.target_id in ids and p.target_id != cand.canonical_id
        assert p.score > 0.0
    import pathlib

    import cairn_retrieval.connections as mod

    text = pathlib.Path(mod.__file__).read_text()
    for banned in ("numpy", "requests", "sklearn", "openai", "httpx", "torch"):
        assert f"import {banned}" not in text and f"from {banned}" not in text


# -- joint: all four constraints on one suggestion set ------------------------

def test_joint_connection_suggestion() -> None:
    """Content (A) + structural (B via seed C) + provenance + determinism, one call."""
    corpus = _corpus()
    # add an entity-entity edge so a seed can drive a structural suggestion
    b = next(e for e in corpus if e.canonical_id == "post::b")
    corpus = [e for e in corpus if e.canonical_id != "post::b"] + [
        Entity(canonical_id="post::b", label="B", entity_type="document",
               relations=(Relation("mentions", "concept::common"),
                          Relation("relates_to", "post::c")))  # B—C entity edge, deg(C)=1
    ]
    picks = suggest_connections(_candidate(), corpus, seeds=["post::c"], graph_weight=0.25)
    got = {p.target_id: p for p in picks}
    assert isinstance(picks[0], ConnectionSuggestion)
    # content: A shares rare+niche -> ranked first at 1.0
    assert picks[0].target_id == "post::a" and picks[0].content_score == 1.0
    assert picks[0].shared and picks[0].via == ()                 # content-only provenance
    # structural: B is a neighbour of seed C -> surfaced via structure alone
    assert got["post::b"].content_score == 0.0
    assert got["post::b"].via == ("post::c",) and got["post::b"].shared == ()
    # closed world + determinism
    assert "post::c" not in got                                   # seed is an input
    assert all(p.target_id in {"post::a", "post::b"} for p in picks)
    assert repr(picks) == repr(
        suggest_connections(_candidate(), corpus, seeds=["post::c"], graph_weight=0.25))
    _ = b
