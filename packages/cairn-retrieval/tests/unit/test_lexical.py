"""Constraint tests for intents/lexical_signal_intent.yaml (M3.2, OP-30).

Each test maps 1:1 to a constraint (C-LEX-1..5) plus one joint test. BM25 golden
values hand-computed. Stdlib-only, deterministic.
"""

from __future__ import annotations

import math
import pathlib

import pytest

from cairn_retrieval.lexical import LexicalIndex, ScanMatch, scan

_SRC = pathlib.Path(__file__).parents[3] / "cairn-retrieval" / "src" / "cairn_retrieval"


# -- C-LEX-1: BM25 ranking (tf + idf) --------------------------------------------

def test_bm25_ranking() -> None:
    idx = LexicalIndex.from_documents({
        "d1": "cat cat cat",       # tf(cat)=3, dl=3
        "d2": "cat dog",           # tf(cat)=1, dl=2
        "d3": "dog dog dog dog",   # tf(cat)=0, dl=4
    })
    hits = idx.search("cat")
    # d3 has no query term -> not a hit; d1 (higher tf) outranks d2
    assert [h.doc_id for h in hits] == ["d1", "d2"]
    # golden top score: idf=ln(1.6); term=6.6/4.2 -> 0.738577...
    idf = math.log(1.6)
    assert hits[0].score == pytest.approx(idf * (3 * 2.2) / (3 + 1.2 * 1.0))
    assert hits[0].score > hits[1].score


# -- C-LEX-2: length normalization (b) -------------------------------------------

def test_length_normalization() -> None:
    docs = {"short": "cat", "long": "cat filler filler filler filler"}
    shorter, longer = LexicalIndex.from_documents(docs).search("cat")
    assert (shorter.doc_id, longer.doc_id) == ("short", "long")  # shorter wins
    assert shorter.score > longer.score
    # b=0 removes the length penalty -> equal scores
    flat = LexicalIndex.from_documents(docs, b=0.0).search("cat")
    assert flat[0].score == pytest.approx(flat[1].score)


# -- C-LEX-3: determinism + closed-world miss ------------------------------------

def test_determinism_and_miss() -> None:
    idx = LexicalIndex.from_documents({"a": "term x", "b": "term x", "c": "term x"})
    hits = idx.search("term")
    # equal scores -> stable tie-break by doc_id asc
    assert [h.doc_id for h in hits] == ["a", "b", "c"]
    assert idx.search("term", top_k=2) == hits[:2]           # top_k caps
    assert idx.search("nonexistentword") == []               # miss -> [] (no fabrication)
    assert idx.search("term") == idx.search("term")          # byte-stable


# -- C-LEX-4: scan mode ----------------------------------------------------------

def test_scan_mode() -> None:
    docs = {
        "f2": "alpha\nbeta cat\ncat",
        "f1": "no match here\nCAT upper",
    }
    got = scan("cat", docs)  # exact substring, case-sensitive
    assert got == [ScanMatch("f2", 2, "beta cat"), ScanMatch("f2", 3, "cat")]
    # regex mode, case-insensitive via inline flag
    reg = scan(r"(?i)cat", docs, regex=True)
    assert [(m.doc_id, m.line_no) for m in reg] == [("f1", 2), ("f2", 2), ("f2", 3)]
    assert scan("zzz", docs) == []                           # miss -> []
    with pytest.raises(__import__("re").error):
        scan("(unclosed", docs, regex=True)


# -- C-LEX-5: stdlib-only, byte-stable (conflict_prone) --------------------------

def test_stdlib_only_byte_stable() -> None:
    src = (_SRC / "lexical.py").read_text()
    for banned in ("import tantivy", "import bm25s", "import rank_bm25", "import whoosh",
                   "import rapidfuzz", "import numpy", "import requests", "import httpx",
                   "subprocess", "import openai", "import anthropic",
                   "import time", "import datetime"):
        assert banned not in src, f"lexical must stay stdlib-only: {banned!r}"

    docs = {"d1": "cat cat", "d2": "cat dog"}
    assert LexicalIndex.from_documents(docs).search("cat") == \
        LexicalIndex.from_documents(docs).search("cat")


# -- joint satisfaction (5 constraints) ------------------------------------------

def test_joint_lexical() -> None:
    idx = LexicalIndex.from_documents({
        "d1": "cat cat cat",
        "d2": "cat dog",
        "d3": "cat filler filler filler filler filler",  # long -> penalized
        "d4": "dog only",
    })
    hits = idx.search("cat")
    ids = [h.doc_id for h in hits]
    assert ids[0] == "d1"          # highest tf (C-1)
    assert "d4" not in ids         # no query term -> miss (C-3)
    assert ids.index("d2") < ids.index("d3")  # shorter d2 beats long d3 (C-2)
    assert idx.search("cat") == hits                          # byte-stable (C-5)
    # scan mode over the same corpus (C-4)
    assert scan("filler", {"d3": "cat filler\nmore filler"}) == [
        ScanMatch("d3", 1, "cat filler"), ScanMatch("d3", 2, "more filler")]
