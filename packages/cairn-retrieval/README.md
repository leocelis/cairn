# cairn-retrieval

**The agent-retrieval layer on top of the [`cairn-engine`](https://github.com/leocelis/cairn/tree/main/packages/cairn-engine) entity engine.**

The three retrieval primitives above the entity map — all deterministic, all
generative-LLM-free on the default path:

- **A · Adaptive gate** (`gate`) — two-stage, LLM-free decision *before* any
  signal runs: deterministic bypass (temporal markers, multi-entity relational,
  private entities) then a CA-RAG utility cost function. `strategy=none` (skip
  retrieval) is a first-class, reachable outcome — selective retrieval beats
  always-on empirically.
- **C · Signal orchestration** — `LexicalIndex` (pure-Python BM25) + `scan`
  (exact/regex), opt-in `SemanticIndex` (caller-supplied embedder; no model SDK
  imported), graph traversal via `cairn-engine`; ranked lists merged with `fuse`
  (Reciprocal Rank Fusion, k=1, rank-only — no score normalization).
- **E · Context assembler** (`assemble`) — budget → MMR select → cosine dedup →
  fold ordering (strongest evidence at the edges) → provenance-tagged emit with
  a trace manifest. Never re-embeds; zero LLM.

`RetrievalEngine.retrieve(query, *, budget)` ties them end-to-end:
resolve → gate → orchestrate → fuse → assemble. A query the gate routes to
`none` returns no context at all — the skip is the point.

Also here: `rank_links` — TF-IDF-cosine document↔document link recommendation
over shared canonical concepts — and `suggest_connections` — cold-start link
prediction: rank the existing entities a NEW candidate node should connect to
(content-first, seed-optional structural signal, full provenance).

> Status: **feature-complete, 0.x.** Stays 0.x until the benchmark phase
> (OP-31 eval vs. agentic-grep / vector-RAG / Graphiti) proves the quality
> claims. Depends only on `cairn-engine` (which is itself zero-dependency). See
> the [roadmap](https://github.com/leocelis/cairn/blob/main/ROADMAP.md) and
> [`intents/`](https://github.com/leocelis/cairn/tree/main/packages/cairn-retrieval/intents)
> for the constraint-tested design of each module.

## Install

```bash
pip install cairn-retrieval   # pulls cairn-engine automatically
```

## License

MIT — Copyright (c) 2026 Leo Celis
