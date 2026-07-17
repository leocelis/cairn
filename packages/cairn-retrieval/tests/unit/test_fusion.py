"""Constraint tests for intents/fusion_intent.yaml (M3.4, OP-32).

Each test maps 1:1 to a constraint (C-FUSE-1..5) plus one joint test. RRF golden
values hand-computed. Stdlib-only, rank-only (no score normalization).
"""

from __future__ import annotations

import inspect
import pathlib

import pytest

from cairn_retrieval.fusion import fuse

_SRC = pathlib.Path(__file__).parents[3] / "cairn-retrieval" / "src" / "cairn_retrieval"


# -- C-FUSE-1: RRF k=1 scores ----------------------------------------------------

def test_rrf_k1_scores() -> None:
    hits = fuse({"lex": ["a", "b", "c"], "sem": ["b", "a", "d"]})
    by_id = {h.doc_id: h.score for h in hits}
    assert by_id["a"] == pytest.approx(1.0 + 0.5)   # lex r0 + sem r1
    assert by_id["b"] == pytest.approx(0.5 + 1.0)   # lex r1 + sem r0
    assert by_id["c"] == pytest.approx(1 / 3)       # lex r2 only
    assert by_id["d"] == pytest.approx(1 / 3)       # sem r2 only
    # a and b tie at 1.5 -> doc_id asc; c and d tie at 1/3 -> doc_id asc
    assert [h.doc_id for h in hits] == ["a", "b", "c", "d"]


# -- C-FUSE-2: missing signal contributes 0 --------------------------------------

def test_missing_signal_contributes_zero() -> None:
    hits = fuse({"lex": ["x"], "sem": ["y"]})
    by_id = {h.doc_id: h.score for h in hits}
    assert by_id["x"] == pytest.approx(1.0)   # only lex, no penalty for sem absence
    assert by_id["y"] == pytest.approx(1.0)   # only sem
    # each carries a single contribution
    assert all(len(h.contributions) == 1 for h in hits)


# -- C-FUSE-3: dedup + determinism + top_k ---------------------------------------

def test_dedup_determinism_topk() -> None:
    signals = {"a": ["d1", "d2", "d3"], "b": ["d1", "d3", "d2"]}
    hits = fuse(signals)
    assert len(hits) == 3 and len({h.doc_id for h in hits}) == 3     # deduped
    assert [h.doc_id for h in hits] == ["d1", "d2", "d3"]            # d1 top; d2/d3 tie -> asc
    assert fuse(signals, top_k=1) == hits[:1]                        # top_k caps
    assert fuse(signals) == fuse(signals)                            # byte-stable
    # audit breakdown present, one entry per signal that ranked the doc
    d1 = next(h for h in hits if h.doc_id == "d1")
    assert {c[0] for c in d1.contributions} == {"a", "b"}


# -- C-FUSE-4: weights + configurable k ------------------------------------------

def test_weights_and_k() -> None:
    signals = {"lex": ["a", "b"], "sem": ["b", "a"]}
    # unweighted: a and b tie -> a first by doc_id
    assert [h.doc_id for h in fuse(signals)] == ["a", "b"]
    # weight lex 2x: a = 2*1.0 + 1*0.5 = 2.5 ; b = 2*0.5 + 1*1.0 = 2.0 -> a clearly first
    weighted = fuse(signals, weights={"lex": 2.0, "sem": 1.0})
    by_id = {h.doc_id: h.score for h in weighted}
    assert by_id["a"] == pytest.approx(2.5) and by_id["b"] == pytest.approx(2.0)
    # larger k flattens: with k=60, rank-1 (1/61) vs rank-2 (1/62) nearly equal
    flat = {h.doc_id: h.score for h in fuse({"lex": ["a", "b"]}, k=60)}
    assert abs(flat["a"] - flat["b"]) < 0.001


# -- C-FUSE-5: rank-only, stdlib, byte-stable (conflict_prone) --------------------

def test_rank_only_stdlib_byte_stable() -> None:
    src = (_SRC / "fusion.py").read_text()
    for banned in ("import requests", "import httpx", "urllib", "import openai",
                   "import anthropic", "import numpy", "import time", "import datetime",
                   "normalize", "min_max", "z_score"):
        assert banned not in src, f"fusion must stay rank-only/stdlib: {banned!r}"
    # the signature takes ranked id lists, NOT scores
    params = inspect.signature(fuse).parameters
    assert "signals" in params and "scores" not in params
    assert fuse({"a": ["d1", "d2"]}) == fuse({"a": ["d1", "d2"]})


# -- joint satisfaction (5 constraints) ------------------------------------------

def test_joint_fusion() -> None:
    signals = {
        "lexical": ["d1", "d2", "d3"],   # d1 r0
        "semantic": ["d2", "d1", "d4"],  # d2 r0, d4 only here
        "graph": ["d1", "d4"],           # d1 r0
    }
    hits = fuse(signals, top_k=3)
    by_id = {h.doc_id: h.score for h in hits}
    # C-1 RRF k=1: d1 = 1.0(lex) + 0.5(sem) + 1.0(graph) = 2.5
    assert by_id["d1"] == pytest.approx(2.5)
    # C-2 d4 present only in semantic(r2)+graph(r1): 1/3 + 0.5
    assert fuse(signals, top_k=10)  # ensure d4 exists
    d4 = next(h for h in fuse(signals, top_k=10) if h.doc_id == "d4")
    assert d4.score == pytest.approx(1 / 3 + 0.5)
    # C-3 dedup + top_k + determinism
    assert [h.doc_id for h in hits] == ["d1", "d2", "d4"]  # d4(0.833) > d3(0.333)
    assert fuse(signals, top_k=3) == hits
    # C-4 weight graph down -> d1 still top but score drops
    w = {h.doc_id: h.score for h in fuse(signals, weights={"graph": 0.0})}
    assert w["d1"] == pytest.approx(1.5)  # lex 1.0 + sem 0.5, graph zeroed
