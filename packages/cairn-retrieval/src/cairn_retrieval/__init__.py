"""cairn-retrieval — the agent-retrieval layer on top of the Cairn entity engine.

Planned primitives (Phase 3):
  A  Adaptive gate         — decide whether/what to retrieve (OP-1, OP-33, OP-25)
  C  Signal orchestration  — lexical (OP-30) / semantic / graph, fused via RRF (OP-32)
  E  Context assembler     — budget -> MMR -> dedup -> edge-load -> emit (OP-29, FF-11)

Implemented:
  adaptive_gate — two-stage LLM-free gate: decide whether/what to retrieve (OP-33).
  lexical       — BM25 index + exact/regex scan, pure-Python, deterministic (OP-30).
  semantic      — dense cosine retrieval over caller-embedded docs, opt-in (OP-3).
  fusion        — Reciprocal Rank Fusion (k=1) of the signals' ranked lists (OP-32).
  assembler     — budget->MMR->dedup->fold-order->emit+trace, pure (OP-29, FF-11).
  retrieve      — the end-to-end entry point: resolve->gate->orchestrate->fuse->assemble.
  link_ranking  — concept-weighted (IDF) document<->document link recommendation.
                 Ranking/relevance lives here, NOT in the cairn entity engine.
  connections   — cold-start link prediction: rank existing entities a NEW
                 candidate node should connect to (OP-36). Content-first, seed-
                 optional structural; the candidate-vs-corpus form of link_ranking.
"""

from cairn_retrieval.assembler import (
    AssembledContext,
    Candidate,
    ManifestEntry,
    assemble,
)
from cairn_retrieval.retrieve import DocMeta, RetrievalEngine, RetrievalResult
from cairn_retrieval.fusion import FusedHit, fuse
from cairn_retrieval.gate import (
    DEFAULT_GATE,
    GateConfig,
    RoutingDecision,
    complexity,
    gate,
)
from cairn_retrieval.lexical import LexicalHit, LexicalIndex, ScanMatch, scan
from cairn_retrieval.semantic import SemanticHit, SemanticIndex
from cairn_retrieval.link_ranking import (
    LinkRecommendation,
    concept_idf,
    rank_links,
    tfidf_vectors,
)
from cairn_retrieval.connections import ConnectionSuggestion, suggest_connections

__version__ = "0.1.0"

__all__ = [
    "AssembledContext",
    "Candidate",
    "ConnectionSuggestion",
    "DEFAULT_GATE",
    "DocMeta",
    "FusedHit",
    "GateConfig",
    "LexicalHit",
    "LexicalIndex",
    "LinkRecommendation",
    "ManifestEntry",
    "RetrievalEngine",
    "RetrievalResult",
    "RoutingDecision",
    "ScanMatch",
    "SemanticHit",
    "SemanticIndex",
    "__version__",
    "assemble",
    "complexity",
    "concept_idf",
    "fuse",
    "gate",
    "rank_links",
    "scan",
    "suggest_connections",
    "tfidf_vectors",
]
