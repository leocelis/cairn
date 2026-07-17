"""Integration test — the full entity-engine path on a WordPress-like mini corpus.

End-to-end: build entities from blog posts -> freeze the alias table + graph ->
resolve concept mentions in post text -> traverse to connected posts -> derive
the two link surfaces of the M1.6 use case:

    (a) mid-content anchors: concept mentions found in a post's body, each
        linking to the post that owns that concept
    (b) end-of-post next reads: graph-connected posts, capped at 3, ordered

This crosses every implemented module (model, normalize, memory adapters,
resolve, traverse) through public APIs only.
"""

from __future__ import annotations

from cairn_engine.adapters.memory import InMemoryAliasTable, InMemoryGraph
from cairn_engine.entity.model import Entity, Ref, Relation
from cairn_engine.entity.resolve import resolve
from cairn_engine.entity.traverse import traverse

# --- the corpus: 3 posts, 2 concepts (as a WordPress site would author it) ----

POSTS = {
    "post::decision_layer": {
        "title": "The Decision Layer",
        "body": "Most teams automate labor. The real shift is entity resolution "
                "applied to decisions — the decision layer sits above the tools.",
    },
    "post::entity_resolution_101": {
        "title": "Entity Resolution 101",
        "body": "Entity resolution maps messy references to canonical identity. "
                "It is the foundation under any world model.",
    },
    "post::world_models": {
        "title": "World Models for Agents",
        "body": "A world model is a map of entities and relations. Retrieval "
                "without it is guessing.",
    },
}


def _build() -> tuple[InMemoryAliasTable, InMemoryGraph]:
    entities = [
        # concepts (what an authoring pass would extract and a human would freeze)
        Entity(canonical_id="concept::entity_resolution", label="entity resolution",
               entity_type="concept", aliases=("entity-resolution",),
               refs=(Ref(doc_id="post::entity_resolution_101"),)),
        Entity(canonical_id="concept::world_model", label="world model",
               entity_type="concept", aliases=("world models",),
               refs=(Ref(doc_id="post::world_models"),)),
        Entity(canonical_id="concept::decision_layer", label="the decision layer",
               entity_type="concept", aliases=("decision layer",),
               refs=(Ref(doc_id="post::decision_layer"),)),
        # posts as entities, edges = "mentions concept" (authoring output)
        Entity(canonical_id="post::decision_layer", label="The Decision Layer",
               entity_type="document", refs=(Ref(doc_id="post::decision_layer"),),
               relations=(Relation("mentions", "concept::entity_resolution"),
                          Relation("mentions", "concept::decision_layer"))),
        Entity(canonical_id="post::entity_resolution_101", label="Entity Resolution 101",
               entity_type="document", refs=(Ref(doc_id="post::entity_resolution_101"),),
               relations=(Relation("mentions", "concept::entity_resolution"),
                          Relation("mentions", "concept::world_model"))),
        Entity(canonical_id="post::world_models", label="World Models for Agents",
               entity_type="document", refs=(Ref(doc_id="post::world_models"),),
               relations=(Relation("mentions", "concept::world_model"),)),
    ]
    table, graph = InMemoryAliasTable(), InMemoryGraph()
    for e in entities:
        table.add(e)
        graph.add(e)
    return table.freeze(), graph.freeze()


def test_mid_content_anchor_detection() -> None:
    """(a) concept mentions in a post body resolve to canonical concepts —
    these become the mid-content anchors."""
    table, _ = _build()
    body = POSTS["post::decision_layer"]["body"]
    resolved, unresolved = resolve(body, table=table)
    ids = {r.canonical_id for r in resolved}
    assert "concept::entity_resolution" in ids   # anchor found mid-content
    assert "concept::decision_layer" in ids
    assert unresolved == []
    # each anchor knows its target post (the concept's ref)
    # concept::entity_resolution -> post::entity_resolution_101 (by construction)


def test_end_of_post_next_reads_via_traversal() -> None:
    """(b) 2-hop traversal from a post reaches sibling posts through shared
    concepts — post -> concept -> (refs of concept + onward posts' refs)."""
    _, graph = _build()
    res = traverse("post::decision_layer", graph=graph, depth=2)
    assert res.traversal_mode == "graph"
    doc_ids = [h.ref.doc_id for h in res.hits]
    # the sibling post that shares 'entity resolution' is reachable
    assert "post::entity_resolution_101" in doc_ids
    # next-reads = connected docs excluding self, capped at 3 (choice overload)
    next_reads = [d for d in dict.fromkeys(doc_ids) if d != "post::decision_layer"][:3]
    assert 1 <= len(next_reads) <= 3
    assert next_reads[0] == "post::entity_resolution_101"  # hop-1 concept ref outranks hop-2


def test_full_pipeline_deterministic_and_closed_world() -> None:
    """The whole path — resolve + traverse — is byte-stable and never invents IDs."""
    def run() -> str:
        table, graph = _build()  # rebuilt from scratch
        body = POSTS["post::entity_resolution_101"]["body"]
        r, u = resolve(body, table=table)
        t = traverse("post::entity_resolution_101", graph=graph, depth=2)
        return repr((r, u, t))

    assert run() == run()
    table, graph = _build()
    r, _ = resolve("something about world models and unknown nonsense", table=table)
    assert all(table.has_id(x.canonical_id) for x in r)
    assert traverse("post::nope", graph=graph).hits == ()
