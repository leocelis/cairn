"""Shared build-time folding + indexing for alias-table adapters.

Both InMemoryAliasTable and SqliteAliasTable call these — so a merge behaves
identically no matter where the frozen data lives. This IS the storage-agnostic
guarantee, made concrete: one folding algorithm, N storage backends.
"""

from __future__ import annotations

import dataclasses
from typing import Mapping, Sequence

from cairn_engine.entity.model import Entity, Ref, Relation
from cairn_engine.entity.normalize import normalize

__all__ = ["find_root", "fold_entities", "build_indexes"]


def find_root(canonical_id: str, merged: Mapping[str, str]) -> str:
    """Union-Find `find`: follow parent links to the class representative (TH-1)."""
    while canonical_id in merged:
        canonical_id = merged[canonical_id]
    return canonical_id


def fold_entities(entities: Mapping[str, Entity], merged: Mapping[str, str]) -> list[Entity]:
    """Fold merged classes into their representatives (OP-35 reference forwarding).

    The representative absorbs every member's aliases, refs, and relations;
    relation targets are rewritten through find(); self-loops are dropped;
    merged_from records provenance. Deterministic (sorted). Returns the
    class representatives only — merged-away ids are gone from the result.
    """
    members: dict[str, list[str]] = {}
    for cid in sorted(entities):
        members.setdefault(find_root(cid, merged), []).append(cid)

    canonical: list[Entity] = []
    for root in sorted(members):
        rep = entities[root]
        aliases: list[str] = list(rep.aliases)
        refs: list[Ref] = list(rep.refs)
        relations: list[Relation] = []
        merged_from: list[str] = list(rep.merged_from)
        for cid in members[root]:
            ent = entities[cid]
            if cid != root:
                merged_from.append(cid)
                aliases.append(ent.label)
                aliases.extend(ent.aliases)
                refs.extend(ent.refs)
            for rel in ent.relations:
                target = find_root(rel.target_id, merged)
                if target == root:
                    continue  # merged-away edge would self-loop — drop
                relations.append(
                    rel if target == rel.target_id else dataclasses.replace(rel, target_id=target)
                )
        canonical.append(
            dataclasses.replace(
                rep,
                aliases=tuple(dict.fromkeys(aliases)),
                refs=tuple(sorted(dict.fromkeys(refs), key=lambda r: (r.doc_id, r.locator or ""))),
                relations=tuple(sorted(dict.fromkeys(relations),
                                       key=lambda r: (r.predicate, r.target_id))),
                merged_from=tuple(dict.fromkeys(merged_from)),
            )
        )
    return canonical


def build_indexes(
    canonical: Sequence[Entity],
) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
    """(exact, normalized) surface -> sorted canonical ids, from folded entities."""
    exact: dict[str, list[str]] = {}
    norm: dict[str, list[str]] = {}
    for ent in canonical:
        for surface in (ent.label, *ent.aliases):
            exact.setdefault(surface, []).append(ent.canonical_id)
            n = normalize(surface)
            if n:
                norm.setdefault(n, []).append(ent.canonical_id)
    return (
        {s: tuple(sorted(set(ids))) for s, ids in exact.items()},
        {s: tuple(sorted(set(ids))) for s, ids in norm.items()},
    )
