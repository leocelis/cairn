#!/usr/bin/env python3
"""Cairn demo — the WordPress entity-graph use case (M1.6 preview), end to end.

Builds a tiny 3-post blog corpus, freezes the entity map, then produces the two
link surfaces:
  (a) mid-content anchors — concept mentions inside each post body, each linking
      to the post that owns that concept
  (b) end-of-post next reads — graph-connected posts (max 3, subordinate)

Run it (no API keys, no network, stdlib + cairn only):

    .venv/bin/python examples/blog_graph_demo.py
"""

from __future__ import annotations

from cairn_engine.adapters.memory import InMemoryAliasTable, InMemoryGraph
from cairn_engine.entity.model import Entity, Ref, Relation
from cairn_engine.entity.ontology import with_mirror_edges
from cairn_engine.entity.resolve import resolve
from cairn_engine.entity.traverse import traverse

POSTS = {
    "post::decision_layer": (
        "The Decision Layer",
        "Most teams automate labor. The real shift is entity resolution applied "
        "to decisions — the decision layer sits above the tools.",
    ),
    "post::entity_resolution_101": (
        "Entity Resolution 101",
        "Entity resolution maps messy references to canonical identity. It is "
        "the foundation under any world model.",
    ),
    "post::world_models": (
        "World Models for Agents",
        "A world model is a map of entities and relations. Retrieval without "
        "it is guessing.",
    ),
}

# The frozen entity map (in real life: authored offline via author_from_text,
# human-reviewed, then frozen — see OP-35).
CONCEPTS = {
    "concept::entity_resolution": ("entity resolution", ("entity-resolution",), "post::entity_resolution_101"),
    "concept::world_model": ("world model", ("world models",), "post::world_models"),
    "concept::decision_layer": ("the decision layer", ("decision layer",), "post::decision_layer"),
}
MENTIONS = {
    "post::decision_layer": ("concept::entity_resolution", "concept::decision_layer"),
    "post::entity_resolution_101": ("concept::entity_resolution", "concept::world_model"),
    "post::world_models": ("concept::world_model",),
}


def build() -> tuple[InMemoryAliasTable, InMemoryGraph]:
    table, graph = InMemoryAliasTable(), InMemoryGraph()
    entities: list[Entity] = []
    for cid, (label, aliases, owner_post) in CONCEPTS.items():
        entities.append(Entity(canonical_id=cid, label=label, entity_type="concept",
                               aliases=aliases, refs=(Ref(doc_id=owner_post),)))
    for pid, (title, _body) in POSTS.items():
        entities.append(Entity(canonical_id=pid, label=title, entity_type="document",
                               refs=(Ref(doc_id=pid),),
                               relations=tuple(Relation("mentions", c) for c in MENTIONS[pid])))
    # Mirror edges (mentions -> mentioned_in) make traversal symmetric: without
    # them, a post can't reach its sibling back through a shared concept.
    for e in with_mirror_edges(entities):
        table.add(e)
        graph.add(e)
    return table.freeze(), graph.freeze()


def main() -> None:
    table, graph = build()
    concept_owner = {cid: spec[2] for cid, spec in CONCEPTS.items()}

    for pid, (title, body) in POSTS.items():
        print(f"\n=== {title} ({pid})")

        # (a) mid-content anchors
        resolved, _ = resolve(body, table=table)
        anchors = [(r.surface_form, concept_owner[r.canonical_id])
                   for r in resolved
                   if r.canonical_id in concept_owner and concept_owner[r.canonical_id] != pid]
        print("  mid-content anchors:")
        for surface, target in anchors or [("(none)", "-")]:
            print(f'    "{surface}" -> {target}')

        # (b) end-of-post next reads (max 3, self excluded, hop-ordered)
        result = traverse(pid, graph=graph, depth=2)
        next_reads = [d for d in dict.fromkeys(h.ref.doc_id for h in result.hits) if d != pid][:3]
        print("  next reads:")
        for d in next_reads or ["(none)"]:
            print(f"    {d}")

    print("\nDeterministic, offline, zero-LLM — run it twice, get identical output.")


if __name__ == "__main__":
    main()
