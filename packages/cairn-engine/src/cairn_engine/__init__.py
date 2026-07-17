"""Cairn — the deterministic entity / world-model engine for AI agents.

Resolve messy references to canonical IDs, traverse their relations, and author
the frozen alias table that makes it all reproducible — storage-agnostic,
local-first, zero generative-LLM on the hot path.

Public API (everything importable straight off `cairn`):

    HOT PATH (deterministic, offline)
        resolve(query, *, table, ...)          -> (resolved, unresolved)
        traverse(canonical_id, *, graph, ...)  -> TraversalResult
        traverse_cypher(canonical_id, *, run, ...) -> same, via a graph DB (M2.3)
        compile_traversal(canonical_id, ...)   -> CypherQuery (no-query-language)
        as_at(facts, *, valid_as_of, known_as_of)  -> point-in-time slice (TH-3)
        supersede(history, new_fact, *, at)        -> append-only correction

    BUILD TIME (offline authoring; human gate mandatory)
        author_from_text(text, *, source, extractor=...)
        dedup_candidates(candidates, ...)
        with_mirror_edges(entities)
        suggest_canonical_id(surface, entity_type)
        dump_entities(entities) / load_entities(text)

    DATA MODEL (immutable value records — TH-5)
        Entity, Ref, Relation, ResolvedEntity, Candidate, DedupReport,
        TraversalHit, TraversalResult, ResolverConfig

    CROSS-SYSTEM IDENTITY (M2.4)
        CrossSystemIndex — canonical entity <-> its many system-specific IDs

    ADAPTERS (storage-agnostic protocols + in-memory implementations)
        AliasTableAdapter, GraphAdapter, InMemoryAliasTable, InMemoryGraph

Design foundations: docs/patterns/patterns_entities.yaml (TH-1..TH-5,
OP-28/34/35) and docs/research/foundations/.
"""

from cairn_engine.adapters.base import AliasTableAdapter, GraphAdapter
from cairn_engine.adapters.cypher import CypherQuery, CypherRunFn, compile_traversal, traverse_cypher
from cairn_engine.adapters.jsonfile import dump_entities, load_entities
from cairn_engine.adapters.memory import InMemoryAliasTable, InMemoryGraph
from cairn_engine.adapters.sqlite import SqliteAliasTable
from cairn_engine.entity.bitemporal import as_at, supersede
from cairn_engine.entity.crosssystem import CrossSystemIndex
from cairn_engine.entity.model import Entity, Ref, Relation, ResolvedEntity
from cairn_engine.entity.ontology import (
    Candidate,
    DedupReport,
    author_from_text,
    dedup_candidates,
    find_alias_conflicts,
    suggest_canonical_id,
    with_mirror_edges,
)
from cairn_engine.entity.resolve import ArbiterFn, ResolverConfig, resolve
from cairn_engine.entity.semantic import EmbedderFn, EmbeddingIndex, cosine
from cairn_engine.entity.traverse import TraversalHit, TraversalResult, traverse

__version__ = "0.1.0"

__all__ = [
    "AliasTableAdapter",
    "ArbiterFn",
    "Candidate",
    "CrossSystemIndex",
    "CypherQuery",
    "CypherRunFn",
    "DedupReport",
    "EmbedderFn",
    "EmbeddingIndex",
    "Entity",
    "GraphAdapter",
    "InMemoryAliasTable",
    "InMemoryGraph",
    "SqliteAliasTable",
    "Ref",
    "Relation",
    "ResolvedEntity",
    "ResolverConfig",
    "TraversalHit",
    "TraversalResult",
    "__version__",
    "as_at",
    "author_from_text",
    "compile_traversal",
    "cosine",
    "dedup_candidates",
    "dump_entities",
    "find_alias_conflicts",
    "load_entities",
    "resolve",
    "suggest_canonical_id",
    "supersede",
    "traverse",
    "traverse_cypher",
    "with_mirror_edges",
]
