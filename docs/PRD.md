# Cairn — Product Requirements Document

**Version:** 0.1.1 · **Date:** 2026-06-27 · **Status:** Living document — engine + retrieval layer implemented; OP-31 eval phase next
**License:** MIT · Copyright (c) 2026 Leo Celis — https://leocelis.com
**Built with / verified by:** IVD — https://ivdframework.dev

**Derived from:** `cairn_system_intent.yaml` v0.2.1 · `docs/patterns/patterns_entities.yaml` · `docs/patterns/patterns_retrieval_knowledge.yaml` · `docs/research/**`

> Every pain point and every solution below cites the research that grounds it. References use the form (OP-xx / FF-xx / TH-x; DOC_NAME). The pattern IDs resolve in the two `docs/patterns/*.yaml` files; the DOC_NAMEs resolve in `docs/research/`.

---

## 1. Overview

Cairn is a deterministic, storage-agnostic retrieval engine for AI agents. It sits between an agent and the stores it already has (files, SQL, vector DB, graph DB), and answers one question well: *given a request, what is the smallest, most relevant, most trustworthy context to hand the model?*

Cairn is **not** a database, **not** an LLM ingestion pipeline, and **not** a graph query language. It is the decision + routing + assembly layer above the store: it decides whether to retrieve, resolves the entities a request refers to, traverses their relations, fuses the chosen signals, and assembles a minimal context package — with **zero generative-LLM calls on the hot path** (`zero_llm_calls_on_hot_path`, `deterministic_resolution_no_llm`).

---

## 2. Who this is for

Anyone building or operating **many agents** that must retrieve context over **large, interconnected, private corpora**. Concretely:

- **Agent developers** whose agents must reliably reference a user's real entities (accounts, projects, people, files, services) without hallucinating which one.
- **Teams running fleets of agents** over shared private data who cannot afford per-query LLM/embedding cost or non-reproducible behavior.
- **Coding agents** retrieving over a repository (symbols, files, call graphs).
- **Privacy-first / regulated operators** who cannot send their corpus to a cloud LLM to index it.
- **Anyone who refuses to adopt another database** just to give an agent memory.

The common thread: the agent's quality is bounded by the quality and trustworthiness of the context it is given (FF-1; WHEN_TO_RELY_ON_LLM_ALONE). The model is rarely the bottleneck — the context is.

---

## 3. The problem

Today's retrieval infrastructure was built for other problems and retrofitted onto agents:

- **Vector DBs** were built for semantic document search — no entity identity, no relation traversal, blind top-k.
- **Graph DBs** (Neo4j, FalkorDB, Neptune) were built for enterprise graph workloads — they give you a query language, but *someone has to write the queries*.
- **LLM-memory engines** (Graphiti/Zep, Mem0) build the memory graph with an LLM in the loop (3–6 LLM calls per episode in Graphiti; GRAPH_DATABASES_AND_ENTITY_LIBRARIES) — costly, non-deterministic, and the graph **drifts** over time.

None were designed around how an agent actually accesses context: detect entities → resolve to canonical identity → traverse relations → decide the signal → assemble the minimum. The recurring, unsolved problems live **above the store**, and they are orthogonal to which database holds the bytes (intent §rationale).

**Market reality (honest):** this space is crowded and funded — Graphiti/Zep (~27.9K stars), Mem0, MinnsDB. Cairn does not enter an empty niche; it enters with a contrarian thesis: a retrieval layer you can **trust** because it is deterministic, auditable, local-first, and storage-agnostic — the one axis the LLM-in-the-loop incumbents cannot follow without abandoning their architecture (intent §market_positioning).

Three honest caveats on "best" (intent §market_positioning.honest_caveats):

- **Conditional** — "best" is scoped to the trustworthy / local-first / auditable axis, not best-at-everything.
- **Unproven** — "best" is a thesis until the benchmark (UC-12 / OP-31) measures determinism + quality + cost against the named baselines. Until then it is a well-grounded claim, not a fact.
- **Distribution** — best-technically does not auto-win; incumbents have stars and funding. Cairn wins only if the target user's pain is genuinely trust/auditability, not speed.

---

## 4. Pain points (grounded in research)

