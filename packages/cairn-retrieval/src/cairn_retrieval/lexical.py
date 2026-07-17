"""Lexical retrieval signal (M3.2, OP-30) — two modes, pure-Python, deterministic.

Two ways to hit text lexically, one module:

  INDEX  LexicalIndex — BM25-ranked ('which docs are most about these terms?').
         Build -> freeze -> search. k1=1.2, b=0.75, non-negative Lucene idf.
  SCAN   scan() — exact/regex match positions ('where does this token appear?'),
         over the live input, no index, always fresh, unranked.

Both are zero-LLM, offline, byte-stable, and STDLIB-ONLY. OP-30 names ripgrep /
SQLite-FTS5 / Tantivy / bm25s as engines; those are external / compile-time
optional / added deps, so they are the opt-in ACCELERATION ladder (faster
drop-ins with the same semantics), never the default path — the shipping default
keeps cairn's zero-dep + determinism invariants. These feed RRF fusion (M3.4).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Mapping

__all__ = ["LexicalHit", "LexicalIndex", "ScanMatch", "scan"]

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens — deterministic, no stemming/stopwords."""
    return _TOKEN_RE.findall(text.lower())


@dataclass(frozen=True, slots=True)
class LexicalHit:
    """One BM25-ranked document."""

    doc_id: str
    score: float


@dataclass(frozen=True, slots=True)
class ScanMatch:
    """One line where the query matched (scan mode — no ranking)."""

    doc_id: str
    line_no: int  # 1-based
    line: str


class LexicalIndex:
    """Pure-Python BM25 index. Build -> freeze -> search (read-only)."""

    def __init__(self, *, k1: float = 1.2, b: float = 0.75) -> None:
        self._k1 = k1
        self._b = b
        self._frozen = False
        self._docs: dict[str, list[str]] = {}
        self._postings: dict[str, dict[str, int]] = {}  # term -> {doc_id: tf}
        self._dl: dict[str, int] = {}
        self._avgdl = 0.0
        self._n = 0

    @classmethod
    def from_documents(
        cls, documents: Mapping[str, str], *, k1: float = 1.2, b: float = 0.75
    ) -> "LexicalIndex":
        index = cls(k1=k1, b=b)
        for doc_id, text in documents.items():
            index.add(doc_id, text)
        return index.freeze()

    def add(self, doc_id: str, text: str) -> None:
        if self._frozen:
            raise RuntimeError("lexical index is frozen — build-time mutations only")
        if doc_id in self._docs:
            raise ValueError(f"duplicate doc_id: {doc_id}")
        self._docs[doc_id] = _tokenize(text)

    def freeze(self) -> "LexicalIndex":
        for doc_id, tokens in self._docs.items():
            self._dl[doc_id] = len(tokens)
            tf: dict[str, int] = {}
            for tok in tokens:
                tf[tok] = tf.get(tok, 0) + 1
            for term, count in tf.items():
                self._postings.setdefault(term, {})[doc_id] = count
        self._n = len(self._docs)
        self._avgdl = (sum(self._dl.values()) / self._n) if self._n else 0.0
        self._frozen = True
        return self

    def _idf(self, term: str) -> float:
        """Lucene BM25 idf — always >= 0 (classic Robertson idf can go negative)."""
        df = len(self._postings.get(term, {}))
        return math.log(1 + (self._n - df + 0.5) / (df + 0.5))

    def search(self, query: str, *, top_k: int = 10) -> list[LexicalHit]:
        """BM25 top_k, sorted (score desc, doc_id asc). Empty on no term match."""
        if not self._frozen:
            raise RuntimeError("lexical index must be frozen before search")
        scores: dict[str, float] = {}
        for term in set(_tokenize(query)):
            postings = self._postings.get(term)
            if not postings:
                continue
            idf = self._idf(term)
            for doc_id, tf in postings.items():
                norm = 1 - self._b + self._b * self._dl[doc_id] / self._avgdl
                contrib = idf * tf * (self._k1 + 1) / (tf + self._k1 * norm)
                scores[doc_id] = scores.get(doc_id, 0.0) + contrib
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return [LexicalHit(doc_id, score) for doc_id, score in ranked[:top_k]]


def scan(query: str, documents: Mapping[str, str], *, regex: bool = False) -> list[ScanMatch]:
    """Exact-substring (or regex) line matches over live documents — fresh, unranked.

    Returns ScanMatch(doc_id, line_no, line) in (doc_id, line_no) order. No index
    is built (always current). Invalid regex raises re.error. Empty on no match.
    """
    pattern = re.compile(query) if regex else None
    matches: list[ScanMatch] = []
    for doc_id in sorted(documents):
        for line_no, line in enumerate(documents[doc_id].splitlines(), start=1):
            hit = pattern.search(line) is not None if pattern else query in line
            if hit:
                matches.append(ScanMatch(doc_id, line_no, line))
    return matches
