"""Constraint tests for intents/graph_backend_intent.yaml (M2.3, OQ-3 openCypher).

Each test maps 1:1 to a constraint (C-CYPHER-1..5) plus one joint test. The
"backend" is a fake run() that answers the compiled query FROM an in-memory
graph via an independent BFS — the differential oracle. Stdlib-only, no driver.
"""

from __future__ import annotations

import pathlib
from typing import Iterable, Mapping

import pytest

from cairn_engine.adapters.cypher import CypherRunFn, compile_traversal, traverse_cypher
from cairn_engine.adapters.memory import InMemoryGraph
from cairn_engine.entity.bitemporal import _within
from cairn_engine.entity.model import Entity, Ref, Relation
from cairn_engine.entity.traverse import traverse

_CORE = pathlib.Path(__file__).parents[3] / "cairn-engine" / "src" / "cairn_engine"


# -- a small graph + a fake openCypher backend over it ---------------------------

def _graph() -> InMemoryGraph:
    """a -> b -> c -> d; a also -> e. b has two refs; c is ref-less."""
    return InMemoryGraph.from_entities([
        Entity(canonical_id="e::a", label="A", entity_type="concept",
               refs=(Ref(doc_id="doc::a"),),
               relations=(Relation("r", "e::b"), Relation("r", "e::e"))),
        Entity(canonical_id="e::b", label="B", entity_type="concept",
               refs=(Ref(doc_id="doc::b1"), Ref(doc_id="doc::b2", locator="p3")),
               relations=(Relation("r", "e::c"),)),
        Entity(canonical_id="e::c", label="C", entity_type="concept",  # ref-less
               relations=(Relation("r", "e::d"),)),
        Entity(canonical_id="e::d", label="D", entity_type="concept",
               refs=(Ref(doc_id="doc::d"),)),
        Entity(canonical_id="e::e", label="E", entity_type="concept",
               refs=(Ref(doc_id="doc::e"),)),
    ])


def _fake_db(graph: InMemoryGraph, *, depth: int) -> CypherRunFn:
    """Independent BFS oracle standing in for a graph DB. Emits DB-style rows in
    REVERSE order (one per node-ref, plus a null-ref row for ref-less nodes) to
    prove traverse_cypher re-sorts and skips null refs."""

    def run(query_text: str, params: Mapping[str, str]) -> Iterable[Mapping[str, object]]:
        seed = params["seed"]
        as_of = params.get("as_of")
        known = params.get("known_as_of")
        if not graph.has_entity(seed):
            return []
        visited = {seed: 0}
        frontier = [seed]
        for hop in range(depth):
            nxt: list[str] = []
            for eid in frontier:
                for rel in graph.edges(eid):
                    if as_of is not None and not _within(rel.valid_from, rel.valid_until, as_of):
                        continue
                    if known is not None and not _within(rel.known_from, rel.known_until, known):
                        continue
                    t = rel.target_id
                    if t in visited or not graph.has_entity(t):
                        continue
                    visited[t] = hop + 1
                    nxt.append(t)
            frontier = sorted(set(nxt))
        rows: list[Mapping[str, object]] = []
        for eid, hop in visited.items():
            refs = graph.refs(eid)
            if not refs:
                rows.append({"entity_id": eid, "hop": hop, "doc_id": None, "locator": None})
            for r in refs:
                rows.append({"entity_id": eid, "hop": hop, "doc_id": r.doc_id, "locator": r.locator})
        rows.reverse()
        return rows

    return run


# -- C-CYPHER-1: golden query, no temporal filter --------------------------------

def test_compile_golden() -> None:
    q = compile_traversal("e::a", depth=2)
    assert q.text == (
        "MATCH p = (seed:Entity {id: $seed})-[rels*0..2]->(n:Entity)\n"
        "WITH n, min(length(p)) AS hop\n"
        "OPTIONAL MATCH (n)-[:HAS_REF]->(ref:Ref)\n"
        "RETURN n.id AS entity_id, hop, ref.doc_id AS doc_id, ref.locator AS locator\n"
        "ORDER BY hop, entity_id, doc_id"
    )
    assert q.params == {"seed": "e::a"}
    assert compile_traversal("e::a", depth=2).text == q.text  # byte-stable


# -- C-CYPHER-2: conditional per-axis bitemporal filters -------------------------

