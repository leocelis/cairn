"""Semantic retrieval signal (M3.3, OP-3 layer 3) — dense cosine ranking, opt-in.

The lexical signal (M3.2) catches exact tokens; this catches "what is RELATED to
this concept" — documents that share meaning but no literal words. It is OPT-IN:
the embedder is a caller-supplied callable (`cairn.EmbedderFn`), exactly like the
Tier-3 entity resolver and the LLM arbiter. cairn imports no model SDK and makes
no network call — document vectors are computed once at build, and the hot path
embeds only the query. Feeds RRF fusion (M3.4).

    idx = SemanticIndex.from_documents({"d1": "...", "d2": "..."}, embedder=embed)
    idx.search("a query", embedder=embed, top_k=5, floor=0.6)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from cairn_engine import EmbedderFn, cosine

__all__ = ["SemanticHit", "SemanticIndex"]


@dataclass(frozen=True, slots=True)
class SemanticHit:
    """One cosine-ranked document."""

    doc_id: str
    score: float


class SemanticIndex:
    """Dense-vector document index. Build (embed once) -> freeze -> search."""

    def __init__(self) -> None:
        self._frozen = False
        self._vectors: dict[str, tuple[float, ...]] = {}

    @classmethod
    def from_documents(
        cls, documents: Mapping[str, str], *, embedder: EmbedderFn
    ) -> "SemanticIndex":
        index = cls()
        doc_ids = list(documents)  # preserve caller order for the batch
        if doc_ids:
            vectors = embedder([documents[d] for d in doc_ids])  # ONE batch call
            for doc_id, vec in zip(doc_ids, vectors):
                index._vectors[doc_id] = tuple(float(x) for x in vec)
        index._frozen = True
        return index

    def search(
        self,
        query: str,
        *,
        embedder: EmbedderFn,
        top_k: int = 10,
        floor: float = 0.0,
    ) -> list[SemanticHit]:
        """Cosine top_k, sorted (score desc, doc_id asc), floor-filtered.

        Embeds ONLY the query (one embedder call); doc vectors are precomputed.
        Empty corpus or nothing >= floor -> []. Deterministic given the embedder.
        """
        if not self._frozen:
            raise RuntimeError("semantic index must be frozen before search")
        if not self._vectors:
            return []
        query_vec = tuple(float(x) for x in embedder([query])[0])
        # Explicit dimension guard: cairn.cosine returns 0.0 on a length mismatch
        # (silently mis-scoring), so a query/doc dimension mismatch — a caller
        # embedder inconsistency between build and search — is caught loudly here.
        doc_dim = len(next(iter(self._vectors.values())))
        if len(query_vec) != doc_dim:
            raise ValueError(
                f"query embedding dim {len(query_vec)} != document embedding dim "
                f"{doc_dim} — the embedder must be consistent between build and search"
            )
        scored = [
            (cosine(query_vec, vec), doc_id) for doc_id, vec in self._vectors.items()
        ]
        ranked = sorted(
            ((doc_id, score) for score, doc_id in scored if score >= floor),
            key=lambda kv: (-kv[1], kv[0]),
        )
        return [SemanticHit(doc_id, score) for doc_id, score in ranked[:top_k]]
