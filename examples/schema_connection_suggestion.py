#!/usr/bin/env python3
"""Connection suggestion — which existing tables should a NEW table connect to?

The schema-graph problem: an agent asked to design a new `news` table has no map
of the existing schema, so it designs in isolation and misses the foreign keys it
should share. `suggest_connections` scores the candidate table against the
existing entity graph and returns the ranked tables it should link to — with the
shared concepts (columns/tags) that earned each suggestion.

Cold start: the `news` table has no edges yet, so structural indices are 0 and
CONTENT similarity (shared concepts, corpus IDF) does the work. If the agent
already knows one relationship ("news relates to author"), pass it as a seed to
add a Resource-Allocation structural boost over that neighbourhood.

Fictional CMS schema — no real data.

Run:  .venv/bin/python examples/schema_connection_suggestion.py
"""

from __future__ import annotations

from cairn_engine import Entity, Relation
from cairn_retrieval import suggest_connections


def _tbl(name: str, concepts: list[str], links: list[str] = []) -> Entity:
    rels = [Relation("has_column", f"concept::{c}") for c in concepts]
    rels += [Relation("relates_to", f"table::{t}") for t in links]  # entity-entity edges
    return Entity(canonical_id=f"table::{name}", label=name,
                  entity_type="document", relations=tuple(rels))


def build() -> list[Entity]:
    """A small fictional CMS schema: 6 tables, shared 'column' concepts."""
    concepts = [
        Entity(canonical_id=f"concept::{c}", label=c, entity_type="concept")
        for c in ("id", "author_id", "category_id", "title", "body",
                  "published_at", "media_id", "tag_id", "slug")
    ]
    tables = [
        _tbl("article",  ["id", "author_id", "category_id", "title", "body",
                           "published_at", "slug"], links=["author", "category"]),
        _tbl("author",   ["id", "slug"]),
        _tbl("category", ["id", "slug"]),
        _tbl("comment",  ["id", "author_id", "body", "published_at"], links=["author"]),
        _tbl("media",    ["id", "media_id", "slug"]),
        _tbl("tag",      ["id", "tag_id", "slug"]),
    ]
    return concepts + tables


def main() -> None:
    existing = build()

    # The NEW table the agent is about to design — its planned columns.
    news = Entity(
        canonical_id="table::news", label="news", entity_type="document",
        relations=(Relation("has_column", "concept::id"),
                   Relation("has_column", "concept::author_id"),
                   Relation("has_column", "concept::category_id"),
                   Relation("has_column", "concept::title"),
                   Relation("has_column", "concept::body"),
                   Relation("has_column", "concept::published_at"),
                   Relation("has_column", "concept::slug")))

    print("=" * 72)
    print("NEW TABLE: news  (columns: id, author_id, category_id, title, body,")
    print("                          published_at, slug)")
    print("=" * 72)
    print("\nCOLD START — no known relationships yet (content similarity only):\n")
    for p in suggest_connections(news, existing, top_k=4):
        cols = ", ".join(c.split("::")[1] for c in p.shared)
        print(f"  connect to  table::{p.target_id.split('::')[1]:10} "
              f"score={p.score:.3f}  shared columns: {cols}")

    print("\nWITH A SEED — agent already knows 'news relates to author':\n")
    for p in suggest_connections(news, existing, seeds=["table::author"], top_k=4):
        cols = ", ".join(c.split("::")[1] for c in p.shared) or "(structural only)"
        via = ", ".join(v.split("::")[1] for v in p.via)
        boost = f"  +structural via {via}" if via else ""
        print(f"  connect to  table::{p.target_id.split('::')[1]:10} "
              f"score={p.score:.3f}  {cols}{boost}")

    print("\nCairn SUGGESTS the connections with evidence; the agent (or a human)")
    print("decides which foreign keys to actually create. No edge is invented.")


if __name__ == "__main__":
    main()