| # | Pain | Evidence |
|---|---|---|
| P1 | Agents hallucinate or pick the **wrong entity** ("my Schwab account" → invented/stale ID) | OP-28; WORLD_MODEL_TOOL_ROUTING (Graph Explorer ACL 2026: +22.5 Hit@1 when args ⊆ visible IDs) |
| P2 | **Always-on retrieval wastes tokens/latency and can lower quality** | OP-1/OP-33; SRACG (AAAI 2026): naive always-on = −2.6 to −3.6pp vs no retrieval; Mallen 2023 ACL: retrieval misleads on popular facts |
| P3 | **Too much context degrades quality** even when retrieval is perfect | FF-11; Du 2025 (arXiv:2510.05381): 13.9–85% drop from length alone; Liu 2023: 20–30pt lost-in-the-middle |
| P4 | Vector RAG **can't connect two entities** (misses the bridging doc); grep has no relations | OP-34; GraphRAG (arXiv:2404.16130); the join-set retrieval property |
| P5 | Semantic search **fails on exact symbols / fresh / OOD tokens** | OP-30; CONTEXT_BEATS_MODEL_SEMANTIC_VS_GREP (Claude Code removed vector index — "agentic grep won by a lot") |
| P6 | LLM-built memory graphs **drift** and are **not auditable** | TH-5 (CWA); GRAPH_DATABASES (Graphiti drift critique); Graphiti 3–6 LLM calls/episode |
| P7 | Adopting a memory system means **adopting a database + migration** | storage_agnostic_core; intent §alternatives |
| P8 | Cannot index **without sending data to a cloud LLM** (privacy/regulated) | local_first_no_mandatory_cloud; Graphiti requires cloud embeddings |
| P9 | **Per-query LLM/embedding cost** does not scale across an agent fleet | zero_llm_calls_on_hot_path; CA-RAG (arXiv:2606.02581): 26% token savings at matched quality |
| P10 | The **same entity has different IDs** across tools/namespaces | OP-28 cross_system_entity_index |
| P11 | Stale facts: a **single timestamp** conflates "true then" vs "known then" | TH-3; OP-28 bi_temporal_model; VersionRAG 58→90% |
| P12 | Graph backends require the agent to **author queries** (Gremlin/Cypher), which is non-deterministic | intent §interface.design_principle_no_query_language |

---

## 5. Use cases

Each use case states the scenario, the pain today (with research), how Cairn solves it (with research + the primitive/pattern), and the requirement it generates.

> **Cairn's primitives:** **A** Adaptive Gate · **B** Entity-First Routing · **C** Signal Orchestration · **E** Context Assembler. (intent §intent)

### UC-1 — Resolve a messy human reference to the right entity
- **Scenario:** An agent receives "what's in my Schwab account?". "Schwab" must map to one stable, real entity — not an invented or stale ID.
- **Pain today (P1):** LLMs synthesize plausible-but-wrong IDs; vector RAG returns semantically *similar* docs, not the *identity* — similarity is not relevance (FF-2). (OP-28; FF-2; WORLD_MODEL)
- **Cairn solution:** Primitive **B** resolves the surface form to a canonical ID through a deterministic cascade — exact → normalized (NFKC) → fuzzy (RapidFuzz ≥0.85) → embedding → LLM only as a last-resort arbiter on the ambiguous <5% (OP-28; OP-35; TH-1). On a miss it returns **explicit "unresolved"** — never a synthesized ID (TH-5, negation-as-failure; Clark 1978).
- **Requirement:** A `resolve(query) → [{canonical_id, surface_form, confidence, tier}] + unresolved[]` API, deterministic on Tiers 1–2, zero generative-LLM on the hot path.

### UC-2 — Connect two entities (multi-hop / relational retrieval)
- **Scenario:** "How does the payment retry policy connect to the circuit breaker?" — the answer lives in a doc that bridges *both* entities.
- **Pain today (P4):** Vector top-k may never surface the bridging doc; grep has no notion of relations. (OP-34; GraphRAG)
- **Cairn solution:** Primitive **B** computes a **bounded relation closure** (BFS depth-2 default, hop-distance discount, bi-temporal filter) from the resolved entities; the **join-set** doc (in both closures) is ranked highest after fusion (OP-34; OP-32; TH-4 bounded transitive closure).
- **Requirement:** Deterministic bounded traversal from canonical IDs, storage-agnostic via `GraphAdapter`, with a flat-store fallback when no graph backend exists (OP-34).

