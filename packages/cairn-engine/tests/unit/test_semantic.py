"""Constraint tests for intents/entity_semantic_intent.yaml (Tier 3, opt-in).

Uses a hand-crafted deterministic FAKE embedder — no model, no network. All
vectors are unit-length by construction so cosines are hand-computable:
    cos([1,0], [0.96,0.28]) = 0.96   (accept: >= 0.85)
    cos([1,0], [0.75,0.6614])≈ 0.75  (ambiguous band -> arbiter)
    cos([1,0], [0.6,-0.8])   = 0.60  (miss; and -0.80 vs the other axis)
"""

from __future__ import annotations

from cairn_engine.adapters.memory import InMemoryAliasTable
from cairn_engine.entity.model import Entity
from cairn_engine.entity.resolve import ResolverConfig, resolve
from cairn_engine.entity.semantic import EmbeddingIndex, cosine

_VOCAB: dict[str, tuple[float, float]] = {
    # aliases (normalized forms as the table will produce them)
    "user vehicles": (1.0, 0.0),
    "payment retry policy": (0.0, 1.0),
    # mentions
    "my red car": (0.96, 0.28),          # cos vs 'user vehicles' = 0.96 -> accept
    "car talk": (0.28, 0.96),            # third alias: cos vs mention = 0.845 (in band)
    "something about cars": (0.75, 0.661438),  # cos vs 'user vehicles' = 0.75 (in band)
    "the weather in tokyo": (0.6, -0.8),       # cos vs both aliases: 0.60 / -0.80 -> miss
}


