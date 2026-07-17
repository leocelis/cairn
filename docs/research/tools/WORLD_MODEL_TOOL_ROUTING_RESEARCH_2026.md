# World Model — Tool Routing Research (2026)

**Research date:** 2026-06-25  
**Status:** Living document — v1.1  
**Scope:** World Model as the **entity-grounding layer** for agent tool build, selection, and chaining — **agnostic** (any agent platform). Pure research.  
**Related research:** agent tool routing literature (2026)  
**Frontiers (multimodal, federated, multilingual, GraphRAG):** see entity-resolution and graph-database research in this corpus  
**Product rationale:** entity-grounded routing over domain semantics (see Part 2)

---

## Executive summary

**World Model** (agent-system sense) = structured map of **entities, relationships, constraints, and mutable state** in a domain — used to **ground tool arguments and tool selection** before the LLM improvises IDs, policies, or cross-system links from text alone.

This is **not** Yann LeCun / AMI Labs “world models” (3D physical simulation from sensor data). Agent World Model is closer to:

- **Domain ontology + entity registry + state slices**
- **Knowledge graph** for multi-hop “which object, which tool, which ID”
- **Constraint layer** for valid tool transitions (state machines, invariants)

**Core thesis:** Models and SDKs commoditize reasoning and tool-calling primitives; **proprietary domain semantics** remain the durable moat. World Model turns routing from “pick by description similarity” into “pick by **entity type + state + rules**.”

**2026 academic alignment:** KG-grounded agents (Graph Explorer ACL 2026, Chain-of-Relations, GCR arXiv:2502.13247) show the same failure mode agents see: **correct tool name, hallucinated entity ID** — fixed by **visibility-grounded** supervision (tool args may only reference entities visible in context).

---

## Part 0 — Term disambiguation

| Term | Meaning | Tool routing relevance |
|------|---------|------------------------|
| **Agent World Model** | Domain entity graph + rules + mutable state | ✓ Core of this doc |
| **LeCun / AMI “world model”** | Predictive model of physical 3D environment | ✗ Different field |
| **Model-based RL world model** | Learned env simulator for planning | ◐ Analog for “simulate before write tool” |
| **World model (cognitive science)** | Mental model of how a system works | ◐ Informs UX/explainability |
| **RAG corpus** | Unstructured chunks | Complement — not substitute |
| **Tool RAG** | Retrieve tool schemas by query | Downstream of entity resolution |
| **Semantic corpus / outcome loop** | Semantic memory over documents | T3 until entity-linked |

---

## Part 1 — Problem: tool routing without a World Model

### 1.1 Symptom taxonomy

| Symptom | Root cause (no World Model) | Tool-layer manifestation |
|---------|----------------------------|---------------------------|
| Same question, different answers | No canonical entity ID | `get_card` vs wrong card |
| Agents contradict each other | Silo context per sub-agent | Financial vs research disagree on “MELI” |
| Invalid tool calls pass schema | Schema valid, semantics wrong | `update_trello_card(id=hallucinated)` |
| Wrong tool selected | Description overlap | Route to business agent for stock query |
| Cross-system failure | No entity linking | CRM name ≠ Trello card title |
| Stale writes | Corpus chunk outdated | Policy from 2024 applied in 2026 |
| “Smart but stateless” | No persistent entity state | Re-fetch every turn; no continuity |

These appear in production agent deployments (user/dev symptoms). **Tool selection accuracy can be high while end-to-end task success is low** — BFCL-style benchmarks miss entity grounding.

### 1.2 Two failure layers

```
Layer A — Tool selection:  "which function?"     → Tool RAG, descriptions, coordinator routing
Layer B — Tool grounding:  "which entity IDs?"    → World Model (this doc)
```

Prior tool-routing research closed Layer A. **Layer B was stub-only (Part 27)** until this document.

### 1.3 MAST mapping

