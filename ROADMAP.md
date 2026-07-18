# Cairn — Roadmap

**Version:** 0.1.0 · **Date:** 2026-06-27 · **Status:** Living document
**Derived from:** `cairn_system_intent.yaml` v0.2.1 · `docs/PRD.md` · `docs/patterns/*.yaml`

> Legend: ✅ done · 🚧 in progress · ⏳ planned · 💡 exploratory
> Status legend is kept honest: a ✅ means implemented, tested, and gated locally (make check).

---

## Guiding principles

1. **Entities first.** The entity / world-model engine (`cairn-engine`) is the foundational subsystem and ships before the retrieval layer.
2. **Determinism is the product.** Zero generative-LLM on the hot path; the frozen alias table is the determinism boundary. (`deterministic_resolution_no_llm`, `zero_llm_calls_on_hot_path`)
3. **Storage-agnostic.** Cairn stores the *map* (references), never the bytes; all storage behind adapters. (`storage_agnostic_core`)
4. **Staggered publication.** Stabilize + publish `cairn-engine` first (real users, semver, docs); keep `cairn-retrieval` at 0.x until proven — this gives clean package boundaries without paying "two stable products at once."
5. **Prove, don't assert.** "Best" is a thesis until the benchmark (OP-31) measures it against real baselines.
6. **Validate against a real corpus.** Each milestone is exercised on a real use case, not a toy — first target: the **WordPress entity graph** (see M1.6).

---

## Package strategy (monorepo, uv workspace)

| Package | Scope | First release |
|---------|-------|---------------|
| **`cairn-engine`** | Entity engine: model · resolution · ontology authoring · traversal · adapters | `0.1.0` — the current focus |
| **`cairn-retrieval`** | Retrieval layer: gate · lexical/semantic/graph signals · fusion · assembler | after `cairn-engine` is stable |

---

## Phases & milestones

### Phase 0 — Scaffold ✅
- ✅ Monorepo (uv workspace), two packages, MIT, CI-ready layout
- ✅ Charter (`cairn_system_intent.yaml` v0.2.1), research corpus, patterns, PRD
- ✅ Dev environment: `.venv` (py3.11, gitignored) + `requirements-dev.txt` (pytest/ruff/mypy); editable installs
- ✅ Test layout (OSS canon): `tests/unit/` (constraint tests per module intent) + `tests/integration/` (cross-module e2e) + `examples/` (runnable demos)

---

### Phase 1 — `cairn-engine` 0.1: the entity engine ✅ **(COMPLETE — engine + real-corpus use case)**

The deterministic, in-memory, local-first entity engine. Delivers PRD use cases **UC-1, UC-9, UC-10** and the foundation for UC-2/UC-11.

**Status (2026-07-12):** M1.1–M1.6 ✅ done — full OP-28 cascade (exact→normalized→fuzzy→semantic→llm, last two opt-in via caller callables), bounded bitemporal traversal, build-time authoring + 3-tier dedup + Union-Find merge (whole-class forwarding), JSON serialization, conflict-audit gate, and the real-corpus WordPress use case. **60 tests at Phase-1 close (whole monorepo suite now 114), ruff + mypy strict clean, zero runtime deps, byte-stable.** Passed a fresh-eyes review (F1–F19 all closed). Runnable examples incl. a full e2e walkthrough, the agent-integration pattern, a deterministic graph visualizer, and the M1.6 internal-link deliverable — validated on the author's real 14-post blog corpus (gitignored; bring your own via `wordpress_corpus_prep.py`).

