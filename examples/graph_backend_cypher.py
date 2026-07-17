#!/usr/bin/env python3
"""M2.3 — run a bounded traversal on an external graph DB via openCypher.

The agent never writes Cypher (design_principle_no_query_language). Cairn owns
the bounded-closure INTENT and compiles it into ONE openCypher query; a graph DB
(Neo4j / FalkorDB / Neptune openCypher) runs it. Cairn imports no DB driver —
the driver enters as a caller-supplied `run(query, params)` callable
(storage_agnostic_core).

This demo prints the compiled query, then executes it through a stand-in `run`
(a real deployment passes a Neo4j session; see `neo4j_run` at the bottom). The
result is identical to the in-memory `traverse` on the same graph.

Run:  .venv/bin/python examples/graph_backend_cypher.py
"""

from __future__ import annotations

from typing import Iterable, Mapping

from cairn_engine import (
    Entity,
    InMemoryGraph,
    Ref,
    Relation,
    compile_traversal,
    traverse,
    traverse_cypher,
)


def build() -> InMemoryGraph:
    """A tiny knowledge graph: a paper cites two others; one edge is time-boxed."""
    return InMemoryGraph.from_entities([
        Entity(canonical_id="paper::a", label="A", entity_type="document",
               refs=(Ref(doc_id="doc::a"),),
               relations=(
                   Relation("cites", "paper::b"),
                   Relation("cites", "paper::c", valid_from="2026-07-01", valid_until=None),
               )),
        Entity(canonical_id="paper::b", label="B", entity_type="document",
               refs=(Ref(doc_id="doc::b"),),
               relations=(Relation("cites", "paper::d"),)),
        Entity(canonical_id="paper::c", label="C", entity_type="document", refs=(Ref(doc_id="doc::c"),)),
        Entity(canonical_id="paper::d", label="D", entity_type="document", refs=(Ref(doc_id="doc::d"),)),
    ])


def in_memory_run(graph: InMemoryGraph, *, depth: int) -> "object":
    """A stand-in graph backend: answers the compiled query from `graph`.

    A production deployment replaces this with `neo4j_run` (bottom of file) —
    cairn's traverse_cypher does not care which, it only calls run(text, params).
    """
    from cairn_engine.entity.bitemporal import _within

    def run(query_text: str, params: Mapping[str, str]) -> Iterable[Mapping[str, object]]:
        seed, as_of = params["seed"], params.get("as_of")
        visited, frontier = {seed: 0}, [seed]
        for hop in range(depth):
            nxt = []
            for eid in frontier:
                for rel in graph.edges(eid):
                    if as_of is not None and not _within(rel.valid_from, rel.valid_until, as_of):
                        continue
                    if rel.target_id not in visited and graph.has_entity(rel.target_id):
                        visited[rel.target_id] = hop + 1
                        nxt.append(rel.target_id)
            frontier = sorted(set(nxt))
        return [
            {"entity_id": eid, "hop": hop, "doc_id": r.doc_id, "locator": r.locator}
            for eid, hop in visited.items() for r in graph.refs(eid)
        ]

    return run


def main() -> None:
    graph = build()
    print("=" * 68)
    print("M2.3 — BOUNDED TRAVERSAL COMPILED TO openCypher")
    print("=" * 68)

    q = compile_traversal("paper::a", depth=2, as_of="2026-03-01")
    print("\nCompiled query (the agent never writes this — cairn does):\n")
    print("  " + q.text.replace("\n", "\n  "))
    print(f"\n  params = {dict(q.params)}")

    run = in_memory_run(graph, depth=2)
    got = traverse_cypher("paper::a", run=run, depth=2, as_of="2026-03-01")  # type: ignore[arg-type]
    want = traverse("paper::a", graph=graph, depth=2, as_of="2026-03-01")

    print("\nResult via the graph backend (as_of 2026-03-01 — future edge excluded):")
    for h in got.hits:
        print(f"    {h.ref.doc_id:<8} hop={h.hop} score={h.score:.3f}  ({h.entity_id})")

    print(f"\n  identical to in-memory traverse? {got == want}")
    print("  (same bounded-closure semantics; only the executor changed)")


# --- what a real Neo4j deployment passes as `run` (kept out of the demo path) ---
def neo4j_run(session: "object"):  # pragma: no cover - illustrative only
    """Adapt a neo4j driver session to cairn's run() callable.

        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(uri, auth=(user, pwd))
        with driver.session() as s:
            traverse_cypher("paper::a", run=neo4j_run(s), as_of="2026-03-01")

    Note: `neo4j` is the CALLER's dependency — cairn never imports it.
    """
    def run(query_text: str, params: Mapping[str, str]) -> Iterable[Mapping[str, object]]:
        return [dict(record) for record in session.run(query_text, **params)]  # type: ignore[attr-defined]
    return run


if __name__ == "__main__":
    main()