| MAST mode | World Model gap |
|-----------|-----------------|
| FM-1.1 Disobey task spec | Action on wrong entity still “completes” |
| FM-2.4 Information withholding | Sub-agent lacks entity slice |
| FM-2.6 Reasoning-action mismatch | Plan references entity not in registry |
| FM-3.2 Incomplete verification | No oracle on entity ID validity |

---

## Part 2 — Definition: World Model for tool routing

### 2.1 Components

| Component | Contents | Tool routing role |
|-----------|----------|-------------------|
| **Entity types** | `Customer`, `Ticket`, `Account`, `Article`, `Task` | Filter eligible tools (`write` only on types agent owns) |
| **Entity instances** | Canonical IDs + aliases + `valid_from`/`valid_to` | Tool argument binding |
| **Relations** | `Customer HAS Ticket`, `Invoice IN Account`, `Doc SUPERSEDES Doc` | Multi-hop tool chains |
| **Constraints / rules** | Invariants, allowed transitions, role permissions | Block or gate tool calls |
| **Mutable state** | Last-known field values + `state_as_of` timestamp | Pre-fill read tools; detect stale |
| **Goals/metrics** (optional) | Success criteria per workflow | Outcome gate inputs |

### 2.2 What it is not

- Not a giant prompt dump of all domain facts  
- Not a replacement for live tools (Trello MCP = mutable truth for “current”)  
- Not the same as document RAG (documents ≠ typed entities unless linked)  
- Not a second coordinator router (rules **constrain** tools; LLM still selects among valid set)

### 2.3 Design principles (business logic)

Design principles (entity-grounded tool routing):

1. **One world per domain** (finance, PM, creative) + shared ontology for cross-cutting entities (`User`, `Project`)  
2. **Grounded reasoning** — actions reference entity IDs and rules  
3. **Simulation before execution** where side effects are costly  
4. **Explainable outputs** — cite entity + rule triggered  
5. **Evolution** — schema versioned as domain grows  

---

## Part 3 — World Model in the tool stack

### 3.1 Stack position

```
User query
  → [Intent / mode]           (fresh-fetch vs reference — routing policy)
  → [World Model resolve]     ← THIS DOC: entities, relations, state slice
  → [Tool RAG loadout]        (entity-type-scoped tool shortlist)
  → [LLM tool select + args]  (within visible entity set)
  → [Execute tools]
  → [World Model update]      (post-tool state patch + contradiction check)
  → [Outcome gate]            (external oracle — state-of-art Part 28)
```

World Model sits **before Tool RAG** and **after intent classification**. Injecting tool schemas before entity resolution causes Layer A fixes to fail at Layer B.

### 3.2 Relation to other layers

| Layer | Question answered | World Model interaction |
|-------|-------------------|-------------------------|
| **Intent routing** | Reference vs standalone vs explicit agent? | Skips WM resolve for pure meta chat |
| **World Model** | Which entities + state? | Core |
| **Tool RAG** | Which tools visible this turn? | Filter by `entity_type`, `side_effect_class` |
| **Context/corpus** | Which docs support reasoning? | Retrieve **via entity ID**, not string match alone |
| **MCP/REST tools** | What is true now? | Refresh mutable state; WM stores pointer + timestamp |
| **Skills** | How to execute procedure? | `allowed-tools` scoped by entity domain |

### 3.3 Coordinator vs domain agent

| Level | World Model scope |
|-------|-------------------|
| **Coordinator** | Cross-domain entities (`Project`, `User`, active `Topic`); routes to domain agent tools |
| **Domain agent** | Domain entity subgraph (all `Ticket` entities for project X); micro-tool args |
| **Sub-agent via sub-agent delegation** | **Entity slice package** — must include resolved IDs (Part 20 state-of-art) |

Multi-hop agent pattern: coordinator → domain agent → micro-tools. World Model **narrows at each hop**, not copied wholesale.

---

## Part 4 — Entity-first tool routing pipeline

### 4.1 Resolve phase

