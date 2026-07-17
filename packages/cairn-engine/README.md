# cairn-engine

**The deterministic entity / world-model engine for AI agents.** (The brand is
**Cairn**; the distribution is `cairn-engine` and the import package is
`cairn_engine`.)

Resolve messy human references to stable canonical IDs, traverse their relations
bi-temporally, and author the frozen alias table that makes it all reproducible —
storage-agnostic, local-first, **zero generative-LLM and zero network on the
default path**, **zero runtime dependencies** (pure stdlib).

`cairn-engine` is the foundational entity subsystem. The agent-retrieval layer
(gate, signals, fusion, assembler) lives in the separate
[`cairn-retrieval`](https://github.com/leocelis/cairn/tree/main/packages/cairn-retrieval)
package, which depends on this one.

> **Status:** feature-complete, pre-release (0.1.0) — full resolution cascade,
> bounded bi-temporal traversal, ontology authoring + 3-tier dedup, SQLite and
> openCypher adapters, and a cross-system entity index. 120 tests, ruff + mypy
> strict, byte-stable. The retrieval-quality benchmark (OP-31) is the next phase;
> until then, treat determinism/portability as proven and quality as unclaimed.
> See the [roadmap](https://github.com/leocelis/cairn/blob/main/ROADMAP.md).

## Install

```bash
pip install cairn-engine
```

## Quickstart

```python
from cairn_engine import (
    Entity, InMemoryAliasTable, InMemoryGraph, Ref, Relation, resolve, traverse,
)

entities = [
    Entity("account::schwab_main", "Schwab", "config", aliases=("my Schwab account",),
           refs=(Ref(doc_id="doc::accounts"),)),
    Entity("doc::payment_retry_policy", "Payment Retry Policy", "document",
           refs=(Ref(doc_id="doc::retry"),),
           relations=(Relation("references", "account::schwab_main"),)),
]

table = InMemoryAliasTable.from_entities(entities)     # build -> freeze -> read-only
graph = InMemoryGraph.from_entities(table.canonical_entities())

resolved, unresolved = resolve("does the payment retry policy touch my Schwab account?",
                               table=table)
# both entities found by gazetteer scan; unresolved == []  (a miss is never a made-up ID)

result = traverse(resolved[0].canonical_id, graph=graph, depth=2)
# connected DocumentRefs, hop-scored 1/(1+hop), byte-stable
```

The resolution cascade: **exact → normalized (NFKC) → fuzzy (token-sort ≥ 0.85,
entropy-gated) → semantic (opt-in: your embedder) → LLM arbiter (opt-in: your
callable; picks among presented candidates in the 0.70–0.85 band — never mints an
ID)**. Misses come back in `unresolved` — never a synthesized ID (closed world).

Build-time authoring (offline, human-gated): `author_from_text` →
`dedup_candidates` (exact → MinHash/LSH → review band, never auto-merged) → your
approval → `freeze()`. Optional extractors (GLiNER / LLM) enter as callables you
supply — the engine never imports third-party packages or calls APIs.

Also here: bi-temporal state (`as_at`, `supersede`), a cross-system entity index
(`CrossSystemIndex`), a SQLite alias-table backend, and an openCypher compiler
(`compile_traversal` / `traverse_cypher`) that runs the same bounded traversal on
Neo4j / FalkorDB — the engine imports no DB driver; you pass the connection.

## Design foundations

Grounded in five CS theories (canonicalization over equivalence classes, labeled
property graphs, the bi-temporal model, bounded transitive closure, and the
closed-world assumption) — see
[`docs/patterns/`](https://github.com/leocelis/cairn/tree/main/docs/patterns) and
[`docs/research/foundations/`](https://github.com/leocelis/cairn/tree/main/docs/research/foundations).
Every module is developed intent-first ([IVD](https://ivdframework.dev)):
constraints in `intents/` map 1:1 to tests with hand-computed golden fixtures.

## License

MIT — Copyright (c) 2026 Leo Celis