| Milestone | Deliverable | Patterns | UC |
|-----------|-------------|----------|----|
| **M1.1 Entity model** ✅ | Immutable `Entity` value record (canonical_id, aliases, entity_type, valid_from, refs, relations); ECS/value-object, not OOP. Frozen dataclasses, hashable. | TH-2, TH-5, OP-35 | UC-1 |
| **M1.2 Resolution** ✅ | **Full OP-28 cascade implemented** — Tier 1a exact → 1b normalized (NFKC) → **Tier 2** fuzzy (pure-stdlib **token-sort** ratio ≥0.85 — token-set rejected: subset containment scores 1.0, caught by constraint test; entropy gate 1.5) → **Tier 3** semantic (opt-in: precomputed `EmbeddingIndex` + caller-supplied `EmbedderFn`; ≥0.85 accepts at tier `embedding`; aliases embedded once at build, hot path embeds only the mention) → **Tier 4** LLM arbiter (opt-in `ArbiterFn`: fires only on 2+ candidate ambiguity or scores in [0.70, 0.85); picks among presented candidates, **never mints an ID**; abstain → unresolved). Explicit `unresolved` on miss (NAF). Gazetteer scan for free text (longest-match-first). Default path: zero LLM, zero network, zero deps, byte-stable — unchanged by the opt-in tiers. Intents: `entity_resolution_intent.yaml` v0.1.3 + `entity_semantic_intent.yaml` (split per IVD Rule 6, 7-constraint budget). | OP-28, TH-1, TH-5 | UC-1 |
| **M1.3 Alias table + authoring** ✅ | In-memory `AliasTableAdapter` (build → freeze → read-only, `merged_from` forwarding). Authoring: `author_from_text` staging `Candidate(pending_review)` — human gate mandatory; `extractor="heuristic"` (stdlib, deterministic, recall-oriented) built in; **GLiNER/LLM enter as caller-supplied CALLABLES** (strings like `"llm"` raise — cairn never auto-imports or calls APIs, even at build time). Three-tier dedup: exact/normalized → MinHash/LSH (fixed blake2b salts, 32 perms, 8 bands) + token-sort ≥0.85 → **[0.70, 0.85) flagged for review, never auto-merged**. `with_mirror_edges` (the M1.4 finding — traversal now symmetric). Serialization: **deterministic JSON** (stdlib; YAML = future opt-in extra — zero-dep invariant beats format preference). Module intent: `packages/cairn-engine/intents/ontology_authoring_intent.yaml`. | OP-35, TH-1, OP-28 | UC-1, UC-8 |
| **M1.4 Bounded traversal** ✅ | Core-owned BFS (adapters serve 1-hop edges only — storage-agnostic split); depth-2 default, hard max 3; hop-distance discount 1/(1+hop); bitemporal edge filter on **explicit** `as_of` only (no wall-clock reads — determinism); flat depth-0 fallback with `traversal_mode` tag; closed world (unknown seed → empty, dangling targets skipped). Module intent: `packages/cairn-engine/intents/entity_traversal_intent.yaml`. AUTHORING RULE for M1.3 (found via the demo): emit MIRROR edges (concept→post `mentioned_in`) or next-reads are asymmetric (OP-28 reversal-curse mitigation). | OP-34, TH-4, TH-3 | UC-2 |
| **M1.5 Determinism gate** ✅ | `make check` = ruff + mypy strict + full constraint suite (byte-stability + sockets-disabled tests included); `.github/workflows/ci.yml` runs it on 3.11/3.12/3.13 + demo byte-stability diff. OSS canon shipped: public API (35 curated exports as of Phase 3), `py.typed` (PEP 561), Union-Find merge with transitive whole-class forwarding (surfaces + refs + relations — verified by a resolve→traverse regression test), `from_entities` builders, CONTRIBUTING, CHANGELOG, Makefile. | `deterministic_resolution_no_llm` | UC-7 |
| **M1.6 First use case: the WordPress entity graph** ✅ | Proven end-to-end on the real 14-post blog (`examples/wordpress_m16_links.py`). Human-approved concept ontology (OP-35 gate) → scan each post body (TF per concept + post-title citations) → freeze to a SQLite `.db` (dogfoods M2.2) → TF-IDF cosine link ranking (`cairn-retrieval`). Emits both surfaces: **(a) mid-content** — a concept mention links to the authority post that covers it most; **(b) next reads** — direct citations (strongest) + TF-IDF-ranked siblings, one primary next step (no CTA wall). Cairn emits recommendations with provenance; WordPress renders them. Corpus stays gitignored — never enters the repo. | OP-34, OP-35 | UC-2 |
| **→ Release `cairn-engine` 0.1.0** ⏳ | Publish to PyPI; README, quickstart, semver | — | — |

**Resolves open questions:** OQ-2 (doc_id stability contract), OQ-4 (bi-temporal open-end sentinel — schema decision).

---

### Phase 2 — `cairn-engine` 0.2+: richer entity engine ✅ **(COMPLETE — M2.1–M2.4)**