```
Input: user text + session entity carryover + topic state
  1. Mention detection (NER / LLM extract — research: prefer structured when available)
  2. Alias lookup → canonical entity_id (corpus metadata, prior session, registry)
  3. Ambiguity: same string → multiple IDs → ONE clarifier or disambiguation tool
  4. Bind relation closure: for task, fetch 1-hop related entities (card → list → board)
  5. Emit EntityContextPackage { ids, types, state_as_of, visibility_set }
```

**Visibility set:** IDs the model may use in tool args this turn — Graph Explorer (ACL 2026 Findings 387) proves agents fail when args reference IDs **not in prompt**. Same rule for agents: **no tool arg outside `visibility_set`.**

### 4.2 Select phase (tool + agent)

```
Input: EntityContextPackage + intent
  1. Filter agent tools: domain matches entity types (finance agent iff `Portfolio`/`Symbol` in package)
  2. Tool RAG within filtered set (Part 18 state-of-art)
  3. CMTF / causal filter: preconditions match entity state (e.g. card.status == "open" for move tool)
  4. LLM chooses among k remaining tools
```

### 4.3 Bind phase (arguments)

| Strategy | When | Example |
|----------|------|---------|
| **Pre-fill** | Single unambiguous entity | `card_id` injected; model confirms |
| **Enum from visibility** | k candidates in set | Args constrained to listed IDs |
| **Validate post-hoc** | Model proposes ID | Server rejects if ∉ visibility_set |
| **Tool-grounded refresh** | Mutable state | `get_card` before `update_card` |

### 4.4 Execute + update phase

```
Tool result → parse affected entities
  → patch World Model state slice (with state_as_of = now)
  → if contradicts vector index / T0 rule → flag conflict (ConflictRAG types — context Part 29)
  → if write tool → outcome gate before promoting to long-term corpus
```

### 4.5 Cross-system entity index (enterprise pattern)

From context Part 25.2:

```
Entity: "customer Acme"
  → { crm_id, board_id, channel_id, corpus_doc_ids[], asset_symbols[] }
```

Without this index, each tool system is a **cold silo** — Tool RAG picks correctly, args attach to wrong silo's ID namespace.

**Research recommendation:** unified entity index is **orthogonal to embedding model** — graph/metadata layer, not vector layer.

---

## Part 5 — Representation options (research comparison)

Open design question: schema-only vs graph vs state machines. Research comparison:

| Representation | Strengths | Weaknesses | Tool routing fit |
|----------------|-----------|------------|------------------|
| **JSON schema / registry** | Simple; versionable; visibility sets easy | Weak multi-hop | **Agent default (v1)** — entity types + instances |
| **Property graph** | Multi-hop; audit trail; GraphRAG | Ops complexity | Finance, legal, dependency graphs |
| **State machine per entity type** | Valid transitions = valid tools | Rigid; many machines | Workflow tools (card lifecycle, pipeline stages) |
| **RDF/OWL ontology** | Formal reasoning | Heavy; sparse tooling | Regulated domains only |
| **Event sourcing log** | Temporal truth; replay | Read path harder | Audit + “what did tools do” |

**Hybrid (research consensus):** typed registry (entities + relations) + **per-type state machines** for write tools + **event log** for mutations. Graph DB optional when multi-hop benchmarks fail flat registry.

### 5.1 Subset selection policy (what enters context)

| Policy | Mechanism | Token cost |
|--------|-----------|------------|
| **Task closure** | 1-hop neighbors of mentioned entities | Low–medium |
| **GraphRAG community** | Summarize cluster | Medium |
| **Full domain** | ✗ Never for coordinator | Explodes |
| **Lazy expand** | Tool returns new IDs → add to visibility next turn | Graph Explorer pattern |

Context Part 29 GraphRAG: use when **multi-hop entity traversal** required — org charts, citation nets, portfolio dependency. Not default for Trello card ops.

---

## Part 6 — Academic & industry landscape (2025–2026)

