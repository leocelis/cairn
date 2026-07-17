"""Bounded entity-graph traversal — relation closure (OP-34, TH-4, TH-3).

Implements the module intent `intents/entity_traversal_intent.yaml`:

    BFS from a resolved canonical ID, bounded (default depth 2, hard max 3),
    hop-distance discount score = 1 / (1 + hop), bitemporal edge filter that
    fires ONLY on an explicit `as_of` (the traversal never reads the wall
    clock — a hidden now() would break byte-stability), flat depth-0 fallback
    when the graph source has no edges.

The CORE owns this algorithm; GraphAdapter implementations only serve 1-hop
edges and node refs. Stdlib-only, zero LLM, zero network, closed world:
an unknown seed returns an empty result — nothing is ever fabricated.
"""

from __future__ import annotations

from dataclasses import dataclass
from cairn_engine.adapters.base import GraphAdapter
from cairn_engine.entity.bitemporal import _within
from cairn_engine.entity.model import Ref, Relation

__all__ = ["TraversalHit", "TraversalResult", "traverse"]

_MAX_DEPTH = 3


@dataclass(frozen=True, slots=True)
class TraversalHit:
    """One collected document reference: where it is anchored, how far, how strong."""

    ref: Ref
    entity_id: str
    hop: int
    score: float  # 1 / (1 + hop) — deterministic PPR-decay surrogate (TH-4)


@dataclass(frozen=True, slots=True)
class TraversalResult:
    """The bounded relation closure of one seed entity."""

    hits: tuple[TraversalHit, ...]
    traversal_mode: str  # "graph" | "flat" (OP-34 fallback tag)


def traverse(
    canonical_id: str,
    *,
    graph: GraphAdapter,
    depth: int = 2,
    as_of: str | None = None,
    known_as_of: str | None = None,
) -> TraversalResult:
    """Collect DocumentRefs connected to `canonical_id` within `depth` hops.

    Output order: (hop asc, entity_id asc, doc_id asc) — byte-stable.
    Edges are filtered on BOTH bi-temporal axes (TH-3), half-open, None = open:
    `as_of` filters valid-time [valid_from, valid_until) — what was TRUE then;
    `known_as_of` filters transaction-time [known_from, known_until) — what was
    KNOWN then. None on an axis disables that axis (time is always an explicit
    input, never a wall-clock read).
    """
    if not 0 <= depth <= _MAX_DEPTH:
        raise ValueError(
            f"depth must be in 0..{_MAX_DEPTH} (bounded closure — full closure degenerates "
            f"to the connected component; see TH-4 / OP-34): got {depth}"
        )
    mode = "graph" if graph.edge_capable() else "flat"
    if not graph.has_entity(canonical_id):
        return TraversalResult((), mode)  # closed world: unknown seed -> empty

    # BFS — every node visited at its SHORTEST hop distance.
    visited: dict[str, int] = {canonical_id: 0}
    frontier: list[str] = [canonical_id]
    effective_depth = depth if mode == "graph" else 0
    for hop in range(effective_depth):
        next_frontier: list[str] = []
        for entity_id in frontier:  # frontier is kept sorted -> deterministic
            for rel in graph.edges(entity_id):  # adapter order is deterministic
                if not _edge_valid(rel, as_of, known_as_of):
                    continue
                target = rel.target_id
                if target in visited or not graph.has_entity(target):
                    continue  # shortest-hop wins; dangling targets never fabricated
                visited[target] = hop + 1
                next_frontier.append(target)
        frontier = sorted(set(next_frontier))

    hits = [
        TraversalHit(ref=ref, entity_id=entity_id, hop=hop, score=1.0 / (1 + hop))
        for entity_id, hop in visited.items()
        for ref in graph.refs(entity_id)
    ]
    hits.sort(key=lambda h: (h.hop, h.entity_id, h.ref.doc_id))
    return TraversalResult(tuple(hits), mode)


def _edge_valid(rel: Relation, as_of: str | None, known_as_of: str | None) -> bool:
    """Both-axis bi-temporal edge filter, half-open [start, end) — TH-3.

    Delegates to `_within` (the single OQ-4 sentinel rule) on each axis: an edge
    passes only if it was TRUE at `as_of` AND KNOWN at `known_as_of`. None on an
    axis disables that axis. No wall-clock reads.
    """
    return _within(rel.valid_from, rel.valid_until, as_of) and _within(
        rel.known_from, rel.known_until, known_as_of
    )
