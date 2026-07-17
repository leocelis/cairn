"""Deterministic entity resolution — the hot path (OP-28, TH-1, TH-5).

Implements `intents/entity_resolution_intent.yaml` (+ the semantic tier intent):

    Tier 1a  exact          (surface string == declared label/alias)
    Tier 1b  normalized     (NFKC + casefold + collapse — see normalize.py)
    Tier 2   fuzzy          (pure-Python token-sort ratio >= 0.85, entropy gate 1.5)
    Tier 3   semantic       (opt-in: precomputed EmbeddingIndex + caller EmbedderFn)
    Tier 4   LLM arbiter    (opt-in: fires ONLY for 2+ candidates in [0.70, 0.85))

Cascade discipline (OP-28): cheap-first; each tier runs only after the previous
missed; the arbiter is the LAST resort — it judges the pooled fuzzy+semantic
ambiguous-band candidates, never preempts Tier 3, and never sees exact-tier
hits (exact ambiguity returns ALL candidates, confidence 1.0 — outside the band).

Guarantees:
  * closed world: a miss lands in `unresolved` — a canonical_id is NEVER
    synthesized; the arbiter may pick among presented candidates, never mint
  * byte-stable on the default path: same (query, table, config) -> identical
    output; opt-in tiers scope determinism to the caller's callables
  * stdlib only; zero LLM, zero network on the default path

Deliberate deviation from OP-28's entropy-gate wording ("route to exact or
LLM"): an entropy-gated mention that missed Tiers 1a/1b has NO candidates, and
cairn's arbiter is constrained-choice only — with nothing to pick from, the
mention goes to `unresolved` rather than to an unconstrained LLM link (which
could mint). Recorded in the intent changelog.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Callable

from cairn_engine.adapters.base import AliasTableAdapter
from cairn_engine.entity.model import ResolvedEntity
from cairn_engine.entity.normalize import normalize, shannon_entropy_bits, tokenize

if TYPE_CHECKING:
    from cairn_engine.entity.semantic import EmbedderFn, EmbeddingIndex

__all__ = ["ArbiterFn", "ResolverConfig", "resolve", "token_sort_ratio"]

_TIER_FUZZY = "fuzzy"
_TIER_EMBEDDING = "embedding"
_TIER_LLM = "llm"

# Tier 4 — the opt-in LLM arbiter (OP-28: 2+ candidates in the 0.70-0.85 band).
# Caller-supplied callable: (surface_form, candidates) -> chosen canonical_id,
# or None to abstain. Cairn never imports an SDK or calls an API itself. The
# arbiter can only SELECT among presented candidates; an answer outside the
# set is ignored (closed world: pick, never mint).
ArbiterFn = Callable[[str, tuple[ResolvedEntity, ...]], "str | None"]


@dataclass(frozen=True, slots=True)
class ResolverConfig:
    """Knobs with research-grounded defaults (ENTITY_RELATIONSHIP_RESOLUTION §5)."""

    fuzzy_threshold: float = 0.85         # inclusive
    entropy_min_bits: float = 1.5         # Graphiti entropy-gate pattern
    enable_fuzzy: bool = True
    arbiter: "ArbiterFn | None" = None    # Tier 4, opt-in; None = default LLM-free path
    arbiter_band: tuple[float, float] = (0.70, 0.85)  # the ambiguous band Tier 4 judges
    # Tier 3, opt-in: precomputed alias-embedding index + the caller's embedder
    # for the mention. Both None on the default path (zero network, zero models).
    semantic_index: "EmbeddingIndex | None" = None
    embedder: "EmbedderFn | None" = None
    semantic_threshold: float = 0.85      # inclusive, mirrors fuzzy_threshold


_DEFAULT_CONFIG = ResolverConfig()


def token_sort_ratio(a: str, b: str) -> float:
    """Token-SORT ratio, pure stdlib (difflib), deterministic, in [0, 1].

    Compares the FULL sorted-token strings — word order is ignored, typos are
    tolerated, but there is no subset freebie. (Classic token-SET ratio scores
    1.0 whenever one side's tokens are a subset of the other's — wrong
    semantics for resolution; see the intent changelog v0.1.1.)
    """
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0.0
    return SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()


def resolve(
    query: str,
    *,
    table: AliasTableAdapter,
    mentions: list[str] | None = None,
    config: ResolverConfig | None = None,
) -> tuple[list[ResolvedEntity], list[str]]:
    """Resolve entity mentions to canonical IDs against a frozen table.

    With `mentions`, each surface form runs the full cascade; misses populate
    `unresolved`. Without `mentions`, the normalized query is gazetteer-scanned
    for known aliases (longest-match-first, then leftmost; deduped; query
    order) — the scan cannot miss by construction, so `unresolved` stays empty
    on that path. Scan hits carry tier='normalized' (matching happens on the
    normalized text; the exact/normalized audit split exists on the mentions
    path only).
    """
    cfg = config or _DEFAULT_CONFIG
    if mentions is not None:
        return _resolve_mentions(mentions, table, cfg)
    return _scan(query, table), []


# -- explicit mentions: full cascade ---------------------------------------


def _resolve_mentions(
    mentions: list[str], table: AliasTableAdapter, cfg: ResolverConfig
) -> tuple[list[ResolvedEntity], list[str]]:
    resolved: list[ResolvedEntity] = []
    unresolved: list[str] = []
    for surface in mentions:
        hits = table.lookup(surface)  # Tiers 1a + 1b; ambiguity returns ALL candidates
        band: dict[str, ResolvedEntity] = {}  # id -> best in-band candidate (Tier 4 pool)
        if not hits and cfg.enable_fuzzy:
            hits = _fuzzy(surface, table, cfg, band)  # Tier 2
        if not hits and cfg.semantic_index is not None and cfg.embedder is not None:
            hits = _semantic(surface, cfg, band)  # Tier 3
        if not hits and cfg.arbiter is not None and len(band) >= 2:
            # Tier 4, last resort: 2+ distinct candidates in [0.70, 0.85) (OP-28)
            hits = _arbitrate(surface, _ordered(list(band.values())), cfg) or []
        if hits:
            resolved.extend(_ordered(hits))
        else:
            unresolved.append(surface)  # closed world: never synthesized
    return resolved, unresolved


def _pool(band: dict[str, ResolvedEntity], candidate: ResolvedEntity) -> None:
    """Collect an in-band candidate for Tier 4, keeping the best score per id."""
    prev = band.get(candidate.canonical_id)
    if prev is None or candidate.confidence > prev.confidence:
        band[candidate.canonical_id] = candidate


def _fuzzy(
    surface: str,
    table: AliasTableAdapter,
    cfg: ResolverConfig,
    band: dict[str, ResolvedEntity],
) -> list[ResolvedEntity]:
    norm_surface = normalize(surface)
    if shannon_entropy_bits(norm_surface) < cfg.entropy_min_bits:
        return []  # entropy gate: short/repetitive strings skip fuzzy (see module docstring)
    low, high = cfg.arbiter_band
    best_score = 0.0
    best_ids: list[str] = []
    for alias_norm, ids in table.normalized_entries():  # deterministic order
        score = token_sort_ratio(norm_surface, alias_norm)
        if score > best_score:
            best_score, best_ids = score, list(ids)
        elif score == best_score and score > 0.0:
            best_ids.extend(ids)
        if low <= score < high:  # pool EVERY in-band candidate, not just top ties
            for cid in ids:
                _pool(band, ResolvedEntity(surface_form=surface, canonical_id=cid,
                                           confidence=round(score, 6), tier=_TIER_LLM))
    if best_score >= cfg.fuzzy_threshold:  # threshold inclusive: >= resolves
        confidence = round(best_score, 6)
        return [
            ResolvedEntity(surface_form=surface, canonical_id=cid, confidence=confidence, tier=_TIER_FUZZY)
            for cid in sorted(set(best_ids))
        ]
    return []


def _semantic(
    surface: str, cfg: ResolverConfig, band: dict[str, ResolvedEntity]
) -> list[ResolvedEntity]:
    """Tier 3 (opt-in): cosine against PRECOMPUTED alias embeddings.

    Only the mention is embedded at query time (one embedder call); alias
    vectors were built offline (EmbeddingIndex.build). >= semantic_threshold
    resolves at tier 'embedding'; in-band candidates join the Tier-4 pool."""
    from cairn_engine.entity.semantic import EmbeddingIndex

    index, embedder = cfg.semantic_index, cfg.embedder
    if not isinstance(index, EmbeddingIndex) or not callable(embedder):
        raise TypeError(
            "semantic tier misconfigured: semantic_index must be an EmbeddingIndex "
            "and embedder a callable (see entity_semantic_intent.yaml)"
        )
    vectors = embedder([normalize(surface)])
    if not vectors:
        return []
    low, high = cfg.arbiter_band
    for score, ids in index.scored(vectors[0]):
        if low <= score < high:
            for cid in ids:
                _pool(band, ResolvedEntity(surface_form=surface, canonical_id=cid,
                                           confidence=round(score, 6), tier=_TIER_LLM))
    best_score, best_ids = index.nearest(vectors[0])
    if best_ids and best_score >= cfg.semantic_threshold:
        confidence = round(best_score, 6)
        return [
            ResolvedEntity(surface_form=surface, canonical_id=cid, confidence=confidence, tier=_TIER_EMBEDDING)
            for cid in best_ids  # already sorted by the index
        ]
    return []


def _arbitrate(
    surface: str, candidates: list[ResolvedEntity], cfg: ResolverConfig
) -> list[ResolvedEntity] | None:
    """Tier 4: consult the caller's arbiter on the pooled ambiguous band.

    Constrained choice only — an answer outside the presented candidate set is
    ignored (closed world: pick, never mint). Returns the single chosen hit,
    or None (abstain / invalid pick)."""
    arbiter = cfg.arbiter
    if arbiter is None:  # pragma: no cover — guarded by caller
        return None
    choice = arbiter(surface, tuple(candidates))
    if choice is None:
        return None
    for hit in candidates:
        if hit.canonical_id == choice:
            return [hit]
    return None  # invalid pick -> ignored


# -- free text: gazetteer scan ----------------------------------------------


def _scan(query: str, table: AliasTableAdapter) -> list[ResolvedEntity]:
    q_tokens = tokenize(query)
    if not q_tokens:
        return []
    gazetteer = dict(table.normalized_entries())
    if not gazetteer:
        return []
    max_gram = min(max(len(a.split(" ")) for a in gazetteer), len(q_tokens))
    covered = [False] * len(q_tokens)
    matches: list[tuple[int, str, tuple[str, ...]]] = []  # (start, alias_norm, ids)
    for length in range(max_gram, 0, -1):  # longest-match-first
        for start in range(0, len(q_tokens) - length + 1):  # then leftmost
            if any(covered[start : start + length]):
                continue
            gram = " ".join(q_tokens[start : start + length])
            ids = gazetteer.get(gram)
            if ids:
                matches.append((start, gram, ids))
                for i in range(start, start + length):
                    covered[i] = True
    matches.sort(key=lambda m: m[0])  # output order = query position
    out: list[ResolvedEntity] = []
    seen: set[tuple[str, str]] = set()
    for _, gram, ids in matches:
        for hit in _ordered(
            [ResolvedEntity(surface_form=gram, canonical_id=cid, confidence=1.0, tier="normalized") for cid in ids]
        ):
            key = (hit.surface_form, hit.canonical_id)
            if key not in seen:  # dedupe repeated occurrences
                seen.add(key)
                out.append(hit)
    return out


def _ordered(hits: list[ResolvedEntity]) -> list[ResolvedEntity]:
    """Ambiguity order: confidence desc, then canonical_id asc — all candidates
    returned, never a silent pick (OP-35 conflict resolution)."""
    return sorted(hits, key=lambda h: (-h.confidence, h.canonical_id))
