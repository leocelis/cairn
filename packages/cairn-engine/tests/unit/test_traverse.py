"""Constraint tests for intents/entity_traversal_intent.yaml.

Each test maps 1:1 to a constraint. Golden fixtures hand-computed. Stdlib-only.
"""

from __future__ import annotations

import socket

import pytest

from cairn_engine.adapters.memory import InMemoryGraph
from cairn_engine.entity.model import Entity, Ref, Relation
from cairn_engine.entity.traverse import traverse


def _chain() -> InMemoryGraph:
    """a -> b -> c, one ref per node."""
    g = InMemoryGraph()
    g.add(Entity(canonical_id="post::a", label="A", entity_type="document",
                 refs=(Ref(doc_id="doc::a"),), relations=(Relation("links_to", "post::b"),)))
    g.add(Entity(canonical_id="post::b", label="B", entity_type="document",
                 refs=(Ref(doc_id="doc::b"),), relations=(Relation("links_to", "post::c"),)))
    g.add(Entity(canonical_id="post::c", label="C", entity_type="document",
                 refs=(Ref(doc_id="doc::c"),)))
    return g.freeze()


# -- constraint: hop_distance_discount ----------------------------------------

def test_hop_distance_discount() -> None:
    res = traverse("post::a", graph=_chain(), depth=2)
    by_id = {h.entity_id: h for h in res.hits}
    assert by_id["post::a"].score == 1.0          # hop 0
    assert by_id["post::b"].score == 0.5          # hop 1
    assert by_id["post::c"].score == 1.0 / 3      # hop 2 — exactly 1/(1+2)


# -- constraint: bounded_depth_default2_max3 -----------------------------------

def test_bounded_depth_and_shortest_hop() -> None:
    # depth bound respected
    res1 = traverse("post::a", graph=_chain(), depth=1)
    assert {h.entity_id for h in res1.hits} == {"post::a", "post::b"}  # c is beyond
    # default depth = 2
    res2 = traverse("post::a", graph=_chain())
    assert {h.entity_id for h in res2.hits} == {"post::a", "post::b", "post::c"}
    # out-of-bounds raises
    with pytest.raises(ValueError):
        traverse("post::a", graph=_chain(), depth=4)
    with pytest.raises(ValueError):
        traverse("post::a", graph=_chain(), depth=-1)
    # diamond: a->b, a->c, b->d, c->d AND a->d — d reachable at hop 1 and 2 -> counted ONCE at hop 1
    g = InMemoryGraph()
    g.add(Entity(canonical_id="n::a", label="a", entity_type="concept",
                 relations=(Relation("r", "n::b"), Relation("r", "n::c"), Relation("r", "n::d"))))
    g.add(Entity(canonical_id="n::b", label="b", entity_type="concept",
                 relations=(Relation("r", "n::d"),)))
    g.add(Entity(canonical_id="n::c", label="c", entity_type="concept",
                 relations=(Relation("r", "n::d"),)))
    g.add(Entity(canonical_id="n::d", label="d", entity_type="concept", refs=(Ref(doc_id="doc::d"),)))
    res3 = traverse("n::a", graph=g.freeze(), depth=2)
    d_hits = [h for h in res3.hits if h.entity_id == "n::d"]
    assert len(d_hits) == 1 and d_hits[0].hop == 1  # shortest hop wins


# -- constraint: bitemporal_filter_explicit_asof_only ---------------------------

def test_bitemporal_edge_filter() -> None:
    g = InMemoryGraph()
    g.add(Entity(canonical_id="e::a", label="a", entity_type="concept",
                 relations=(Relation("r", "e::b", valid_from="2026-01-01", valid_until="2026-06-01"),)))
    g.add(Entity(canonical_id="e::b", label="b", entity_type="concept", refs=(Ref(doc_id="doc::b"),)))
    graph = g.freeze()
    inside = traverse("e::a", graph=graph, depth=1, as_of="2026-03-01")
    assert any(h.entity_id == "e::b" for h in inside.hits)          # within [from, until)
    at_end = traverse("e::a", graph=graph, depth=1, as_of="2026-06-01")
    assert not any(h.entity_id == "e::b" for h in at_end.hits)      # half-open: until excluded
    before = traverse("e::a", graph=graph, depth=1, as_of="2025-12-31")
    assert not any(h.entity_id == "e::b" for h in before.hits)      # before valid_from
    unfiltered = traverse("e::a", graph=graph, depth=1, as_of=None)
    assert any(h.entity_id == "e::b" for h in unfiltered.hits)      # None = no filter


