#!/usr/bin/env python3
"""M3.2 — the lexical signal: BM25 index (ranked) + exact/regex scan (fresh).

Two modes, one module, both pure-Python and deterministic (OP-30):
  INDEX  'which docs are most about these terms?'  -> BM25 ranking
  SCAN   'where does this exact token appear?'      -> match positions, no index

Run:  .venv/bin/python examples/lexical_signal_demo.py
"""

from __future__ import annotations

from cairn_retrieval import LexicalIndex, scan

CORPUS = {
    "post::gate": "The adaptive gate decides whether to retrieve. Retrieval is not free.",
    "post::bm25": "BM25 ranks documents by term frequency and inverse document frequency.",
    "post::determinism": "A deterministic retrieval layer returns the same results every run.",
    "post::retrieval": "Retrieval augments a model with documents. Retrieval quality matters.",
}


def main() -> None:
    print("=" * 70)
    print("M3.2 — LEXICAL SIGNAL  (BM25 index + exact scan, pure-Python)")
    print("=" * 70)

    index = LexicalIndex.from_documents(CORPUS)

    print("\nINDEX mode — BM25 ranked for query 'retrieval documents':")
    for hit in index.search("retrieval documents", top_k=3):
        print(f"    {hit.score:.4f}  {hit.doc_id}")

    print("\n  query 'gate' (rare term -> high idf):")
    for hit in index.search("gate"):
        print(f"    {hit.score:.4f}  {hit.doc_id}")

    print("\n  query 'nonexistent' -> closed world, no fabricated hit:")
    print(f"    {index.search('nonexistent')}")

    print("\nSCAN mode — exact 'Retrieval' (case-sensitive, always fresh, unranked):")
    for m in scan("Retrieval", CORPUS):
        print(f"    {m.doc_id}:{m.line_no}  {m.line}")

    print("\n-> INDEX answers 'most about these terms'; SCAN answers 'where exactly'.")
    print("   ripgrep / FTS5 / Tantivy are opt-in accelerators with the same semantics.")


if __name__ == "__main__":
    main()