### UC-3 — Decide whether to retrieve at all
- **Scenario:** "What is 2+2?" or a fact the model already knows — retrieval would only add cost and noise.
- **Pain today (P2):** Always-on retrieval burns tokens/latency and can *lower* accuracy. (SRACG; Mallen 2023)
- **Cairn solution:** Primitive **A** runs an LLM-free two-stage gate before any signal fires: deterministic bypass (temporal / private-entity / relational flags) → cost-function scoring (CA-RAG utility; complexity signal; entity head/tail) → may return `strategy=none`, and when it does retrieve it routes the paradigm (none | grep | semantic | graph | composite) (OP-1; OP-33; OP-25). "No retrieval" is a valid, reachable decision (`adaptive_gate_precedes_retrieval`).
- **Requirement:** A `route(query) → RoutingDecision{strategy, signals[], rationale}` gate that runs before retrieval and can choose `none`, all without a generative-LLM call.

### UC-4 — Exact symbol / keyword / fresh-corpus lookup
- **Scenario:** "Find every call to `authenticate_user` that bypasses the rate limiter."
- **Pain today (P5):** Semantic search returns similar-looking code, not the exact call site; a stale index misses fresh changes. (OP-30; CONTEXT_BEATS_MODEL)
- **Cairn solution:** Primitive **C** lexical signal — ripgrep scan (always fresh, zero index) for exact/symbol/fresh queries; BM25 index (SQLite FTS5 / Tantivy) for multi-term over a stable corpus (OP-30). The gate routes symbol/exact queries to scan first.
- **Requirement:** A `LexicalSignal` with a scan adapter (default) and an index adapter, both deterministic and zero-LLM.

### UC-5 — Assemble the smallest sufficient context
- **Scenario:** Many candidates come back; the agent needs the minimal set that answers the request, in the right order.
- **Pain today (P3):** Dumping candidates degrades quality (length alone) and inflates cost; the relevant doc buried mid-context is missed; more is not better — top-1 often beats top-5 (FF-3). (FF-11 Du 2025; FF-3; Liu 2023)
- **Cairn solution:** Primitive **E** assembler — `budget → MMR(λ) select → cosine-dedup(≥0.95) → edge-load order → emit + trace manifest`, a pure deterministic function within a token budget (OP-29; OP-15; FF-11). Edge-load ordering places rank-1 first / rank-2 last to defeat lost-in-the-middle.
- **Requirement:** A deterministic assembler producing a byte-stable `ContextPackage` within a configurable token budget, plus a trace manifest for auditability.

### UC-6 — Fuse lexical + semantic + graph signals coherently
- **Scenario:** A query needs both keyword precision and relational reach; running one signal loses recall, naive union adds noise.
- **Pain today:** Choosing a single signal is lossy; un-normalized score merging is incoherent. (OP-3; OP-32)
- **Cairn solution:** Primitive **C** fuses ranked lists with **RRF k=1** (not the TREC k=60 — short agent lists need rank to matter), equal weights by default, cosine score floor 0.6 (OP-32), within the two-stage retrieve→rerank pipeline (OP-4). Optional cross-encoder rerank stays local and deterministic.
- **Requirement:** Deterministic multi-signal fusion (RRF) producing one ranked candidate list, tie-broken by doc_id.

### UC-7 — Deterministic, reproducible, auditable retrieval
- **Scenario:** A regulated/eval-driven team needs the *same query on the same corpus* to yield the *same context*, and to explain why each item was retrieved.
- **Pain today (P6):** LLM-in-the-loop systems drift and are black boxes. (TH-5; Graphiti drift)
- **Cairn solution:** The whole hot path is deterministic (`deterministic_resolution_no_llm`); the canonical map is a **frozen closed world** built offline (CWA — representation without inference, TH-5); every package carries a **trace manifest** (OP-29). Same input → byte-identical output.
- **Requirement:** Byte-stable `retrieve()` across runs; a determinism test; a trace manifest on every package.

