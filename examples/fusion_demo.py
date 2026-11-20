#!/usr/bin/env python3
"""M3.4 — fuse the signals with Reciprocal Rank Fusion (RRF, k=1).

Lexical, semantic, and graph signals each return a RANKED list. Their scores are
on incomparable scales (BM25 vs cosine vs hop distance) — you cannot average them.
RRF combines by RANK POSITION: each signal votes 1/(k+rank), votes sum. No score
normalization. k=1 suits cairn's short agent lists.

Run:  .venv/bin/python examples/fusion_demo.py
"""

from __future__ import annotations

from cairn_retrieval import fuse

# each signal already ran and returned its ranked doc_ids (best first)
SIGNALS = {
    "lexical": ["post::bm25", "post::gate", "post::cost"],       # BM25 order
    "semantic": ["post::cost", "post::gate", "post::determinism"],  # cosine order
    "graph": ["post::gate", "post::bm25"],                       # traversal order
}


def main() -> None:
    print("=" * 70)
    print("M3.4 — SIGNAL FUSION via RRF (k=1, rank-only, no normalization)")
    print("=" * 70)

    print("\nInput — each signal's ranked list:")
    for name, docs in SIGNALS.items():
        print(f"    {name:<9} {docs}")

    print("\nFused ranking (score = Σ 1/(1+rank) across signals):")
    for hit in fuse(SIGNALS, top_k=5):
        votes = "  ".join(f"{s}#{r+1}={c:.2f}" for s, r, c in hit.contributions)
        print(f"    {hit.score:.3f}  {hit.doc_id:<18} [{votes}]")

    print("\n-> post::gate wins: ranked by all three signals. RRF rewards agreement")
    print("   across signals without ever comparing their raw score scales.")


if __name__ == "__main__":
    main()
