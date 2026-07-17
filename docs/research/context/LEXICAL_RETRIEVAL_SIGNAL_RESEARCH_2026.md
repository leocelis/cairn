# Lexical Retrieval Signal — Research (2026)

**For:** Cairn (agent-native retrieval engine) — primitive **C (Signal Orchestration)**, the **lexical signal** (grep/keyword) adapter.
**Gap closed:** prior corpus said "grep wins for exact-symbol/keyword/fresh/OOD queries" but never named the concrete engine to build on.
**Invariants honored:** zero LLM on hot path · deterministic · storage-agnostic · local-first/offline · permissive OSS license.
**Date:** 2026-06-26 · **Confidence:** ✓ verified · ~ inferred · ? assumed

All candidates below clear zero-LLM and offline trivially (none calls a model). The differentiators are **ranking, persistence, freshness, license, Python API**.

---

## 1. Candidate matrix

| Candidate | Embedded/Local | Index vs Scan | Deterministic rank | Persistence | License | Speed | Freshness (reindex on change?) |
|---|---|---|---|---|---|---|---|
| **ripgrep** | ✓ subprocess | scan (no index) | n/a (match order, no ranking) | none | MIT / Unlicense | 8–13× GNU grep ✓ | always fresh, never reindex ✓ |
| **bm25s** | ✓ embedded (pip) | index (Scipy sparse) | ✓ BM25 (fixed k1/b) | ✓ save/load disk | MIT | up to 500× rank_bm25 ✓ | full rebuild on change |
| **rank_bm25** | ✓ pure Python | index (in-memory) | ✓ BM25 | ✗ none | Apache-2.0 ~ | slow (baseline) | rebuild each run |
| **Tantivy / tantivy-py** | ✓ embedded (Rust+pyo3) | index (Lucene-like, mmap) | ✓ BM25 | ✓ on-disk segments | MIT | very fast (Rust) ~ | incremental ✓ |
| **SQLite FTS5** | ✓ embedded (stdlib `sqlite3`) | index (in DB file) | ✓ BM25 (k1=1.2, b=0.75) | ✓ in `.db` | Public Domain ✓ | incremental (triggers/rebuild) |
| **DuckDB FTS** | ✓ embedded | index (in DB) | ✓ Okapi BM25 (k=1.2, b=0.75) | ✓ in `.db` | MIT ~ | manual reindex (`overwrite:=1`), no auto-update |
| **Whoosh / whoosh-reloaded** | ✓ pure Python | index | ✓ BM25F | ✓ on-disk | BSD-2 | — | **effectively dead** ✗ |

---

## 2. Buildable recommendation — two-mode adapter

Ship **two adapters** behind one `LexicalSignal` interface, mapping the scan-vs-index split onto the invariants.

### DEFAULT (scan mode): ripgrep subprocess
- The only candidate that is **always fresh with zero index** — no build step, no staleness, no persistence to manage. Directly satisfies the existing finding "grep wins for exact-symbol/keyword/fresh/OOD."
- Deterministic by construction (no scoring float math; stable match positions). MIT/Unlicense = maximally permissive. Matches how coding agents already work.
- Implementation: shell out to the `rg` binary (detect on PATH; the `ripgrep` PyPI wheel only vendors the binary). **Avoid Python regex-engine bindings** — the value is the Rust engine + parallel walker.

### OPTIONAL (index mode, BM25 ranking)
- **SQLite FTS5 — default index adapter.** Public-domain (zero attribution burden), **zero added dependency** (ships in CPython `sqlite3`; FTS5 is a compile-time option present in modern builds), deterministic BM25 (k1=1.2, b=0.75), persistence = the `.db` file, one portable file (storage-agnostic-friendly). Best invariant fit for a dependency-light local-first index. **Feature-detect FTS5 at startup; fall back to ripgrep-only if absent.**
- **Tantivy / tantivy-py — fast/large-corpus optional.** MIT, Rust-fast, true **incremental indexing** (no full reindex), mmap segments. Cost: compiled Rust dependency (wheels for common platforms; else source build). Use when corpus is large or churns frequently.
- **bm25s — no-DB pure-Python/Numpy ranker.** MIT, save/load, up to 500× rank_bm25. Use when you want BM25 without a DB file or Rust toolchain. Weakness: eager sparse-matrix precompute → poor freshness (rebuild on corpus change).

