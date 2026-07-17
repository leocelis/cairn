"""Constraint tests for intents/retrieve_e2e_intent.yaml (M3.6 — the capstone).

Each test maps 1:1 to a constraint (C-RET-1..5) plus one joint test. A full engine
(table + corpus + lexical + semantic + graph) is driven end to end; a counting
embedder proves hot-path purity. Stdlib-only, deterministic.
"""

from __future__ import annotations

import hashlib
import math
import pathlib
from typing import Sequence

from cairn_engine import Entity, InMemoryAliasTable, InMemoryGraph, Ref, Relation
from cairn_retrieval.lexical import LexicalIndex
from cairn_retrieval.retrieve import DocMeta, RetrievalEngine
from cairn_retrieval.semantic import SemanticIndex

_SRC = pathlib.Path(__file__).parents[3] / "cairn-retrieval" / "src" / "cairn_retrieval"


def _entities() -> list[Entity]:
    return [
        Entity("org::acme", "Acme", "org", aliases=("acme",), refs=(Ref("doc::acme_home"),),
               relations=(Relation("mentions", "concept::pricing"),)),
        Entity("org::beta", "Beta", "org", aliases=("beta",), refs=(Ref("doc::beta_home"),)),
        Entity("concept::pricing", "pricing", "concept", aliases=("pricing",),
               refs=(Ref("doc::pricing_guide"),)),
        Entity("proj::secret", "secret project", "project", aliases=("secret project",),
               refs=(Ref("doc::secret"),)),
    ]


_CORPUS = {
    "doc::acme_home": DocMeta("acme company overview and history", 20, (1.0, 0.0)),
    "doc::beta_home": DocMeta("beta company overview", 20, (0.0, 1.0)),
    "doc::pricing_guide": DocMeta("pricing plans and tiers", 20, (0.7, 0.7)),
    "doc::secret": DocMeta("secret internal project notes", 20, (0.5, 0.5)),
}


class _CountingEmbedder:
    """Deterministic hashing embedder that records how many times it is called."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        out = []
        for text in texts:
            vec = [0.0] * 8
            for tok in text.lower().split():
                h = int(hashlib.blake2b(tok.encode(), digest_size=2).hexdigest(), 16)
                vec[h % 8] += 1.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            out.append([x / norm for x in vec])
        return out


def _engine(**over: object) -> tuple[RetrievalEngine, _CountingEmbedder]:
    embedder = _CountingEmbedder()
    texts = {k: v.content for k, v in _CORPUS.items()}
    kwargs: dict[str, object] = dict(
        table=InMemoryAliasTable.from_entities(_entities()),
        corpus=_CORPUS,
        graph=InMemoryGraph.from_entities(_entities()),
        lexical=LexicalIndex.from_documents(texts),
        semantic=SemanticIndex.from_documents(texts, embedder=embedder),
        embedder=embedder,
        semantic_floor=0.0,  # so the semantic signal always contributes in tests
    )
    kwargs.update(over)
    embedder.calls.clear()  # ignore build-time embedding; count only retrieve()
    return RetrievalEngine(**kwargs), embedder  # type: ignore[arg-type]


def _signal_names(result) -> set[str]:  # type: ignore[no-untyped-def]
    return {sig for h in result.fused for sig, _r, _c in h.contributions}


# -- C-RET-1: skip path runs no signals ------------------------------------------

def test_skip_path_runs_no_signals() -> None:
    engine, _ = _engine()
    # "acme" -> single head entity, simple -> gate 'none'. Lexical WOULD match
    # doc::acme_home, so an empty fused proves the signal never ran.
    result = engine.retrieve("acme", budget=100)
    assert result.decision.strategy == "none"
    assert result.context is None and result.fused == ()
    assert result.entities == ("org::acme",)   # still resolved


# -- C-RET-2: strategy selects signals -------------------------------------------

def test_strategy_selects_signals() -> None:
    grep_engine, _ = _engine(tail_ids=frozenset({"org::acme"}))
    grep = grep_engine.retrieve("acme", budget=100)
    assert grep.decision.strategy == "grep"
    assert _signal_names(grep) == {"lexical"}          # grep -> lexical only

    comp_engine, _ = _engine()
    comp = comp_engine.retrieve("acme and beta", budget=100)   # 2 entities -> composite
    assert comp.decision.strategy == "composite"
    assert _signal_names(comp) == {"lexical", "semantic", "graph"}  # all available


# -- C-RET-3: graph signal is entity-grounded ------------------------------------

def test_graph_signal_entity_grounded() -> None:
    engine, _ = _engine(private_ids=frozenset({"proj::secret"}))
    result = engine.retrieve("secret project", budget=100)   # private -> graph route
    assert result.decision.strategy == "graph"
    ids = {h.doc_id for h in result.fused}
    assert "doc::secret" in ids                              # from traverse(proj::secret)
    # closed world: same query, engine with NO graph -> no graph contribution
    nogfx, _ = _engine(graph=None, private_ids=frozenset({"proj::secret"}))
    assert nogfx.retrieve("secret project", budget=100).fused == ()


# -- C-RET-4: end-to-end package -------------------------------------------------

def test_end_to_end_package() -> None:
    engine, _ = _engine()
    result = engine.retrieve("acme and beta", budget=60, top_k=20)   # composite
    ctx = result.context
    assert ctx is not None
    assert ctx.total_tokens <= 60                           # budget respected
    assert len(ctx.manifest) == len(ctx.chunks)             # manifest complete
    assert all(f"[[{c.doc_id}]]" in ctx.text for c in ctx.chunks)  # provenance
    # byte-stable end to end
    again, _ = _engine()
    assert again.retrieve("acme and beta", budget=60, top_k=20) == result


# -- C-RET-5: hot-path purity (conflict_prone) -----------------------------------

def test_hot_path_purity() -> None:
    src = (_SRC / "retrieve.py").read_text()
    for banned in ("import openai", "import anthropic", "import requests",
                   "import httpx", "urllib", "import time", "import datetime"):
        assert banned not in src, f"retrieve must stay LLM/network/clock-free: {banned!r}"

    # 'none' route -> zero embedder calls
    e1, emb1 = _engine()
    e1.retrieve("acme", budget=100)
    assert emb1.calls == []

    # grep route (lexical only) -> zero embedder calls
    e2, emb2 = _engine(tail_ids=frozenset({"org::acme"}))
    e2.retrieve("acme", budget=100)
    assert emb2.calls == []

    # composite route -> exactly one embedder call (the query)
    e3, emb3 = _engine()
    e3.retrieve("acme and beta", budget=100)
    assert len(emb3.calls) == 1 and emb3.calls[0] == ["acme and beta"]


# -- joint satisfaction (5 constraints) ------------------------------------------

def test_joint_retrieve() -> None:
    engine, emb = _engine()
    # skip (C-1) + zero embed (C-5)
    skip = engine.retrieve("acme", budget=100)
    assert skip.decision.strategy == "none" and skip.context is None
    assert emb.calls == []

    # composite: all signals (C-2), entity-grounded graph (C-3), budgeted package (C-4)
    emb.calls.clear()
    comp = engine.retrieve("acme and beta", budget=60)
    assert _signal_names(comp) == {"lexical", "semantic", "graph"}
    assert "doc::acme_home" in {h.doc_id for h in comp.fused}  # graph/lexical grounded
    assert comp.context is not None and comp.context.total_tokens <= 60
    assert len(emb.calls) == 1  # C-5: exactly one query embed on the semantic branch
    # byte-stable
    engine2, _ = _engine()
    assert engine2.retrieve("acme and beta", budget=60) == comp
