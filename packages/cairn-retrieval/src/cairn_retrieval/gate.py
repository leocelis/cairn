"""Adaptive retrieval gate (M3.1) — decide whether/what to retrieve, LLM-free.

Always-on retrieval empirically HURTS (SRACG AAAI 2026: -2.6 to -3.6pp); selective
retrieval helps (+2.4 to +7.1pp). `strategy=none` is the correct answer for a large
slice of queries, not a fallback. This gate (OP-33) makes the decision BEFORE any
signal runs, deterministically, with zero generative-LLM calls — using an LLM to
decide whether to call an LLM is circular.

Two stages:
  Stage 1  deterministic bypass — temporal/version markers, multi-entity relational,
           private entity. Shortcut to a decision with no scoring.
  Stage 2  CA-RAG utility cost function — utility(s) = w_Q·quality_prior − w_L·latency
           − w_C·token, argmax over the tiers. `none` (direct LLM) is in the pool.

Inputs are closed and pre-computed: `entities` are canonical_ids already resolved by
the caller (cairn tier-1); `private_ids` / `tail_ids` are static popularity labels
built at ontology-authoring time (OP-35). The gate invents nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Mapping

__all__ = ["GateConfig", "RoutingDecision", "DEFAULT_GATE", "complexity", "gate"]

# strategy tiers (OP-25 / OP-33), cheapest first — also the tie-break order
_TIERS = ("none", "grep", "semantic", "graph", "composite")

# Relational cue words + phrases (feed both complexity and Stage-1 relational detection)
_CUE_WORDS = frozenset({"compare", "why", "connect", "between", "related",
                        "versus", "vs", "difference", "path"})
_CUE_PHRASES = ("history of", "what changed", "compared to")

# Stage-1 freshness markers (STATIC text match — never a wall-clock read)
_TEMPORAL_MARKERS = ("today", "current", "currently", "latest", "now", "recent",
                     "recently", "this week", "this month", "as of", "up to date",
                     "up-to-date", "nowadays")
_VERSION_WORDS = frozenset({"version", "release", "changelog"})
_VERSION_RE = re.compile(r"\bv?\d+\.\d+")  # 1.2, v3.4, ...


@dataclass(frozen=True, slots=True)
class GateConfig:
    """Calibratable weights/priors (OP-33 defaults; tune per corpus after OP-31)."""

    w_q: float = 0.6
    w_l: float = 0.2
    w_c: float = 0.2
    tail_boost: float = 0.15
    quality_prior: Mapping[str, float] = field(default_factory=lambda: {
        "none": 0.52, "grep": 0.64, "semantic": 0.73, "graph": 0.82, "composite": 0.86})
    latency_cost: Mapping[str, float] = field(default_factory=lambda: {
        "none": 0.0, "grep": 0.2, "semantic": 0.4, "graph": 0.6, "composite": 0.85})
    token_cost: Mapping[str, float] = field(default_factory=lambda: {
        "none": 0.0, "grep": 0.2, "semantic": 0.4, "graph": 0.5, "composite": 0.7})
    complexity_gain: Mapping[str, float] = field(default_factory=lambda: {
        "none": 0.0, "grep": 0.05, "semantic": 0.20, "graph": 0.30, "composite": 0.40})


DEFAULT_GATE = GateConfig()


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """The gate's verdict — strategy plus a full audit of how it was reached."""

    strategy: str                       # none | grep | semantic | graph | composite
    stage: int                          # 1 = deterministic bypass, 2 = cost function
    reason: str
    complexity: float
    freshness_required: bool
    scores: tuple[tuple[str, float], ...]  # per-tier utility (Stage 2); () for Stage 1


def complexity(query: str) -> float:
    """CA-RAG complexity in [0,1]: 0.6·(wordlen/20) + 0.4·(cues/3), clipped."""
    words = query.split()
    wordlen = len(words)
    lower = query.lower()
    cues = sum(1 for w in words if w.strip(".,;:!?").lower() in _CUE_WORDS)
    cues += sum(1 for p in _CUE_PHRASES if p in lower)
    raw = 0.6 * (wordlen / 20) + 0.4 * (cues / 3)
    return max(0.0, min(1.0, raw))


def _has_relational_cue(query: str) -> bool:
    lower = query.lower()
    if any(p in lower for p in _CUE_PHRASES):
        return True
    return any(w.strip(".,;:!?").lower() in _CUE_WORDS for w in query.split())


def _freshness_marker(query: str) -> bool:
    lower = query.lower()
    if any(m in lower for m in _TEMPORAL_MARKERS):
        return True
    if _VERSION_RE.search(lower):
        return True
    return any(w.strip(".,;:!?").lower() in _VERSION_WORDS for w in query.split())


def gate(
    query: str,
    *,
    entities: Iterable[str] = (),
    private_ids: frozenset[str] = frozenset(),
    tail_ids: frozenset[str] = frozenset(),
    config: GateConfig = DEFAULT_GATE,
) -> RoutingDecision:
    """Return the RoutingDecision for `query`. Deterministic, zero-LLM (OP-33)."""
    ents = tuple(dict.fromkeys(entities))  # distinct, order-preserving
    c = complexity(query)
    fresh = _freshness_marker(query)

    # --- Stage 1: deterministic bypass (precedence: relational > temporal > private)
    if len(ents) >= 2 or (_has_relational_cue(query) and ents):
        return RoutingDecision("composite", 1, "multi-entity relational", c, fresh, ())
    if fresh:
        strat = "graph" if ents else "semantic"
        return RoutingDecision(strat, 1, "freshness marker -> retrieve", c, True, ())
    if any(e in private_ids for e in ents):
        return RoutingDecision("graph", 1, "private entity (model cannot know)", c, fresh, ())

    # --- Stage 2: CA-RAG utility cost function ---------------------------------
    is_tail = any(e in tail_ids for e in ents)
    scores: list[tuple[str, float]] = []
    for tier in _TIERS:
        quality = config.quality_prior[tier] + c * config.complexity_gain[tier]
        if is_tail and tier != "none":
            quality += config.tail_boost
        utility = config.w_q * quality - config.w_l * config.latency_cost[tier] \
            - config.w_c * config.token_cost[tier]
        scores.append((tier, utility))
    # argmax; ties broken by cheapest (earlier in _TIERS)
    best = max(range(len(scores)), key=lambda i: (scores[i][1], -i))
    strategy = scores[best][0]
    reason = f"utility argmax (c={c:.2f}, tail={is_tail})"
    return RoutingDecision(strategy, 2, reason, c, fresh, tuple(scores))
