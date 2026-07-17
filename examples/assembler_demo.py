#!/usr/bin/env python3
"""M3.5 — assemble the smallest sufficient context package (OP-29).

FF-11 (Du 2025): context LENGTH alone degrades accuracy 13.9-85% even with perfect
retrieval — fewest chunks wins. The assembler is a pure pipeline over precomputed
inputs: budget -> MMR-select -> cosine-dedup -> fold-order -> emit + trace. Zero
LLM, no re-embedding.

Run:  .venv/bin/python examples/assembler_demo.py
"""

from __future__ import annotations

from cairn_retrieval import Candidate, assemble

# candidates already scored + embedded by the signals (embeddings are precomputed)
CANDS = [
    Candidate("doc::pricing", "Pricing changed in Q3.", 30, 0.92, (1.0, 0.0, 0.0)),
    Candidate("doc::pricing_dup", "Q3 pricing update.", 30, 0.88, (0.99, 0.01, 0.0)),  # near-dup
    Candidate("doc::latency", "P99 latency dropped 20%.", 30, 0.74, (0.0, 1.0, 0.0)),
    Candidate("doc::hiring", "Two senior hires joined.", 30, 0.61, (0.0, 0.0, 1.0)),
    Candidate("doc::huge", "A very long appendix.", 500, 0.95, (0.0, 0.2, 0.9)),  # busts budget
]


def main() -> None:
    print("=" * 70)
    print("M3.5 — CONTEXT ASSEMBLER  (budget -> MMR -> dedup -> fold -> trace)")
    print("=" * 70)

    pkg = assemble(CANDS, budget=100, lam=0.5)  # ~3 chunks fit

    print(f"\nbudget=100 tokens  ->  selected {pkg.total_tokens} tokens, "
          f"{len(pkg.chunks)} chunks (dropped near-dup + oversized)")

    print("\nTrace manifest (the auditability artifact most assemblers lack):")
    print(f"    {'position':<9}{'doc_id':<18}{'rel':<7}{'mmr':<8}tokens")
    for m in pkg.manifest:
        print(f"    {m.position:<9}{m.doc_id:<18}{m.rel:<7.2f}{m.mmr_score:<8.3f}{m.tokens}")

    print("\nEmitted order (strongest at the EDGES — lost-in-the-middle mitigation):")
    print("    " + " -> ".join(c.doc_id.split('::')[1] for c in pkg.chunks))

    print("\n-> near-dup 'pricing_dup' dropped (cosine >= 0.95); 'huge' didn't fit the")
    print("   budget; strongest evidence sits first & last, weakest in the middle.")


if __name__ == "__main__":
    main()