### 6.1 Knowledge-graph grounded tool use

| Work | Finding | Tool routing implication |
|------|---------|-------------------------|
| **Graph Explorer** (ACL 2026 Findings 387) | Visibility-grounded fine-tuning +22.5 Hit@1 | **Args ⊆ visible IDs** — hard rule |
| **Chain-of-Relations** (ACL 2026 Findings 2138) | Relation-centric > entity-centric KGQA | Traverse relations before committing entity args |
| **GCR** (arXiv:2502.13247) | Graph-constrained decoding +26.5% on GRBench | Constrain tool arg tokens to valid entity set |
| **GraphSearch / RAGSearch** (arXiv:2604.09666) | GraphRAG wins on multi-hop agentic search | Entity graph for research agents; flat RAG for simple lookup |
| **ConflictRAG** (arXiv:2605.17301) | 88.7% F1 conflict detection | WM update must detect factual/temporal clash |
| **VersionRAG / SmartVector** (arXiv:2604.20598) | 58% → 90% version-sensitive QA | Entity `valid_from` / `supersedes` on tool planning |

### 6.2 Simulation before execution

Model-based planning literature (RL world models) analog for tools:

| Pattern | Tool analog | Research status |
|---------|-------------|-----------------|
| **Dry-run / validate-only tool** | `preview_update_card` | Common in APIs; underused in agents |
| **Counterfactual check** | Outcome gate with shadow read | outcome-gated evaluation pattern |
| **Policy simulation** | Rule engine evaluates proposed args | Entity-grounded design: simulation before execution |

Not full physics simulation — **semantic simulation**: “if these args applied, which invariants break?”

### 6.3 What vendors will not ship

Industry pattern (2026):

- OpenAI/Anthropic improve tool calling, MCP, orchestration  
- They will **not** ship cross-system entity linking or custom domain ontology  
- World Model = **proprietary semantic layer** above vendor primitives  

---

## Part 7 — World Model × tool chain patterns

### 7.1 Sequential chains

Each step consumes **updated visibility_set**:

```
resolve(entities) → search_tool → new doc IDs in visibility
  → read_tool(doc_id) → extract entity mention
  → write_tool(entity_id) — only if ID ∈ visibility
```

Cascade corruption (Part 19 state-of-art): wrong entity at step 2 → wrong tool args at step 5. WM **checkpoint** after each tool: re-resolve mentions from tool output into registry.

### 7.2 Parallel read tools

Parallel OK when **disjoint entity sets** (Part 9). WM rule: parallel batch iff `visibility_set(tool_i) ∩ side_effects` disjoint and **no shared mutable entity** across writes.

### 7.3 Sub-agent `as_tool()`

Sub-agent must receive **EntityContextPackage**, not raw user string:

```yaml
entity_context:
  primary: { type: Ticket, id: abc123, state_as_of: 2026-06-25T12:00:00Z }
  related: [{ type: Project, id: proj_alpha }, { type: User, id: user_42 }]
  visibility_set: [abc123, proj_alpha, list_789]
  constraints: [card.status == open]
  freshness_required: [abc123]  # re-fetch via get_card before write
```

Aligns with the scoped sub-agent context-package multi-agent pattern — WM supplies the **entity** half; context doc supplies **memory** half.

### 7.4 Write tools and temporal rules

Mutable-domain tool chain (context Part 29):

1. WM provides candidate ID from corpus (**may be stale**)  
2. **Mandatory** refresh tool for `freshness_required` entities  
3. Conflict detector if refresh ≠ corpus  
4. Write tool with refreshed ID  
5. WM patch + event log entry  

---

## Part 9 — Evaluation (research metrics)

Entity-grounded tool metrics — refined for tool layer:

