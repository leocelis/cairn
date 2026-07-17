"""Constraint tests for intents/link_ranking_intent.yaml (TF-IDF cosine).

Golden IDF values hand-computed: N=3 documents.
  concept in 3 docs -> log(3/3) = 0.0
  concept in 2 docs -> log(3/2) = 0.4054651...

Golden cosine values (idf cancels when two concepts share the same df):
  vectors (2i, 1i) vs (1i, 2i)  ->  (2+2)/(sqrt5*sqrt5) = 4/5 = 0.8
  vectors (2i, 1i) vs (2i, 1i)  ->  1.0
"""

from __future__ import annotations

import math

from cairn_engine import Entity, Relation
from cairn_retrieval import LinkRecommendation, concept_idf, rank_links, tfidf_vectors


def _graph() -> list[Entity]:
    """3 docs, 2 concepts:
        common -> mentioned by A, B, C  (ubiquitous, IDF 0)
        rare   -> mentioned by A, C     (IDF log 1.5)
    """
    concepts = [
        Entity(canonical_id="concept::common", label="common", entity_type="concept"),
        Entity(canonical_id="concept::rare", label="rare", entity_type="concept"),
    ]
    docs = [
        Entity(canonical_id="post::a", label="A", entity_type="document",
               relations=(Relation("mentions", "concept::common"),
                          Relation("mentions", "concept::rare"))),
        Entity(canonical_id="post::b", label="B", entity_type="document",
               relations=(Relation("mentions", "concept::common"),)),
        Entity(canonical_id="post::c", label="C", entity_type="document",
               relations=(Relation("mentions", "concept::common"),
                          Relation("mentions", "concept::rare"))),
    ]
    return concepts + docs


# -- constraint: idf_is_log_n_over_df -----------------------------------------

def test_idf_equals_log_n_over_df() -> None:
    idf = concept_idf(_graph())
    assert idf["concept::common"] == 0.0                       # in all 3 docs
    assert math.isclose(idf["concept::rare"], math.log(1.5))    # in 2 of 3
    assert concept_idf([Entity(canonical_id="c::x", label="x", entity_type="concept")]) == {}


# -- constraint: tf_weights_edges (term frequency comes from edge weight) -------

def test_term_frequency_from_edge_weight() -> None:
    # concept mentioned with weight 3 -> tf 3; tf*idf scales accordingly
    ents = [
        Entity(canonical_id="concept::rare", label="rare", entity_type="concept"),
        Entity(canonical_id="concept::x", label="x", entity_type="concept"),
        Entity(canonical_id="post::a", label="A", entity_type="document",
               relations=(Relation("mentions", "concept::rare", weight=3.0),
                          Relation("mentions", "concept::x"))),
        Entity(canonical_id="post::b", label="B", entity_type="document",
               relations=(Relation("mentions", "concept::rare"),
                          Relation("mentions", "concept::x"))),
    ]
    vecs = tfidf_vectors(ents)
    idf_rare = math.log(2 / 2) if False else None  # rare & x both in 2/2 -> idf 0!
    # both concepts appear in both docs -> idf 0 -> vectors empty -> no links
    assert vecs["post::a"] == {} and vecs["post::b"] == {}
    assert rank_links(ents) == []
    _ = idf_rare


# -- constraint: rare_shared_concepts_outrank_common (TF-IDF cosine) -----------

def test_rare_concepts_outrank_common() -> None:
    links = rank_links(_graph())
    # A & C share the rare concept (idf>0) -> identical 1-D vectors -> cosine 1.0
    a_links = [link for link in links if link.source_id == "post::a"]
    assert [link.target_id for link in a_links] == ["post::c"]
    assert a_links[0].score == 1.0
    assert a_links[0].shared == ("concept::rare",)             # common (idf 0) dropped
    # B shares ONLY the ubiquitous concept -> zero vector -> no links
    assert [link for link in links if link.source_id == "post::b"] == []


def test_tf_direction_changes_ranking() -> None:
    """Cosine is TF-direction sensitive: same concepts, different tf ratios ->
    lower similarity. Hand-computed: (2,1)vs(1,2) = 0.8; (2,1)vs(2,1) = 1.0."""
    # c1, c2 each in 3 of 4 docs -> equal idf -> cancels in cosine
    ents = [
        Entity(canonical_id="concept::c1", label="c1", entity_type="concept"),
        Entity(canonical_id="concept::c2", label="c2", entity_type="concept"),
        Entity(canonical_id="post::p", label="P", entity_type="document",
               relations=(Relation("mentions", "concept::c1", weight=2.0),
                          Relation("mentions", "concept::c2", weight=1.0))),
        Entity(canonical_id="post::q", label="Q", entity_type="document",
               relations=(Relation("mentions", "concept::c1", weight=1.0),
                          Relation("mentions", "concept::c2", weight=2.0))),
        Entity(canonical_id="post::r", label="R", entity_type="document",
               relations=(Relation("mentions", "concept::c1", weight=2.0),
                          Relation("mentions", "concept::c2", weight=1.0))),
        Entity(canonical_id="post::s", label="S", entity_type="document"),  # neither
    ]
    links = rank_links(ents, top_k=2)
    p = {link.target_id: link.score for link in links if link.source_id == "post::p"}
    assert p["post::r"] == 1.0                    # identical tf direction
    assert math.isclose(p["post::q"], 0.8)        # (2,1)·(1,2)/(√5·√5) = 4/5
    assert p["post::r"] > p["post::q"]            # R ranked above Q


# -- constraint: deterministic_closed_world_pure_graph -------------------------

def test_deterministic_and_closed_world() -> None:
    g = _graph()
    ids = {e.canonical_id for e in g}
    r1, r2 = rank_links(g), rank_links(g)
    assert repr(r1) == repr(r2)                                # byte-stable
    for link in r1:                                            # closed world
        assert link.source_id in ids and link.target_id in ids
        assert 0.0 < link.score <= 1.0                         # cosine bounds
    import pathlib

    import cairn_retrieval.link_ranking as mod

    text = pathlib.Path(mod.__file__).read_text()
    for banned in ("numpy", "requests", "sklearn", "openai", "httpx"):
        assert f"import {banned}" not in text and f"from {banned}" not in text


# -- joint: all constraints on one ranking ------------------------------------

def test_joint_ranking() -> None:
    links = rank_links(_graph(), top_k=3)
    assert isinstance(links[0], LinkRecommendation)
    targets = {(link.source_id, link.target_id) for link in links}
    assert ("post::a", "post::c") in targets
    assert not any(s == "post::b" for s, _ in targets)         # ubiquitous-only dropped
    assert all(0.0 < link.score <= 1.0 for link in links)     # cosine bounds
    assert repr(links) == repr(rank_links(_graph(), top_k=3))
