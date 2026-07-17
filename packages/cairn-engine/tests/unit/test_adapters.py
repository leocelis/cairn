"""Adapter behavior tests — the frozen closed world's lifecycle (OP-35, TH-1).

Covers what the constraint files for resolve/traverse don't: freeze discipline,
Union-Find merge forwarding, and the from_entities conveniences.
"""

from __future__ import annotations

import pytest

from cairn_engine.adapters.memory import InMemoryAliasTable, InMemoryGraph
from cairn_engine.entity.model import Entity


def _entity(cid: str, label: str, aliases: tuple[str, ...] = ()) -> Entity:
    return Entity(canonical_id=cid, label=label, entity_type="concept", aliases=aliases)


def test_freeze_discipline() -> None:
    table = InMemoryAliasTable()
    table.add(_entity("c::x", "x"))
    with pytest.raises(RuntimeError):
        table.lookup("x")  # not frozen yet — the determinism boundary is the frozen table
    table.freeze()
    assert table.lookup("x")[0].canonical_id == "c::x"
    with pytest.raises(RuntimeError):
        table.add(_entity("c::y", "y"))  # frozen — build-time mutations only
    with pytest.raises(ValueError):
        InMemoryAliasTable.from_entities([_entity("c::x", "x"), _entity("c::x", "x2")])  # dup id


def test_merge_is_union_find_whole_class_moves() -> None:
    """TH-1: after union, EVERY surface of the merged class resolves to the
    representative — including transitively (a -> b -> c)."""
    table = InMemoryAliasTable()
    table.add(_entity("c::llm", "LLM", aliases=("large language model",)))
    table.add(_entity("c::llms", "LLMs"))
    table.add(_entity("c::language_models", "language models"))
    table.merge("c::llms", "c::llm")                    # llms -> llm
    table.merge("c::language_models", "c::llms")        # language_models -> (llms -> llm)
    table.freeze()

    # every surface of the whole class resolves to the ONE representative
    for surface in ("LLM", "LLMs", "language models", "large language model"):
        hits = table.lookup(surface)
        assert [h.canonical_id for h in hits] == ["c::llm"], surface
    # audit trail: records never deleted (has_record), but merged ids are NOT
    # resolvable (has_id False) — two pinned semantics (F7)
    assert table.has_record("c::llms") and table.has_record("c::language_models")
    assert not table.has_id("c::llms") and not table.has_id("c::language_models")
    assert table.has_id("c::llm")
    # merged ids never appear in resolution output
    all_ids = {cid for _, ids in table.normalized_entries() for cid in ids}
    assert all_ids == {"c::llm"}


def test_merge_guards() -> None:
    table = InMemoryAliasTable()
    table.add(_entity("c::a", "a"))
    table.add(_entity("c::b", "b"))
    with pytest.raises(KeyError):
        table.merge("c::ghost", "c::a")
    table.merge("c::a", "c::b")
    table.merge("c::a", "c::b")  # idempotent: same class already
    table.freeze()
    with pytest.raises(RuntimeError):
        table.merge("c::a", "c::b")  # frozen


def test_graph_from_entities_and_freeze_discipline() -> None:
    graph = InMemoryGraph.from_entities([_entity("c::x", "x")])
    assert graph.has_entity("c::x") and not graph.edge_capable()
    with pytest.raises(RuntimeError):
        graph.add(_entity("c::y", "y"))
    unfrozen = InMemoryGraph()
    unfrozen.add(_entity("c::z", "z"))
    with pytest.raises(RuntimeError):
        unfrozen.edges("c::z")

def test_merge_forwards_refs_and_relations_to_representative() -> None:
    """F1: OP-35 'forward all merged_id references' — after a merge, the
    representative's canonical_entities() record absorbs the merged entity's
    refs AND inbound relations are rewritten, so resolve() -> traverse() stays
    coherent (the UC-1 -> UC-2 contract)."""
    from cairn_engine.adapters.memory import InMemoryGraph
    from cairn_engine.entity.model import Ref, Relation
    from cairn_engine.entity.resolve import resolve
    from cairn_engine.entity.traverse import traverse

    table = InMemoryAliasTable()
    table.add(Entity(canonical_id="c::llm", label="LLM", entity_type="concept",
                     refs=(Ref(doc_id="post::intro_llm"),)))
    table.add(Entity(canonical_id="c::llms", label="LLMs", entity_type="concept",
                     refs=(Ref(doc_id="post::llms_deep_dive"),)))
    table.add(Entity(canonical_id="post::a", label="Post A", entity_type="document",
                     refs=(Ref(doc_id="post::a"),),
                     relations=(Relation("mentions", "c::llms"),)))  # edge to the MERGED id
    table.merge("c::llms", "c::llm")
    table.freeze()

    folded = {e.canonical_id: e for e in table.canonical_entities()}
    assert "c::llms" not in folded                       # merged-away: not a representative
    rep = folded["c::llm"]
    assert {r.doc_id for r in rep.refs} == {"post::intro_llm", "post::llms_deep_dive"}  # refs folded
    assert folded["post::a"].relations == (Relation("mentions", "c::llm"),)  # edge rewritten

    # end to end: resolve the merged surface -> traverse finds the folded refs
    graph = InMemoryGraph.from_entities(table.canonical_entities())
    resolved, _ = resolve("", table=table, mentions=["LLMs"])
    assert [r.canonical_id for r in resolved] == ["c::llm"]
    hits = traverse(resolved[0].canonical_id, graph=graph, depth=1).hits
    assert "post::llms_deep_dive" in {h.ref.doc_id for h in hits}  # nothing stranded

    # self-loop dropped: merging entities that pointed at each other
    t2 = InMemoryAliasTable()
    t2.add(Entity(canonical_id="a::x", label="x", entity_type="concept",
                  relations=(Relation("rel", "a::y"),)))
    t2.add(Entity(canonical_id="a::y", label="y", entity_type="concept"))
    t2.merge("a::y", "a::x")
    t2.freeze()
    (rep2,) = t2.canonical_entities()
    assert rep2.relations == ()                          # would-be self-loop dropped
