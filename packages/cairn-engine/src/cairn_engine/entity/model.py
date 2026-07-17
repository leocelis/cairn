"""The entity data model — immutable value records.

Per TH-5 (relational / ECS separation, not OOP): entities are IMMUTABLE VALUE
RECORDS. They carry data only; the algorithms (resolve, traverse, author) live in
their own modules and operate *over* entities — never as methods *on* them.

Schema per OP-35 (docs/patterns/patterns_entities.yaml). Immutability is enforced
with frozen dataclasses and tuples (not lists) so an Entity is hashable and
byte-stable — a prerequisite for the determinism invariant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class Ref:
    """A stable, resolvable pointer to where an entity is mentioned.

    Cairn stores references, never the content itself (build_boundary). The
    adapter for each store knows how to fetch the content from `doc_id`/`locator`.
    Stability + resolvability of `doc_id` across re-indexing is OQ-2.
    """

    doc_id: str
    locator: str | None = None  # path / row-key / offset — adapter-specific


@dataclass(frozen=True, slots=True)
class Relation:
    """A typed, directed edge to another canonical entity.

    Bi-temporal validity (valid_from/valid_until) lives ON the edge (TH-2/TH-3);
    this is why a labeled property graph — not RDF triples — is the right model.
    """

    predicate: str
    target_id: str
    valid_from: str | None = None   # valid-time  (TH-3): when the fact was TRUE
    valid_until: str | None = None  #   half-open [valid_from, valid_until); None = open (+inf)
    known_from: str | None = None   # transaction-time (TH-3): when the system KNEW it
    known_until: str | None = None  #   half-open [known_from, known_until); None = open (+inf)
    weight: float = 1.0             # structural edge weight, e.g. mention count
    #                                 (term frequency). Default 1.0 = unweighted.
    #                                 Traversal ignores it; retrieval ranking uses it.


@dataclass(frozen=True, slots=True)
class Entity:
    """A canonical entity — the representative of an equivalence class of surface forms (TH-1).

    Required fields are the OP-35 minimal schema; the rest are optional.
    `aliases`, `refs`, `relations`, `merged_from` are tuples to keep the record
    immutable and hashable.
    """

    canonical_id: str                      # stable slug, e.g. "person::jane_doe"
    label: str
    # Recommended vocabulary (OP-35): person|org|concept|function|document|config|system.
    # Deliberately NOT enforced — users own their taxonomy; the slug prefix in
    # canonical_id (type::label) is the working convention.
    entity_type: str
    aliases: tuple[str, ...] = ()
    valid_from: str | None = None          # valid-time start (None = always been true)
    source: str | None = None              # where first observed
    description: str | None = None
    valid_until: str | None = None         # valid-time end (None = still true); for deprecated entities
    known_from: str | None = None          # transaction-time start: when the system learned it
    known_until: str | None = None         # transaction-time end (None = still current knowledge)
    merged_from: tuple[str, ...] = ()       # provenance of merges (Union-Find, TH-1)
    refs: tuple[Ref, ...] = ()
    relations: tuple[Relation, ...] = ()
    # Open bag for corpus-specific fields (JSON-native values only — enforced at
    # dump time). Excluded from __hash__/__eq__ so the record stays hashable —
    # identity is the canonical_id, not the metadata. Wrapped read-only in
    # __post_init__ so a frozen record cannot be mutated through its dict (TH-5).
    metadata: Mapping[str, object] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ResolvedEntity:
    """Output of the resolver: a surface form mapped to a canonical entity.

    `tier` records which resolution tier fired (exact | normalized | fuzzy |
    embedding | llm), so every resolution is auditable. A miss is represented by
    the surface form appearing in the resolver's `unresolved` list — never a
    synthesized canonical_id (closed-world / negation-as-failure, TH-5).
    """

    surface_form: str
    canonical_id: str
    confidence: float
    tier: str
