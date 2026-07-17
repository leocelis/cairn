#!/usr/bin/env python3
"""M3.3 — the semantic signal: dense cosine retrieval, opt-in via a caller embedder.

cairn imports no model and hits no network. The embedder is YOUR callable
(cairn.EmbedderFn). This demo ships a tiny deterministic bag-of-words embedder so
it runs with zero dependencies; in production you pass a real model instead
(sentence-transformers, OpenAI embeddings, etc.) — same interface.

Run:  .venv/bin/python examples/semantic_signal_demo.py
"""

from __future__ import annotations

import hashlib
import math
from typing import Sequence

from cairn_retrieval import SemanticIndex

_DIM = 64


def toy_embedder(texts: Sequence[str]) -> list[list[float]]:
    """A deterministic, dependency-free hashing bag-of-words embedder (L2-normed).

    NOT a real semantic model — it captures token overlap, enough to demo the
    interface. Swap in a real EmbedderFn for actual semantic similarity.
    """
    vectors: list[list[float]] = []
    for text in texts:
        vec = [0.0] * _DIM
        for token in text.lower().split():
            h = int(hashlib.blake2b(token.encode(), digest_size=4).hexdigest(), 16)
            vec[h % _DIM] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        vectors.append([x / norm for x in vec])
    return vectors


CORPUS = {
    "post::gate": "the adaptive gate decides whether retrieval is worth its cost",
    "post::bm25": "bm25 ranks documents by term frequency and document frequency",
    "post::determinism": "a deterministic engine returns identical results every run",
    "post::cost": "retrieval has a cost decide when it is worth paying that cost",
}


def main() -> None:
    print("=" * 70)
    print("M3.3 — SEMANTIC SIGNAL  (dense cosine, opt-in caller embedder)")
    print("=" * 70)

    index = SemanticIndex.from_documents(CORPUS, embedder=toy_embedder)

    for query in ("when is retrieval worth the cost", "same results every run"):
        print(f'\nquery: "{query}"')
        for hit in index.search(query, embedder=toy_embedder, top_k=3, floor=0.01):
            print(f"    {hit.score:.4f}  {hit.doc_id}")

    print("\n-> cairn embedded no text itself — the model is the caller's EmbedderFn.")
    print("   Doc vectors were computed once at build; each search embeds only the query.")


if __name__ == "__main__":
    main()