| Metric | Definition | Target (research) |
|--------|------------|-------------------|
| **Invalid entity arg rate** | Tool calls where ID ∉ registry or visibility | < 5% |
| **Stale write rate** | Writes without freshness refresh when required | < 2% |
| **Cross-agent entity consistency** | Same entity ID across sub-agents in one turn | > 95% |
| **Entity resolution recall** | Mention → correct canonical ID | > 90% on curated set |
| **Tool selection given grounded args** | Correct tool with pre-bound IDs | > 90% |
| **Contradiction rate** | Post-tool WM vs corpus conflict | Tracked; trending down |

**Eval oracles:** execution-derived (card exists, API 200) — not LLM-as-judge alone (IVD rule).

**Benchmarks to adapt:** Graph Explorer finish-or-fail protocol; BFCL format sensitivity + **entity perturbation** split; VersionRAG version-sensitive subset.

---

## Part 10 — Blind spots & research holes (World Model specific)

| # | Blind spot | Risk | Status in this doc |
|---|------------|------|-------------------|
| 1 | Confusing this WM with physical/LeCun WM | Wrong literature path | Part 0 |
| 2 | Tool RAG without entity resolve | Right tool, wrong ID | Part 3–4 |
| 3 | SPARQL-global vs agent-local visibility | Hallucinated args | Part 4, §6.1 Graph Explorer |
| 4 | Cross-system silo IDs | CRM ≠ Trello | Part 4.5 |
| 5 | Stale corpus → write args | Version clash | Part 7.4 |
| 6 | Sub-agent without entity package | FM-2.4 | Part 7.3 |
| 7 | Graph overkill for simple CRUD | Complexity tax | Part 5 |
| 8 | WM as second router | Duplicates coordinator | Part 2.2 |
| 9 | No simulation before irreversible write | Invalid transitions | Part 6.2 |
| 10 | Eval measures tool name only, not entity | False confidence | Part 9 |

**Still open (research):**

| Topic | Where expanded |
|-------|----------------|
| Multimodal entities (image/video/audio) | Multimodal routing research (future) |
| Federated WM multi-tenant | Federated entity-registry research (future) |
| GraphRAG vs registry routing | `GRAPH_DATABASES_AND_ENTITY_LIBRARIES_2026.md` |
| Cross-lingual entity aliases + tools | Multilingual routing research (future) |
| Learned entity linker depth | `ENTITY_RELATIONSHIP_RESOLUTION_RESEARCH_2026.md` |
| Tool-WM benchmark | Benchmark spec (future) |
| Code/symbolic WM | Symbolic entity research (future) |
| Streaming/async WM | Async state-sync research (future) |
| GDPR/provenance | Privacy/provenance research (see context Part 32) |

**Closed in this doc:** text-entity definition, stack position, pipeline, representations, core literature, eval metrics, blind spots 1–10.

---

## Part 11 — Reading order & cross-refs

1. This doc (World Model × tools — text entities)  
2. Entity-resolution + graph-database research in `docs/research/`  
3. `ENTITY_RELATIONSHIP_RESOLUTION_RESEARCH_2026.md` — entity grounding spine  
4. Cairn entity-first routing charter — product rationale  

---

## Sources

### Academic (verified IDs)

- Graph Explorer — ACL 2026 Findings [387](https://aclanthology.org/2026.findings-acl.387/)  
- Chain-of-Relations — ACL 2026 Findings [2138](https://aclanthology.org/2026.findings-acl.2138/)  
- Grounding LLM Reasoning with KGs — arXiv:[2502.13247](https://arxiv.org/pdf/2502.13247)  
- RAGSearch / GraphRAG agentic — arXiv:[2604.09666](https://arxiv.org/pdf/2604.09666)  
- ConflictRAG — arXiv:[2605.17301](https://arxiv.org/abs/2605.17301)  
- VersionRAG / SmartVector — arXiv:[2604.20598](https://arxiv.org/abs/2604.20598)

---

## Changelog

- **v1.1 — 2026-06-25** — Agnostic framing; pilot topics moved to companion research files.
- **v1.0 — 2026-06-25** — Initial dedicated research.