### UC-8 — Local-first, no cloud LLM to index
- **Scenario:** A privacy-first or regulated operator cannot send the corpus to a cloud LLM for indexing.
- **Pain today (P8):** Graphiti and peers require cloud embeddings even with a local LLM. (local_first_no_mandatory_cloud)
- **Cairn solution:** The default path is fully offline — discriminative extraction (GLiNER/ReLiK/REBEL, CPU-viable, "deterministic and fast"; ENTITY_RELATIONSHIP_RESOLUTION) at build time; zero API key required to run the quickstart (intent §success_metric ADOPTABILITY).
- **Requirement:** Default functionality with no mandatory cloud account / API key; a local-first extraction + resolution path.

### UC-9 — Route over existing stores without adopting a database
- **Scenario:** A team wants to give agents memory over data that already lives in files, SQL, a vector DB, and a graph DB — without migrating it.
- **Pain today (P7):** Memory systems make you adopt their storage and migrate. (storage_agnostic_core)
- **Cairn solution:** Cairn stores only the **map** (canonical records + relations + **references** to docs) and routes over the user's stores via adapters; it never holds the bytes (intent §build_boundary). The same public API serves an in-memory 100-entity corpus and a 100k+-entity backend (`progressive_scale_one_api`).
- **Requirement:** A storage adapter interface; the core has zero hard dependency on any specific store; references are stable + resolvable (OQ-2).

### UC-10 — Stable entity identity across tools/namespaces
- **Scenario:** The same "Acme" is `crm_id=…` in one system, a board in another, a symbol in a third.
- **Pain today (P10):** Tools become cold silos; the right tool binds the wrong namespace ID. (OP-28 cross_system_entity_index)
- **Cairn solution:** A unified entity index maps one canonical entity → {system-specific IDs}; the canonical→system binding happens at retrieval time (OP-28).
- **Requirement:** Canonical entity records carry per-system reference mappings.

### UC-11 — Point-in-time / temporally-correct retrieval
- **Scenario:** "What did we know about X on March 1?" vs "What was actually true about X on March 1?"
- **Pain today (P11):** A single timestamp conflates the two; stale facts surface. (TH-3; VersionRAG)
- **Cairn solution:** Bi-temporal entity/edge state — valid-time and transaction-time as independent axes; traversal filters edges by validity; version-sensitive facts are resolved to the as-of state (TH-3; OP-28 bi_temporal_model; OP-22 temporal RAG + conflict resolution; OP-34).
- **Requirement:** Bi-temporal fields on entities/edges; point-in-time query support (open-end sentinel pinned — OQ-4).

### UC-12 — Prove retrieval quality at lower cost
- **Scenario:** A team must justify adopting Cairn over agentic grep / vector-RAG / Graphiti / Mem0.
- **Pain today (P9):** "Better" is asserted, not measured; cost claims are made without a quality control. (OP-31)
- **Cairn solution:** A deterministic, LLM-free eval harness — nDCG@10 primary, join-set Recall@k for multi-hop, via pytrec_eval over a custom entity-centric held-out set; p50/p95/p99 latency + token cost via the model's own tokenizer; **token reduction reported only at matched quality** (OP-31).
- **Requirement:** A benchmark harness + corpus producing quality-alongside-cost numbers vs named baselines.

---

## 6. Functional requirements (by primitive)