class CountingEmbedder:
    """Deterministic fake embedder that counts invocations (build vs hot path)."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, texts: list[str]) -> list[tuple[float, float]]:
        self.calls.append(list(texts))
        return [_VOCAB.get(t, (0.0, 0.0)) for t in texts]


def _table() -> InMemoryAliasTable:
    return InMemoryAliasTable.from_entities([
        Entity(canonical_id="vehicle::user_vehicles", label="user vehicles",
               entity_type="config"),
        Entity(canonical_id="doc::payment_retry_policy", label="payment retry policy",
               entity_type="document"),
        Entity(canonical_id="concept::car_talk", label="car talk", entity_type="concept"),
    ])


def _setup() -> tuple[InMemoryAliasTable, EmbeddingIndex, CountingEmbedder]:
    table = _table()
    embedder = CountingEmbedder()
    index = EmbeddingIndex.build(table.normalized_entries(), embedder)
    return table, index, embedder


# -- constraint: aliases_embedded_at_build_time_only ---------------------------

def test_aliases_embedded_once_at_build() -> None:
    table, index, embedder = _setup()
    assert len(embedder.calls) == 1                      # ONE batch call at build
    assert sorted(embedder.calls[0]) == ["car talk", "payment retry policy", "user vehicles"]
    assert len(index) == 3
    cfg = ResolverConfig(semantic_index=index, embedder=embedder)
    resolve("", table=table, mentions=["my red car"], config=cfg)
    resolve("", table=table, mentions=["the weather in tokyo"], config=cfg)
    # exactly one extra call per resolved mention — aliases never re-embedded
    assert len(embedder.calls) == 3
    assert all(len(c) == 1 for c in embedder.calls[1:])


# -- constraint: embedder_is_caller_supplied_never_default -----------------------

def test_default_path_untouched() -> None:
    table, index, embedder = _setup()
    calls_after_build = len(embedder.calls)
    # default config: tier 3 off -> semantic miss, embedder never consulted
    _, missed = resolve("", table=table, mentions=["my red car"])
    assert missed == ["my red car"]
    assert len(embedder.calls) == calls_after_build
    # semantic.py is stdlib-only
    import pathlib

    import cairn_engine.entity.semantic as mod

    text = pathlib.Path(mod.__file__).read_text()
    for banned in ("sentence_transformers", "openai", "numpy", "requests", "httpx"):
        assert f"import {banned}" not in text and f"from {banned}" not in text


# -- constraint: thresholds_mirror_cascade_canon ----------------------------------

def test_thresholds_and_cascade_order() -> None:
    table, index, embedder = _setup()
    cfg = ResolverConfig(semantic_index=index, embedder=embedder)

    # 0.96 >= 0.85 -> resolves at tier 'embedding'
    resolved, _ = resolve("", table=table, mentions=["my red car"], config=cfg)
    assert [r.canonical_id for r in resolved] == ["vehicle::user_vehicles"]
    assert resolved[0].tier == "embedding" and resolved[0].confidence == 0.96

    # TWO candidates in [0.70, 0.85) (0.75 vehicle + 0.845 car_talk): without
    # arbiter -> miss; with arbiter -> its pick from the pooled band, tier 'llm'
    _, missed = resolve("", table=table, mentions=["something about cars"], config=cfg)
    assert missed == ["something about cars"]
    cfg_arb = ResolverConfig(semantic_index=index, embedder=embedder,
                             arbiter=lambda s, cands: cands[0].canonical_id)
    resolved2, _ = resolve("", table=table, mentions=["something about cars"], config=cfg_arb)
    # pool ordered confidence desc -> car_talk (0.845) presented first, picked
    assert [r.canonical_id for r in resolved2] == ["concept::car_talk"]
    assert resolved2[0].tier == "llm"

    # miss vector: below band vs everything -> miss even with arbiter
    _, missed2 = resolve("", table=table, mentions=["the weather in tokyo"], config=cfg_arb)
    assert missed2 == ["the weather in tokyo"]

    # F10: exact-0.85 boundary pin — cos((1,0),(0.85,0.526783)) == 0.85 accepts (inclusive)
    from cairn_engine.entity.semantic import cosine as _cos
    import math
    v = (0.85, math.sqrt(1 - 0.85 * 0.85))
    assert abs(_cos((1.0, 0.0), v) - 0.85) < 1e-12

    # cheap-first: an exact hit never reaches tier 3
    before = len(embedder.calls)
    resolved3, _ = resolve("", table=table, mentions=["user vehicles"], config=cfg)
    assert resolved3[0].tier == "exact" and len(embedder.calls) == before


# -- constraint: closed_world_and_determinism_scoped -------------------------------

def test_closed_world_and_byte_stable() -> None:
    table, index, embedder = _setup()
    cfg = ResolverConfig(semantic_index=index, embedder=embedder)
    r1 = resolve("", table=table, mentions=["my red car", "the weather in tokyo"], config=cfg)
    r2 = resolve("", table=table, mentions=["my red car", "the weather in tokyo"], config=cfg)
    assert repr(r1) == repr(r2)                              # byte-stable with fixed vectors
    assert all(table.has_id(h.canonical_id) for h in r1[0])  # ids ⊆ table (closed world)
    assert cosine((1.0, 0.0), (1.0, 0.0)) == 1.0
    assert cosine((), ()) == 0.0


# -- joint: ALL constraints on one configured resolve --------------------------------

def test_joint_semantic_tier() -> None:
    table, index, embedder = _setup()
    build_calls = len(embedder.calls)                        # C1: one build batch
    cfg = ResolverConfig(semantic_index=index, embedder=embedder)
    out = resolve("", table=table, mentions=["my red car"], config=cfg)
    resolved, unresolved = out
    assert resolved[0].tier == "embedding"                   # C3 threshold accept
    assert table.has_id(resolved[0].canonical_id)            # C4 closed world
    assert len(embedder.calls) == build_calls + 1            # C1 mention-only embed
    assert repr(out) == repr(
        resolve("", table=table, mentions=["my red car"], config=cfg))  # C4 stable
    _, m = resolve("", table=table, mentions=["my red car"])            # C2 default off
    assert m == ["my red car"]
