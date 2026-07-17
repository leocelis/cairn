"""Constraint tests for intents/adaptive_gate_intent.yaml (M3.1, OP-33).

Each test maps 1:1 to a constraint (C-GATE-1..5) plus one joint test. Utility
golden values hand-computed. Stdlib-only, zero LLM.
"""

from __future__ import annotations

import pathlib

import pytest

from cairn_retrieval.gate import complexity, gate

_SRC = pathlib.Path(__file__).parents[3] / "cairn-retrieval" / "src" / "cairn_retrieval"


# -- C-GATE-1: Stage 1 temporal/version bypass -----------------------------------

def test_stage1_temporal() -> None:
    d = gate("what is the latest pricing")
    assert d.stage == 1 and d.freshness_required is True and d.strategy == "semantic"

    d2 = gate("current status of org::acme", entities=["org::acme"])
    assert d2.stage == 1 and d2.freshness_required and d2.strategy == "graph"  # entity -> graph

    d3 = gate("what changed in version 2.1")
    assert d3.stage == 1 and d3.freshness_required and d3.strategy == "semantic"


# -- C-GATE-2: Stage 1 relational + private --------------------------------------

def test_stage1_relational_and_private() -> None:
    # two distinct entities -> composite
    d = gate("how do these relate", entities=["e::a", "e::b"])
    assert d.stage == 1 and d.strategy == "composite"
    # relational cue + one entity -> composite
    d2 = gate("compare this to the baseline", entities=["e::a"])
    assert d2.stage == 1 and d2.strategy == "composite"
    # single private entity, no relational/temporal -> graph
    d3 = gate("tell me about my project", entities=["proj::x"],
              private_ids=frozenset({"proj::x"}))
    assert d3.stage == 1 and d3.strategy == "graph" and d3.reason.startswith("private")


# -- C-GATE-3: complexity formula ------------------------------------------------

def test_complexity_formula() -> None:
    # "capital of France": wordlen 3, cues 0 -> 0.6*3/20 = 0.09
    assert complexity("capital of France") == pytest.approx(0.09)
    # "compare why these connect": wordlen 4, cues 3 -> 0.6*0.2 + 0.4*1.0 = 0.52
    assert complexity("compare why these connect") == pytest.approx(0.52)
    # clip upper bound
    assert complexity(" ".join(["why compare between"] * 20)) == 1.0


# -- C-GATE-4: Stage 2 none reachable + tail flip --------------------------------

def test_stage2_none_reachable_and_tail_flip() -> None:
    plain = gate("capital of France", entities=["geo::france"])
    assert plain.stage == 2 and plain.strategy == "none"   # strategy=none REACHABLE
    scores = dict(plain.scores)
    assert scores["none"] == pytest.approx(0.312)
    assert scores["grep"] == pytest.approx(0.3067)

    # same query, but the entity is long-tail -> retrieve tier wins
    tail = gate("capital of France", entities=["geo::france"],
                tail_ids=frozenset({"geo::france"}))
    assert tail.stage == 2 and tail.strategy == "grep"
    assert dict(tail.scores)["grep"] == pytest.approx(0.3967)


# -- C-GATE-5: no LLM, byte-stable (conflict_prone) ------------------------------

def test_no_llm_byte_stable() -> None:
    src = (_SRC / "gate.py").read_text()
    for banned in ("import openai", "import anthropic", "import requests",
                   "import httpx", "import time", "import datetime", "from datetime"):
        assert banned not in src, f"gate must stay LLM/clock-free: {banned!r}"

    args = dict(entities=["geo::france"], tail_ids=frozenset({"geo::france"}))
    assert gate("capital of France", **args) == gate("capital of France", **args)


# -- joint satisfaction (5 constraints) ------------------------------------------

def test_joint_gate() -> None:
    # C-1 temporal + entity -> stage 1 graph + freshness
    t = gate("current revenue of org::acme", entities=["org::acme"])
    assert (t.stage, t.strategy, t.freshness_required) == (1, "graph", True)
    # C-2 two entities -> composite
    r = gate("link them", entities=["a", "b"])
    assert (r.stage, r.strategy) == (1, "composite")
    # C-3 + C-4 plain popular query -> none via utility argmax
    p = gate("capital of France", entities=["geo::france"])
    assert (p.stage, p.strategy) == (2, "none")
    assert p.complexity == pytest.approx(0.09)
    # C-4 tail flip -> grep
    tl = gate("capital of France", entities=["geo::france"],
              tail_ids=frozenset({"geo::france"}))
    assert tl.strategy == "grep"
    # C-5 byte-stable across the whole set
    assert gate("current revenue of org::acme", entities=["org::acme"]) == t
