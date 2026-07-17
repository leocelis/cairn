"""Tier 3 — opt-in semantic (embedding) resolution (OP-28). BUILD-TIME index, hot-path lookup.

Implements the module intent `intents/entity_semantic_intent.yaml`:

    EmbeddingIndex.build(entries, embedder)   BUILD TIME: embed every alias ONCE
    index.nearest(vector)                     HOT PATH: cosine against precomputed vectors

Boundaries (consistent with the rest of the engine):
  * the embedder is a CALLER-SUPPLIED callable (local model or API — the
    caller's choice and the caller's boundary); cairn never imports an
    embedding SDK and never calls a network itself
  * alias vectors are precomputed at build time — the hot path embeds ONLY
    the mention being resolved, never the alias table (OP-29 rule: reuse,
    never re-embed on the hot path)
  * closed world: the index can only return ids that exist in the table
  * determinism is scoped to the embedder: fixed vectors in -> byte-stable
    ranking out (sorted tie-breaks, no randomness added by cairn)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Sequence

__all__ = ["EmbedderFn", "EmbeddingIndex", "cosine"]

# Batch embedder: texts -> one vector per text, same order. Caller-owned.
EmbedderFn = Callable[[Sequence[str]], Sequence[Sequence[float]]]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Plain cosine similarity, stdlib only. 0.0 on zero/mismatched vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


@dataclass(frozen=True, slots=True)
class _Entry:
    alias_norm: str
    ids: tuple[str, ...]
    vector: tuple[float, ...]


class EmbeddingIndex:
    """Precomputed alias-embedding index — built offline, read-only afterwards."""

    def __init__(self, entries: tuple[_Entry, ...]) -> None:
        self._entries = entries

    @classmethod
    def build(
        cls,
        normalized_entries: Sequence[tuple[str, tuple[str, ...]]],
        embedder: EmbedderFn,
    ) -> "EmbeddingIndex":
        """BUILD TIME: embed every normalized alias exactly once (one batch call).

        `normalized_entries` is `AliasTableAdapter.normalized_entries()` — the
        frozen closed world; the index therefore cannot contain unknown ids.
        """
        aliases = [alias for alias, _ in normalized_entries]
        vectors = embedder(aliases) if aliases else []
        if len(vectors) != len(aliases):
            raise ValueError(
                f"embedder returned {len(vectors)} vectors for {len(aliases)} aliases"
            )
        entries = tuple(
            _Entry(alias_norm=alias, ids=ids, vector=tuple(float(x) for x in vec))
            for (alias, ids), vec in zip(normalized_entries, vectors)
        )
        return cls(entries)

    def scored(self, vector: Sequence[float]) -> tuple[tuple[float, tuple[str, ...]], ...]:
        """HOT PATH: (cosine, ids) for every entry, deterministic order (build
        order). Lets the resolver pool ALL ambiguous-band candidates for the
        Tier-4 arbiter — not just the top ties."""
        return tuple((cosine(vector, e.vector), e.ids) for e in self._entries)

    def nearest(self, vector: Sequence[float]) -> tuple[float, tuple[str, ...]]:
        """HOT PATH: best cosine score and the canonical ids at that score.

        Deterministic: ties merge their ids; ids are returned sorted. Returns
        (0.0, ()) on an empty index.
        """
        best_score = 0.0
        best_ids: set[str] = set()
        for entry in self._entries:  # build order is deterministic
            score = cosine(vector, entry.vector)
            if score > best_score:
                best_score, best_ids = score, set(entry.ids)
            elif score == best_score and score > 0.0:
                best_ids.update(entry.ids)
        return best_score, tuple(sorted(best_ids))

    def __len__(self) -> int:
        return len(self._entries)