# -- constraint: flat_fallback_depth0 -------------------------------------------

def test_flat_fallback() -> None:
    g = InMemoryGraph()
    g.add(Entity(canonical_id="p::x", label="x", entity_type="document",
                 refs=(Ref(doc_id="doc::x1"), Ref(doc_id="doc::x2"))))
    g.add(Entity(canonical_id="p::y", label="y", entity_type="document"))
    graph = g.freeze()  # no edges anywhere -> flat
    res = traverse("p::x", graph=graph, depth=2)
    assert res.traversal_mode == "flat"
    assert [h.ref.doc_id for h in res.hits] == ["doc::x1", "doc::x2"]
    assert all(h.hop == 0 and h.score == 1.0 for h in res.hits)


# -- constraint: closed_world_unknown_seed_empty ---------------------------------

def test_unknown_seed_empty_never_synthesized() -> None:
    graph = _chain()
    res = traverse("post::does_not_exist", graph=graph)
    assert res.hits == ()
    # property: every entity_id in any output is a member of the graph
    res2 = traverse("post::a", graph=graph)
    assert all(graph.has_entity(h.entity_id) for h in res2.hits)
    # dangling edge target (not in graph) is skipped, not fabricated
    g = InMemoryGraph()
    g.add(Entity(canonical_id="d::a", label="a", entity_type="concept",
                 refs=(Ref(doc_id="doc::a"),), relations=(Relation("r", "d::ghost"),)))
    res3 = traverse("d::a", graph=g.freeze())
    assert {h.entity_id for h in res3.hits} == {"d::a"}


# -- constraint: deterministic_order_stdlib_offline -------------------------------

def test_deterministic_and_offline() -> None:
    def run() -> str:
        return repr(traverse("post::a", graph=_chain(), depth=2, as_of="2026-01-01"))

    assert run() == run() == run()  # rebuilt graph each time

    # output ordering: hop asc, then entity_id asc, then doc_id asc
    res = traverse("post::a", graph=_chain(), depth=2)
    keys = [(h.hop, h.entity_id, h.ref.doc_id) for h in res.hits]
    assert keys == sorted(keys)

    real_socket = socket.socket

    def _no_network(*a: object, **k: object) -> object:
        raise AssertionError("network call attempted on the hot path")

    socket.socket = _no_network  # type: ignore[misc, assignment]
    try:
        out = run()
    finally:
        socket.socket = real_socket  # type: ignore[misc]
    assert out == run()


# -- joint satisfaction: ALL constraints on ONE output ----------------------------

def test_joint_all_constraints_on_one_traverse() -> None:
    g = InMemoryGraph()
    g.add(Entity(canonical_id="post::a", label="A", entity_type="document",
                 refs=(Ref(doc_id="doc::a"),),
                 relations=(Relation("links_to", "post::b", valid_from="2026-01-01"),
                            Relation("links_to", "post::gone", valid_from="2020-01-01",
                                     valid_until="2021-01-01"))))
    g.add(Entity(canonical_id="post::b", label="B", entity_type="document",
                 refs=(Ref(doc_id="doc::b"),), relations=(Relation("links_to", "post::c"),)))
    g.add(Entity(canonical_id="post::c", label="C", entity_type="document",
                 refs=(Ref(doc_id="doc::c"),)))
    g.add(Entity(canonical_id="post::gone", label="G", entity_type="document",
                 refs=(Ref(doc_id="doc::gone"),)))
    graph = g.freeze()

    run1 = traverse("post::a", graph=graph, depth=2, as_of="2026-03-01")
    ids = {h.entity_id for h in run1.hits}
    assert run1.traversal_mode == "graph"
    assert ids == {"post::a", "post::b", "post::c"}                       # bounded, temporal filter cut 'gone'
    assert "post::gone" not in ids                                        # bitemporal (expired edge)
    scores = {h.entity_id: h.score for h in run1.hits}
    assert (scores["post::a"], scores["post::b"], scores["post::c"]) == (1.0, 0.5, 1.0 / 3)  # discount
    assert all(graph.has_entity(i) for i in ids)                          # closed world
    assert repr(run1) == repr(traverse("post::a", graph=graph, depth=2, as_of="2026-03-01"))  # byte-stable
