"""retrieve() end-to-end (M3.6) — the single entry point for the retrieval layer.

One call turns a raw query into a minimal, audited context package — or, when the
gate says retrieval is not worth it, into NOTHING:

    resolve -> gate -> orchestrate signals -> fuse (RRF) -> assemble

The default path is deterministic and generative-LLM-free. Embeddings run ONLY
when the gate's strategy selects the semantic signal AND an embedder was supplied;
a `strategy='none'` route or a lexical/graph route touches no embedder and no LLM.
This module is the integration of all of Phase 3 (gate OP-33, lexical OP-30,
semantic OP-3, graph OP-34, fusion OP-32, assembler OP-29/FF-11).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from cairn_engine import (
    AliasTableAdapter,
    EmbedderFn,
    GraphAdapter,
    resolve,
    traverse,
)
from cairn_retrieval.assembler import AssembledContext, Candidate, assemble
from cairn_retrieval.fusion import FusedHit, fuse
from cairn_retrieval.gate import DEFAULT_GATE, GateConfig, RoutingDecision, gate
from cairn_retrieval.lexical import LexicalIndex
from cairn_retrieval.semantic import SemanticIndex

__all__ = ["DocMeta", "RetrievalEngine", "RetrievalResult"]


@dataclass(frozen=True, slots=True)
class DocMeta:
    """Per-document content the assembler needs (precomputed; caller-owned)."""

    content: str
    tokens: int
    embedding: tuple[float, ...] = ()


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """What retrieve() returns: the gate verdict, the package (or None), the trace."""

    decision: RoutingDecision
    context: AssembledContext | None            # None when the gate skipped retrieval
    fused: tuple[FusedHit, ...]
    entities: tuple[str, ...]                    # resolved canonical ids


@dataclass(frozen=True, slots=True)
class RetrievalEngine:
    """Holds the pre-built table / corpus / signal indexes; retrieve() orchestrates them."""

    table: AliasTableAdapter
    corpus: Mapping[str, DocMeta]
    graph: GraphAdapter | None = None
    lexical: LexicalIndex | None = None
    semantic: SemanticIndex | None = None
    embedder: EmbedderFn | None = None
    private_ids: frozenset[str] = frozenset()
    tail_ids: frozenset[str] = frozenset()
    gate_config: GateConfig = DEFAULT_GATE
    lam: float = 0.5
    semantic_floor: float = 0.6                 # OP-32 cosine floor for the semantic sub-signal
    depth: int = 2

    def retrieve(self, query: str, *, budget: int, top_k: int = 20) -> RetrievalResult:
        """Resolve -> gate -> orchestrate -> fuse -> assemble. Deterministic; LLM-free default."""
        resolved, _ = resolve(query, table=self.table)
        entities = tuple(dict.fromkeys(r.canonical_id for r in resolved))

        decision = gate(
            query,
            entities=entities,
            private_ids=self.private_ids,
            tail_ids=self.tail_ids,
            config=self.gate_config,
        )
        if decision.strategy == "none":
            return RetrievalResult(decision, None, (), entities)  # the skip — no signals

        strat = decision.strategy
        signals: dict[str, list[str]] = {}
        if strat in ("grep", "composite") and self.lexical is not None:
            signals["lexical"] = [h.doc_id for h in self.lexical.search(query, top_k=top_k)]
        if strat in ("semantic", "composite") and self.semantic is not None and self.embedder is not None:
            signals["semantic"] = [
                h.doc_id
                for h in self.semantic.search(
                    query, embedder=self.embedder, top_k=top_k, floor=self.semantic_floor
                )
            ]
        if strat in ("graph", "composite") and self.graph is not None and entities:
            signals["graph"] = self._graph_docs(entities, top_k)

        fused = tuple(fuse(signals, top_k=top_k)) if signals else ()
        context = self._assemble(fused, budget) if fused else None
        return RetrievalResult(decision, context, fused, entities)

    # -- orchestration helpers ------------------------------------------------

    def _graph_docs(self, entities: tuple[str, ...], top_k: int) -> list[str]:
        """Doc-ids from the resolved entities' bounded neighborhood, hop-ordered."""
        assert self.graph is not None
        best: dict[str, tuple[int, float]] = {}  # doc_id -> (min_hop, best_score)
        for entity_id in entities:
            for hit in traverse(entity_id, graph=self.graph, depth=self.depth).hits:
                cur = best.get(hit.ref.doc_id)
                if cur is None or (hit.hop, -hit.score) < (cur[0], -cur[1]):
                    best[hit.ref.doc_id] = (hit.hop, hit.score)
        ordered = sorted(best.items(), key=lambda kv: (kv[1][0], -kv[1][1], kv[0]))
        return [doc_id for doc_id, _ in ordered][:top_k]

    def _assemble(self, fused: tuple[FusedHit, ...], budget: int) -> AssembledContext | None:
        """Fused doc-ids -> Candidates (corpus content + normalized rel) -> assemble."""
        top = fused[0].score if fused else 0.0
        candidates: list[Candidate] = []
        for hit in fused:
            meta = self.corpus.get(hit.doc_id)
            if meta is None:
                continue  # closed world: no content for this id -> skip, never fabricate
            rel = hit.score / top if top > 0 else 0.0
            candidates.append(Candidate(hit.doc_id, meta.content, meta.tokens, rel, meta.embedding))
        if not candidates:
            return None
        return assemble(candidates, budget=budget, lam=self.lam)
