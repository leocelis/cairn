#!/usr/bin/env python3
"""M3.6 — retrieve() end-to-end: the whole library in one call.

    resolve -> gate -> orchestrate signals -> fuse (RRF) -> assemble

The default path is deterministic and generative-LLM-free. Embeddings run ONLY
when the gate's strategy selects the semantic signal; a query the gate routes to
'none' returns NO context at all (the skip that always-on retrieval gets wrong).

Run:  .venv/bin/python examples/retrieve_end_to_end.py
"""

from __future__ import annotations

import hashlib
import math
from typing import Sequence

from cairn_engine import Entity, InMemoryAliasTable, InMemoryGraph, Ref, Relation
from cairn_retrieval import DocMeta, LexicalIndex, RetrievalEngine, SemanticIndex


def toy_embedder(texts: Sequence[str]) -> list[list[float]]:
    """Deterministic, dependency-free stand-in. Real use passes a real EmbedderFn."""
    out = []
    for text in texts:
        vec = [0.0] * 16
        for tok in text.lower().split():
            h = int(hashlib.blake2b(tok.encode(), digest_size=2).hexdigest(), 16)
            vec[h % 16] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        out.append([x / norm for x in vec])
    return out


ENTITIES = [
    Entity("org::acme", "Acme", "org", aliases=("acme",), refs=(Ref("doc::acme"),),
           relations=(Relation("mentions", "concept::pricing"),)),
    Entity("org::beta", "Beta", "org", aliases=("beta",), refs=(Ref("doc::beta"),)),
    Entity("concept::pricing", "pricing", "concept", aliases=("pricing",), refs=(Ref("doc::pricing"),)),
]

CORPUS = {
    "doc::acme": DocMeta("Acme Inc company overview and history", 18, (1.0, 0.0)),
    "doc::beta": DocMeta("Beta LLC company overview", 15, (0.0, 1.0)),
    "doc::pricing": DocMeta("Pricing plans, tiers, and discounts", 16, (0.7, 0.7)),
}


def main() -> None:
    texts = {k: v.content for k, v in CORPUS.items()}
    engine = RetrievalEngine(
        table=InMemoryAliasTable.from_entities(ENTITIES),
        corpus=CORPUS,
        graph=InMemoryGraph.from_entities(ENTITIES),
        lexical=LexicalIndex.from_documents(texts),
        semantic=SemanticIndex.from_documents(texts, embedder=toy_embedder),
        embedder=toy_embedder,
        semantic_floor=0.0,
    )

    print("=" * 74)
    print("M3.6 — retrieve() END TO END  (resolve -> gate -> signals -> fuse -> assemble)")
    print("=" * 74)

    for query in ("acme", "how do acme and beta and pricing relate"):
        result = engine.retrieve(query, budget=40)
        d = result.decision
        print(f'\nquery: "{query}"')
        print(f"    resolved entities : {list(result.entities)}")
        print(f"    gate              : {d.strategy}  (stage {d.stage} — {d.reason})")
        if result.context is None:
            print("    -> SKIP: the gate judged retrieval not worth it. No context built.")
            continue
        print(f"    signals fused     : {sorted({s for h in result.fused for s, _, _ in h.contributions})}")
        print(f"    package           : {result.context.total_tokens} tokens, "
              f"{len(result.context.chunks)} chunks (budget 40)")
        for m in result.context.manifest:
            print(f"        pos {m.position}  {m.doc_id:<14} rel={m.rel:.2f}")

    print("\n-> 'acme' skipped (popular, model knows it); the relational multi-entity")
    print("   query ran all signals, fused by RRF, packed under budget. One embed call,")
    print("   only because the semantic signal was selected — the rest is deterministic.")


if __name__ == "__main__":
    main()
