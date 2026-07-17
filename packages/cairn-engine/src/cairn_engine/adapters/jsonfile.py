"""Deterministic JSON serialization of the entity map (M1.3, OP-35 serialization).

JSON — not YAML — is the 0.1 format: the stdlib has no yaml module and PyYAML
would be the core's first hard dependency (zero-dep invariant beats format
preference; YAML lands later as an opt-in extra). Output is byte-stable:
sorted keys, fixed separators, entities ordered by canonical_id.
"""

from __future__ import annotations

import json
from typing import Any

from cairn_engine.entity.model import Entity, Ref, Relation

__all__ = ["dump_entities", "load_entities"]

_SCHEMA_VERSION = 1


def dump_entities(entities: tuple[Entity, ...] | list[Entity]) -> str:
    """Serialize to deterministic JSON (same entities -> same bytes, always).

    `metadata` must contain JSON-native values only (str/int/float/bool/None,
    lists, string-keyed dicts) — validated here so type-changing round-trips
    (e.g. tuple -> list) fail loudly at dump time instead of corrupting silently.
    """
    for e in entities:
        _require_json_native(dict(e.metadata), f"{e.canonical_id}.metadata")
    payload: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "entities": [_to_dict(e) for e in sorted(entities, key=lambda e: e.canonical_id)],
    }
    return json.dumps(payload, sort_keys=True, indent=2, separators=(",", ": ")) + "\n"


def _require_json_native(value: Any, where: str) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, list):
        for i, item in enumerate(value):
            _require_json_native(item, f"{where}[{i}]")
        return
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise TypeError(f"non-string metadata key at {where}: {k!r}")
            _require_json_native(v, f"{where}.{k}")
        return
    raise TypeError(
        f"non-JSON-native metadata value at {where}: {type(value).__name__} "
        "(allowed: str/int/float/bool/None, lists, string-keyed dicts)"
    )


def load_entities(text: str) -> tuple[Entity, ...]:
    """Inverse of dump_entities: load_entities(dump_entities(x)) == sorted(x)."""
    payload = json.loads(text)
    version = payload.get("schema_version")
    if version != _SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version: {version!r} (expected {_SCHEMA_VERSION})")
    return tuple(_from_dict(d) for d in payload["entities"])


def _to_dict(e: Entity) -> dict[str, Any]:
    return {
        "canonical_id": e.canonical_id,
        "label": e.label,
        "entity_type": e.entity_type,
        "aliases": list(e.aliases),
        "valid_from": e.valid_from,
        "valid_until": e.valid_until,
        "known_from": e.known_from,
        "known_until": e.known_until,
        "source": e.source,
        "description": e.description,
        "merged_from": list(e.merged_from),
        "refs": [{"doc_id": r.doc_id, "locator": r.locator} for r in e.refs],
        "relations": [
            {
                "predicate": r.predicate,
                "target_id": r.target_id,
                "valid_from": r.valid_from,
                "valid_until": r.valid_until,
                "known_from": r.known_from,
                "known_until": r.known_until,
                "weight": r.weight,
            }
            for r in e.relations
        ],
        "metadata": dict(e.metadata),
    }


def _from_dict(d: dict[str, Any]) -> Entity:
    return Entity(
        canonical_id=d["canonical_id"],
        label=d["label"],
        entity_type=d["entity_type"],
        aliases=tuple(d.get("aliases", ())),
        valid_from=d.get("valid_from"),
        valid_until=d.get("valid_until"),
        known_from=d.get("known_from"),
        known_until=d.get("known_until"),
        source=d.get("source"),
        description=d.get("description"),
        merged_from=tuple(d.get("merged_from", ())),
        refs=tuple(Ref(doc_id=r["doc_id"], locator=r.get("locator")) for r in d.get("refs", ())),
        relations=tuple(
            Relation(
                predicate=r["predicate"],
                target_id=r["target_id"],
                valid_from=r.get("valid_from"),
                valid_until=r.get("valid_until"),
                known_from=r.get("known_from"),
                known_until=r.get("known_until"),
                weight=r.get("weight", 1.0),
            )
            for r in d.get("relations", ())
        ),
        metadata=d.get("metadata", {}),
    )
