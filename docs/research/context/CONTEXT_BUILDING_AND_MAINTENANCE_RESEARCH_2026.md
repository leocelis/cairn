# Context Building & Maintenance for Agents — Master Research (2026)

> **Status:** Living document — **v1.5 FINAL (research + corpus)** (2026-06-25)
> **Scope:** How to build, retrieve, maintain, and compound context so **models + tools + memory** work as one system.
> **Method:** Full review of existing agent `context/` corpus + fresh pass on official docs (Anthropic, OpenAI, LangChain, MCP), community/engineering posts, and peer-reviewed papers (2023–2026).
> **Sourcing rule:** Every load-bearing claim has a verified source (paper arXiv ID, official doc URL, or named production system). Findings marked `~` are practitioner consensus without controlled benchmarks.

---

## Executive summary

**Context is the glue layer.** The model supplies reasoning; tools supply actions and fresh data; embeddings/RAG supply external knowledge; session memory supplies continuity. None of these work without **intent-aware curation** — the smallest high-signal token set per step.

**Proven (high confidence):**
1. **Adaptive retrieval beats always-on RAG** — retrieve when tail/fresh/private/high-stakes; skip when head knowledge + reasoning-only (Self-RAG, Adaptive-RAG, FLARE; Mallen 2023).
2. **Retrieval quality > retrieval presence** — wrong/similar-but-irrelevant chunks hurt (−5% to −15%); task-needed context helps (+6% to +27%) (CodeRAG-Bench, SRACG, Oracle-SWE).
3. **Context rot is universal** — all 18 frontier models tested degrade as input grows; bigger windows ≠ free lunch (Chroma 2025; Liu 2023 lost-in-the-middle).
4. **Memory hierarchy** — working (context window) + episodic/semantic (external store) + procedural (skills/intents); treat window as RAM (Packer 2023; Mem0 2025; hierarchical memory theory arXiv:2603.21564).
5. **Write / Select / Compress / Isolate** — industry-converged operator framework (Anthropic Sep 2025; LangChain 2025; Claude Code arXiv:2604.14228).
6. **Hybrid retrieval + bounded rerank** — BM25 + dense + RRF, then cross-encoder on top-k≤20 (BEIR; production RAG playbooks 2025–2026).
7. **Intent/goal gates everything** — what to retrieve, how much to keep, and when to compact depend on task type, stakes, and freshness requirements.

**Contested / context-dependent:**
- Semantic index vs agentic grep as default (Cursor vs Claude Code — opposite production choices; both valid hybrid).
- RAG Fusion at scale (recall gains often lost after rerank + truncation — arXiv:2603.02153).
- Always-on long context vs aggressive compaction (trade latency, cost, coherence).

**Corpus gaps this doc closes:** end-to-end **build → maintain → hygiene by intent** playbook (v1.4); corpus housekeeping v1.5 (companion research consolidated). Remaining gap vs **implementation**: Part 42 gap map only.

**Companions (read with this doc):** `RAG_ROUTING_AND_PARADIGM_SELECTION_2026.md` (paradigm + depth **before** LLM tier); `CONTEXT_BEATS_MODEL_SEMANTIC_VS_GREP.md`; `WHEN_TO_RELY_ON_LLM_ALONE.md`.

**Blind spots v1.0 missed (Part 12–20):** trust-boundary collapse; cascading corruption; static NIAH ≠ agentic robustness; token budget + caching; query transforms; tool RAG; sub-agent propagation; negative selection; memory decay; Breunig taxonomy.

**Blind spots v1.2 missed (Part 29–35):** **temporal RAG + conflict resolution** (stale vs current docs); **multimodal + structured-data routing** (SQL vs RAG vs vision); **parent-child / late-interaction retrieval**; **privacy-as-context** (GDPR erasure at write); **eval ≠ production context**; **procedural constraint layer** as T0 spine; **retrieval latency SLA** (rerank budget).

**Blind spots v1.3 missed (Part 37–41):** parallel shared-state races; instruction stack (rules/hooks vs RAG); agent context planes (orchestrator/background worker/scheduled jobs/IDE); multilingual retrieval; HITL before memory write.

**Coverage status (v1.5 FINAL):** Four literature passes + corpus housekeeping complete. **Stop expanding literature.** Next work = **Part 42 implementation gap map** or product-triggered pilots only.

---

## Part 0 — Review of existing agent context research

### What we already have (still valid)

| Doc | Role | Freshness |
|-----|------|-----------|
| `CONTEXT_BEATS_MODEL_SEMANTIC_VS_GREP.md` | Strategic: context > model; hybrid retrieval | ✓ Jun 2026 |
| `WHEN_TO_RELY_ON_LLM_ALONE.md` | 7-test retrieval gate | ✓ Jun 2026 |
| `RAG_SEMANTIC_INDEXING_*` | When RAG helps/hurts; Oracle-SWE signals | ✓ May 2026 |
| `OPENAI_EMBEDDINGS_*`, `EMBEDDING_*` | Implementation + thresholds | ✓ 2026 |
| `CONTEXT_BUILDING_AND_MAINTENANCE_RESEARCH_2026.md` (Parts 6, 24) | Conversation memory + compression design | ✓ 2026 |
| Research-to-patterns distillation | Research → rules in prompts | ✓ 2026 |
| `patterns_retrieval_knowledge.yaml` | Distilled retrieval patterns | ✓ Jun 2026 |

### Outdated or incomplete areas

| Area | Issue | Update (this doc + external 2025–2026) |
|------|-------|----------------------------------------|
| **Terminology** | Corpus says "prompt engineering" + scattered RAG | **Context engineering** is now canonical (Anthropic Sep 2025) — covers system, tools, MCP, history, external data |
| **Always-on RAG assumption** | Early RAG docs implied embed-everything | Adaptive/self-RAG is SOTA; naive RACG **hurts** (SRACG AAAI 2026) |
| **Semantic index mandatory** | Partially corrected in CONTEXT_BEATS | Production split: pre-index **or** JIT grep; hybrid is default recommendation |
| **Bigger context = better** | Underweighted until RAG doc §7 | **Context rot** (Chroma 2025): degradation at all lengths; k=1 often beats k=5 |
| **Memory = chat history** | Conversation docs strong; store weak | **Mem0**, hierarchical memory, compaction pipelines (Claude Code 5-layer) |
| **Intent-scoped assembly** | Generic context-engineering docs ≠ per-task agent profiles | Missing: per-intent **context profile** (what sources, budget, hygiene) |
| **Tool output hygiene** | Mentioned in Anthropic indirectly | Tool-result clearing, structured returns, progressive disclosure now first-class |
| **MCP in context folder** | Implementation research | Belongs in `tools/`; context doc should reference protocol, not duplicate |
| **Parametric vs contextual evidence** | Consolidated in corpus | ✓ | See `WHEN_TO_RELY_ON_LLM_ALONE.md` + `CONTEXT_BEATS_MODEL_SEMANTIC_VS_GREP.md` |

### Corpus organization (v1.5 — done)

- ✓ Context research consolidated under `docs/research/context/`
- ✓ Tool-routing research under `docs/research/tools/`
- ✓ Database research under `docs/research/databases/`

---

## Part 1 — Mental model: context as finite attention budget

Anthropic (Sep 2025): context = all tokens at inference time. Engineering goal = **maximize P(desired outcome | tokens)** under attention scarcity. Transformer n² pairwise attention → diminishing returns as length grows (**context rot**, Chroma 2025; **lost-in-the-middle**, Liu et al. TACL 2024).

**Design invariant:** Every token must earn its place. More context is a **cost**, not a feature, until proven otherwise for that intent.

---

## Part 2 — Memory hierarchy (what lives where)

Unified stack (Packer 2023; CoALA; Mem0 arXiv:2504.19413; hierarchical theory arXiv:2603.21564):

| Layer | Storage | Lifetime | Contents | Agent mapping |
|-------|---------|----------|----------|-------------|
| **Working** | Context window | Current turn / run | System prompt, intent slice, recent turns, retrieved chunks, tool results | Orchestrator prompt + context assembly injection |
| **Episodic** | Session store | Session → cross-session | Raw turns, summaries, topic state | session store, topic state service |
| **Semantic** | Semantic embeddings | Persistent | Docs, research, patterns, quotes | vector index + document corpus |
| **Procedural** | Skills, intents, patterns | Versioned | HOW to act — intent artifacts, `*_patterns.yaml`, skills | intent store, pattern files, skill files |
| **Personal / encrypted** | Personal archive | Persistent, scoped | User-specific private memory | scoped personal memory store |
| **External JIT** | APIs, MCP, grep, files | On demand | Fresh data, execution results | tools, MCP, retrieval APIs |

**Rule:** Working memory holds **pointers + summaries**; bulk data stays external until JIT-loaded (Anthropic "just-in-time" context; Claude Code grep/glob/read).

---

## Part 3 — The four operators: Write · Select · Compress · Isolate

LangChain / Anthropic convergence (2025):

### 3.1 Write (persist outside the window)

- **Structured notes:** project notes, todo lists, intent/spec artifacts
- **Memory extraction:** Mem0-style salience filter — store facts, not raw transcripts
- **Scratchpads:** tool-accessible files; conclusions only re-enter context
- **Outcome logs:** outcome feedback loop pattern — label what worked/failed for future retrieval

**Proven:** Agentic memory improves long-horizon tasks (Mem0: +26% vs full-history on LOCOMO benchmark, arXiv:2504.19413).

### 3.2 Select (pull in only what the step needs)

Pipeline per turn:

```
Intent + current message + topic state
    → Retrieval gate (7 tests, WHEN_TO_RELY)
    → Route by source (internal / external / tool / parametric)
    → Rank + dedupe + truncate to budget
    → Position for attention (critical at start/end)
    → Inject into working memory
```

**Selective retrieval signals (Oracle-SWE, arXiv:2604.07789 — coding, but generalizable):**

| Rank | Signal | When critical |
|------|--------|---------------|
| 1 | Reproduction / failing test | Debug, fix tasks |
| 2 | Execution context (errors, traces) | Runtime failures |
| 3 | Edit location (file:line) | Code change |
| 4 | API usage examples | Integration tasks |
| 5 | Regression tests | Safe refactor |

