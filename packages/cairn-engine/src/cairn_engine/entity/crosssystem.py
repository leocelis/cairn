"""Cross-system entity index (M2.4) — canonical entity <-> its many system IDs.

The same real-world entity "Acme" is `cus_42` in the CRM, `C0299` in Slack, and
`acme-inc` on GitHub. An agent resolves a mention to the CANONICAL entity, then
must bind the RIGHT system-specific id when it calls a tool against a system —
otherwise the tool is selected correctly but the arg lands in the wrong
namespace (research finding: cross_system_entity_index; the cold-silo failure).

This index makes that binding a lookup, not a guess. Build -> freeze -> read-only
(the frozen index is the deterministic boundary, like the alias table). Closed
world (TH-5): every miss returns () or None — an external id is NEVER synthesized.

    idx = CrossSystemIndex.from_entities(entities)   # reads metadata["system_ids"]
    idx.bind("org::acme", system="crm")              # -> "cus_42"
    idx.canonical_for(system="slack", external_id="C0299")   # -> "org::acme"

Forward is one-to-many (a TH-1 merge can leave one canonical with two ids in a
system); reverse is one-to-one (each system id belongs to exactly one canonical
— a violation is a data error caught at freeze). Stdlib only, deterministic.
"""

from __future__ import annotations

from typing import Iterable

from cairn_engine.entity.model import Entity

__all__ = ["CrossSystemIndex"]

_METADATA_KEY = "system_ids"


class CrossSystemIndex:
    """Bidirectional canonical <-> {system: external ids} map. Build, freeze, read."""

    def __init__(self) -> None:
        self._frozen = False
        # canonical_id -> system -> set of external ids  (forward, one-to-many)
        self._forward: dict[str, dict[str, set[str]]] = {}
        # (system, external_id) -> canonical_id  (reverse, one-to-one)
        self._reverse: dict[tuple[str, str], str] = {}

    # -- build time ------------------------------------------------------

    @classmethod
    def from_entries(cls, entries: Iterable[tuple[str, str, str]]) -> "CrossSystemIndex":
        """Build from an iterable of (canonical_id, system, external_id) triples."""
        index = cls()
        for canonical_id, system, external_id in entries:
            index.add(canonical_id, system=system, external_id=external_id)
        return index.freeze()

    @classmethod
    def from_entities(cls, entities: Iterable[Entity]) -> "CrossSystemIndex":
        """Build from entities carrying metadata['system_ids'] = {system: id | [ids]}."""
        index = cls()
        for entity in entities:
            index._add_entity(entity)
        return index.freeze()

    def add(self, canonical_id: str, *, system: str, external_id: str) -> None:
        self._require_building()
        # reverse one-to-one integrity (C-XSYS-4): same id, different owner -> error
        owner = self._reverse.get((system, external_id))
        if owner is not None and owner != canonical_id:
            raise ValueError(
                f"cross-system conflict: ({system!r}, {external_id!r}) is claimed by "
                f"both {owner!r} and {canonical_id!r} — these entities should be merged (TH-1)"
            )
        self._reverse[(system, external_id)] = canonical_id
        self._forward.setdefault(canonical_id, {}).setdefault(system, set()).add(external_id)

    def _add_entity(self, entity: Entity) -> None:
        raw = entity.metadata.get(_METADATA_KEY)
        if raw is None:
            return
        if not isinstance(raw, dict):
            raise TypeError(
                f"{entity.canonical_id}.metadata['{_METADATA_KEY}'] must be a "
                f"dict of system -> id | [ids]; got {type(raw).__name__}"
            )
        for system, value in raw.items():
            ids = value if isinstance(value, (list, tuple)) else [value]
            for external_id in ids:
                self.add(entity.canonical_id, system=str(system), external_id=str(external_id))

    def freeze(self) -> "CrossSystemIndex":
        self._frozen = True
        return self

    # -- read (closed world; frozen) -------------------------------------

    def external_ids(self, canonical_id: str, *, system: str) -> tuple[str, ...]:
        """All external ids `canonical_id` has in `system`, sorted. () on any miss."""
        self._require_frozen()
        return tuple(sorted(self._forward.get(canonical_id, {}).get(system, set())))

    def bind(self, canonical_id: str, *, system: str) -> str | None:
        """The single external id for a tool arg. None if none; ValueError if 2+."""
        ids = self.external_ids(canonical_id, system=system)
        if not ids:
            return None
        if len(ids) > 1:
            raise ValueError(
                f"ambiguous binding: {canonical_id!r} has {len(ids)} ids in "
                f"{system!r} ({ids}) — caller must choose"
            )
        return ids[0]

    def canonical_for(self, *, system: str, external_id: str) -> str | None:
        """Which canonical owns (system, external_id). None on miss (closed world)."""
        self._require_frozen()
        return self._reverse.get((system, external_id))

    def systems(self, canonical_id: str) -> tuple[str, ...]:
        """The systems `canonical_id` is known in, sorted. () on unknown canonical."""
        self._require_frozen()
        return tuple(sorted(self._forward.get(canonical_id, {})))

    # -- guards ----------------------------------------------------------

    def _require_building(self) -> None:
        if self._frozen:
            raise RuntimeError("cross-system index is frozen — build-time mutations only")

    def _require_frozen(self) -> None:
        if not self._frozen:
            raise RuntimeError("cross-system index must be frozen before lookup")
