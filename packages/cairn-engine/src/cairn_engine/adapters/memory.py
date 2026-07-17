"""In-memory adapters — the frozen closed world for small corpora (OP-35).

Build offline from Entity records, then freeze(); the hot path only reads.
All structures are sorted at freeze time so every iteration is deterministic.

Merge is Union-Find (TH-1) and moves the WHOLE class: at freeze, every surface,
ref, and relation of a merged entity is folded into its class representative
(relation targets are rewritten through find(); self-loops are dropped). Merged
records are preserved for audit (`has_record`) but are not resolvable ids
(`has_id`). Build the graph from `canonical_entities()` so resolve() and
traverse() agree on ids after any merge.
"""

from __future__ import annotations

from typing import Iterable

from cairn_engine.adapters._build import build_indexes, fold_entities, find_root
from cairn_engine.entity.model import Entity, Ref, Relation, ResolvedEntity
from cairn_engine.entity.normalize import normalize

__all__ = ["InMemoryAliasTable", "InMemoryGraph"]

_TIER_EXACT = "exact"
_TIER_NORMALIZED = "normalized"


class InMemoryAliasTable:
    """Build -> freeze -> read-only lookup. Mutations after freeze() raise."""

    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}
        self._frozen = False
        self._merged: dict[str, str] = {}  # Union-Find parent links (TH-1)
        # Derived at freeze():
        self._canonical: tuple[Entity, ...] = ()
        self._exact: dict[str, tuple[str, ...]] = {}
        self._norm: dict[str, tuple[str, ...]] = {}
        self._norm_entries: tuple[tuple[str, tuple[str, ...]], ...] = ()

    @classmethod
    def from_entities(cls, entities: Iterable[Entity]) -> "InMemoryAliasTable":
        """Convenience: build and freeze in one step."""
        table = cls()
        for entity in entities:
            table.add(entity)
        return table.freeze()

    # -- build time ------------------------------------------------------

    def add(self, entity: Entity) -> None:
        if self._frozen:
            raise RuntimeError("alias table is frozen — build-time mutations only (OP-35)")
        if entity.canonical_id in self._entities:
            raise ValueError(f"duplicate canonical_id: {entity.canonical_id}")
        self._entities[entity.canonical_id] = entity

    def merge(self, source_id: str, target_id: str) -> None:
        """Union (TH-1): the WHOLE class moves — surfaces, refs, and relations of
        `source_id` fold into `target_id` at freeze (transitively). The source
        record is never deleted (audit); provenance lands in target.merged_from."""
        if self._frozen:
            raise RuntimeError("alias table is frozen — merges are build-time (OP-35)")
        root_src, root_dst = self._find(source_id), self._find(target_id)
        if root_src not in self._entities or root_dst not in self._entities:
            raise KeyError(f"merge of unknown entity: {source_id} -> {target_id}")
        if root_src == root_dst:
            return  # already the same class
        self._merged[root_src] = root_dst  # union

    def _find(self, canonical_id: str) -> str:
        return find_root(canonical_id, self._merged)

    def freeze(self) -> "InMemoryAliasTable":
        """Fold merged classes into their representatives, then index — the
        folding + indexing is the shared adapters._build logic (identical across
        every backend)."""
        self._canonical = tuple(fold_entities(self._entities, self._merged))
        self._exact, self._norm = build_indexes(self._canonical)
        self._norm_entries = tuple(sorted(self._norm.items()))
        self._frozen = True
        return self

    # -- hot path (read-only) ---------------------------------------------

    def lookup(self, surface: str) -> list[ResolvedEntity]:
        """Tier 1a (exact) then Tier 1b (normalized). Deterministic order:
        canonical_id asc within a tier. Empty list = miss (closed world)."""
        self._require_frozen()
        ids = self._exact.get(surface)
        tier = _TIER_EXACT
        if ids is None:
            ids = self._norm.get(normalize(surface))
            tier = _TIER_NORMALIZED
        if ids is None:
            return []
        return [
            ResolvedEntity(surface_form=surface, canonical_id=cid, confidence=1.0, tier=tier)
            for cid in ids
        ]

    def normalized_entries(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        self._require_frozen()
        return self._norm_entries

    def canonical_entities(self) -> tuple[Entity, ...]:
        """The folded closed world — class representatives with all merged
        members' aliases/refs/relations absorbed. Feed THIS to InMemoryGraph
        so resolve() and traverse() agree on ids after merges."""
        self._require_frozen()
        return self._canonical

    def has_id(self, canonical_id: str) -> bool:
        """True only for RESOLVABLE ids (class representatives) — the ids
        resolve() can return. Merged-away ids are not resolvable."""
        return (
            canonical_id in self._entities and self._find(canonical_id) == canonical_id
        )

    def has_record(self, canonical_id: str) -> bool:
        """True for any record ever added, including merged-away ones (audit)."""
        return canonical_id in self._entities

    def _require_frozen(self) -> None:
        if not self._frozen:
            raise RuntimeError(
                "alias table must be frozen before lookup — the determinism boundary is the frozen table"
            )


class InMemoryGraph:
    """In-memory GraphAdapter built from Entity records (relations = edges,
    refs = node-anchored docs). Build -> freeze -> read-only, like the alias
    table; every collection is sorted at freeze time (deterministic).

    After merges, build from `InMemoryAliasTable.canonical_entities()` so the
    graph's ids match what resolve() returns."""

    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}
        self._frozen = False
        self._edges: dict[str, tuple[Relation, ...]] = {}
        self._refs: dict[str, tuple[Ref, ...]] = {}
        self._edge_capable = False

    @classmethod
    def from_entities(cls, entities: Iterable[Entity]) -> "InMemoryGraph":
        """Convenience: build and freeze in one step."""
        graph = cls()
        for entity in entities:
            graph.add(entity)
        return graph.freeze()

    def add(self, entity: Entity) -> None:
        if self._frozen:
            raise RuntimeError("graph is frozen — build-time mutations only")
        if entity.canonical_id in self._entities:
            raise ValueError(f"duplicate canonical_id: {entity.canonical_id}")
        self._entities[entity.canonical_id] = entity

    def freeze(self) -> "InMemoryGraph":
        for cid in sorted(self._entities):
            ent = self._entities[cid]
            self._edges[cid] = tuple(sorted(ent.relations, key=lambda r: (r.predicate, r.target_id)))
            self._refs[cid] = tuple(sorted(ent.refs, key=lambda r: (r.doc_id, r.locator or "")))
        self._edge_capable = any(self._edges[cid] for cid in self._edges)
        self._frozen = True
        return self

    def edges(self, entity_id: str) -> tuple[Relation, ...]:
        self._require_frozen()
        return self._edges.get(entity_id, ())

    def refs(self, entity_id: str) -> tuple[Ref, ...]:
        self._require_frozen()
        return self._refs.get(entity_id, ())

    def has_entity(self, entity_id: str) -> bool:
        return entity_id in self._entities

    def edge_capable(self) -> bool:
        return self._edge_capable

    def _require_frozen(self) -> None:
        if not self._frozen:
            raise RuntimeError(
                "graph must be frozen before traversal — the determinism boundary is the frozen graph"
            )
