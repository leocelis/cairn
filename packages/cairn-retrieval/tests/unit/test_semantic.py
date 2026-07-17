"""Constraint tests for intents/semantic_signal_intent.yaml (M3.3, OP-3).

Each test maps 1:1 to a constraint (C-SEM-1..5) plus one joint test. A fake
deterministic embedder stands in for the caller's model. Stdlib-only.
"""

from __future__ import annotations

import pathlib
from typing import Sequence

import pytest

from cairn_retrieval.semantic import SemanticIndex

_SRC = pathlib.Path(__file__).parents[3] / "cairn-retrieval" / "src" / "cairn_retrieval"

# fixed 2-D unit vectors per text — deterministic stand-in for a real embedder
_VECS = {
    "cats and dogs": (1.0, 0.0),
    "feline pets": (0.92, 0.39),      # ~23 deg from query -> high cosine
    "quarterly finance report": (0.0, 1.0),  # orthogonal -> cosine 0
    "the query": (1.0, 0.0),
}


def _embed(texts: Sequence[str]) -> list[tuple[float, float]]:
    return [_VECS[t] for t in texts]


# -- C-SEM-1: cosine ranking -----------------------------------------------------

def test_cosine_ranking() -> None:
    idx = SemanticIndex.from_documents(
        {"d_exact": "cats and dogs", "d_near": "feline pets", "d_far": "quarterly finance report"},
        embedder=_embed,
    )
    hits = idx.search("the query", embedder=_embed)  # query vec (1,0)
    assert [h.doc_id for h in hits] == ["d_exact", "d_near", "d_far"]
    assert hits[0].score == pytest.approx(1.0)       # identical direction -> 1.0
    assert hits[2].score == pytest.approx(0.0)       # orthogonal -> 0.0


# -- C-SEM-2: floor + top_k ------------------------------------------------------

def test_floor_and_topk() -> None:
    idx = SemanticIndex.from_documents(
        {"d_exact": "cats and dogs", "d_near": "feline pets", "d_far": "quarterly finance report"},
        embedder=_embed,
    )
    floored = idx.search("the query", embedder=_embed, floor=0.6)
    assert [h.doc_id for h in floored] == ["d_exact", "d_near"]  # d_far (0.0) dropped
    assert [h.doc_id for h in idx.search("the query", embedder=_embed, top_k=1)] == ["d_exact"]
    assert idx.search("the query", embedder=_embed, floor=0.999999) == \
        [h for h in floored if h.score >= 0.999999]  # high floor prunes hard


# -- C-SEM-3: hot-path economy + closed-world miss -------------------------------

def test_embed_call_counts_and_miss() -> None:
    calls: list[Sequence[str]] = []

    def counting(texts: Sequence[str]) -> list[tuple[float, float]]:
        calls.append(list(texts))
        return [_VECS[t] for t in texts]

    idx = SemanticIndex.from_documents({"a": "cats and dogs", "b": "feline pets"}, embedder=counting)
    assert len(calls) == 1 and len(calls[0]) == 2         # build: ONE batch of N
    idx.search("the query", embedder=counting)
    assert len(calls) == 2 and calls[1] == ["the query"]  # search: ONE query embed
    # empty corpus -> [] (no embed, no fabrication)
    empty = SemanticIndex.from_documents({}, embedder=counting)
    assert empty.search("the query", embedder=counting) == []


# -- C-SEM-4: dimension guard (IVD Rule 5 — cosine returns 0.0, we raise) ---------

def test_dimension_mismatch_raises() -> None:
    idx = SemanticIndex.from_documents({"a": "cats and dogs"}, embedder=_embed)  # 2-D docs

    def three_d(texts: Sequence[str]) -> list[tuple[float, float, float]]:
        return [(1.0, 0.0, 0.0) for _ in texts]

    with pytest.raises(ValueError):
        idx.search("the query", embedder=three_d)


# -- C-SEM-5: no model SDK, byte-stable (conflict_prone) -------------------------

def test_no_model_sdk_byte_stable() -> None:
    src = (_SRC / "semantic.py").read_text()
    for banned in ("sentence_transformers", "import openai", "import anthropic",
                   "import torch", "import transformers", "import requests",
                   "import httpx", "urllib", "import time", "import datetime"):
        assert banned not in src, f"semantic must stay model/network/clock-free: {banned!r}"

    idx = SemanticIndex.from_documents({"a": "cats and dogs", "b": "feline pets"}, embedder=_embed)
    assert idx.search("the query", embedder=_embed) == idx.search("the query", embedder=_embed)


# -- joint satisfaction (5 constraints) ------------------------------------------

def test_joint_semantic() -> None:
    calls: list[int] = []

    def counting(texts: Sequence[str]) -> list[tuple[float, float]]:
        calls.append(len(texts))
        return [_VECS[t] for t in texts]

    idx = SemanticIndex.from_documents(
        {"d_exact": "cats and dogs", "d_near": "feline pets", "d_far": "quarterly finance report"},
        embedder=counting,
    )
    hits = idx.search("the query", embedder=counting, top_k=2, floor=0.6)  # C-1,C-2
    assert [h.doc_id for h in hits] == ["d_exact", "d_near"]
    assert calls == [3, 1]  # C-3: build one batch of 3, search one query
    assert idx.search("the query", embedder=counting, top_k=2, floor=0.6) == hits  # C-5 stable
