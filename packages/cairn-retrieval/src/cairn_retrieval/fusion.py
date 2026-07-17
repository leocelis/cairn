"""Signal fusion via Reciprocal Rank Fusion (M3.4, OP-32).

The signals — lexical (M3.2), semantic (M3.3), graph traversal — each return a
RANKED list. Their scores live on incomparable scales (BM25 vs cosine vs hop
distance), so you cannot average them. RRF fuses by RANK POSITION instead: each
signal votes 1/(k + rank) for the docs it ranked, and the votes sum. No score
normalization, ever — that is the whole point.

k=1 for cairn (Graphiti/Zep, short agent lists): rank-1 -> 1.0, rank-2 -> 0.5,
rank-3 -> 0.33. The TREC default k=60 collapses short top-k lists into
near-identical scores and is wrong here. Deterministic, stdlib-only. Output feeds
the assembler (M3.5).

    fuse({"lexical": ["d1", "d2"], "semantic": ["d2", "d3"]})
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

__all__ = ["FusedHit", "fuse"]


@dataclass(frozen=True, slots=True)
class FusedHit:
    """One fused document with its per-signal contribution breakdown (auditable)."""

    doc_id: str
    score: float
    contributions: tuple[tuple[str, int, float], ...]  # (signal, rank_0based, contribution)


def fuse(
    signals: Mapping[str, Sequence[str]],
    *,
    k: int = 1,
    top_k: int = 10,
    weights: Mapping[str, float] | None = None,
) -> list[FusedHit]:
    """Reciprocal Rank Fusion of ranked doc-id lists into one ranking.

    `signals` maps a signal name to its ranked doc_ids (best first). Each signal
    contributes weight·1/(k + rank_0based) to every doc it ranked; a doc absent
    from a signal gets 0 from it. Deduplicated by doc_id, sorted (score desc,
    doc_id asc), capped at top_k. Rank-only — raw signal scores never enter.
    """
    weights = weights or {}
    totals: dict[str, float] = {}
    breakdown: dict[str, list[tuple[str, int, float]]] = {}
    for signal in sorted(signals):  # deterministic contribution order
        weight = weights.get(signal, 1.0)
        for rank, doc_id in enumerate(signals[signal]):
            contribution = weight * (1.0 / (k + rank))
            totals[doc_id] = totals.get(doc_id, 0.0) + contribution
            breakdown.setdefault(doc_id, []).append((signal, rank, contribution))
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        FusedHit(doc_id, score, tuple(breakdown[doc_id]))
        for doc_id, score in ranked[:top_k]
    ]