| Milestone | Deliverable | Patterns | UC |
|-----------|-------------|----------|----|
| **M2.1 Bi-temporal state** ✅ | Second time axis added: **transaction-time** (`known_from`/`known_until`) on `Entity` AND `Relation`, independent of the existing valid-time (`valid_from`/`valid_until`). `as_at(facts, *, valid_as_of, known_as_of)` = point-in-time slice over both axes (four-column half-open predicate); `supersede(history, new, *, at)` = **append-only** correction (closes the current version's transaction-time, appends the new one — old records never mutated or dropped, full audit chain reconstructable). `traverse` gained `known_as_of` so edges filter on both axes. **Resolves OQ-4**: `None` == open end (+∞); one `_within` predicate is the single sentinel rule. Transaction-time is caller-explicit — **zero wall-clock reads** (byte-stable; static-guarded). Intent `entity_bitemporal_intent.yaml`; 6 tests incl. joint; example `bitemporal_audit.py`. | TH-3, OP-22, OP-28 | UC-11 |
| **M2.2 SQLite adapter** ✅ | `SqliteAliasTable` — the second live backend, **proving `storage_agnostic_core`**. Same Protocol, byte-identical behavior to in-memory (folding reused from `adapters._build`, extracted so there is ONE Union-Find algorithm, N backends). Frozen closed world persists in a `.db`; reads served by SQL (a large corpus need not sit in RAM); `open(path)` reopens read-only across processes. Stdlib `sqlite3` — zero new deps. Intent `sqlite_adapter_intent.yaml`; **differential test** asserts equality vs in-memory; example `two_backends_identical.py`. Delivers success-metric **PORTABILITY (≥2 backends)**. | OP-35 | UC-9 |
| **M2.3 Graph backend adapter** ✅ | The bounded-traversal INTENT compiles to **one** deterministic openCypher query executed on an external graph DB (Neo4j / FalkorDB / Neptune openCypher). `compile_traversal(seed, *, depth, as_of, known_as_of)` → `CypherQuery(text, params)` (pure, byte-stable; variable-length bounded path, both-axis bitemporal edge filter, shortest-hop, refs via OPTIONAL MATCH; depth inlined as a literal, user strings always `$params` — injection-safe). `traverse_cypher(seed, *, run, ...)` executes via a **caller-supplied `run(query, params)` callable** and maps rows → the SAME `TraversalResult` as in-memory `traverse` (differential test asserts equality). **Resolves OQ-3 for openCypher.** cairn core imports **no DB driver** (`storage_agnostic_core`, static-guarded) — the driver is the caller's. Intent `graph_backend_intent.yaml`; 6 tests incl. joint; example `graph_backend_cypher.py`. | OP-34, `design_principle_no_query_language` | UC-2 |
| **M2.4 Cross-system entity index** ✅ | `CrossSystemIndex` — one canonical entity ↔ its many system-specific IDs (`{crm: cus_42, slack: C0299, github: acme-inc}`), bidirectional. `bind(cid, system=…)` gives the single id for a tool arg (None if absent, ValueError if ambiguous); `canonical_for(system=…, external_id=…)` is the reverse, keyed by (system, id) so the same string in two systems never collides; `external_ids`/`systems` enumerate. Forward is one-to-many (a TH-1 merge can leave two ids in a system); **reverse is one-to-one, enforced at freeze** (two canonicals claiming one id → error). Closed world (TH-5): every miss is `()`/`None` — an id is **never synthesized** (the hallucinated-binding failure cairn removes). Build→freeze→read-only, stdlib-only. Intent `cross_system_index_intent.yaml`; 6 tests incl. joint; example `cross_system_binding.py`. | OP-28, TH-1, TH-5 | UC-10 |

**Resolves open questions:** OQ-1 (where relations live + scale cutoff — cross-system index side delivered in M2.4; scale-cutoff for relations storage still open), OQ-3 ✅ (traversal → backend-query compilation — done for openCypher in M2.3; Gremlin/SPARQL later).

**Second real corpus:** a narrative / game-lore corpus — characters / worlds / events + story timeline (stresses bi-temporal + causal traversal).

---

### Phase 3 — `cairn-retrieval` 0.1: the retrieval layer ✅ **(FEATURE-COMPLETE — M3.0–M3.7; release pending Leo's go)**

Built on top of `cairn-engine`. Delivers UC-3, UC-4, UC-5, UC-6.

| Milestone | Deliverable | Patterns | UC |
|-----------|-------------|----------|----|
| **M3.1 Adaptive gate** ✅ | `gate(query, *, entities, private_ids, tail_ids, config)` → `RoutingDecision(strategy ∈ none\|grep\|semantic\|graph\|composite, stage, reason, complexity, freshness_required, scores)`. **Stage 1** deterministic bypass (temporal/version markers → freshness+retrieve; ≥2 entities or relational cue → composite; private entity → graph). **Stage 2** CA-RAG utility argmax (`w_Q·quality_prior + c·gain − w_L·latency − w_C·token`, OP-33 defaults in `GateConfig`, calibratable). **`strategy=none` reachable** (popular query → skip; the same entity in `tail_ids` flips to a retrieve tier). `complexity()` = CA-RAG formula. **Zero generative-LLM / embedding / clock** — deciding whether to call an LLM never calls one (static-guarded, byte-stable). Intent `adaptive_gate_intent.yaml`; 6 tests incl. joint; example `adaptive_gate_demo.py`. | OP-1, OP-33, OP-25 | UC-3 |
| **M3.2 Lexical signal** ✅ | Two modes, one module, pure-Python + deterministic (OP-30). **INDEX** — `LexicalIndex.from_documents(...).search(query, top_k)` → BM25 (k1=1.2, b=0.75, non-negative Lucene idf), sorted (score desc, doc_id asc). **SCAN** — `scan(query, docs, regex=…)` → exact/regex match positions over live input, no index, unranked. Closed world (no match → `[]`). **Shipping default is zero-dep pure-Python** — FTS5's BM25/tokenizer vary by SQLite build (a determinism risk), so ripgrep / SQLite-FTS5 / Tantivy / bm25s are the documented **opt-in acceleration ladder** (same semantics), never the default path; no subprocess, no auto-detected accelerator (static-guarded). Intent `lexical_signal_intent.yaml`; 6 tests incl. joint; example `lexical_signal_demo.py`. | OP-30 | UC-4 |
| **M3.3 Semantic signal (opt)** ✅ | `SemanticIndex.from_documents(docs, *, embedder).search(query, *, embedder, top_k, floor)` → cosine-ranked `SemanticHit`s (score desc, doc_id asc), floor-filtered, closed-world `[]`. **Opt-in via the caller's `cairn.EmbedderFn`** — cairn imports no model SDK and makes no network call (static-guarded). Doc vectors embedded once at build; the hot path embeds **only the query** (reuses `cairn.cosine`). Explicit dimension guard raises on a build/search embedder mismatch (IVD Rule 5: `cairn.cosine` returns 0.0 on mismatch, so the index checks itself). Intent `semantic_signal_intent.yaml`; 6 tests incl. joint; example `semantic_signal_demo.py` (ships a toy embedder). | OP-3 | — |
| **M3.4 Fusion** ✅ | `fuse(signals, *, k=1, top_k, weights)` → `FusedHit(doc_id, score, contributions)`. Reciprocal Rank Fusion: `score(d) = Σ_signals weight·1/(k + rank₀)`; a doc absent from a signal contributes 0. **Rank-only — no score normalization** (BM25 & cosine scales never compared; the keystone, static-guarded). k=1 default (short agent lists: rank-1→1.0, rank-2→0.5; k configurable). Deduped by doc_id, sorted (score desc, doc_id asc), per-signal audit breakdown. Optional per-signal weights. Intent `fusion_intent.yaml`; 6 tests incl. joint; example `fusion_demo.py`. | OP-32, OP-4 | UC-6 |
| **M3.0 Concept-weighted link ranking** ✅ | **cairn-retrieval's first real module.** TF-IDF cosine over shared concepts: IDF (rarity, from document-frequency) zeroes ubiquitous concepts; TF (centrality) comes from `Relation.weight` = mention count (added to the entity model as a structural build-time fact — round-trips in JSON, preserved on mirrors, ignored by `traverse`). `score = cosine(tfidf(A), tfidf(B))` in [0,1]. Scoring lives here, NOT in the engine's `traverse()` — boundary preserved. Intent: `link_ranking_intent.yaml` v0.2.0. 6 tests (IDF golden, TF-direction cosine 0.8, closed-world, joint), example on the real 14-post corpus. | OP-32 | UC-2, UC-6 |
| **M3.5 Context assembler** ✅ | `assemble(candidates, *, budget, lam=0.5, dedup_threshold=0.95)` → `AssembledContext(chunks, text, manifest, total_tokens)`. Pure pipeline (OP-29, FF-11 — fewest chunks wins): **budget** greedy-pack → **MMR** `argmax λ·rel − (1−λ)·max cos-to-selected` (diverse beats near-dup) → **dedup** hard gate (cos ≥ 0.95 dropped) → **fold-order** (rank-1 first, rank-2 last, weakest middle — lost-in-the-middle) → **emit** provenance-tagged text + `ManifestEntry(doc_id, tokens, rel, mmr_score, position)`. **Zero-LLM, never re-embeds** (precomputed `Candidate.embedding` only; no embedder param), byte-stable. Intent `assembler_intent.yaml`; 6 tests incl. joint; example `assembler_demo.py`. | OP-29, OP-15, FF-11 | UC-5 |
| **M3.6 `retrieve()` end-to-end** ✅ | `RetrievalEngine(table, corpus, graph?, lexical?, semantic?, embedder?, …).retrieve(query, *, budget)` → `RetrievalResult(decision, context, fused, entities)`. Ties the whole layer: **resolve** (cairn tier-1) → **gate** (`strategy='none'` short-circuits with **no** signal/embed/LLM) → **orchestrate** per strategy (grep→lexical, semantic→semantic, graph→traverse from resolved entities, composite→all *available*) → **fuse** (RRF) → **assemble** (fused → `Candidate`s, rel = normalized fused score → budgeted package). **Hot-path purity proven**: embedder invoked only on the semantic branch (0 calls on skip/lexical/graph routes), zero LLM, byte-stable. Optional signals skipped gracefully; closed-world (no corpus content → doc skipped). Intent `retrieve_e2e_intent.yaml`; 6 tests incl. joint; flagship example `retrieve_end_to_end.py`. | all | — |
| **M3.7 Connection suggestion** ✅ | `suggest_connections(candidate, existing, *, top_k=5, seeds=(), graph_weight=0.25)` → `list[ConnectionSuggestion(target_id, score, content_score, structural_score, shared, via)]`. **Cold-start link prediction**: rank the existing entities a NEW candidate node (a table/module about to be created) should connect to. A brand-new node has no edges → structural indices (CN/AA/RA) are 0 → **content leads**: TF-IDF cosine over shared concepts using corpus IDF (candidate-vs-corpus generalisation of M3.0 `rank_links`, reusing `concept_idf`). Optional **Resource-Allocation** structural term (`1/deg` over `seeds ∩ Γ(y)`) fires **only** when seeds are given — absent seeds it is exactly 0 (never faked). Provenance (`shared` concepts, `via` seeds) + closed-world (novel/empty → `[]`). Scoring stays in retrieval, not the engine. Research `LINK_PREDICTION_AND_CONNECTION_SUGGESTION_RESEARCH_2026.md`; intent `connection_suggestion_intent.yaml`; 6 tests incl. joint; example `schema_connection_suggestion.py`. | OP-36, OP-33 | UC-2 |
| **→ Release `cairn-engine` + `cairn-retrieval` 0.1.0** ✅ | Published (2026-07-18): [`cairn-engine`](https://pypi.org/project/cairn-engine/0.1.0/) and [`cairn-retrieval`](https://pypi.org/project/cairn-retrieval/0.1.0/) live on PyPI; repo public at [github.com/leocelis/cairn](https://github.com/leocelis/cairn), tag `v0.1.0`. | — | — |

---

### Phase 4 — Evaluation & proof ⏳

| Milestone | Deliverable | Patterns | UC |
|-----------|-------------|----------|----|
| **M4.1 Eval harness** ⏳ | pytrec_eval; nDCG@10 + join-set Recall@k; deterministic, LLM-free scoring | OP-31 | UC-12 |
| **M4.2 Held-out corpus** ⏳ | Entity-centric, MuSiQue-style multi-hop; graded 0–3; human-verified gold | OP-31 | UC-12 |
| **M4.3 Benchmark vs baselines** ⏳ | Quality + p50/p95/p99 latency + token cost vs agentic-grep, vector-RAG, Graphiti, Mem0 — quality reported alongside cost | OP-31 | UC-12 |

**This is where "best" becomes a fact, not a thesis** (intent §market_positioning.honest_caveats).

---

### Phase 5 — Hardening & ecosystem 💡

- 💡 More storage adapters (Neo4j, FalkorDB, Neptune, pgvector) via the adapter protocols
- 💡 Optional cross-encoder reranker tier (local, deterministic)
- 💡 Docs site, quickstart cookbook, example corpora
- 💡 Community: contribution guide, issue templates, adapter-authoring guide

---

## Out of scope (permanent — from the charter)

Cairn will **not** become: a database / storage engine · a graph query language · an LLM ingestion pipeline · an extractor (it orchestrates GLiNER/ReLiK/REBEL) · a reasoning engine. Crossing the `build_boundary` collapses the thesis into "yet another database." See `cairn_system_intent.yaml` §risks, §build_boundary.

## When Cairn is not the right choice

- You want the richest possible graph regardless of drift → an LLM-in-the-loop builder wins.
- Pure document semantic search with no entity/relational structure → a vector DB alone suffices.
