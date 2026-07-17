"""Constraint tests for intents/assembler_intent.yaml (M3.5, OP-29).

Each test maps 1:1 to a constraint (C-ASM-1..5) plus one joint test. MMR / fold
values hand-computed. Stdlib-only, zero-LLM, no re-embed.
"""

from __future__ import annotations

import inspect
import pathlib

from cairn_retrieval.assembler import Candidate, assemble

_SRC = pathlib.Path(__file__).parents[3] / "cairn-retrieval" / "src" / "cairn_retrieval"


def _c(doc_id: str, tokens: int, rel: float, emb: tuple[float, ...]) -> Candidate:
    return Candidate(doc_id, f"body of {doc_id}", tokens, rel, emb)


# -- C-ASM-1: MMR + greedy budget ------------------------------------------------

def test_mmr_budget() -> None:
    cands = [
        _c("a", 40, 0.9, (1.0, 0.0)),
        _c("b", 40, 0.8, (1.0, 0.0)),   # near-dup of a (same vector), higher rel than c
        _c("c", 40, 0.7, (0.0, 1.0)),   # diverse
    ]
    pkg = assemble(cands, budget=100, lam=0.5)   # fits 2 x 40
    ids = {c.doc_id for c in pkg.chunks}
    assert ids == {"a", "c"}                     # MMR picks diverse c over near-dup b
    assert "b" not in ids
    assert pkg.total_tokens == 80 and pkg.total_tokens <= 100


# -- C-ASM-2: dedup hard gate ----------------------------------------------------

def test_dedup_hard_gate() -> None:
    cands = [
        _c("a", 10, 0.9, (1.0, 0.0)),
        _c("b", 10, 0.8, (1.0, 0.0)),   # cos(a,b)=1.0 >= 0.95 -> dropped even though it fits
        _c("c", 10, 0.7, (0.0, 1.0)),
    ]
    pkg = assemble(cands, budget=1000, lam=0.5)   # budget fits all 3
    ids = {c.doc_id for c in pkg.chunks}
    assert ids == {"a", "c"} and "b" not in ids   # b dropped by dedup, not by budget


# -- C-ASM-3: fold ordering ------------------------------------------------------

def test_fold_ordering() -> None:
    # 5 orthogonal candidates so all are selected; rel a>b>c>d>e
    cands = [
        _c("a", 10, 0.9, (1, 0, 0, 0, 0)),
        _c("b", 10, 0.8, (0, 1, 0, 0, 0)),
        _c("c", 10, 0.7, (0, 0, 1, 0, 0)),
        _c("d", 10, 0.6, (0, 0, 0, 1, 0)),
        _c("e", 10, 0.5, (0, 0, 0, 0, 1)),
    ]
    pkg = assemble(cands, budget=1000)
    # rank-1 first, rank-2 last, rank-3 second, rank-4 second-to-last, rank-5 middle
    assert [c.doc_id for c in pkg.chunks] == ["a", "c", "e", "d", "b"]


# -- C-ASM-4: manifest + provenance ----------------------------------------------

def test_manifest_and_provenance() -> None:
    cands = [_c("a", 10, 0.9, (1, 0)), _c("b", 10, 0.5, (0, 1))]
    pkg = assemble(cands, budget=1000)
    # positions match emitted order; every field present
    assert [(m.doc_id, m.position) for m in pkg.manifest] == \
        [(c.doc_id, i) for i, c in enumerate(pkg.chunks)]
    assert all(m.tokens == 10 and 0.0 <= m.rel <= 1.0 for m in pkg.manifest)
    # provenance tag names each doc; total tokens sums selected
    assert "[[a]]" in pkg.text and "[[b]]" in pkg.text
    assert pkg.total_tokens == 20


# -- C-ASM-5: no LLM, no re-embed, byte-stable (conflict_prone) ------------------

def test_no_llm_no_reembed_byte_stable() -> None:
    src = (_SRC / "assembler.py").read_text()
    for banned in ("import openai", "import anthropic", "sentence_transformers",
                   "import torch", "import requests", "import httpx",
                   "import time", "import datetime"):
        assert banned not in src, f"assembler must stay LLM/embed/clock-free: {banned!r}"
    # no embedder parameter -> cannot re-embed
    assert "embedder" not in inspect.signature(assemble).parameters
    cands = [_c("a", 10, 0.9, (1, 0)), _c("b", 10, 0.6, (0, 1))]
    assert assemble(cands, budget=100) == assemble(cands, budget=100)


# -- joint satisfaction (5 constraints) ------------------------------------------

def test_joint_assembler() -> None:
    cands = [
        _c("a", 30, 0.9, (1.0, 0.0, 0.0)),
        _c("dup", 30, 0.85, (1.0, 0.0, 0.0)),   # near-dup of a -> dedup drop (C-2)
        _c("b", 30, 0.7, (0.0, 1.0, 0.0)),
        _c("c", 30, 0.6, (0.0, 0.0, 1.0)),
        _c("big", 999, 0.95, (0.0, 0.0, 1.0)),  # too big for budget (C-1)
    ]
    pkg = assemble(cands, budget=100, lam=0.5)   # fits 3 x 30 = 90
    ids = [c.doc_id for c in pkg.chunks]
    assert "dup" not in ids and "big" not in ids           # C-2 dedup + C-1 budget
    assert set(ids) == {"a", "b", "c"} and pkg.total_tokens == 90
    # C-3 fold order by rel (a>b>c): a first, b last, c middle
    assert ids == ["a", "c", "b"]
    # C-4 manifest complete + positions
    assert [m.position for m in pkg.manifest] == [0, 1, 2]
    assert all(m.doc_id == c.doc_id for m, c in zip(pkg.manifest, pkg.chunks))
    # C-5 byte-stable
    assert assemble(cands, budget=100, lam=0.5) == pkg