def test_compile_bitemporal_axes() -> None:
    none = compile_traversal("e::a")
    assert "WHERE" not in none.text and none.params == {"seed": "e::a"}

    v = compile_traversal("e::a", as_of="2026-03-01")
    assert "r.valid_from IS NULL OR r.valid_from <= $as_of" in v.text
    assert "$as_of < r.valid_until" in v.text
    assert "known" not in v.text and v.params["as_of"] == "2026-03-01"

    k = compile_traversal("e::a", known_as_of="2026-03-01")
    assert "r.known_from IS NULL OR r.known_from <= $known_as_of" in k.text
    assert "valid_from" not in k.text and k.params["known_as_of"] == "2026-03-01"

    both = compile_traversal("e::a", as_of="2026-01-01", known_as_of="2026-02-01")
    assert both.text.count("all(r IN rels WHERE") == 1  # one combined predicate
    assert " AND " in both.text.split("all(r IN rels WHERE")[1]
    assert both.params == {"seed": "e::a", "as_of": "2026-01-01", "known_as_of": "2026-02-01"}


# -- C-CYPHER-3: depth bound + injection-safety ----------------------------------

def test_depth_bound_and_no_injection() -> None:
    for bad in (-1, 4, 99):
        with pytest.raises(ValueError):
            compile_traversal("e::a", depth=bad)
    assert "*0..0" in compile_traversal("e::a", depth=0).text
    assert "*0..3" in compile_traversal("e::a", depth=3).text

    evil = '") DELETE (x) //'
    q = compile_traversal(evil, depth=1)
    assert q.params["seed"] == evil          # user string is a param...
    assert evil not in q.text                # ...never interpolated into the query


# -- C-CYPHER-4: executor result == in-memory traverse ---------------------------

def test_traverse_cypher_matches_in_memory() -> None:
    g = _graph()
    got = traverse_cypher("e::a", run=_fake_db(g, depth=2), depth=2)
    want = traverse("e::a", graph=g, depth=2)
    assert got == want
    assert got.traversal_mode == "graph"
    # sanity: ref-less node e::c is reached but contributes no hit
    assert all(h.entity_id != "e::c" for h in got.hits)
    assert {h.ref.doc_id for h in got.hits} == {"doc::a", "doc::b1", "doc::b2", "doc::e"}


# -- C-CYPHER-5: core imports no DB driver; compile byte-stable (conflict_prone) --

def test_core_imports_no_db_driver() -> None:
    banned = ("import neo4j", "from neo4j", "import falkordb", "from falkordb",
              "import pyodbc", "import psycopg", "import redis", "GraphDatabase")
    for path in _CORE.rglob("*.py"):
        src = path.read_text()
        for token in banned:
            assert token not in src, f"{path.name} imports a DB driver: {token!r}"

    a = compile_traversal("e::a", depth=2, as_of="2026-01-01", known_as_of="2026-02-01")
    b = compile_traversal("e::a", depth=2, as_of="2026-01-01", known_as_of="2026-02-01")
    assert a == b  # byte-stable


# -- joint satisfaction (5 constraints) ------------------------------------------

def test_joint_cypher() -> None:
    """Compile a bitemporal bounded traversal (C-1,2,3), execute via a fake driver
    (C-5: no real driver imported), and assert the result equals in-memory
    traverse WITH the same filter (C-4), byte-stable (C-5)."""
    g = InMemoryGraph.from_entities([
        Entity(canonical_id="e::a", label="A", entity_type="concept",
               refs=(Ref(doc_id="doc::a"),),
               relations=(
                   Relation("r", "e::b", valid_from="2026-01-01", valid_until="2026-06-01"),
                   Relation("r", "e::c", valid_from="2026-07-01", valid_until=None),  # future
               )),
        Entity(canonical_id="e::b", label="B", entity_type="concept", refs=(Ref(doc_id="doc::b"),)),
        Entity(canonical_id="e::c", label="C", entity_type="concept", refs=(Ref(doc_id="doc::c"),)),
    ])
    as_of = "2026-03-01"  # b-edge valid, c-edge not yet

    q = compile_traversal("e::a", depth=2, as_of=as_of)
    assert q.params == {"seed": "e::a", "as_of": as_of}      # C-2/C-3
    assert "*0..2" in q.text                                  # C-1/C-3

    got = traverse_cypher("e::a", run=_fake_db(g, depth=2), depth=2, as_of=as_of)
    want = traverse("e::a", graph=g, depth=2, as_of=as_of)   # C-4 oracle
    assert got == want
    assert {h.ref.doc_id for h in got.hits} == {"doc::a", "doc::b"}  # c excluded by time
    assert compile_traversal("e::a", depth=2, as_of=as_of) == q     # C-5 byte-stable