**Anti-pattern:** retrieve "similar domain" content instead of **task-needed** content (−15% Pass@1, arXiv:2503.20589).

### 3.3 Compress (stay under budget)

Techniques (ordered by invasiveness):

1. **Tool result clearing** — drop raw tool output after step completes (Anthropic platform; Claude Code)
2. **Summarization** — discourse-level summary preserving decisions, open threads, constraints (compaction)
3. **Structured compaction** — OpenAI `responses.compact`; Claude Code 5-layer: budget reduction → snip → micro-compact → collapse → auto-compact (arXiv:2604.14228)
4. **Hierarchical memory** — RAPTOR, GraphRAG-style summaries at multiple granularities
5. **Session limit** — OpenAI Agents SDK `SessionSettings(limit=N)`

**Compaction rule:** Maximize **recall** first (don't lose constraints/decisions), then improve **precision** (drop fluff). Over-aggressive compaction loses subtle constraints (Anthropic).

### 3.4 Isolate (scope context by sub-task)

- **Sub-agents return summaries** (1–2K tokens), not full traces (Anthropic multi-agent research)
- **ScopedContextPackage** (multi-agent pattern) — domain-scoped slice, not orchestrator blast
- **Skill `context: fork`** — isolated subagent window (Agent Skills standard)
- **MCP resource per domain** — expose only relevant tool/data surface

---

## Part 4 — Intent / goal-driven context profiles

**Key insight:** Context assembly is not one pipeline — it's a **profile per intent class**.

### 4.1 Intent dimensions

| Dimension | Drives |
|-----------|--------|
| **Stakes** | Provenance required? → force retrieval + citations |
| **Freshness** | Post-cutoff / live data? → tools/MCP over parametric |
| **Privacy** | User/org data? → personal archive + encrypted store |
| **Reasoning vs lookup** | Skill task → minimal retrieval; fact task → maximal grounding |
| **Horizon** | Single turn vs multi-hour → compaction + notes vs full history |
| **Domain** | Code vs conversation vs finance → different retrieval routes |

### 4.2 Context profiles (templates)

**Profile A — Reasoning / craft (e.g. write article, refactor with spec)**
- Parametric + **provided input** is the context
- Retrieve: intent artifact, patterns, 1–3 exemplars only
- Skip: broad RAG unless explicit fact gap
- Hygiene: no tool dump; summarize prior turns lightly

**Profile B — Grounded Q&A (e.g. "what did we decide about X?")**
- Retrieve: chat episodic + semantic retrieval + topic state
- Gate: adaptive — if head knowledge + confident, skip semantic retrieval
- Hygiene: cite source layer (chat vs semantic corpus vs tool)

**Profile C — Live / fresh (e.g. stock price, Trello state)**
- **Tools first** — never parametric for mutable state
- Minimal history; current intent + entity IDs
- Hygiene: TTL on cached tool results; mark stale explicitly

**Profile D — Long-horizon agent (e.g. migration, research sweep)**
- Compaction every N tokens or M tool calls
- Structured notes (decisions, blockers, file pointers)
- Sub-agents for exploration; parent keeps plan + summaries only
- Hygiene: clear tool results; dedupe retrieved chunks

**Profile E — Persona / eval gate (reviewer, investor persona)**
- RAG over **grounded quotes** + outcome-labeled history (persona-grounded retrieval pattern)
- Never persona-only without retrieved evidence
- Hygiene: decay stale persona facts; human validation loop

### 4.3 Decision: retrieve or not?

Use **7-test gate** (`WHEN_TO_RELY_ON_LLM_ALONE.md`) — all must pass to skip retrieval:

1. Popular/head knowledge  
2. Stable/pre-cutoff  
3. Reasoning/skill; input contains data  
4. Low stakes, no provenance  
5. Not private/proprietary  
6. High calibrated confidence  
7. Clean context available (retrieval won't add noise)

Modern systems add **learned routers** (Adaptive-RAG, Self-RAG, FLARE confidence gating).

---

## Part 5 — Where to search: data sources & routing

### 5.1 Source catalog

| Source | Search method | Best for | Avoid for |
|--------|---------------|----------|-----------|
| **Parametric** | None | Head facts, reasoning, transform input | Tail entities, fresh, private |
| **Semantic embeddings** | Dense cosine + metadata filter | NL conceptual, research, patterns | Exact symbols, IDs, fresh mutable |
| **Lexical / grep** | BM25, ripgrep | APIs, filenames, error strings, identifiers | Paraphrase, conceptual |
| **Session / episodic store** | Temporal + semantic routes | Prior turns, user preferences | Static docs |
| **Topic state** | Key lookup | Active topic, abandoned topics | Unrelated history |
| **Intent artifacts** | Path load | Constraints, tests, anti-patterns | Bulk knowledge |
| **Patterns YAML** | Domain loader | Craft rules | Raw research |
| **Tools / MCP** | Agent-invoked | Live systems, execution, files | Bulk static corpus |
| **Web** | Search API | Fresh public facts | Private data |
| **Personal archive** | Encrypted semantic | User-specific long-term | Shared org knowledge |

### 5.2 Hybrid retrieval pipeline (proven production pattern)

**Route paradigm first:** see `RAG_ROUTING_AND_PARADIGM_SELECTION_2026.md` — pick LLM-only / naive / hybrid / graph / iterative **before** embedding; CA-RAG utility = quality − α·latency − β·tokens.

```
Query (+ intent profile + metadata filters)
    → Parallel: dense top-k_d + BM25 top-k_b
    → RRF merge
    → Dedupe (near-duplicate chunks)
    → Cross-encoder rerank → top-k_r (k_r=1–3 default; justify if higher)
    → Necessity check (SRACG-style: skip if model confidence high)
    → Inject with source tags + position at START or END (never bury critical facts in middle)
```

**Defaults from agent research:**
- Similarity thresholds: see `EMBEDDING_SIMILARITY_THRESHOLDS_RESEARCH_2026.md`
- **k=1 default** for code; top-5 often hurts (arXiv:2511.05302)
- Metadata filters before vector search (org, domain, doc type, date)

### 5.3 Chunking & indexing hygiene

- **Structure-aware chunking** (AST/tree-sitter for code; headings for MD) — Cursor production pattern
- **Chunk size:** match embedding model + use case (400–800 tokens common; test on your corpus)
- **Overlap:** minimal unless discourse continuity requires it
- **Freshness:** Merkle/incremental re-index; stale index worse than grep (Claude Code removed vector index)
- **Provenance metadata:** source path, date, intent_id, outcome label — required for outcome feedback loops

---

## Part 6 — Conversation turns & topic memory

From topic-switching and long-horizon conversation research (Part 6, Part 24):

**Multi-timescale processing:**
- **Turn (1–8s):** last 1–3 raw turns always in working memory
- **Topic (16–32s+):** topic_state primary/secondary/abandoned; switch rate target **5–8%** of time
- **Session (cross-turn):** summaries + episodic retrieval
- **Long-term:** semantic index + personal store

**Topic transition protocol (4 steps):**
1. Acknowledge closure of current thread  
2. Bridge/reference shared context  
3. Introduce new topic with anchor  
4. Confirm common ground  

**Topic resumption:** abandoned topics need explicit stack — don't rely on model to remember silently.

**Continuation query enrichment:** short follow-ups ("so what next?") carry no semantic signal — enrich with active topic before embedding search (the `context_assembler.py` pattern).

---

## Part 7 — Tool outputs & MCP in the context budget

Tools are **context pumps** — each call can flood the window.

**Proven hygiene:**
- Return **structured, minimal** payloads (JSON fields the model needs; not raw HTML)
- **Truncate** with pointer ("full output in `/tmp/x`; use read_file for lines 100–200")
- **Clear after use** — tool results deep in history are rarely re-needed (Anthropic)
- **Progressive disclosure** — metadata first (file name, size, modified); load content on demand
- **MCP:** stateless tool exposure; orchestrator remains stateful — don't duplicate session in MCP layer

**Tool design = context design** (Anthropic): non-overlapping tools, unambiguous names, docstring-quality descriptions, few-shot tool use examples in system prompt — not 50 edge-case rules.

---

## Part 8 — Quality, hygiene & consistency

### 8.1 Context pollution types

| Pollution | Symptom | Fix |
|-----------|---------|-----|
| **Stale facts** | Wrong API/version | TTL, freshness metadata, tool re-fetch |
| **Similar-but-wrong** | Confident wrong answer | Necessity-aware retrieval; k=1; rerank |
| **Duplicate** | Wasted tokens | Dedupe at merge |
| **Middle burial** | Ignored constraints | Position critical text start/end |
| **Scope bleed** | Sub-agent or prior topic noise | Isolate; domain filters |
| **Stale index** | Deleted code referenced | JIT grep validation; incremental index |
| **Persona caricature** | Generic "user wants X" | Ground persona RAG in real quotes |

### 8.2 Consistency across turns

1. **Single source of truth per fact class** — mutable state from tools; stable from semantic corpus; procedural from intents  
2. **Topic state machine** — explicit active topic; don't infer-only  
3. **Version pins** — intent artifact version in context header  
4. **Conflict resolution** — newer tool result > older chat > semantic corpus > parametric  
5. **Compaction preserves:** decisions, open constraints, entity IDs, file pointers — drops: raw tool I/O, redundant assistant fluff  

### 8.3 Evaluation (required to know context works)

- **Retrieval:** precision@k, nDCG — on *your* corpus with human labels  
- **End-to-end:** task success with/without retrieval ablation  
- **Context ablation:** remove layer (semantic corpus, history, tools) — measure delta  
- **Needle tests:** position sweep (start/middle/end)  
- **Long-session:** quality vs turn count (detect rot)  
- **Observability:** token breakdown by source per turn (LangSmith pattern)

**Critical blind spot:** static NIAH scores **do not predict agentic robustness**. HaystackCraft (arXiv:2510.07414) shows GPT-5 mini matches GPT-5 on single-pass NIAH but **collapses under enforced multi-round** reasoning — more rounds can hurt more than longer single-pass context. Benchmark agent workflows, not just retrieval recall.

**Agentic eval additions:**
- **Multi-round stress:** 2–3 enforced retrieval/refinement rounds; measure drift from original intent  
- **Cascade detection:** inject one wrong fact at step 1–2; measure propagation to final answer (CHARM framework, arXiv:2606.04435 — 89.4% cascade detection rate vs 12.8% for LLM self-correction)  
- **Tool storm / retrieval thrash:** count redundant tool calls per task; cap and measure quality delta  
- **Context clash injection:** deliberately inject contradictory doc + system rule; measure which wins  
- **Compaction recall audit:** after summarize, can agent answer constraint-check questions from pre-compaction trace?

---

## Part 9 — Proven vs contested (calibrated)

| Claim | Verdict | Source |
|-------|---------|--------|
| Good context beats bigger model | ✓ Strong | RETRO, Atlas, DPR; CONTEXT_BEATS_MODEL_SEMANTIC_VS_GREP.md |
| Adaptive retrieval beats always-on | ✓ Strong | Self-RAG, Adaptive-RAG, FLARE |
| Wrong retrieval hurts | ✓ Strong | SRACG, arXiv:2503.20589 |
| k=1 often beats k=5 | ✓ Strong | arXiv:2511.05302; SRACG |
| Context rot at all lengths | ✓ Strong | Chroma 2025 (18 models) |
| Lost-in-the-middle | ✓ Strong | Liu TACL 2024 |
| Hybrid BM25+dense | ✓ Strong | BEIR; production 2025–2026 |
| Bounded reranking helps | ✓ Strong | BEIR; cross-encoder literature |
| Semantic index always wins grep | ✗ Contested | Claude Code vs Cursor |
| RAG Fusion helps production | ⚠️ Often neutral/negative | arXiv:2603.02153 |
| Bigger context window fixes memory | ✗ Refuted as sole strategy | Context rot + Anthropic |
| Mem0 / structured long-term memory | ✓ Directional | arXiv:2504.19413 |
| Hierarchical memory theory unification | ~ Emerging | arXiv:2603.21564 |
| Compaction without recall tuning | ⚠️ Risky | Anthropic engineering |
| Persona RAG = ground truth | ✗ Proxy only | persona-grounded retrieval research |
| Static NIAH predicts agentic context | ✗ Refuted | HaystackCraft arXiv:2510.07414 |
| LLM self-correction stops cascades | ✗ Weak | CHARM arXiv:2606.04435 (12.8% CDR) |
| Tool poisoning is prompt-layer only | ✗ Structural | MCP arXiv:2603.22489; CVE-2025-54136 |
| Prompt caching without static/dynamic split | ✗ No benefit | OpenAI/Anthropic docs |
| HyDE always helps | ⚠️ Can retrieve around wrong idea | Gao et al.; Alex Chernysh 2026 |
| >20 tools in context without selection | ⚠️ Context confusion | Breunig; "Less is More" tool study |
| Tool RAG ~3× selection accuracy | ✓ Directional | Red Hat ET; Anthropic RAG-MCP |
| Full context = accuracy ceiling | ✓ Strong | Mem0 LOCOMO; arXiv:2504.19413 |
| External memory ~90% token/latency savings | ✓ Strong | Mem0: 26K→1.7K tokens; 17s→1.4s p95 |
| Passive summarization enough for agents | ✗ Insufficient | ARC ACL 2026; AdaCoM arXiv:2605.30785 |
| Embedding drift shows in error rates | ✗ Silent failure | Azure/Tian Pan/decompressed.io 2025–2026 |
| Stronger agent = more raw context OK | ✓ Emerging | AdaCoM fidelity–reliability tradeoff |
| Global memory rewrite scales | ✗ Poor ops | Agent-native memory arXiv:2606.24775 |
| Version-blind RAG on policy docs | ✗ Major failure mode | VersionRAG / SmartVector arXiv:2604.20598 (~58%→90%) |
| ConflictRAG-style detect+resolve | ✓ Strong on NQ-Conflict | arXiv:2605.17301 (88.7% detection F1) |
| Parent-child beats flat chunking | ✓ Directional (+15–30%) | Production RAG literature 2025 |
| GDPR erasure without subject_id at write | ✗ Non-compliant | Velsof/Kronvex/Tian Pan 2026 |
| Eval retrieval-only ≈ prod agent context | ✗ Diverges | Part 33; end-to-end ablation required |

## Part 11 — Blind spots audit (what v1.0 underweighted)

Meta-review of the master doc + agent corpus against 2025–2026 literature and production failures.

| Blind spot | Why it matters | Severity | Now covered |
|------------|----------------|----------|-------------|
| **Uniform trust in context stream** | Model treats user prompt, system, RAG chunks, tool metadata, tool outputs with equal authority | 🔴 Critical | Part 15 |
| **Cascading corruption** | Step-1 error becomes step-N ground truth; self-correction confirms wrong chain | 🔴 Critical | Part 16 |
| **Agentic rot ≠ static rot** | Single-pass NIAH green; multi-round agent fails | 🔴 Critical | Part 8.3, 16 |
| **No token budget in code** | Mentioned conceptually; not enforced per layer | 🟠 High | Part 13 |
| **Prompt cache invalidation** | Dynamic data in static prefix → 0% cache hit + cost blowup | 🟠 High | Part 13 |
| **Query transformation routing** | HyDE/decompose/step-back used ad hoc or never | 🟠 High | Part 14 |
| **Tool loadout at scale** | All MCP tools in system prompt past ~20 confuses models | 🟠 High | Part 17 |
| **Sub-agent context vacuum** | Coordinator memory doesn't cross `as_tool()` boundary | 🟠 High | Part 18 |
| **Negative selection** | Corpus says what to add; not what to **exclude** | 🟡 Medium | Part 19 |
| **Memory decay / forgetting** | Mem0 write without delete/TTL → stale beliefs compound | 🟡 Medium | Part 20 |
| **RAG corpus poisoning** | Few bad docs corrupt outputs; outcome-labeled corpus is attack surface | 🟡 Medium | Part 15, 20 |
| **Context clash across turns** | Fragmented multi-turn updates → ~39% performance drop (~ Microsoft/Salesforce study, cited Turing College 2025) | 🟡 Medium | Part 12 taxonomy |
| **Multimodal context** | Images/files in agent loops — budget, ordering, OCR quality | 🟡 Medium | Part 12 (gap remains) |
| **Cross-session identity drift** | Same user, new session — procedural context vs episodic recall | 🟡 Medium | Part 20 |
| **GraphRAG / entity graphs** | Mentioned once; no when-to-use vs flat RAG | 🟡 Medium | Part 14 |
| **Instruction hierarchy** | System vs developer vs user vs tool — conflict resolution weak | 🟡 Medium | Part 15 |
| **Outcome-labeled retrieval** | outcome feedback loop pattern not wired into retrieval ranking | 🟡 Medium | Part 20 |
| **Accuracy/latency/cost map** | No explicit when to pay for full-context vs external memory | 🟠 High | Part 22 |
| **Passive-only compaction** | Summarize-on-threshold misses surgical context ops | 🟠 High | Part 23 |
| **Embedding drift monitoring** | Semantic index degrades silently — no benchmark query set | 🔴 Critical | Part 24 |
| **Cross-system cold start** | CRM + Trello + chat each cold per call | 🟠 High | Part 25 |
| **Context observability** | Can't debug "why did agent believe X?" | 🟠 High | Part 26 |
| **Memory write propagation cost** | Graph/hierarchical memory rewrite stalls throughput | 🟡 Medium | Part 27 |
| **Parametric vs contextual spine** | `WHEN_TO_RELY_ON_LLM_ALONE.md` + `CONTEXT_BEATS_MODEL_SEMANTIC_VS_GREP.md` | 🟡 Medium | ✓ `context/` (v1.5) |
| **Temporal / versioned knowledge** | Flat corpus treats 2024 doc = 2026 truth | 🔴 Critical | Part 29 |
| **Inter-doc conflict resolution** | Retrieved set can contradict; model picks wrong | 🔴 Critical | Part 29 |
| **Multimodal context** | Images/PDFs — pointer vs inline, OCR quality | 🟡 Medium | Part 30 |
| **Structured vs unstructured routing** | SQL/tabular conflated with semantic RAG | 🟠 High | Part 30 |
| **Parent-child retrieval** | Small-chunk search, big-chunk generate | 🟠 High | Part 31 |
| **Late interaction (ColBERT)** | Single-vector loses term-level signal | 🟡 Medium | Part 31 |
| **Privacy / GDPR erasure** | Mem0/semantic index without subject_id = undeletable | 🔴 Critical | Part 32 |
| **Eval ≠ prod context** | Golden set uses clean context; prod is messy | 🟠 High | Part 33 |
| **Procedural constraints as T0** | Craft rules not wired as context spine | 🟠 High | Part 34 |
| **Rerank latency SLA** | Quality vs 100–200ms budget untradeoff'd | 🟡 Medium | Part 35 |
| **Parallel shared-state races** | Two agents overwrite same memory silently | 🔴 Critical | Part 37 |
| **Instruction stack / rules files** | Policy files vs semantic corpus vs compaction survival | 🟠 High | Part 38 |
| **Agent plane separation** | Orchestrator context ≠ background worker ≠ scheduled jobs | 🟠 High | Part 39 |
| **Multilingual retrieval** | ES/EN mix in multilingual workflows | 🟡 Medium | Part 40 |
| **HITL before memory write** | Unverified facts promoted to long-term | 🟠 High | Part 41 |

**Still open after v1.5:** implementation only — see **Part 42** gap map. Domain pilots: GraphRAG, multimodal vision, learned ContextCurator (RL).

---

## Part 12 — Failure taxonomy: four modes + agentic extensions

Drew Breunig (Jun 2025) — industry-standard taxonomy, adopted by LangChain and O'Reilly:

| Mode | Definition | Agent-specific trigger | Mitigation |
|------|------------|------------------------|------------|
| **Poisoning** | Error/hallucination enters context and gets re-referenced | Bad retrieval chunk; wrong tool result accepted as fact | Quarantine unverified writes; provenance tags; CHARM-style stage checks |
| **Distraction** | Model over-indexes on long context vs training | >100K tokens → action repetition (Gemini Pokémon agent, Breunig) | Compaction; offloading; phase boundaries |
| **Confusion** | Superfluous context steers response | 46 tools vs 19 for same 8B model; early wrong attempts in history | Tool RAG; pruning; remove failed attempts from history |
| **Clash** | Contradictory facts/tools/instructions coexist | Stale corpus doc + fresh tool result; overlapping tool descriptions | Conflict resolution hierarchy (Part 8.2); dedupe; version pins |

**Agentic extensions (not in Breunig, from HaystackCraft + practitioner literature):**

- **Cascade corruption** — derived conclusions become inputs; logical chain looks valid at every step (Tian Pan 2026; CHARM)  
- **Retrieval thrash** — oscillating search strategies without convergence  
- **Tool storm** — redundant calls filling window with noise  
- **Self-distraction** — model's own prior reasoning rounds become distractors (HaystackCraft "self-generated distractors")

**Operational rule:** classify every production failure into one mode before patching — adding more context fixes confusion poorly and often worsens clash.

---

## Part 13 — Token budget & prompt architecture

v1.0 said "finite budget" but did not specify **enforceable allocations**. Production pattern (Atlan 2026; llmbestpractices.com):

### 13.1 Default budget split (200K window agent; adjust by profile)

| Layer | % budget | Notes |
|-------|----------|-------|
| System + procedural (intents, patterns) | 10–15% | Stable; cacheable |
| Tool definitions (selected loadout only) | 10–15% | Tool RAG first — never full registry |
| Conversation history | 25–30% | Raw recent + topic summary |
| Retrieved evidence | 25–30% | Hard cap; k=1–3 default |
| Tool results (current step) | 10–15% | Clear after step |
| Response headroom | 15–20% | Never steal from this |

**Enforce in code before every LLM call** — reject or compress lowest-priority layer first (typically: old tool results → old history → retrieved overflow).

### 13.2 Static / dynamic ordering (prompt caching)

**Order matters for cost and constraint decay:**

```
[STATIC — cache breakpoint]
  System instructions
  Intent constraints (version-pinned)
  Selected tool schemas (tool RAG output)
  Few-shot examples
[DYNAMIC — never cache]
  Topic state
  Retrieved chunks (this turn)
  Recent turns
  Current user message
  Tool results (this step)
```

**Rules:**
- Any edit to static prefix **invalidates** provider cache for everything after it (OpenAI auto-cache; Anthropic `cache_control`)  
- Never put timestamps, session IDs, or per-turn retrieval in static block  
- Minimum cacheable prefix typically **1,024 tokens** (OpenAI, Anthropic)  
- April 2026 TTL reduction is a cost fragility (see vendor pricing changelogs)

**Three cache tiers (~ practitioner stack):**
1. **Semantic cache** — identical/near-identical queries skip LLM entirely  
2. **Embedding cache** — don't re-embed unchanged chunks  
3. **Prompt prefix cache** — provider KV reuse for static block (50–90% input cost reduction)

---

## Part 14 — Query transformation routing

v1.0 covered hybrid retrieval but not **when to transform the query**. Symptom → technique map (Alex Chernysh 2026; Step-Back paper; HyDE Gao et al.):

| Symptom | First technique | Cost | Risk |
|---------|-----------------|------|------|
| Vague / elliptical query | **Rewrite** (clarity) | 1 LLM call | Over-specification |
| Compound / multi-hop | **Decomposition** → sub-queries per index | 1+ calls | Sub-query error propagates |
| Over-specific literal terms | **Step-back** (broader abstraction) | 1 call + 2 retrievals | Misses if corpus is flat |
| Short query, long docs | **HyDE** (hypothetical doc embed) | 1 call + embed | Retrieves around wrong hypothetical |
| Multiple useful variants | **Multi-query + RRF** | N retrievals | Volume → confusion if not reranked |
| Messy corpus | **Fix ingestion first** | — | No transform fixes bad chunks |

**Agentic RAG loop:** agent chooses transform based on first retrieval confidence (FLARE: retrieve when generation confidence drops mid-stream).

**Agent default:** continuation-query enrichment (topic state) before any transform; decomposition for cross-domain questions (vector index + chat + tools); HyDE only when enrichment + direct embed under-threshold.

**GraphRAG gap:** use when answers require **multi-hop entity traversal** (org charts, dependency graphs, citation networks) — flat chunk RAG misses relational paths. Not yet in agent production; candidate for venture/legal/finance profiles.

---

## Part 15 — Trust boundaries & context security

**Structural blind spot:** context engineering docs treat all tokens as **content**. Security research treats the same stream as **attack surface** — because models don't distinguish instruction from data.

### 15.1 Trust levels (must label at injection)

| Level | Source | Model treatment | Agent handling |
|-------|--------|-----------------|--------------|
| **T0 — Binding** | System prompt, binding constraints | Instruction | Human-authored; version-pinned |
| **T1 — Procedural** | Patterns, skills | Instruction | Distilled; no raw research |
| **T2 — Verified data** | Tool results from owned APIs, passing schema | Data | Structured JSON; TTL |
| **T3 — Retrieved** | Semantic corpus, web, RAG | Untrusted data | Wrap in `<retrieved source="...">`; never merge into system |
| **T4 — External tool** | MCP third-party, web scrape | **Hostile until proven** | Pin tool inventory at session start; post-exec output scan |

### 15.2 Attack vectors in context pipeline

| Vector | Mechanism | Mitigation |
|--------|-----------|------------|
| **Tool description poisoning** | Malicious text in MCP tool metadata (CVE-2025-54136) | Pin schemas; gateway inspect; allowlist servers |
| **Tool output injection** | Free-text response treated as instruction (OWASP LLM01) | Separate privilege tiers; external-text tools never co-context with write tools |
| **RAG poisoning** | Adversarial chunks in vector store (arXiv:2507.08862) | Ingestion gate; corpus curation; outcome-labeled trust scores |
| **Rug pull** | Benign tool later changes behavior | Re-validate schema each session |
| **Compaction amplification** | Poisoned fact summarized into "trusted" summary | Quarantine before write; human gate for memory extract |

MCP threat model (arXiv:2603.22489): **57 threats** across host/client/LLM/server/data/auth — 34% tampering + information disclosure; tool poisoning exploits client-server trust gap.

**Agent rule:** never let T3/T4 content **overwrite** T0 constraints. Conflict → explicit clash flag to user, not silent merge.

---

## Part 16 — Cascading corruption & containment

**The deepest agent blind spot:** one wrong fact at step 2 shapes tool choice, parameters, and interpretation for 50+ steps. Chain is logically coherent given the wrong premise — so self-correction fails (confirmation bias).

**Evidence:**
- HaystackCraft: multi-round **amplifies** early errors; GPT-5 / Gemini 2.5 Pro not immune  
- CHARM: cascade detection 89.4% vs self-correction 12.8%; interrupts at ~stage 2.1  
- Practitioner pattern: early-stage errors (steps 1–4) have longest propagation chain (Tian Pan 2026)

**Containment architecture:**

```
Phase boundary (fresh window)
  ← verified outputs only (structured handoff)
Checkpoint verifier (independent, no shared chain)
  ← NLI / cross-encoder / rule oracle on stage output
Scope isolation
  ← sub-agent explores; parent gets summary + citations only
Hard stop rules
  ← max N retrieval rounds; max M tool calls per sub-task
Belief tracking (optional)
  ← explicit "agent believes X" with source tag; re-verify before write
```

**Compaction interaction:** summarizing a corrupted chain **cements** the error into "trusted" compressed memory. Run verification **before** compact, not after.

**Agent mapping:** Binding constraints + execution-derived tests as checkpoint oracles; `ScopedContextPackage` as scope isolation; outcome-labeled corpus data must distinguish **verified** vs **agent-derived** facts.

---

## Part 17 — Tool RAG & loadout limits

v1.0 covered tool **output** hygiene but not tool **selection** as context problem.

**Problem:** 100+ MCP tools in prompt → context confusion (Breunig; Llama 3.1 8B fails at 46 tools, succeeds at 19 — "Less is More"). Overlapping tool descriptions amplify clash.

**Tool RAG pipeline (Toolshed 2025; ToolReAGt ACL 2025; Red Hat ET 2025):**

```
User intent + task decomposition (optional)
  → Embed against tool knowledge base (enhanced docs: name, description, params, examples, constraints)
  → Hybrid retrieve top-k tools (k=3–7 typical)
  → Rerank / self-correct
  → Inject ONLY selected schemas into static tool block
  → Iterative: re-retrieve per sub-task (ToolReAGt +8.9% recall@5 vs one-shot)
```

**Reported gains:** Anthropic RAG-MCP 13% → 43% tool selection accuracy; Red Hat cites ~3× accuracy + ~50% prompt reduction; Toolshed +46–56% absolute over BM25 on benchmarks.

**Agent implication:** The agent MCP tool surface will grow — **never** pass full registry to the orchestrator. Route: intent profile → domain tool subset → optional semantic tool retrieve. Aligns with `patterns_retrieval_knowledge.yaml` but needs explicit tool-index.

**Tools spine:** operational extract + MAST mapping → `../tools/WORLD_MODEL_TOOL_ROUTING_RESEARCH_2026.md`. **Implementation:** tools research ↔ context research (implementation phases).

---

## Part 18 — Multi-agent context propagation

**Blind spot:** v1.0 mentioned `ScopedContextPackage` once; multi-agent memory propagation research defines this gap precisely.

**Current failure:** sub-agent delegation (`as_tool` pattern) passes routing string only — sub-agent gets zero chat/vector index/personal memory.

**Wrong fixes:**
- **Shared full history** — scope bleed (personal content in research agent)  
- **Raw history file + grep** — keyword-only; ignores semantic ranking the agent already has

**Right fix — relevance-filtered package per sub-agent:**

```
Coordinator assemble(intent, sub_agent_domain, topic, query)
  → chat temporal route (domain-filtered)
  → semantic retrieval (metadata: domain, doc_type)
  → personal (if authorized + relevant)
  → topic state slice
  → compress to token budget
  → ScopedContextPackage { constraints, retrieved, topic, pointers }
  → inject into sub-agent system prompt
  → sub-agent returns { summary, citations, artifacts } — NOT full trace
```

**Semantics-informed summarization:** before orchestrator compaction, run context assembly over full turns → high-signal turn IDs → summarize with explicit anchors; persist raw turns to recovery table.

**Cross-agent consistency:** parent maintains **conflict resolution hierarchy** (Part 8.2); sub-agent summaries are T3 until verified by tool/oracle.

---

## Part 19 — Negative selection (what NOT to include)

Context quality is as much **subtraction** as addition.

| Exclude | Why | When to re-include |
|---------|-----|-------------------|
| Failed tool outputs (after fix) | Confusion + clash with success path | Never — log externally |
| Early wrong assistant attempts | Context confusion (Breunig/O'Reilly) | Never in working memory |
| Superseded retrieved chunks | Stale clash | Only if user asks history |
| Full research `.md` in prompt | Distraction; use patterns instead | Link/path only |
| Duplicate near-identical chunks | Wasted tokens | Dedupe at merge |
| Parametric filler when retrieving | Clash with grounded answer | Strip after retrieval inject |
| Other agents' full traces | Scope bleed | Summary + citations only |
| Unverified Mem0 extractions | Poisoning risk | After human or oracle confirm |
| Raw `.env` / secrets | Security | Never — structured redacted refs |

**Negative retrieval:** some systems store "anti-patterns" or failed approaches with outcome labels — retrieve to **avoid**, not to repeat (outcome feedback loop). The outcome corpus should support `outcome: failed` filter.

---

## Part 20 — Memory decay, corpus hygiene & compounding

### 20.1 Forgetting is a feature

Long-term memory without TTL/decay → **stale belief poisoning**. Mem0 and hierarchical memory papers emphasize **salience filtering on write** — but production also needs:

- **TTL by fact class:** mutable state (hours); preferences (months); procedural (versioned)  
- **Explicit invalidation:** when tool result contradicts stored fact, delete or downgrade  
- **Decay on read failure:** if retrieved memory repeatedly unused or contradicted, archive  
- **Session boundary refresh:** cross-session recall re-validates mutable facts via tool

### 20.2 Corpus ingestion hygiene (semantic index)

From corpus hygiene literature + RAG safety research (MassiveDS, FreshLLMs, arXiv:2507.08862):

1. **Curate before embed** — noise compounds at scale  
2. **Poisoning gate** — few bad docs dominate retrieval (arXiv:2507.08862)  
3. **Provenance metadata** — source, date, author, outcome label  
4. **Distill research → patterns** — raw research is T3; patterns are T1  
5. **Merkle / incremental re-index** — stale chunks worse than no index  
6. **Ground-truth moat** — outcome-labeled data must be **verified**, not synthetic echo (Shumailov *Nature* 2024 — model collapse from recursive AI-generated training data)

### 20.3 Outcome-weighted retrieval (open implementation)

Rank retrieval by: `similarity × outcome_weight × freshness`. Successful patterns/outcomes surface first; failed approaches surface only when query is "what didn't work". Connects outcome feedback loops to context assembly — **not yet wired in typical context assembly pipelines**.

---

## Part 22 — Accuracy · latency · cost tradeoff map

v1.1 treated context rot as quality-only. Production also requires an explicit **Pareto map** — you cannot maximize all three.

**Reference numbers (Mem0 LOCOMO benchmark, arXiv:2504.19413 — treat as directional, not project-specific):**

| Strategy | Accuracy (J score) | p95 latency | Tokens/query | When to use |
|----------|-------------------|-------------|--------------|-------------|
| **Full context** (entire history) | ~73% (ceiling) | ~17s | ~26,000 | Bounded high-stakes sessions; legal review window; incident debug |
| **Mem0 / fact extract** | ~67% (−6 pts) | ~1.4s (−91%) | ~1,764 (−93%) | Production default; cross-session personalization |
| **Mem0g (graph)** | ~68% | ~2.6s | higher than Mem0 | Multi-hop when flat RAG fails benchmarks |
| **Vector + metadata only** | ~67% | <1.5s | low | Simple preference/history retrieval |

**Key insight (arXiv:2603.04814, cited in practitioner analysis 2026):** nominal 200K–1M windows ≠ **effective utilization** — longer input can impair reasoning even when affordable. Full context is the accuracy ceiling but an **architectural impossibility** for months-long agents.

**Decision rule by stakes:**

```
if stakes == HIGH and horizon == BOUNDED:
    prefer full context or large raw window
elif stakes == HIGH and horizon == UNBOUNDED:
    external memory + verify-before-answer + tool grounding
elif stakes == LOW:
    external memory + adaptive retrieval gate (7-test)
```

**Agent implication:** orchestrator should **profile-select** memory strategy — not one-size context assembly for all routes. casual chat ≠ constraint-heavy implementation ≠ live tool fetch.

---

## Part 23 — Active context management (beyond passive compress)

v1.1 covered **passive** Compress (summarize when full). 2025–2026 research shows passive summarization **preserves early errors** and lacks surgical ops. Next frontier: **active, revisable context state**.

### 23.1 Passive vs active

| Approach | Mechanism | Failure |
|----------|-----------|---------|
| **Append-only** | Raw history grows | Distraction, clash, cost |
| **Passive summarize** | Compress at threshold | Cements errors; can't purge mid-history |
| **Keep-last-k** | Drop old turns | Loses constraints silently |
| **Active curation** | Agent/context-manager decides prune/hide/restore/search | Needs policy or learned manager |

### 23.2 Frameworks (verified 2025–2026)

| System | Idea | Result |
|--------|------|--------|
| **ARC** (ACL Findings 2026) | Reflection-driven **revisable** internal state; separate Context Manager | +11% abs on BrowseComp-ZH vs passive summarize |
| **AdaCoM** (arXiv:2605.30785) | Learned manager; **agent-compatible** compression rate | Stronger agents keep more raw context; weaker agents need eager distillation |
| **ActiveContext** (arXiv:2604.11462) | RL-trained **ContextCurator** + frozen TaskExecutor | Decouples memory ops from reasoning capacity |
| **Context-ReAct / LongSeeker** (arXiv:2605.05191) | Co-generate **meta-operations** with each tool call (hide, restore, fragment) | Surgical ops on own trajectory |
| **Sculptor** (arXiv:2508.04664) | ACM tools: fragment, summary/hide/restore, precise search | Mitigates **proactive interference** — old irrelevant context disrupts recall |

### 23.3 Fidelity–reliability tradeoff (AdaCoM)

**Not one compression policy for all models:**
- **Stronger agents** (GLM, Qwen): tiered strategy — let context grow, occasional batched compress (~5–7K tokens managed)  
- **Weaker agents** (DeepSeek, Kimi): eager distillation every round (~1.9–3.4K tokens)  

**Agent rule:** compaction aggressiveness should be **model-calibrated**, not global constant. Using Opus compaction policy on a fast sub-agent may discard evidence it needed.

### 23.4 Practical near-term (no RL required)

Before training a ContextCurator, implement **rule-based active ops:**
1. **Hide** — tool output replaced by one-line pointer after step success  
2. **Restore** — on explicit "show earlier X", grep recovery table / file  
3. **Purge failed branch** — remove assistant attempts that failed validation (Part 19)  
4. **Reflection trigger** — when retrieval confidence drops or tool errors repeat, run ARC-style "reorganize working state" prompt (not full re-run)

---

## Part 24 — Embedding drift & silent degradation

**Critical hole:** v1.1 mentioned incremental re-index but not **monitoring**. Embedding drift throws no errors — recall erodes over weeks.

### 24.1 Three drift sources (Azure AI Foundry 2025; production literature)

1. **Model version change** — new docs in different vector space than old (5–15% cosine shift can reorder top-k)  
2. **Chunking/preprocessing change** — mixed strategies in same index  
3. **Corpus/query distribution shift** — world changes; scores drift left over ~6 weeks without code changes

### 24.2 Detection signals (run weekly on golden query set)

| Signal | Healthy | Degrading | Broken |
|--------|---------|-----------|--------|
| **Top-1 score mean** | Stable band (model-specific) | −0.05 over 4 weeks | −0.10+ |
| **Top-1 minus top-5 spread** | Clear winner | Flattening | Random ranking |
| **NN stability** (same query, week-over-week) | 85–95% overlap | 70–85% | <70% |
| **nDCG@k** (if labels exist) | Flat or up | Down 2+ weeks | Down 5+ pts |

**No alert from:** CPU, latency, error rate — standard ops dashboards miss this entirely.

### 24.3 Prevention discipline

- **Pin pipeline:** model version + chunk size + overlap + preprocessor — version tag on every vector  
- **Never mix generations** in one index — partial re-embed is how drift starts  
- **Model upgrade = migration:** shadow index → benchmark golden set → cutover  
- **Re-embed full corpus** 3–4×/year planned, not panic response  

**Vector index operations:** maintain `benchmark_queries.yaml` (20–50 labeled queries) + weekly cron score report. Tie to `EMBEDDING_SIMILARITY_THRESHOLDS_RESEARCH_2026.md` thresholds.

---

## Part 25 — Cross-session & cross-system cold start

v1.1 mentioned cross-session in Part 20 lightly. Production agents fail on **continuity boundaries**:

### 25.1 Cross-session personalization

**Failure:** User states preference in session 1; session 2 agent cold → re-asks, contradicts, or genericizes.

**Fix stack:**
1. **Read-before-reason** — Mem0-style fact retrieve on session start (preferences, active projects, open blockers)  
2. **Procedural continuity** — intent/spec artifacts + patterns load regardless of session (T0/T1)  
3. **Re-validate mutable facts** — Trello state, calendar, repo status via tool on session start, not stale Mem0  
4. **Session handoff artifact** — explicit `SESSION_SUMMARY` write on close (decisions, entity IDs, next actions)

### 25.2 Cross-system context (enterprise blind spot)

Agent pulls CRM + ticketing + observability + chat — each call **starts cold** unless you maintain a **unified entity index**:

```
Entity: "customer Acme" → {crm_id, ticket_ids[], slack_thread, last_incident}
```

Without entity linking, retrieval returns **silo fragments** that clash (Part 12). Context assembly needs **entity-first routing** before semantic search.

## Part 26 — Context observability & debugging

**Blind spot:** v1.1 listed eval metrics but not **runtime provenance** — when agent is wrong, operators can't answer "which context layer caused this?"

### 26.1 What to trace per LLM call (LangSmith pattern)

| Field | Purpose |
|-------|---------|
| `token_breakdown` | system / tools / history / retrieved / user / tool_results |
| `retrieval_queries` | actual embed/search strings (post-enrichment) |
| `retrieved_chunk_ids` | corpus paths + scores + trust level |
| `retrieval_gate_result` | 7-test pass/fail per test |
| `compaction_event` | what was dropped vs preserved |
| `trust_tags` | T0–T4 per injected block |
| `topic_state_snapshot` | active/abandoned topics |
| `session_id` / `thread_id` | cross-turn grouping |

### 26.2 Debug workflow when output is wrong

1. **Classify failure mode** (Part 12) — poison / distract / confuse / clash / cascade  
2. **Ablation from trace** — re-run with layer removed (no semantic corpus, no history, no tools)  
3. **Retrieval post-mortem** — were right chunks in top-k? Wrong chunks scored higher?  
4. **Compaction audit** — was lost constraint in dropped segment?  
5. **Feed to outcome corpus** — outcome label + root cause layer → outcome-labeled store  

## Part 27 — Memory write economics (agent-native evaluation)

arXiv:2606.24775 (*Are We Ready For An Agent-Native Memory System?*) — evaluates memory systems on **operational cost**, not just accuracy:

**Findings relevant to context building:**

| Mechanism | Utility | Latency/query | Risk |
|-----------|---------|---------------|------|
| **LightMem** (segmented compress + bounded hybrid retrieve) | 48.3 | ~3.7s | Best efficiency frontier |
| **MemTree** (path-local tree aggregation) | 63.5 | ~15.9s | Good utility/cost |
| **Mem0** | 21.4 | ~35.9s | Simple but write cost grows |
| **Graph-wide consolidation** (Cognee, Zep) | 84+ | 116–155s | High utility, **heavy global rewrite** |

**O7 principle:** **Localized maintenance** beats **global memory rewrite**. Systems that reorganize entire graph on each write don't scale.

**Agent implications:**
- Prefer **append + localized update** (single doc/chunk/fact) over whole-vector-index restructure  
- **Async memory writes** — don't block orchestrator turn on Mem0 extract + embed  
- **Raw chunk retrieval** sometimes matches fancy extraction pipelines in accuracy — don't over-engineer extract if corpus is clean (agent-native memory eval)  
- Escalate to graph memory **only when** multi-hop benchmarks fail flat RAG — not by default  

---

## Part 29 — Temporal RAG & conflict resolution

**Blind spot:** v1.2 treated corpus chunks as timeless facts. Agent research, handoffs, and patterns **version over time** — flat cosine RAG retrieves stale + current together → **context clash** (Part 12).

### 29.1 The recency bias failure

Standard RAG ranks by semantic similarity, not validity interval. A 2024 policy doc can outrank the 2026 update because wording is more similar to the query. VersionRAG benchmark: naive RAG **58%** on version-sensitive questions vs **90%** version-aware pipeline (Huwiler et al.; SmartVector arXiv:2604.20598).

**Recency bias is a belief-revision error**, not a ranking tweak (AegisRAG-POE practitioner frame): must distinguish support, contradiction, succession, coexistence, refinement.

### 29.2 Conflict types (ConflictRAG, arXiv:2605.17301)

| Type | Example | Resolution strategy |
|------|---------|---------------------|
| **Factual** | "API uses REST" vs "API uses GraphQL" | Detect pair; prefer verified/tool-grounded source |
| **Temporal** | Old vs new policy | Rank by `valid_from` / doc date; note evolution |
| **Opinion** | Subjective viewpoints | Multi-perspective synthesis + attribution |
| **No conflict** | Complementary chunks | Merge normally |

ConflictRAG two-stage detector: **88.7% F1** binary conflict detection; type classification hardest on opinion (F1 0.685).

### 29.3 Production patterns

**Metadata-first (Phase 1 — implement now):**
- Every corpus chunk: `source_path`, `indexed_at`, `doc_date`, `supersedes`, `intent_version`  
- Filter: `doc_date >= cutoff` OR `status: current` for mutable domains  
- On clash: inject **both with dates** + rule "prefer newer verified source"

**Graph/temporal (Phase 2 — pilot):**
- T-GRAG (ACM MM 2025): time-stamped graph + temporal query decomposition  
- SmartVector: confidence decay + consolidation cron + contradiction edges  

**Fail-closed verification (high stakes):**
- AegisRAG-style: abstain if temporal consistency check fails  
- Never write unresolved conflicts to Mem0 as facts (quarantine)

## Part 30 — Multimodal & structured-data context routing

v1.2 left multimodal as a one-line gap. Production pattern: **route by modality and structure**, don't embed everything as text.

### 30.1 Modality routing table

| Input type | Context strategy | Never do |
|------------|------------------|----------|
| **Text / MD / research** | Hybrid semantic RAG | Dump full corpus |
| **Code** | Grep/AST JIT + optional semantic (Profile D) | Embed-only without grep validation |
| **PDF / scan** | OCR → structured text → chunk; or vision model summary + pointer | Raw PDF bytes in prompt |
| **Image (UI, diagram)** | Vision API → text description in context; store image externally | Assume model sees attachment without call |
| **Audio / video** | Transcript chunk + timestamp pointers | Full transcript in every turn |
| **Tabular / SQL** | **SQL agent route** — schema slice + sample rows + generated query | Serialize table as prose RAG |
| **Live API JSON** | Tool result T2 — structured fields only | HTML scrape as context |

**Enterprise pattern (eSapiens arXiv:2506.16768; AgentMaster):** supervisor routes to IR agent, SQL agent, image agent, or general — each with **scoped context package**, not monolithic window.

### 30.2 Multimodal budget rules

- **Pointer-first:** URL/path + 1-line description; load on demand  
- **Vision calls are expensive** — cap images per turn (typically 1–3)  
- **OCR quality gate** — low-confidence OCR → flag T3, don't promote to T2  
- **Unified entity index** (Part 25) links doc_id → image assets → SQL tables  

### 30.3 Current state

- Semantic corpus = text-first ✓  
- MCP tools = structured live data ✓  
- **Gap:** no image/chart pipeline in orchestrator; no Text2SQL route for operational databases — add when product requires, not before flat text RAG is measured  

---

## Part 31 — Parent-child retrieval & late interaction

v1.0–v1.2 said "structure-aware chunking" but not the **search unit ≠ return unit** pattern — major production upgrade.

### 31.1 Parent-child (small-to-big)

```
Index: child chunks (100–300 tokens) — precise embeddings
Store: parent sections (1000–2000 tokens) — generation context
Query: match children → dedupe parents → return 1–2 parents to LLM
```

**Why:** child hits precise span; parent gives surrounding context — fixes chunk-boundary hallucination. Reported **+15–30%** on context-dependent QA vs flat chunking (production literature 2025).

**Defaults:** 200-token children under 1500-token parents; dedupe when multiple children share parent.

**Vector index operations:** research MD → chunk by heading (parent) + paragraph (child); code → function (parent) + block (child) per Cursor pattern.

### 31.2 Late interaction (ColBERT family)

When single-vector + BM25 still misses term-sensitive matches:
- **ColBERT:** multi-vector per token; MaxSim scoring  
- **ColBERTv2 + PLAID:** production-viable latency at 100M+ scale (Timeless 2025 survey)  
- **Use when:** hybrid retrieval below quality bar on identifier-heavy corpus  
- **Skip when:** hybrid already clears bar — index size 6–10× larger  

**Stack position:** candidate generation (BM25+dense) → **ColBERT rerank** OR cross-encoder on top-20 — pick by latency budget (Part 35).

### 31.3 Auto-merging / sentence window

- **Sentence window:** retrieve sentence, expand ±N sentences  
- **Auto-merging:** hierarchical merge when multiple adjacent children hit  
- **Adaptive (2025):** expand only when query complexity warrants — saves ~40% latency on simple queries (~ practitioner reports)

---

## Part 32 — Privacy-as-context (GDPR / erasure)

**Critical blind spot:** context/memory research focuses on recall; **compliance is a context design constraint**.

### 32.1 The deletion failure mode

User requests erasure (GDPR Art. 17). Team deletes Postgres rows — **cannot find vectors** where PII was embedded into floats without `subject_id` metadata (Velsof 2026; Astraea Counsel 2026). Agent-written scratch files / Mem0 exports without external index = **undeletable**.

### 32.2 Requirements at write time (non-negotiable)

Every memory write (corpus ingest, Mem0, personal archive, chat summary):

| Field | Purpose |
|-------|---------|
| `subject_id` | Fan-out delete target |
| `data_class` | PII / internal / public |
| `source_event_id` | Audit trail |
| `retention_policy` | TTL / legal hold |
| `embedding_pipeline_version` | Drift + migration (Part 24) |

**Tag at write, not at delete.** Erasure = `DELETE WHERE subject_id = X` across vector + graph + logs + file index.

### 32.3 Personal archive

scoped personal memory personal source already scoped — extend pattern to **all** user-specific context. Never embed user PII into shared corpus without redaction. Agent memory tools (Anthropic memory beta) require **external index**: `user_id → [memory_file_ids]`.

### 32.4 Eval addition

**ForgetEval pattern:** after deletion drill, adversarial queries must not surface erased facts — standard RAG eval misses this entirely (Part 33).

---

## Part 33 — Eval vs production context divergence

**Blind spot:** v1.2 listed eval metrics but not **eval design failure** — benchmarks that lie about production.

### 33.1 Common divergences

| Eval setup | Production reality | Lie produced |
|------------|-------------------|--------------|
| Clean golden chunks injected | Noisy retrieval + wrong siblings | Overstates RAG value |
| Retrieval-only metrics | Agent multi-round + tool noise | Misses cascade failures |
| Static single-turn | Topic switches + compaction | Misses clash/distraction |
| No temporal metadata | Stale docs in index | Overstates accuracy |
| Full context in eval | External memory in prod | Wrong cost/quality trade |
| No tool outputs in context | Tool flood every turn | Underestimates confusion |

### 33.2 Production-faithful eval protocol

1. **End-to-end agent task** — same context assembly + tools + budget as prod  
2. **Retrieval ablation** — measure delta when vector index/history/tools removed  
3. **Multi-round stress** — HaystackCraft-style enforced rounds (Part 8.3)  
4. **Conflict injection** — pair stale + current doc in index  
5. **Compaction mid-task** — constraint-recall audit after summarize  
6. **Deletion drill** — ForgetEval after erasure  
7. **Token/cost accounting** — accuracy per 1K tokens, not accuracy alone  

**Rule:** no context architecture decision from retrieval-only nDCG alone.

---

## Part 34 — Procedural constraint layer as context spine

Craft rules and executable constraints were referenced throughout but never formalized as **context layer T0** — distinct from document RAG.

### 34.1 Three knowledge types in every agent turn

| Type | Source | Stability | Context role |
|------|--------|-----------|--------------|
| **Parametric** | Model weights | Frozen per deploy | Head facts, reasoning |
| **Procedural** | Intent/spec artifacts, patterns, skills | Versioned | **HOW** — constraints, tests, anti-patterns |
| **Contextual** | Semantic corpus, chat, tools, RAG | Mutable per turn | **WHAT** — facts for this task |

**Thesis backbone** (`WHEN_TO_RELY_ON_LLM_ALONE.md` + `CONTEXT_BEATS_MODEL_SEMANTIC_VS_GREP.md`): reliable specific/current/long-tail facts must be contextual; procedural rules must be **executable constraints**, not prose summaries of research.

### 34.2 Constraint injection protocol

```
[T0 — BINDING CONSTRAINTS v{version}]
  - constraint list (low entropy)
  - conflict-prone anti-pattern anchors
  - active segment only (if many constraints)
[NOT: full intent YAML dump — extract active segment only]
```

**Why structured constraints beat RAG for craft rules:** near-zero interpretive entropy; tests attached; survives compaction if pinned in T0 static block (Part 13).

### 34.3 Research → context pipeline (canonical)

```
Research MD (T3, dated)
  → patterns YAML (T1, distilled)
    → prompt constants (templates)
      → intent/spec artifacts (T0, verified constraints)
```

**Anti-pattern:** inject raw research `.md` into agent context when patterns exist — distraction + clash with distilled rules.

---

## Part 35 — Retrieval latency SLA & quality-delay tradeoff

METIS (Microsoft SOSP 2025) and production playbooks: retrieval is not "max quality" — it's **quality within SLA**.

### 35.1 Typical production budget

| Stage | Latency target | Notes |
|-------|----------------|-------|
| Embed query | 20–50ms | Cache query embeds |
| BM25 + dense parallel | 30–80ms | Metadata filter first |
| RRF merge | <10ms | |
| Rerank top-20 | 50–150ms | Cross-encoder or ColBERT |
| **Total retrieval** | **100–200ms** | Hard cap for interactive agent |
| Parent expand | +10–30ms | KV lookup |

Exceed budget → drop rerank depth or k before dropping hybrid search.

### 35.2 Quality-delay knobs (ordered)

1. Reduce k (1–3)  
2. Metadata pre-filter (narrow corpus)  
3. Skip rerank (dense+BM25 only) — acceptable for code grep route  
4. Cache frequent queries (semantic cache)  
5. Async prefetch next-likely chunks (only if hit rate proven)  

## Part 37 — Parallel agents & shared-state races

**Blind spot:** v1.3 covered sub-agent **isolation** but not **concurrent writes** to shared context — a distinct failure mode.

When multiple agents run in parallel (Cursor Agent Teams, DeLM, agent future parallel workers), they may read/write the same shared state. Second write **silently overwrites** first — no exception (agenthold 2026; S-Bus arXiv:2605.17076).

### 37.1 Structural race conditions (SRC)

S-Bus names **Structural Race Conditions**: write-write and cross-shard stale-read conflicts that corrupt output without surfacing errors. LangGraph/CrewAI historically lacked write-ownership semantics.

### 37.2 Mitigation patterns

| Pattern | Mechanism | When |
|---------|-----------|------|
| **Optimistic concurrency (OCC)** | Read version N; write only if still N; else retry | Shared KV / MCP state store (agenthold) |
| **Verified shared context (DeLM)** | Agents write **admitted** compact updates to shared C; task queue T | Test-time scaling; parallel research |
| **DACS focus mode** | Orchestrator holds full context for **one** agent; others get registry summaries only | Steering parallel agents (arXiv:2604.07911) |
| **Sub-agent summary return** | No shared write — only parent merges | Agent default today |
| **Append-only event log** | Conflicts resolved by ordering + human merge | Audit-heavy domains |

**Agent rule today:** sub-agents via sub-agent delegation don't share write path — **low race risk**. Risk emerges if parallel background jobs or multi-orchestrator sessions write same storage rows without versioning.

### 37.3 Write admission criteria for shared context

Before promoting any agent output to shared memory (semantic corpus, Mem0, topic state):

1. **Schema-valid** structured payload  
2. **Version check** (OCC) if updating existing key  
3. **Provenance tag** (agent_id, turn, trust level)  
4. **No unresolved conflict** with T0/T2 sources (Part 29)  

---

## Part 38 — Instruction stack & filesystem-as-context

v1.3 treated binding constraints as T0 but not the **full instruction hierarchy** production agents use — policy files, hooks, and skills compete with RAG for the same token budget.

### 38.1 Priority stack (Anthropic / Claude Code / IDE agents, 2026)

| Priority | Source | Context cost | Survives compaction? |
|----------|--------|--------------|----------------------|
| 1 | **Hooks** (deterministic, outside window) | ~0 | N/A — re-runs |
| 2 | **Managed/admin settings** | Low | Yes |
| 3 | **System prompt / output style** | Fixed | Yes |
| 4 | **Root policy files** (AGENTS.md, project rules) | High — always on | **Yes** — re-read from disk |
| 5 | **Path-scoped rules** (rules with `paths:` / glob scope) | On-demand | **No** — until matching file read |
| 6 | **Skills** (on invoke) | Burst; capped on compact | Partial — budget limits |
| 7 | **Subagent return** | Summary only | Parent history only |
| 8 | **RAG / semantic corpus / chat** | Variable T3 | Per turn |

**Key insight:** Project rules loaded as **user message**, not system prompt — rules can be "ignored" under pressure; **hooks enforce** what must never be violated (Anthropic steering docs; Start Debugging 2026).

### 38.2 Compaction survival rules

After `/compact` or auto-compact:
- **Survives:** root policy files, unscoped rules, auto-memory index, system prompt  
- **Lost until re-triggered:** path-scoped rules, nested policy files, invoked skill bodies (may drop oldest)  
- **Rule:** if constraint must survive long sessions → **root policy file**, not chat instruction  

**Generic mapping:**

| Layer | Examples |
|-------|----------|
| Root policy | AGENTS.md, CONTRIBUTING rules, repo-level agent instructions |
| Path-scoped rules | Directory-scoped craft rules, glob-triggered constraints |
| Skills | On-demand skill packages (Agent Skills standard) |
| Auto-memory | Mem0 / personal archive (with index cap) |
| Hooks | CI gates, pre-commit, deterministic validators (outside LLM) |

### 38.3 Anti-patterns

- 1000-line root policy file — use path-scoped rules (200-line target for always-on)  
- Chat-only instructions for craft rules — lost on compact  
- Duplicating same rule in rules + corpus + prompt — **clash** (Part 12)  

---

## Part 40 — Multilingual & cross-lingual context

Multilingual deployments often mix **Spanish + English**. v1.3 did not address language-mixed retrieval.

**Findings (XRAG EMNLP 2025; CroSearch-R1 arXiv:2604.25182; EMNLP 2025 xMRC):**
- Core failure is **reasoning over retrieved cross-lingual content**, not generation language  
- Monolingual retrieval often **underperforms** vs combined EN + native search  
- Same-language-first retrieval, then expand — reduces cross-lingual interference  

**Agent rules:**
- Vector index metadata: `lang` field on chunks  
- Query language detect → prefer same-lang filter first  
- Spanish-language follow-ups: enrich with topic state (already in context assembly pipelines) — extend with **language tag**  
- Patterns/intents: English (T0/T1); user-facing output: match user language  
- **Gap:** no explicit cross-lingual rerank — acceptable until deployments serve non-English corpus at scale  

---

## Part 41 — Human-in-the-loop context gates

**Blind spot:** automatic Mem0/corpus writes promote **unverified** agent beliefs to long-term context (poisoning path).

**Production pattern (LangGraph HITL; CEUR 2025 agent platform):**

| Gate | Trigger | Action |
|------|---------|--------|
| **Dangerous action** | DB write, bulk send, delete | `interrupt()` — user approves |
| **Memory promotion** | Extract fact for long-term store | Review queue or auto if T2-verified |
| **Sensitive generation** | Compliance/finance | Human curates retrieved set before generate |
| **Compaction milestone** | Pre-compact | User steers `/compact` summary (Claude Code) |

**Agent recommendation:**
- **Auto-write:** tool-verified T2 facts, outcome-labeled corpus entries  
- **Queue for human review:** personal archive writes, cross-session preference changes, semantic index ingest from agent output  
- **Never auto-write:** contradicted facts, low-confidence retrieval, persona inferences  

Execution-derived oracles + hooks = deterministic gates; HITL = semantic/high-stakes gates.

---

## Part 43 — Implementation roadmap

**Do not add research passes.** Execute Part 42:

**Phase A (orchestrator context hardening):** 1, 2, 3, 4, 10  
**Phase B (corpus hygiene):** 5, 6, 7, 14  
**Sprint C (scale & safety):** 8, 11, 12, 13  
**Pilots (product-triggered):** GraphRAG (Part 29), multimodal (Part 30), learned curator (Part 23)  

---

## Sources

### Official / industry (verified 2026-06-25)

- Anthropic — [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) (Sep 2025)
- Anthropic — [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- LangChain — [Context engineering for agents](https://www.langchain.com/blog/context-engineering-for-agents) (Write/Select/Compress/Isolate)
- OpenAI — [Agents SDK Sessions](https://openai.github.io/openai-agents-python/sessions/)
- OpenAI — [Responses compaction session](https://openai.github.io/openai-agents-python/ref/memory/openai_responses_compaction_session/)
- MCP — [modelcontextprotocol.io](https://modelcontextprotocol.io/)
- Mem0 — [Agentic workflows with persistent memory](https://mem0.ai/blog/agentic-workflows-with-persistent-memory); [docs](https://docs.mem0.ai/integrations/langgraph)
- Chroma — [Context rot research](https://www.trychroma.com/research/context-rot) (2025)
- Drew Breunig — [How Long Contexts Fail](https://www.dbreunig.com/2025/06/22/how-contexts-fail-and-how-to-fix-them.html); [How to Fix Your Context](https://www.dbreunig.com/2025/06/26/how-to-fix-your-context.html) (Jun 2025)
- OpenAI — [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)
- Atlan — [Context window management guide](https://atlan.com/know/ai-agent/ai-agent-context/how-to-implement-context-window-management-ai-agents/) (2026)
- Red Hat Emerging Tech — [Tool RAG](https://next.redhat.com/2025/11/26/tool-rag-the-next-breakthrough-in-scalable-ai-agents/) (Nov 2025)
- TrueFoundry — [MCP Tool Poisoning CVE-2025-54136](https://www.truefoundry.com/blog/blog-mcp-tool-poisoning-gateway-defense)
- Max Mendes — [AI Agent Security: Runtime Blind Spot](https://maxmendes.dev/en/blog/ai-agent-security-runtime-blind-spot)
- Tian Pan — [Cascading Context Corruption](https://tianpan.co/blog/2026-04-14-cascading-context-corruption-in-long-running-agents) (Apr 2026)
- Alex Chernysh — [Query transformation for RAG](https://alexchernysh.com/blog/query-transformation-for-rag) (2026)
- LangSmith — [Observability concepts](https://docs.langchain.com/langsmith/observability-concepts); [Debugging deep agents](https://www.langchain.com/blog/debugging-deep-agents-with-langsmith)
- Redis — [Long-term memory architectures for agents](https://redis.io/blog/long-term-memory-architectures-ai-agents/)
- Microsoft Azure — [Vector drift in production RAG](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/vector-drift-in-azure-ai-search-three-hidden-reasons-your-rag-accuracy-degrades-/4493031)
- Tian Pan — [Embedding drift in long-lived RAG](https://tianpan.co/blog/2026-04-19-embedding-drift-long-lived-rag-systems) (Apr 2026)
- Velsof — [LLM memory architecture patterns / GDPR erasure](https://www.velsof.com/ai-automation/llm-memory-architecture-patterns/) (2026)
- Tian Pan — [GDPR-ready AI agent architecture](https://tianpan.co/blog/2026-04-10-gdpr-ai-agents-compliance-architecture) (Apr 2026)
- Timeless — [Production RAG beyond naive chunking](https://www.tmls.nyc/research/production-rag-beyond-chunking) (ColBERT, parent-child)
- Anthropic — [Claude Code context window](https://code.claude.com/docs/en/context-window); [Steering: skills, hooks, rules](https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more)
- agenthold — [Shared versioned state / OCC for agents](https://github.com/edobusy/agenthold)

### Academic (arXiv IDs verified)

- Lewis et al. 2020 — RAG — [2005.11401](https://arxiv.org/abs/2005.11401)
- Liu et al. 2023 — Lost in the middle — TACL 2024 — [2307.03172](https://arxiv.org/abs/2307.03172)
- Mallen et al. 2023 — When not to trust LMs — [2212.10511](https://arxiv.org/abs/2212.10511)
- Asai et al. 2023 — Self-RAG — [2310.11511](https://arxiv.org/abs/2310.11511)
- Jiang et al. 2023 — FLARE — [2305.06983](https://arxiv.org/abs/2305.06983)
- Jeong et al. 2024 — Adaptive-RAG — [2403.14403](https://arxiv.org/abs/2403.14403)
- Thakur et al. 2021 — BEIR — [2104.08663](https://arxiv.org/abs/2104.08663)
- Packer et al. 2023 — MemGPT / hierarchical memory — [2310.08560](https://arxiv.org/abs/2310.08560)
- Chhikara et al. 2025 — Mem0 — [2504.19413](https://arxiv.org/abs/2504.19413)
- Hierarchical memory theory — [2603.21564](https://arxiv.org/abs/2603.21564)
- RAG Fusion production study — [2603.02153](https://arxiv.org/abs/2603.02153)
- Claude Code design space — [2604.14228](https://arxiv.org/abs/2604.14228)
- Oracle-SWE — [2604.07789](https://arxiv.org/abs/2604.07789)
- CodeRAG-Bench — [2406.14497](https://arxiv.org/abs/2406.14497)
- SRACG — AAAI 2026 (cited in RAG_SEMANTIC_INDEXING_OUTPUT_QUALITY_RESEARCH_2025_2026.md)
- arXiv:2503.20589 — in-context vs similar-domain retrieval
- arXiv:2511.05302 — top-k degradation in code review
- METIS — Microsoft SOSP 2025 — quality-delay RAG configuration
- HaystackCraft — arXiv:2510.07414 — agentic long-context eval; multi-round cascading errors
- CHARM — arXiv:2606.04435 — cascading hallucination detection in agentic RAG
- MCP threat model — arXiv:2603.22489 — 57 threats; tool poisoning empirical
- Tool-to-Agent Retrieval — arXiv:2511.01854 — joint tool+agent vector space
- Toolshed — SCITEPRESS 2025 — RAG-Tool Fusion (+46–56% over BM25)
- ToolReAGt — ACL KnowLLM 2025 — iterative tool retrieval (+8.9% recall@5)
- RAG poisoning — arXiv:2507.08862
- HyDE — Gao et al. 2022 (hypothetical document embeddings)
- Step-Back prompting — Zheng et al. 2023
- Agent-native memory evaluation — arXiv:2606.24775 — operational cost vs utility
- Effective context utilization — arXiv:2603.04814 — nominal window vs usable reasoning length
- ActiveContext — arXiv:2604.11462 — RL ContextCurator + frozen executor
- AdaCoM — arXiv:2605.30785 — agent-compatible context management; fidelity–reliability tradeoff
- Context-ReAct / LongSeeker — arXiv:2605.05191 — elastic meta-operations on context
- ARC — ACL Findings 2026 — active reflection-driven context management
- Sculptor — arXiv:2508.04664 — active context management tools; proactive interference
- ConflictRAG — arXiv:2605.17301 — conflict detect + type-adaptive resolution
- SmartVector / version-aware RAG — arXiv:2604.20598 — temporal confidence + consolidation
- T-GRAG — ACM MM 2025 — temporal GraphRAG
- eSapiens — arXiv:2506.16768 — multimodal enterprise routing (IR/SQL/vision)
- VersionRAG — Huwiler et al. (cited in SmartVector) — 58% vs 90% on version-sensitive QA
- DeLM — arXiv:2606.10662 — decentralized shared context + task queue
- S-Bus — arXiv:2605.17076 — structural race conditions in multi-agent state
- DACS — arXiv:2604.07911 — dynamic attentional context scoping for parallel agents
- XRAG — EMNLP Findings 2025 — cross-lingual RAG benchmark
- CroSearch-R1 — arXiv:2604.25182 — cross-lingual retrieval strategy
- xMRC cross-lingual — EMNLP 2025 main.1161 — mechanism analysis

## Changelog

- **v1.5 FINAL — 2026-06-25** — Corpus housekeeping: consolidated companion research into canonical folders; cross-linked `RAG_ROUTING_AND_PARADIGM_SELECTION_2026.md`; cross-linked paradigm selection research. **Research + corpus closed.**
- **v1.4 FINAL — 2026-06-25** — Fourth pass: parallel shared-state races (Part 37); instruction stack / rules files (Part 38); agent context planes (Part 39); multilingual context (Part 40); HITL gates (Part 41); **implementation gap map** (Part 42); roadmap → Part 43. **Research closed** — further expansion is implementation not literature.
- **v1.3 — 2026-06-25** — Third blind-spot pass: temporal RAG + conflict resolution (Part 29); multimodal/structured routing (Part 30); parent-child + ColBERT (Part 31); privacy/GDPR-as-context (Part 32); eval≠prod divergence (Part 33); procedural constraint T0 spine (Part 34); retrieval latency SLA (Part 35); roadmap → Part 36. Research synthesis marked complete; remaining items are implementation.
- **v1.2 — 2026-06-25** — Second blind-spot pass: accuracy/latency/cost map (Part 22); active context management vs passive compact (Part 23); embedding drift monitoring (Part 24); cross-session/cross-system cold start (Part 25); context observability (Part 26); memory write economics (Part 27); expanded Part 11 audit + Part 9 proven table; roadmap → Part 28.
- **v1.1 — 2026-06-25** — Blind spots audit (Part 11); Breunig four failure modes (Part 12); token budget + prompt caching (Part 13); query transformation routing (Part 14); trust boundaries & MCP/RAG poisoning (Part 15); cascading corruption + CHARM/HaystackCraft (Part 16); tool RAG (Part 17); multi-agent propagation (Part 18); negative selection (Part 19); memory decay & corpus hygiene (Part 20); expanded eval + proven table; roadmap → Part 21.
- **v1.0 — 2026-06-25** — Initial master synthesis: corpus gap review, external research pass (Anthropic/LangChain/OpenAI/Mem0/Chroma/papers), intent profiles, source routing, hygiene framework, agent stack recommendation.