| Area | Requirement | Source |
|---|---|---|
| **A — Gate** | `gate()` (implemented name, per OP-33) runs before any signal; can return `none`; two-stage, LLM-free, deterministic; `retrieve()` composes resolve → gate | OP-1, OP-33; `adaptive_gate_precedes_retrieval` |
| **B — Resolve** | `resolve()` deterministic cascade to canonical IDs; explicit `unresolved` on miss | OP-28, OP-35; TH-1, TH-5 |
| **B — Traverse** | Bounded relation closure (BFS depth-2 default); `GraphAdapter`; flat fallback | OP-34; TH-4 |
| **B — Ontology** | Offline alias-table authoring (discriminative default, LLM <5% tail, human gate); frozen | OP-35; TH-1 |
| **B — Ontology (invariant)** | Canonical IDs are explicit + user-owned; identity is NOT invented by free-form LLM extraction at query time | `explicit_canonical_ontology`; OP-35; TH-5 |
| **C — Lexical** | Scan + BM25 index behind one interface; shipped default is pure-Python/zero-dep (determinism control — FTS5's ranking varies by SQLite build); ripgrep / FTS5 / Tantivy are the documented opt-in acceleration ladder, same semantics | OP-30 |
| **C — Fusion** | RRF k=1, equal weights default, cosine floor 0.6, deterministic tie-break | OP-32; OP-3 |
| **E — Assemble** | budget → MMR → dedup → edge-load order → emit + trace; byte-stable | OP-29; FF-11 |
| **Eval** | nDCG@10 + join-set Recall@k via pytrec_eval; cost at matched quality | OP-31 |
| **Cross-cutting** | Storage-agnostic adapters; bi-temporal state; zero generative-LLM on hot path | constraints; TH-2, TH-3 |

---

## 7. Non-goals (out of scope)

- **Not a database / storage engine.** Cairn stores the map (references), never the bytes; no replication, no sharding (intent §risks #1, §build_boundary).
- **Not a graph query language.** The agent never writes Gremlin/Cypher/SPARQL; traversal intent compiles and delegates to the backend (intent §interface.design_principle_no_query_language).
- **Not an LLM ingestion pipeline.** No generative LLM on the hot path; the LLM is the offline, human-gated <5% tail of extraction (OP-35; intent §inversions).
- **Not an extractor.** Cairn orchestrates GLiNER/ReLiK/REBEL — it does not reimplement NER/RE.
- **Not a reasoning engine.** Cairn assembles trustworthy context; the agent does the reasoning over it.

### 7.1 When Cairn is not the right choice (intent §market_positioning.not_best_for)

Cairn is deliberately not best-at-everything. Pick something else when:

- **You want the richest possible graph regardless of drift.** An LLM-in-the-loop builder (Graphiti/Zep) will extract more, denser relations — at the cost of determinism and auditability. If drift is acceptable and richness is the goal, that trade favors them.
- **Your need is pure document semantic search** with no entity or relational structure. A vector DB alone is simpler and sufficient; Cairn's entity-first machinery adds no value without entities and relations to route over.

---

## 8. Success metrics

From `cairn_system_intent.yaml` §success_metric, made measurable by UC-12 (OP-31):

- **Correctness:** answer quality ≥ strong baselines (agentic grep, vector-RAG) at materially lower token + latency cost, on a held-out entity-centric benchmark.
- **Determinism:** same query + same corpus → byte-identical `ContextPackage`.
- **Hot-path purity:** default `retrieve()` issues zero generative-LLM / network calls (mocked client receives zero calls).
- **Portability:** core runs against ≥2 storage backends with only an adapter change.
- **Scale:** one public API serves a 100-entity in-memory corpus and a 100k+-entity backend.
- **Adoptability:** clone → install → quickstart with no cloud account and no API key on the default path.

---

## 9. Open questions (block tech spec)

Carried from `cairn_system_intent.yaml` §open_questions (status as of 2026-07-12):

- **OQ-1** Where relations live (own map vs external graph) + scale cutoff. *Partially resolved:* cross-system index delivered (M2.4); relations-storage scale cutoff still open.
- **OQ-2** doc_id stability/resolvability contract per storage adapter. *Open.*
- **OQ-3** Traversal-intent → backend query-language compilation. ✅ *Resolved for openCypher* (M2.3, `compile_traversal`); Gremlin/SPARQL later.
- **OQ-4** Bi-temporal open-end sentinel. ✅ *Resolved* (M2.1): `None` == open end (+∞), half-open `[start, end)`, single `_within` predicate.

---

## 10. References

- **Intent:** `cairn_system_intent.yaml` v0.2.1
- **Patterns:** `docs/patterns/patterns_entities.yaml` (TH-1..5, OP-28/34/35) · `docs/patterns/patterns_retrieval_knowledge.yaml` (FF-1..11, OP-1..33, CF-1..3)
- **Research:** `docs/research/foundations/` (5 theory docs) · `docs/research/context/` · `docs/research/tools/` · `docs/research/databases/`
- **External anchors:** SRACG (AAAI 2026); Mallen 2023 (ACL); Du 2025 (arXiv:2510.05381); Liu 2023 (arXiv:2307.03172); GraphRAG (arXiv:2404.16130); CA-RAG (arXiv:2606.02581); Graphiti/Zep (arXiv:2501.13956).
