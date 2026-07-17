"""Adapter protocols (OP-34, OP-35).

Structural typing (typing.Protocol) so any backend can implement these without
importing Cairn's adapters — keeping the core free of hard storage
dependencies. Concrete adapters (in-memory, JSON, SQLite, graph) are authored
per milestone. The protocols are fully typed against the entity model
(model.py has no adapter imports, so there is no cycle).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from cairn_engine.entity.model import Entity, Ref, Relation, ResolvedEntity


@runtime_checkable
class AliasTableAdapter(Protocol):
    """Persistence + lookup for the canonical alias table (OP-35).

    Default serialization by corpus size: in-memory/JSON (<500), SQLite
    (500-50k), Parquet (50k+) — same interface throughout.
    """

    def lookup(self, surface: str) -> list[ResolvedEntity]:
        """Return canonical matches for a surface form (empty list = unresolved)."""
        ...

    def add(self, entity: Entity) -> None:
        """Add/stage an entity (build-time; staged for review before freezing)."""
        ...

    def merge(self, source_id: str, target_id: str) -> None:
        """Union two canonical IDs (TH-1): the whole class folds into the
        representative at freeze; records are never deleted."""
        ...

    def normalized_entries(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """The closed world as (normalized_alias, sorted canonical_ids) pairs,
        sorted by alias — the gazetteer the scanner walks. Deterministic order."""
        ...

    def has_id(self, canonical_id: str) -> bool:
        """True only for RESOLVABLE ids (class representatives) — exactly the
        ids resolve() can return. Merged-away ids are NOT resolvable (use
        has_record for audit-level existence). Closed-world membership oracle."""
        ...

    def has_record(self, canonical_id: str) -> bool:
        """True for any record ever added, including merged-away ones (audit)."""
        ...


@runtime_checkable
class GraphAdapter(Protocol):
    """Edge/ref source for bounded traversal (OP-34).

    The CORE owns the BFS algorithm; adapters only serve 1-hop out-edges and
    node-anchored refs. That split keeps the core storage-agnostic — one
    deterministic algorithm, N storage backends. (A backend may later execute
    the same bounded intent in its own query language behind this API — OQ-3.)
    """

    def edges(self, entity_id: str) -> tuple[Relation, ...]:
        """1-hop out-edges (with bitemporal validity) — deterministic order."""
        ...

    def refs(self, entity_id: str) -> tuple[Ref, ...]:
        """DocumentRefs anchored to the node — deterministic order."""
        ...

    def has_entity(self, entity_id: str) -> bool:
        """Closed world membership check."""
        ...

    def edge_capable(self) -> bool:
        """False -> flat mode: traversal degrades to depth-0 refs (OP-34 fallback)."""
        ...