### Reject
- **rank_bm25** — slowest, no persistence; bm25s dominates it. Keep only as a dependency-free reference.
- **Whoosh** — original unmaintained; `whoosh-reloaded` fork inactive (no PyPI release 12+ months). Don't build a default on it.
- **DuckDB FTS** — viable, MIT, but redundant with SQLite FTS5 for this role and a heavier dep; pick only if Cairn already embeds DuckDB (e.g. as the graph backend via DuckPGQ). No auto-update.

---

## 3. The grep-vs-BM25 boundary (feeds the gate's signal selection)

**Raw scan (ripgrep)** when:
- Query is an **exact symbol, identifier, error string, path, or regex** — answer is set membership, not a ranking.
- Corpus is **fresh/changing constantly** — index staleness is a correctness risk; scan is always current.
- **OOD / rare tokens** where IDF/term-stats are meaningless or misleading.
- You need **zero setup / no persisted index**.

**BM25 index** when:
- Query is **multi-term, natural-language-ish** ("how does retry backoff work") needing relevance ranking across many partial matches where TF/IDF actually discriminates.
- Corpus is **large and relatively stable**, so amortizing the index build pays off.
- You need **top-k ordered** results to feed Cairn's fusion stage.

**Rule:** *grep answers "where does this token appear?"; BM25 answers "which documents are most about these terms?"* Run scan first for exact/symbol queries (cheap, fresh); fall to BM25 for fuzzy multi-term over a stable corpus. The fusion layer (RRF) can merge both lexical sub-signals before adding semantic/graph.

---

## 4. Tech-spec constraints this produces (for Cairn module intent)

1. `LexicalSignal` is one interface with two adapters: `ScanAdapter` (ripgrep) and `IndexAdapter` (FTS5 default / Tantivy / bm25s).
2. Default path = scan (ripgrep) — always fresh, no index lifecycle.
3. Index adapters must expose a deterministic BM25 top-k (fixed k1/b; deterministic tie-break).
4. FTS5 availability is feature-detected; absence → graceful fallback to scan-only.
5. No bundled mandatory dependency under a non-permissive license (excludes SSPL/BSL backends from the lexical layer).

---

## 5. Sources

- ✓ ripgrep — MIT/Unlicense; 8–13× GNU grep; Rust regex + parallel walker, no index: [BurntSushi/ripgrep](https://github.com/BurntSushi/ripgrep), [benchmark](https://burntsushi.net/ripgrep/).
- ✓ bm25s — MIT, save/load, Numpy/Scipy core, up to 500× rank_bm25: [xhluca/bm25s](https://github.com/xhluca/bm25s), [arXiv:2407.03618](https://arxiv.org/abs/2407.03618).
- ✓ SQLite FTS5 — built-in BM25 (k1=1.2, b=0.75), embedded, in-DB persistence; SQLite public domain: [sqlite.org/fts5.html](https://sqlite.org/fts5.html).
- ✓ tantivy-py — MIT, 0.26.0 (Apr 2026), binary wheels; Tantivy Lucene-like BM25, incremental, mmap: [quickwit-oss/tantivy-py](https://github.com/quickwit-oss/tantivy-py), [tantivy](https://github.com/quickwit-oss/tantivy).
- ✓ DuckDB FTS — `create_fts_index` / `match_bm25` (k=1.2, b=0.75), Snowball stemmer, no auto-update: [DuckDB FTS docs](https://duckdb.org/docs/stable/core_extensions/full_text_search).
- ✓ Whoosh dead / whoosh-reloaded inactive: [Sygil-Dev/whoosh-reloaded](https://github.com/Sygil-Dev/whoosh-reloaded).
- ~ rank_bm25 Apache-2.0 / pure-Python / no persistence — verify license at source before relying.
- ~ DuckDB FTS license MIT (extension within MIT DuckDB) — verify if decision-critical.
- ~ bm25s determinism — BM25 is deterministic; confirm no random tie-break in top-k.
- ? FTS5 compiled into the user's CPython `sqlite3` — default in modern builds but compile-time; feature-detect at startup.
