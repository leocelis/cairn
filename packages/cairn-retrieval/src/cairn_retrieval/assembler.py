"""Context assembler (M3.5, OP-29) — the smallest sufficient context package.

FF-11 (Du 2025): context LENGTH alone degrades accuracy 13.9-85%, even with
perfect retrieval — fewest chunks wins. So after fusion, this builds the MINIMAL
package with a pure-function pipeline (zero generative-LLM, no re-embedding):

    budget -> MMR-select -> cosine-dedup -> fold-order -> emit + trace manifest

Every step is a deterministic function of the candidates, their relevance, and
their PRECOMPUTED embeddings — same (candidates, budget, lam) -> byte-identical
package. The assembler never embeds and never calls a model; it only selects,
orders, and emits from inputs the signals already produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from cairn_engine import cosine

__all__ = ["Candidate", "ManifestEntry", "AssembledContext", "assemble"]


@dataclass(frozen=True, slots=True)
class Candidate:
    """A fused candidate ready for packing. `embedding` is PRECOMPUTED (never re-embedded)."""

    doc_id: str
    content: str
    tokens: int
    rel: float                        # relevance in [0,1] (fusion / rerank score)
    embedding: tuple[float, ...]      # precomputed vector for MMR diversity + dedup


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    """Audit record for one selected chunk."""

    doc_id: str
    tokens: int
    rel: float
    mmr_score: float
    position: int                     # index in the emitted order


@dataclass(frozen=True, slots=True)
class AssembledContext:
    """The emitted package plus its trace manifest."""

    chunks: tuple[Candidate, ...]     # in emitted (fold) order
    text: str                         # concatenated, provenance-tagged
    manifest: tuple[ManifestEntry, ...]
    total_tokens: int


def assemble(
    candidates: Sequence[Candidate],
    *,
    budget: int,
    lam: float = 0.5,
    dedup_threshold: float = 0.95,
) -> AssembledContext:
    """Build the minimal context package (OP-29). Deterministic, zero-LLM, no re-embed."""
    # --- B + C: greedy MMR selection with a dedup hard gate, within budget ------
    selected: list[Candidate] = []
    chosen_ids: set[str] = set()
    mmr_of: dict[str, float] = {}
    remaining = budget
    while True:
        eligible: list[tuple[float, Candidate]] = []
        for cand in candidates:
            if cand.doc_id in chosen_ids or cand.tokens > remaining:
                continue
            max_sim = max((cosine(cand.embedding, s.embedding) for s in selected), default=0.0)
            if selected and max_sim >= dedup_threshold:
                continue  # C dedup hard gate
            eligible.append((lam * cand.rel - (1 - lam) * max_sim, cand))
        if not eligible:
            break
        # tie-break: MMR desc, then rel desc, then doc_id asc — byte-stable
        mmr, chosen = max(eligible, key=lambda mc: (mc[0], mc[1].rel, _neg_id(mc[1].doc_id)))
        selected.append(chosen)
        chosen_ids.add(chosen.doc_id)
        mmr_of[chosen.doc_id] = mmr
        remaining -= chosen.tokens

    # --- D: fold ordering by relevance (strongest at the edges) -----------------
    by_rel = sorted(selected, key=lambda c: (-c.rel, c.doc_id))
    n = len(by_rel)
    ordered: list[Candidate | None] = [None] * n
    lo, hi = 0, n - 1
    for i, cand in enumerate(by_rel):
        if i % 2 == 0:
            ordered[lo] = cand
            lo += 1
        else:
            ordered[hi] = cand
            hi -= 1
    chunks = tuple(c for c in ordered if c is not None)

    # --- E: emit + trace manifest ----------------------------------------------
    manifest = tuple(
        ManifestEntry(c.doc_id, c.tokens, c.rel, mmr_of[c.doc_id], pos)
        for pos, c in enumerate(chunks)
    )
    text = "\n\n".join(f"[[{c.doc_id}]]\n{c.content}" for c in chunks)
    return AssembledContext(chunks, text, manifest, sum(c.tokens for c in chunks))


def _neg_id(doc_id: str) -> tuple[int, ...]:
    """Order key so that SMALLER doc_id wins a tie under `>` comparison (asc)."""
    return tuple(-ord(ch) for ch in doc_id)
