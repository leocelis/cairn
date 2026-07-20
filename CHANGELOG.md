# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) ·
Versioning: [SemVer](https://semver.org/) per package.

## [Unreleased]

### Repo hygiene (2026-07-19)

- Removed `examples/graph.svg` from the repo. It was a generated demo artifact
  that had been committed by mistake (its `.gitignore` entry carried an inline
  comment, which `.gitignore` does not support, so the rule silently never
  matched). Fixed the rule (comment on its own line) and verified `git
  check-ignore` now catches the file, so regenerating it locally no longer
  re-commits it.
- Purged the file from all git history (`git filter-repo`), then force-pushed
  `main` and re-pointed the `v0.1.0` tag to the rewritten commit. The content
  was non-secret (rendered demo labels), but the whole history was scrubbed for
  cleanliness, consistent with the sibling projects. All commit SHAs prior to
  this changed as a result.

### Legal hardening (2026-07-19)

- **Expanded `LEGAL.md`** from a claims-scope note to a full author-protection
  document: added trademark reservation, an explicit patent position (MIT is
  silent on patents; deliberate and family-consistent, with Apache-2.0 named as
  the upgrade path and patent-litigation termination), a Your Responsibilities /
  Acceptable Use section (legal compliance, your-data, not-for-high-risk-use),
  No Professional Relationship, Indemnification, an explicit Limitation of
  Liability (with a nominal cap), and Governing Law (Florida / Broward County,
  matching the IVD/Horizon/EIF family). Data-transmission/processor sections were
  intentionally omitted since Cairn has no hosted service and processes no data
  for the author.
- **Added `TERMS_OF_SERVICE.md`**: the acceptance vehicle ("by using, you agree")
  that makes acceptable-use and indemnification enforceable, scoped honestly to a
  downloadable library (no account, no server). Mirrors the family ToS and
  cross-references LEGAL.md to avoid drift.
- **`CONTRIBUTING.md`**: added a Developer Certificate of Origin (DCO 1.1)
  sign-off requirement (`git commit -s`), protecting the project from
  contributions the submitter had no right to make.
- **`README.md`**: Legal section now points to both LEGAL.md and TERMS_OF_SERVICE.md.
- Rationale: the MIT warranty disclaimer + liability limitation already shield
  the author from a user who has issues with the software; these additions close
  the patent, trademark, acceptable-use, and indemnification gaps and bring
  Cairn to parity with the sibling projects. Not legal advice; author should have
  counsel confirm before relying on any clause.

## [0.1.0] — 2026-07-18

First public release. `cairn-engine` and `cairn-retrieval` published to PyPI;
repository public at [github.com/leocelis/cairn](https://github.com/leocelis/cairn).
Everything below was developed pre-release and ships as of this version.

### OSS-readiness audit pass (2026-07-15)

**Changed**
- Research-corpus scrub: replaced remaining project-specific illustration
  identifiers in `docs/research/` with generic domain equivalents
  (entity-type examples now `Ticket`/`Account`/`Invoice`; the multi-agent
  context pattern is now named `ScopedContextPackage` here and in
  `docs/patterns/patterns_retrieval_knowledge.yaml`). Illustrative examples
  only — no code, tests, or public behavior changed.
- Repository initialized as a git repo (first commit); publish gates
  (leak grep, docs canon, build + `twine check`, synthetic-benchmark check,
  full test suite) re-verified green at commit time.

**Removed**
- OS junk file (`.DS_Store`); already gitignored.

### `cairn-retrieval` — M3.7 connection suggestion (cold-start link prediction, 2026-07-14)

**Added**
- `suggest_connections(candidate, existing, *, top_k=5, doc_type='document',
  concept_type='concept', seeds=(), graph_weight=0.25)` → `list[ConnectionSuggestion]`
  (OP-36). Given a **candidate node not yet in the graph** (a table/module about to
  be created), rank the existing entities it should connect to. A brand-new node
  has no edges, so every structural index (Common Neighbors / Adamic-Adar /
  Resource Allocation) is 0 — the **cold-start** regime, where **content
  similarity leads**: TF-IDF cosine over shared concepts using corpus IDF (reuses
  `concept_idf` — the candidate-vs-corpus generalisation of M3.0 `rank_links`).
- Optional **Resource-Allocation** structural term (`1/deg` over `seeds ∩ Γ(y)`,
  Adamic-Adar the documented alternative) that fires **only** when the caller
  supplies `seeds` (entities the candidate provisionally relates to). Without
  seeds it is exactly 0 — the API never manufactures structural evidence a cold
  node cannot have. Fused content-dominant (`graph_weight=0.25`).
- `ConnectionSuggestion(target_id, score, content_score, structural_score, shared,
  via)` — **provenance**: `shared` = the concept ids that earned the content
  score, `via` = the seed ids that earned the structural score. Closed world: a
  novel-only or empty candidate, and any score-0 suggestion, return nothing — no
  fabricated connection. Deterministic (total desc, target_id asc), stdlib-only.
- Research foundation `docs/research/foundations/LINK_PREDICTION_AND_CONNECTION_SUGGESTION_RESEARCH_2026.md`
  (Lü & Zhou link-prediction survey; cold-start content-similarity literature;
  Rahm & Bernstein schema matching). Intent `connection_suggestion_intent.yaml`
  (4 constraints, critical-last, joint test). 6 tests incl. joint; example
  `examples/schema_connection_suggestion.py` (a new `news` table correctly maps to
  `article` > `comment`, drops the ubiquitous `id` column). Full suite 120 green;
  mypy clean. Ranking stays in retrieval, not the engine (OP-34 boundary honored).

### `cairn-engine` (entity engine) — 0.1.0 in progress

**Added**
- Immutable entity data model: `Entity`, `Ref`, `Relation`, `ResolvedEntity`
  (frozen dataclasses, hashable; ECS/value-record discipline).
- Deterministic resolution (`resolve`): gazetteer scan (longest-match-first) +
  cascade exact → normalized (NFKC/casefold/collapse) → fuzzy (pure-stdlib
  token-sort ratio ≥ 0.85, Shannon-entropy gate 1.5). Closed world: misses are
  explicit `unresolved`, never synthesized IDs.
- Bounded traversal (`traverse`): core-owned BFS, depth 2 default (max 3),
  hop-distance discount 1/(1+hop), bitemporal edge filter on explicit `as_of`
  only (half-open intervals), flat depth-0 fallback.
- Build-time authoring (`author_from_text`): stdlib heuristic extractor with a
  fixed stopword filter; third-party/LLM extractors enter as caller-supplied
  callables only. Output staged `pending_review` — human gate mandatory.
- Three-tier dedup (`dedup_candidates`): exact/normalized → MinHash/LSH (fixed
  blake2b salts) + token-sort confirm; the [0.70, 0.85) band is flagged for
  human review, never auto-merged.
- Mirror edges (`with_mirror_edges`): reverse predicates so traversal is
  symmetric (mentions → mentioned_in).
- Tier-4 LLM arbiter (opt-in): `ResolverConfig.arbiter` takes a caller-supplied
  `ArbiterFn`; consulted only on 2+ candidate ambiguity or fuzzy scores in
  [0.70, 0.85). Constrained choice — picks among presented candidates, never
  mints an ID; abstain → unresolved. Default path unchanged (zero LLM).
- Tier-3 semantic resolution (opt-in): `EmbeddingIndex.build()` embeds every
  alias once offline (caller-supplied `EmbedderFn` — local model or API, the
  caller's boundary); the hot path embeds only the mention. cosine ≥ 0.85
  resolves at tier `embedding`; the [0.70, 0.85) band hands off to the Tier-4
  arbiter; closed world preserved (index built from the frozen table). This
  completes the full OP-28 cascade: exact → normalized → fuzzy → semantic → LLM.
- `cosine()` utility (stdlib) exported.
- Adapters: `AliasTableAdapter` / `GraphAdapter` protocols; in-memory
  implementations with build→freeze→read-only lifecycle and Union-Find merge
  (whole-class forwarding, transitive, audit-preserving).
- Deterministic JSON serialization (`dump_entities` / `load_entities`).
- Typed package (`py.typed`), mypy strict, ruff, CI workflow, WordPress demo
  (`examples/blog_graph_demo.py`) and corpus prep tool.

**Design decisions of record** (full detail in `packages/cairn-engine/intents/`)
- Token-SORT (not token-set) fuzzy ratio — set semantics score 1.0 on subset
  containment, letting short aliases dominate.
- No auto-detected accelerators — output must not depend on what happens to be
  installed.
- JSON (stdlib) over YAML for 0.1 serialization — the zero-dependency core
  invariant beats format preference; YAML later as an opt-in extra.

**Fixed** (fresh-eyes review, 2026-07-11 — F1–F19)
- **F1 (severe):** Union-Find merge now forwards REFERENCES, not just surfaces —
  at freeze, the representative absorbs merged members' refs and all relation
  targets are rewritten through find() (self-loops dropped). `canonical_entities()`
  exposes the folded world; build the graph from it so resolve() → traverse()
  stays coherent after merges. New end-to-end regression test.
- **F2/F3:** Tier-4 gate narrowed to OP-28 canon — band-only ([0.70, 0.85)),
  2+ distinct candidates, pooled across fuzzy + semantic (new
  `EmbeddingIndex.scored()`), semantic always runs before arbitration; exact-tier
  ambiguity is never arbitrated (all candidates returned, unconditionally).
- **F4:** removed dead optional extras (rapidfuzz/gliner/sentence-transformers) —
  nothing consumed them; opt-in tiers take caller callables.
- **F5:** package README rewritten (was: "stubs" + a TypeError-raising example);
  stale roadmap line fixed.
- **F6:** metadata is validated JSON-native at dump (loud TypeError instead of
  silent tuple→list corruption); fidelity now tested on contents.
- **F7:** `has_id` (resolvable representatives only) vs `has_record` (audit)
  pinned on the AliasTableAdapter Protocol.
- **F8:** adapter Protocols fully typed (no more `tuple[object, ...]`/casts);
  semantic misconfiguration raises TypeError (asserts are compiled out by -O).
- **F9:** long capitalized runs chunk into ≤5-token candidates — no tokens dropped.
- **F10:** new tests: positive fuzzy-band arbitration (full pool asserted),
  exact-0.85 cosine boundary, partial-overlap scan policy, dynamic-import ban.
- **F11:** existing-table duplicates carry an `existing_table` sentinel as `kept`.
- **F12:** `Entity.metadata` wrapped read-only (MappingProxyType) — frozen means frozen.
- **F15/F16:** classifiers 3.11–3.13; dev dependency groups aligned.
- **F19:** `find_alias_conflicts()` — the OP-35 conflict-audit CI gate.
- Deferred with a note: char-offset spans for scan anchors (F13 → M1.6),
  entity_type vocabulary deliberately unenforced (F17, documented in model).

### `cairn-engine` — additional

**Added**
- `Relation.weight` (default 1.0) — structural edge weight (e.g. mention count /
  term frequency). Round-trips in JSON, preserved on mirror edges, ignored by
  `traverse` (structural hop-distance only). Enables TF-IDF ranking downstream.
- `SqliteAliasTable` — a second live `AliasTableAdapter` backed by stdlib
  `sqlite3`, **proving `storage_agnostic_core`**: byte-identical behavior to the
  in-memory adapter (a differential test asserts it), the frozen closed world
  persists in a `.db` and reopens read-only across processes, and reads are
  served by SQL so a large corpus need not fit in RAM. Zero new dependencies.
- `adapters._build` — the Union-Find fold + index logic, extracted and shared by
  both adapters so a merge behaves identically regardless of backend.

**Changed**
- In-memory adapter's `freeze()` now delegates folding/indexing to
  `adapters._build` (behavior unchanged; the 55-test suite confirms).
- Heuristic extractor hardened (Rule-5, from the real 14-post blog authoring):
  the fixed stopword list is now a full standard English function-word set
  (catches sentence-start noise like "Every/Because/After/Someone/Just" while
  keeping every domain word — cloud/api/roi/cursor all survive), and clause
  punctuation now breaks capitalized runs ("Cloud, API and ROI" → three
  candidates, not one). Still fixed + deterministic; golden fixtures updated.

### `cairn-engine` — M2.1 bi-temporal state (TH-3)

**Added**
- Transaction-time axis: `known_from` / `known_until` on `Entity` and `Relation`
  (default `None`), independent of the existing valid-time `valid_from` /
  `valid_until`. Both axes round-trip byte-identically through JSON.
- `as_at(facts, *, valid_as_of=None, known_as_of=None)` — point-in-time slice
  over BOTH axes with the four-column half-open predicate. `None` on an axis
  disables that axis, so it answers correctness ("what was TRUE at T") and audit
  ("what did the system KNOW at T") from the same store.
- `supersede(history, new_fact, *, at)` — **append-only** correction: closes the
  current version's transaction-time at `at` and appends the new version; prior
  records are never mutated (frozen) or dropped, so the full history stays
  reconstructable with `as_at`.
- `traverse(...)` gained `known_as_of` — edges now filter on both bi-temporal
  axes; `_edge_valid` delegates to the shared `_within` predicate.

**Design decisions of record** (`intents/entity_bitemporal_intent.yaml`)
- **Resolves OQ-4:** `None` is the open-end sentinel (== +∞); every interval is
  half-open `[start, end)`. A single `_within` function is the one place this
  rule lives (traverse imports it) — no ambiguous `T < end` comparisons.
- Transaction-time is a **caller-supplied explicit instant**; cairn never reads
  the wall clock (no `now()`/`today()`). A naive bitemporal DB auto-stamps
  `now()` at ingestion — that would break byte-stability and the determinism
  invariant, so it is prohibited and statically guarded in tests.
- Naming: `known_from`/`known_until` (plain-English audit phrasing) maps to
  Snodgrass/SQL:2011 transaction-time and Graphiti `t_created`/`t_expired`.

### `cairn-engine` — M2.3 graph-backend adapter (openCypher, OQ-3)

**Added**
- `compile_traversal(canonical_id, *, depth=2, as_of=None, known_as_of=None)`
  → `CypherQuery(text, params)`: the bounded-closure INTENT compiled to one
  deterministic openCypher query (variable-length bounded path, both-axis
  bitemporal edge filter emitted per supplied axis, shortest-hop per node, refs
  via OPTIONAL MATCH). Pure and byte-stable.
- `traverse_cypher(canonical_id, *, run, ...)` → `TraversalResult`: executes the
  compiled query through a **caller-supplied `run(query, params)` callable** and
  maps rows to the SAME hits/scores/order as in-memory `traverse` (a differential
  test asserts equality). `CypherRunFn` type + `CypherQuery` exported.

**Design decisions of record** (`intents/graph_backend_intent.yaml`)
- **Resolves OQ-3 for openCypher.** Neo4j / FalkorDB / Neptune-openCypher run the
  query; Gremlin/SPARQL compilation is a later milestone.
- **`storage_agnostic_core` (SACRED) kept:** cairn imports **no DB driver**. The
  driver enters only as the caller's `run` callable — the same boundary as
  `EmbedderFn`/`ArbiterFn`. Statically guarded (a test scans every core source
  file for driver imports). The agent still never writes Cypher
  (`design_principle_no_query_language`) — cairn generates it.
- `depth` is validated 0..3 and inlined as a literal (openCypher forbids
  parametrized variable-length bounds); every user string is a `$param` —
  injection-safe.

### `cairn-engine` — M2.4 cross-system entity index (TH-1 / TH-5) — Phase 2 complete

**Added**
- `CrossSystemIndex` — one canonical entity ↔ its many system-specific IDs,
  bidirectional and deterministic (build → freeze → read-only, like the alias
  table). `bind(cid, system=…)` returns the single id for a tool arg (None if
  absent, ValueError if ambiguous); `canonical_for(system=…, external_id=…)` is
  the reverse; `external_ids` / `systems` enumerate. Builds from explicit triples
  (`from_entries`) or from `Entity.metadata["system_ids"]` (`from_entities`,
  accepting a scalar id or a list).

**Design decisions of record** (`intents/cross_system_index_intent.yaml`)
- Reverse index is keyed by **(system, external_id)** — the same id string in two
  systems does not collide.
- Reverse is **one-to-one, enforced at freeze**: two distinct canonicals claiming
  one (system, id) raise (TH-1 — they are the same entity, should be merged).
  Forward is one-to-many (a merge can leave one canonical with two ids in a
  system); `bind` surfaces that as an explicit ambiguity rather than hiding it.
- **Closed world (TH-5):** every miss returns `()`/`None` — an external id is
  **never synthesized**. This is the hallucinated-binding failure cairn exists to
  remove; the anti-pattern (slugifying a label into a fake id) is guarded.

This completes **Phase 2** (M2.1 bi-temporal · M2.2 SQLite · M2.3 openCypher
backend · M2.4 cross-system index).

### PyPI packaging + rename for publication (2026-07-12)

The distribution `cairn` was already taken on PyPI (an unrelated 2019 project),
so the packages were renamed. **The brand stays "Cairn"** — only the
distribution and import identifiers changed.

**Changed**
- **Renamed** the engine: distribution `cairn` → **`cairn-engine`**, import
  package `cairn` → **`cairn_engine`** (directory `packages/cairn/` →
  `packages/cairn-engine/`, `src/cairn/` → `src/cairn_engine/`). The retrieval
  distribution stays `cairn-retrieval` (import `cairn_retrieval`). All imports,
  tests, examples, docs, Makefile, CI, and the uv workspace updated; 114 tests
  green, both packages `python -m build` + `twine check` PASS.
- `cairn-retrieval` now pins its dependency: `cairn-engine ~= 0.1.0` (was a bare
  `cairn`, which resolved to the unrelated PyPI package).
- Both packages: version → `0.1.0`, `Development Status :: 3 - Alpha` (honest —
  feature-complete but pre-benchmark, no external users), `Typing :: Typed`
  classifier, `license-files = ["LICENSE"]` (MIT text now ships inside each
  wheel/sdist), and `[project.urls]` with Homepage/Source/Issues.
- Package READMEs (the PyPI long-descriptions) rewritten with the new names,
  `pip install` lines, and **absolute** GitHub links (relative `../` links 404
  on PyPI).

**Publication plan of record:** ship `cairn-engine` first; hold `cairn-retrieval`
until the OP-31 benchmark (staggered publication, per the charter). Rehearse on
TestPyPI before the real upload. Nothing has been pushed to PyPI or GitHub.

### README house-style alignment + OSS canon (2026-07-12)

**Added**
- `SECURITY.md` — responsible-disclosure policy (GitHub Security Advisories +
  email), matching the sibling projects; scope notes flag the three real review
  surfaces (JSON deserialization, openCypher compilation, caller callables).
- `LEGAL.md` — a deliberately minimal "what Cairn is/is not", IP, inherent
  limitations, and **claims-scope** section: research figures are third-party and
  "best" is explicitly not claimed until the OP-31 benchmark. No hosted-service or
  data-processing sections (neither applies to a local, offline library).

**Changed**
- Root README aligned to the IVD / Horizon house style: CI/tests + Python +
  zero-deps badges; a linked research citation; an honest **"What's proven — and
  what's not"** status table (determinism/purity/zero-dep/portability
  test-enforced ✅, retrieval quality ❌ pending benchmark, scale ⚠️); "Design
  invariants (each test-enforced)"; and **Community** + **Legal** sections.

### Publication-readiness pass (2026-07-12)

**Changed**
- READMEs rewritten to current status: root README now documents the
  feature-complete state with a verified quickstart (both code snippets execute
  as written), the real public API, and the honest pre-benchmark caveat;
  `cairn-retrieval`'s README no longer calls itself a placeholder. CONTRIBUTING
  opening updated to match.
- WordPress examples are now bring-your-own-corpus: they read the generic
  `corpus/blog/posts.json` path and exit gracefully with instructions when it is
  absent (`corpus/` is gitignored — user content never ships). Verified: the
  full test suite and all self-contained examples pass on a simulated clean
  clone with no corpus present.
- Research notes and the architecture diagram scrubbed of deployment-specific
  environment details; example ontologies trimmed to generic concepts.
- `examples/graph.svg` (generated from the local corpus by
  `graph_visualize.py`) removed from the tree and gitignored.

### Benchmarks — entity-resolution grounding (2026-07-12)

**Added**
- `benchmarks/` — reproducible, honestly-scored evidence. First entry,
  `benchmarks/entity_resolution/` (harness + report): measures whether feeding a
  consumer Cairn's deterministic resolution raises the rate of producing the
  correct stored canonical id vs. deriving it (`slugify`). **Deterministic,
  byte-stable, zero-dep, zero-key: correct-id accuracy 59% → 100% (all 9 errors
  eliminated)** on a 22-item public synthetic dataset (fictional companies/people;
  no private data). Optional `--llm` mode confirms with a model in the loop
  (single run, gpt-4o-mini: 54% → 90%, honestly not 100% — the model sometimes
  ignores the handed candidate). Controls (clean ids, tickers) tie, proving the
  benchmark isn't rigged; the gain is concentrated where a resolver is required
  (legacy/irregular ids, accents/punctuation, hallucinated ids). README "what's
  proven" table + `benchmarks/README.md` link to it.

### Spec/roadmap audit sync (2026-07-12)

**Removed**
- `cairn-retrieval` optional extras `lexical = ["ripgrepy"]` and
  `rerank = ["sentence-transformers"]` — declared but consumed by no code
  (truth-in-packaging: an extra that changes nothing misleads users). They will
  be re-declared when the accelerator drop-ins actually land.

**Fixed (documentation drift found by the roadmap + tech-spec audits; no code defects)**
- ROADMAP: export count 27 → 35; `entity_resolution_intent` v0.1.2 → v0.1.3;
  M3.0 "5 tests" → 6; Phase-1 test count clarified (60 at phase close, suite now 114).
- Charter (`cairn_system_intent.yaml`): all 7 constraint `test:` paths pointed at
  never-authored "tech-spec phase" files — repointed to the real passing tests;
  the 5 constraints still `ASSUMED` flipped to `KNOWN` (each now validated by an
  executing test). Interface tools section records the implemented names of
  record: `route()` → `cairn_retrieval.gate()` (OP-33's own term; entities
  pre-resolved by design, composition lives in `retrieve()`), `ContextPackage`
  → `RetrievalResult`.
- PRD: Gate row uses the implemented `gate()` name; Lexical row reflects the
  shipped pure-Python default with ripgrep/FTS5/Tantivy as the opt-in ladder;
  §9 open questions annotated with resolution status (OQ-3 ✅ openCypher,
  OQ-4 ✅, OQ-1 partial).

### `cairn-retrieval` — 0.0.x (first real module)

**Added**
- `gate` (M3.1) — the two-stage, LLM-free adaptive retrieval gate (OP-33).
  Stage 1 is a deterministic bypass (temporal/version markers → freshness +
  retrieve; ≥2 entities or a relational cue → `composite`; a private entity →
  `graph`). Stage 2 is the CA-RAG utility cost function
  (`w_Q·quality_prior + c·complexity_gain − w_L·latency − w_C·token`, argmax over
  the tiers, cheapest wins ties). Returns `RoutingDecision(strategy, stage,
  reason, complexity, freshness_required, scores)`. `strategy=none` (skip
  retrieval) is a first-class outcome — a popular-entity query resolves to `none`;
  the same entity in `tail_ids` flips to a retrieve tier. `complexity()`,
  `GateConfig` (OP-33 defaults, calibratable), `DEFAULT_GATE` exported.
  **Zero generative-LLM / embedding / wall-clock** — deciding whether to call an
  LLM never calls one (static-guarded, byte-stable). Entities are pre-resolved
  canonical_ids; `private_ids`/`tail_ids` are authoring-time popularity labels.
- `RetrievalEngine.retrieve` (M3.6) — the end-to-end entry point tying the whole
  layer together: **resolve → gate → orchestrate signals → fuse → assemble** →
  `RetrievalResult(decision, context, fused, entities)`. The gate's
  `strategy='none'` short-circuits with no signal, no embed, no LLM; otherwise
  the strategy selects which of lexical / semantic / graph run (only those the
  engine was given), RRF fuses their ranked lists, and the assembler packs a
  budgeted, provenance-tagged package. **Hot-path purity**: the embedder is
  invoked only on the semantic branch (zero calls on skip / lexical / graph
  routes), zero generative-LLM anywhere, byte-stable. `DocMeta` carries the
  precomputed corpus content/tokens/embedding. This is the integration proof of
  the whole cairn + cairn-retrieval thesis: entities in, minimal context out,
  deterministic and LLM-free on the default path.
- `assemble` (M3.5, OP-29 / FF-11) — the context assembler: a pure pipeline
  building the smallest sufficient package. budget (greedy pack) → MMR select
  (`λ·rel − (1−λ)·max cos-to-selected`, diversity beats near-dups) → dedup hard
  gate (cosine ≥ 0.95 dropped) → fold ordering (strongest evidence at the edges,
  lost-in-the-middle) → emit provenance-tagged text + a trace `ManifestEntry`
  (doc_id, tokens, rel, mmr_score, position). `Candidate`/`ManifestEntry`/
  `AssembledContext` exported. **Zero-LLM, never re-embeds** — MMR/dedup run on
  precomputed `Candidate.embedding` via `cairn.cosine`; no embedder parameter
  exists. Byte-stable (static-guarded).
- `fuse` (M3.4, OP-32) — Reciprocal Rank Fusion of the signals' ranked lists.
  `fuse(signals, *, k=1, top_k, weights)` → `FusedHit(doc_id, score,
  contributions)` where `score(d) = Σ_signals weight·1/(k + rank₀)`. Combines by
  RANK, never by raw score — BM25 and cosine scales are never compared (no
  normalization; the keystone, static-guarded). k=1 default (short agent lists;
  configurable). Deduped, sorted (score desc, doc_id asc), with a per-signal
  audit breakdown; optional per-signal weights.
- `SemanticIndex` (M3.3, OP-3) — the opt-in dense/semantic retrieval signal.
  `from_documents(docs, *, embedder).search(query, *, embedder, top_k, floor)`
  ranks documents by `cairn.cosine(query_vec, doc_vec)`, sorted (score desc,
  doc_id asc), floor-filtered, closed-world `[]`. The embedder is the caller's
  `cairn.EmbedderFn` — cairn imports **no model SDK and makes no network call**
  (static-guarded). Doc vectors are embedded once at build; the hot path embeds
  only the query. An explicit dimension guard raises on a build/search embedder
  mismatch (IVD Rule 5 — `cairn.cosine` returns 0.0 on mismatch, a silent
  mis-score, so the index checks itself).
- `LexicalIndex` + `scan` (M3.2, OP-30) — the lexical signal, two modes,
  pure-Python and deterministic. `LexicalIndex.from_documents(...).search(query,
  top_k)` is BM25 (k1=1.2, b=0.75) with a non-negative Lucene idf, sorted (score
  desc, doc_id asc), closed-world (`[]` on no match). `scan(query, docs,
  regex=…)` returns exact/regex line matches over the live input (no index,
  always fresh, unranked). **Zero-dep, no subprocess, no auto-detected
  accelerator** — the shipping default keeps determinism control; ripgrep /
  SQLite-FTS5 / Tantivy / bm25s are the opt-in acceleration ladder with the same
  semantics (static-guarded against accidental default-path imports).
- `link_ranking` — concept-weighted document↔document link recommendation.
  `concept_idf()` (IDF = log(N/df); a concept in every doc → 0), `tfidf_vectors()`,
  and `rank_links()` scoring by **TF-IDF cosine similarity** in [0,1] — the
  canonical content-based related-documents measure. Pure graph structure
  (no bodies, no model, no network), deterministic. Ranking lives here, not in
  the entity engine's `traverse()` — the engine/retrieval boundary is explicit.
- Still placeholder: adaptive gate, signal orchestration, context assembler (Phase 3).

### M1.6 — real-corpus use case (Phase 1 complete)

**Added**
- `examples/wordpress_m16_links.py` — the end-to-end deliverable over the 14
  real blog posts. Runs the whole engine against a human-approved concept
  ontology (OP-35 gate): scan each post body (TF per concept + post-title
  citations) → freeze to a SQLite `.db` (dogfoods M2.2) → TF-IDF cosine link
  ranking (`cairn-retrieval`). Emits, per post, mid-content anchors (a concept
  mention → the authority post that covers it most) and next reads (direct
  citations + TF-IDF-ranked siblings). Corpus stays gitignored — never enters
  the repo.
- This closes **Phase 1**: the entity engine plus a proven real-world use case.
