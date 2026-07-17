# FalkorDB & Graphiti — Deep Research (2026)

**Scope:** Production-level deep dive on FalkorDB and Graphiti (getzep/graphiti)
for AI agent knowledge graph systems. Companion to
`GRAPH_DATABASES_AND_ENTITY_LIBRARIES_2026.md` (high-level comparison matrix).
**Date:** 2026-06-25
**Sources:** 8+ specialized research sub-agents; source code reads; GitHub issues; community.
**Confidence markers:** ✓ verified (directly from source/code) · ~ inferred · ? assumed

---

## Part 1: FalkorDB — Deep Dive

### 1.1 Architecture & Internals

#### GraphBLAS Sparse Matrix Representation

✓ verified (main research agent — FalkorDB architecture):

FalkorDB uses **SuiteSparse:GraphBLAS** in **CSC (Compressed Sparse Columns)** format.
The graph is stored as matrices: one global adjacency matrix + one per relationship type
(`FRIENDS`, `WORKS_AT`, etc.) + one diagonal per node label. Query execution is **linear algebra**,
not pointer-chasing:

- BFS = sparse matrix-vector multiply
- Friends-of-friends (2-hop) = matrix squaring
- Multi-hop = matrix power

SIMD/AVX acceleration via OpenMP. **Two orthogonal thread pools:**
- `THREAD_COUNT` — query-level parallelism (how many queries run concurrently)
- `OMP_THREAD_COUNT` — intra-query matrix parallelism (CPU lanes per query)

Key consequence: multi-hop queries (2–3 hops) are dramatically faster than record-by-record traversal
(Neo4j/JVM style) because they reduce to algebraic operations the CPU can pipeline.
FalkorDB p99 latency 344× faster than Neo4j on read-heavy workload is directly explained by this.

#### Memory Model

✓ verified (FalkorDB architecture): Nodes and edges live in contiguous **`DataBlock` structures**
with lazy deletion. Property storage is per-entity (`AttributeSet*` pointer), not columnar.
v4.14+ adds compact dual-representation (idle vs runtime), claiming **-30% memory overhead**.
`GRAPH.MEMORY <graph>` gives granular breakdown of memory per component.

**Fully in-memory.** 1M relationships ≈ **3GB RAM.**

| Nodes | Edges | ~RAM |
|---|---|---|
| 100K | 500K | ~1.5GB |
| 1M | 5M | ~15GB |

**No disk spillover.** When the graph exceeds available RAM, operations fail — there is no transparent
paging to disk. This is the primary sizing constraint for production deployments.

#### Persistence (AOF vs RDB)

✓ verified (FalkorDB architecture docs):

FalkorDB inherits Redis persistence via **virtual key sharding** (`VKEY_MAX_ENTITY_COUNT` = 100K entities/chunk,
hash-tagged for cluster co-location). Two persistence modes, configurable together:

| Mode | What it does | Tradeoff |
|---|---|---|
| **RDB** (snapshot) | Periodic point-in-time snapshot to `.rdb` file | Fast startup, potential data loss between snapshots (seconds to minutes) |
| **AOF** (append-only log) | Every write command appended to log; replayed on restart | `everysec`: up to 1s loss. `always`: zero loss but ~2× write overhead |

**Recommended for production:** `appendonly yes` + `appendfsync everysec`. This balances durability
(at most 1 second of data loss on crash) with write performance.

**Docker volume:** The official Docker image persists to `/var/lib/falkordb/data`. Mount a named volume:
```yaml
volumes:
  - falkordb_data:/var/lib/falkordb/data
```

**Backup story:** Per-graph backup via `DUMP` / `RESTORE` commands. No PITR (point-in-time recovery).
⚠ Issue #2048: importing a DUMP with a different graph key name crashes the server.

#### Thread Model

✓ verified (FalkorDB architecture):

- **Reads:** GraphBLAS thread pool for parallel sparse matrix operations. Multi-hop queries saturate all CPU cores.
- **Writes:** Serialized per graph — one writer at a time per graph instance.
- **`MULTI/EXEC` blocks ALL graphs** — a global serialization point. Avoid in high-concurrency scenarios.
- **Query plan cache:** 25-query LRU.
- **Multi-tenant:** 10,000+ named graph instances sharing one server process.
  Isolation is at graph-name granularity.

#### FalkorDB Lite (Embedded)

✓ verified (FalkorDB architecture docs):

`pip install falkordblite` (NOT `falkordb-lite` — different package name) — embedded mode,
spawns a Redis+FalkorDB subprocess over Unix socket. Python 3.12+ only.
API identical to the full client.

| Feature | FalkorDB Full (Docker) | FalkorDB Lite (embedded) |
|---|---|---|
| Persistence | AOF + RDB | In-memory only (session lifetime) |
| Multi-connection | ✓ | ✗ (single process) |
| Multi-tenant | ✓ (10K+ graphs) | Limited |
| Production use | ✓ | Dev/prototyping only |
| Claude Desktop integration | Via Docker + mcp-remote | Direct import (no Docker) |
| Performance | Full GraphBLAS parallel | Full GraphBLAS parallel |

**? assumed:** Lite uses the same query engine but without the Redis server layer. Data does not
survive process restart. Use for local development; use Docker for everything else.

---

### 1.2 Query Language & Capabilities

#### OpenCypher Extensions

~ inferred (FalkorDB docs + community):

FalkorDB supports standard **openCypher** plus extensions:

**Vector KNN search (built-in):**
```cypher
MATCH (n:Entity)
WHERE n.embedding <=>[{k: 10}] $query_vector
RETURN n.name, score
```
Native vector similarity search without a separate vector DB. The `<=>[{k:N}]` syntax is
FalkorDB-proprietary (not openCypher standard).

**Full-text search (built-in via RedisSearch):**
```cypher
CALL db.idx.fulltext.queryNodes('Entity', 'query terms') YIELD node, score
RETURN node.name, score
```
Note: FalkorDB full-text uses **RedisSearch scoring**, NOT true Lucene BM25.
128-token query length limit. Stopwords are filtered.

**Graph algorithms:**
```cypher
CALL algo.pageRank() YIELD node, score
CALL algo.shortestPath(startNode, endNode) YIELD path
CALL algo.bfs.stream(startNode, maxDepth, direction) YIELD path
```
Built-in: PageRank, BFS/DFS, shortest path, Louvain community detection.
Less algorithm coverage than Memgraph's MAGE (40+ algorithms), but covers common agent use cases.

#### Known Query Limitations vs Neo4j Cypher

~ inferred (GitHub issues + community comparisons):

- `CALL {} IN TRANSACTIONS` — not supported (Neo4j 5.x feature)
- `UNION ALL` — limited support
- `APOC` procedures — not available (Neo4j-only)
- Lucene full-text index syntax — different (FalkorDB uses RedisSearch syntax)
- `datetime()` functions — partial; some Neo4j datetime utilities missing

For Graphiti's usage, none of these gaps matter — Graphiti uses basic Cypher (MATCH/CREATE/MERGE/WITH).

---

### 1.3 Python API

#### Installation

```bash
pip install falkordb          # full client (requires running FalkorDB server)
pip install falkordb-lite     # embedded (no server, no persistence)
pip install graphiti-core[falkordb]  # Graphiti with FalkorDB backend
```

#### Core API Pattern

~ inferred (FalkorDB Python client docs):

```python
from falkordb import FalkorDB

# Connect
db = FalkorDB(host='localhost', port=6379)

# Select or create a named graph
g = db.select_graph('my_graph')

# Create nodes
g.query("CREATE (:Person {name: 'Alice', age: 30})")

# Create edges
g.query("""
    MATCH (a:Person {name: 'Alice'}), (b:Person {name: 'Bob'})
    CREATE (a)-[:KNOWS {since: 2020}]->(b)
""")

# Query
result = g.query("""
    MATCH (p:Person)-[:KNOWS]->(friend)
    WHERE p.name = 'Alice'
    RETURN friend.name
""")
for record in result.result_set:
    print(record[0])

# Delete node
g.query("MATCH (p:Person {name: 'Alice'}) DELETE p")

# Delete graph
db.delete_graph('my_graph')
```

#### Async Support

~ inferred: The official `falkordb` Python client is **synchronous** (runs over Redis RESP protocol,
which is synchronous request-response). Graphiti wraps it with `asyncio.to_thread()` or similar
to avoid blocking the event loop. Native async support is not present in the base driver.

When using Graphiti, you don't call the FalkorDB driver directly — Graphiti's
`FalkorDriver` wrapper handles this transparently.

#### Transaction Support

~ inferred: FalkorDB supports **MULTI/EXEC** (Redis transactions) at the Redis protocol level,
but the Python driver wraps these in a `pipeline()` context. Graphiti's writes use single-query
operations; it does not use explicit transactions across multiple queries.

#### Connection Pooling

~ inferred: The `falkordb` Python client uses a Redis connection pool under the hood
(via `redis-py`). Default pool size is configurable via `max_connections` parameter:

```python
db = FalkorDB(host='localhost', port=6379, max_connections=50)
```

---

### 1.4 FalkorDB MCP Ecosystem (3 Distinct Products)

✓ verified (FalkorDB docs, main research agent):

**Important:** FalkorDB ships THREE different MCP products — they are not interchangeable:

| Product | Package | Purpose | Transport |
|---|---|---|---|
| **code-graph** (`cgraph-mcp`) | `claude mcp add-json code-graph` | Code analysis KG: 7 tools (index_repo, search_code, find_symbol, get_neighbors, get_file_neighbors, impact_analysis, find_path). Languages: Python, Java, C# only. Fixed schema. | stdio only |
| **FalkorDB-MCPServer** | `npx @falkordb/mcpserver@latest` | General Cypher access to any FalkorDB graph — no fixed schema | HTTP/stdio |
| **Graphiti MCP** | Docker compose | Episodic agent memory — 13 tools (see Part 3) | HTTP (needs `mcp-remote` for Claude Desktop) |

**code-graph** is for software engineering (codebase analysis). It does NOT handle personal knowledge or agent memory. For AI agent memory use **Graphiti MCP**.

### 1.5 FalkorDB GraphRAG SDK

✓ verified (main research agent, arxiv 2506.05690v3):

`pip install graphrag-sdk[litellm]` — 9-stage pipeline:
Load → Chunk → Lexical Graph → Extract (LLM) → Prune → Resolve (optional LLM) →
Write → Mentions → Chunk Indexing. `finalize()` runs cross-document dedup and creates final indexes.

**Cost:** ~$0.0055 per 1,000-word document (GPT-4o-mini). ~71 LLM calls per document.
Query: ~$0.00065/query at ~3s total latency.

**LLM support:** LiteLLM abstraction — 100+ providers including Anthropic, OpenAI, Gemini, Ollama.

**GraphRAG-Bench #1 claim:** arxiv paper 2506.05690v3 (ICLR '26). 20 Gutenberg novels + NCCN medical guidelines,
2,010 questions, 4 task levels. FalkorDB SDK: **63.73** (novels), **75.73** (medical) vs MS-GraphRAG 50.93.
~ inferred: FalkorDB ran their own eval on the public dataset — not independently reproduced.

---

### 1.6 FalkorDB Production Readiness Summary

#### Current Version & Release Cadence

✓ verified: Current stable is **FalkorDB v4.18.11** (June 24, 2026). Graphiti requires v1.1.2+.
It is the **default backend** for the Graphiti MCP server Docker image.

#### License (SSPLv1) — Practical Implications

✓ verified (GRAPH_DATABASES_AND_ENTITY_LIBRARIES_2026.md):

SSPLv1 = Server Side Public License v1. Not OSI-approved.

**What matters:**
- **Internal AI agents (personal agent use case):** ✅ Fine. No obligation to open-source.
- **Offering FalkorDB as a cloud service:** ❌ Must open-source your entire stack.
- **Embedding in a product you sell:** Gray area — consult legal.

For agents as a personal agent system: SSPLv1 is not a blocker.

#### Known Production Issues — FalkorDB Itself (8 Critical Open Bugs)

✓ verified (FalkorDB GitHub issues, Jun 25 2026):

| Issue # | Description | Severity |
|---|---|---|
| **#2152** | **CrashLoop on upgrade to v4.18.11** (current stable) if full-text indexes exist. Downgrade to 4.18.7 required. | CRITICAL (today's release) |
| **#2129** | **Deadlock under write load + vector indexing** — all threads frozen, requires restart, recurs every 15–40 min | CRITICAL |
| **#2103** | **Silent data corruption** — deleted nodes remain visible by label, properties missing, no error raised | CRITICAL |
| **#1710** | **Silent wrong results** from HNSW index during concurrent writes | CRITICAL |
| **#1642** | **SEGFAULT** from Redis 8.x ABI incompatibility in UNIQUE constraints. Their own Docker uses Redis 8.6.3. | CRITICAL |
| **#1885** | **Double-free heap corruption** from `SET n.x = NULL, n.x = NULL` | HIGH |
| **#1883** | **AndMultiplexer silently truncates result sets** | HIGH |
| **#2112** | Core team private SIGSEGV tracker (full severity undisclosed) | UNKNOWN |
| **#2048** | DUMP/RESTORE crashes on different key name | MEDIUM |

Known Graphiti-specific FalkorDB bugs:

| Issue # | Description | Severity | Status |
|---|---|---|---|
| **#1592** | Edge fulltext search timeout at ~3,300 edges; 19/20 episodes lost | CRITICAL | Open |
| **#1522** | FalkorDB Cloud auth: URI username dropped → broken authentication | HIGH | Open |
| **#1001** | `add_triplet` edge UUIDs not persisted on FalkorDB | MEDIUM | Open |
| **#1517** | Default group ID validation rejects underscore chars | LOW | Open |

#### Backup & Recovery

~ inferred: Use Redis standard backup — `BGSAVE` to create RDB snapshot + copy to safe location.
For AOF: copy the `.aof` file. For containers: volume snapshots (DO block storage snapshots, EBS, etc.).
No built-in backup scheduling — operational responsibility.

---

## Part 2: Graphiti — Deep Dive

### 2.1 Architecture & Bi-Temporal Model

✓ verified (getzep/graphiti source code — `edges.py`, `nodes.py`, arxiv paper 2501.13956v1):

Graphiti is a **temporal knowledge graph** where every fact (`EntityEdge`) carries **four timestamps**
on two independent time axes:

| Field | Time Axis | Meaning | Who sets it |
|---|---|---|---|
| `created_at` | System / Transaction (T') | Wall-clock when edge was written to DB | System (`utc_now()`) |
| `expired_at` | System / Transaction (T') | Wall-clock when system invalidated this record | System on contradiction |
| `valid_at` | Event / Real-world (T) | When the fact became true in the world | LLM-extracted from content |
| `invalid_at` | Event / Real-world (T) | When the fact stopped being true | LLM-extracted, or set by conflict resolver |

This is a proper bi-temporal design. You can ask:
- *"What facts were valid on 2025-01-01?"* → filter by `valid_at ≤ 2025-01-01 AND invalid_at > 2025-01-01`
- *"What did the system know as of last Tuesday?"* → filter by `created_at ≤ last_tuesday AND expired_at > last_tuesday`

**Facts are never deleted** — only marked with `invalid_at` / `expired_at`. Full history is preserved.

`EpisodicNode` (the raw episode) has `valid_at` = the `reference_time` you pass to `add_episode()`.
`SagaNode` adds two watermarks for incremental summarization.

---

### 2.2 Episode Ingestion Pipeline (LLM Call Budget)

✓ verified (getzep/graphiti — `graphiti.py`, `node_operations.py`, `edge_operations.py`):

`add_episode()` executes **10 steps** sequentially. LLM calls are highlighted:

```
Step 1 — Retrieve context            [NO LLM] Fetch last ~4 EpisodicNodes for context window
Step 2 — Extract entities            [LLM #1] Named entity extraction from episode body
Step 3 — Resolve entities            [LLM #2] (only for unresolved nodes — see dedup below)
Step 4 — Extract edges               [LLM #3] Relationship triple extraction (fact, valid_at, invalid_at)
Step 5 — Extract edge timestamps     [LLM #4] Small model; only fires if timestamps missing after step 4
Step 6 — Resolve edges               [LLM #5] Dedup + contradiction detection per edge with candidates
Step 7 — Resolve contradictions      [NO LLM] Datetime comparison; set invalid_at on older edge
Step 8 — Extract node attributes     [LLM #6] (only if custom entity_types schema provided)
Step 9 — Persist to graph            [NO LLM] Cypher writes to DB
Step 10 — (Optional) Community update [LLM #7+] Only if update_communities=True
```

**LLM call budget per episode:**
- **Minimum (clean data, no conflicts):** 3 calls (extract nodes + extract edges + edge timestamps)
- **Typical (5 entities, some conflicts):** 5–8 calls
- **With custom schemas:** add 1–2 for attribute extraction
- **With community updates:** +1 per affected node cluster

**v0.29.0 optimization — combined extraction:**
```python
await graphiti.add_episode(
    ...,
    use_combined_extraction=True  # collapses steps 2+4 into one LLM call
)
```
Reduces to ~2 calls minimum. Not the default.

**Concurrency:** Parallel ingestion via `add_episode_bulk()`. Controlled by
`SEMAPHORE_LIMIT` env var (default: 10).

⚠ **Critical:** `add_episode_bulk()` **skips edge invalidation** — do not use when you need
temporal fact expiry/conflict resolution. Use `add_episode()` in a loop for correctness.

---

### 2.3 Entity Deduplication — 3-Tier Algorithm

✓ verified (getzep/graphiti — `dedup_helpers.py`):

```
For each extracted entity E:

  Tier 1 — Exact name match (deterministic, O(1)):
    normalize(E.name) = lowercase + collapse whitespace
    lookup in dict[normalized_name → list[EntityNode]]
    if exactly 1 match → resolved immediately (no LLM, no embedding)
    if >1 match (ambiguous) → escalate to Tier 3

  Tier 2 — MinHash + LSH fuzzy match (deterministic):
    Entropy gate: compute Shannon entropy over characters of normalized name
    if entropy < 1.5 OR (len < 6 AND tokens < 2) → SKIP (prevents "NYC","Bob","AI" false positives)
    if entropy sufficient:
      compute 3-gram character shingles of name
      compute MinHash signature with 32 hash functions (BLAKE2b, per-seed salting)
      split into 8 bands of size 4 for LSH bucket lookup
      for each LSH candidate: compute exact Jaccard similarity over shingle sets
      if best Jaccard ≥ 0.9 → resolved deterministically (no LLM)

  Tier 3 — Semantic + LLM (fallback):
    embed(E.name) → 1024-dim vector
    cosine_search(vector, graph, threshold=0.6, top_k=15) → candidates_cos
    fulltext_search(E.name + E.summary, graph) → candidates_fts
    merge(candidates_cos, candidates_fts)
    if deterministic similarity check passes → resolved
    else → batch into ONE LLM call (all unresolved nodes together)
    LLM returns NodeResolutions: duplicate_candidate_id per node (-1=new, ≥0=existing UUID)
    if duplicate: keep existing UUID, generate merged name+summary
```

**Constants:**
```python
NODE_DEDUP_CANDIDATE_LIMIT = 15
NODE_DEDUP_COSINE_MIN_SCORE = 0.6
_NAME_ENTROPY_THRESHOLD = 1.5
_MINHASH_PERMUTATIONS = 32
_MINHASH_BAND_SIZE = 4         # 32/4 = 8 bands for LSH
_FUZZY_JACCARD_THRESHOLD = 0.9
```

**Key insight:** MinHash is on **name strings** (character shingles), not on embeddings.
The embedding layer uses standard cosine similarity. They are separate signals.

---

### 2.4 Relationship Extraction

✓ verified (getzep/graphiti — `edge_operations.py`, `prompts/extract_edges.py`):

`extract_edges()` receives the resolved entity list + multi-episode context + edge type definitions.
LLM returns `ExtractedEdges`:

```python
class Edge(BaseModel):
    source_entity_name: str   # must be in ENTITIES list
    target_entity_name: str   # must be in ENTITIES list
    relation_type: str        # SCREAMING_SNAKE_CASE (e.g., WORKS_AT, OWNS, MANAGES)
    fact: str                 # natural-language paraphrase of the relationship
    valid_at: str | None      # ISO 8601 — when fact became true
    invalid_at: str | None    # ISO 8601 — when fact stopped being true
    episode_indices: list[int] # which episodes in the batch this fact came from
```

**Post-processing:**
- Self-edges (source == target) → dropped
- Empty `fact` strings → dropped
- Source/target names validated against entity name list

**Custom edge types:** If `edge_types` dict is passed, `relation_type` must match a schema name.
The schema's `__doc__` is injected into the prompt as `fact_type_description`. After dedup, a separate
small-model LLM call extracts typed attributes.

**Default max_tokens for extraction call:** 16,384.

---

### 2.5 Conflict Resolution & Temporal Invalidation

✓ verified (getzep/graphiti — `edge_operations.py`, `resolve_edge_contradictions`):

When a new fact contradicts an existing one (e.g., "Alice is junior manager" → "Alice is senior manager"):

**Detection:** `resolve_extracted_edge()` LLM call receives:
- `EXISTING FACTS` — edges between the same node pair
- `FACT INVALIDATION CANDIDATES` — broader set from hybrid search
- `NEW FACT` — the newly extracted edge

LLM returns `EdgeDuplicate`: `duplicate_facts: list[int]` and `contradicted_facts: list[int]`.

**Resolution (no additional LLM — pure datetime logic):**

```python
def resolve_edge_contradictions(new_edge, contradicting_candidates):
    for candidate in contradicting_candidates:
        if candidate.valid_at < new_edge.valid_at:
            # candidate is older; new fact supersedes
            candidate.invalid_at = new_edge.valid_at
            candidate.expired_at = utc_now()
        else:
            # new fact is older; candidate supersedes
            new_edge.invalid_at = candidate.valid_at
            new_edge.expired_at = utc_now()
        # skip if temporal ranges don't overlap
```

"Graphiti consistently prioritizes new information." Newer `valid_at` wins.
Out-of-order ingestion is handled correctly — sort by `valid_at`, not by insertion order.
**Old facts are kept in the graph** (queryable as historical data), only marked invalid.

---

### 2.6 Hybrid Retrieval System

✓ verified (getzep/graphiti — `search_utils.py`, `search_config_recipes.py`):

Three signals run in parallel via `semaphore_gather()`:

| Signal | Method | Implementation |
|---|---|---|
| BM25 | `node_fulltext_search()`, `edge_fulltext_search()` | Delegated to graph DB native fulltext (Lucene on Neo4j, RedisSearch on FalkorDB) |
| Semantic | `node_similarity_search()`, `edge_similarity_search()` | Vector cosine similarity on stored embeddings (`name_embedding`, `fact_embedding`) |
| Graph BFS | `node_bfs_search()`, `edge_bfs_search()` | Breadth-first traversal from seed node UUIDs, max depth 3 |

**Important:** BFS is **NOT activated** in the default MCP server recipes. It only fires when you
explicitly supply `bfs_origin_node_uuids` — i.e., when you already know which entity to start from.

**Score fusion — RRF (Reciprocal Rank Fusion):**

```python
def rrf(results: list[list[str]], rank_const=1, min_score=0):
    scores = defaultdict(float)
    for ranking in results:
        for i, uuid in enumerate(ranking):
            scores[uuid] += 1 / (i + rank_const)  # NOT the standard 60 — uses rank_const=1
    return sorted(scores.keys(), key=lambda u: scores[u], reverse=True)
```

**No per-signal weights** — BM25 and cosine contribute equally by rank position.
Each method generates `2 * limit` candidates before fusion.

**Constants:**
```python
DEFAULT_MIN_SCORE = 0.6       # cosine similarity floor
DEFAULT_MMR_LAMBDA = 0.5      # relevance vs diversity in MMR
MAX_SEARCH_DEPTH = 3          # BFS max hops
MAX_QUERY_LENGTH = 128        # BM25 token limit — queries above this return empty
```

**Pre-built search config recipes** (importable from `graphiti_core.search.search_config_recipes`):
- `EDGE_HYBRID_SEARCH_RRF` — default for `search()`
- `EDGE_HYBRID_SEARCH_CROSS_ENCODER` — used by `_search()` when cross-encoder is available
- `EDGE_HYBRID_SEARCH_MMR` — diversity-aware
- `EDGE_HYBRID_SEARCH_NODE_DISTANCE` — graph-proximity aware
- `COMBINED_HYBRID_SEARCH_RRF`, `COMBINED_HYBRID_SEARCH_CROSS_ENCODER` — all entity types

**Rerankers:**
| Reranker | Formula | Use case |
|---|---|---|
| RRF | `1 / (rank + 1)` | Default; fast; no model required |
| MMR | `λ × query_sim + (λ-1) × max_cand_sim` | When diversity matters |
| Node Distance | `1 / distance_from_center_node` | When pivoting around a known entity |
| Episode Mentions | RRF first, then by `MENTIONS` count | Surface frequently-cited facts |
| Cross-encoder | Learned relevance scores | Best quality; slower |

**BM25 caveat on FalkorDB:** FalkorDB uses RedisSearch scoring (not Lucene BM25).
The 128-token cap is FalkorDB-specific. This affects Graphiti searches on FalkorDB backend.

**Embedding model:** Default `text-embedding-3-small` (OpenAI). `EMBEDDING_DIM = 1024` (env-overridable).

---

### 2.7 LLM Requirements & Model Support

✓ verified (getzep/graphiti — `llm_client/`, official docs):

#### Supported LLMs

| Provider | Client Class | Structured Output Mechanism | Status |
|---|---|---|---|
| OpenAI | `OpenAIClient` | `/v1/responses` (beta structured output) | ✅ First-class |
| Anthropic Claude | `AnthropicClient` | Tool-use API (function calling) | ✅ First-class |
| Google Gemini | (built-in) | Native structured output | ✅ First-class |
| Groq | `OpenAIClient` (compat) | OpenAI-compatible endpoint | ✅ Works |
| Ollama / vLLM | `OpenAIGenericClient` | `/v1/chat/completions` + `response_format` | ⚠️ Works with caveats |
| Azure OpenAI | `OpenAIClient` with v1 opt-in | `/v1/responses` | ⚠️ Needs v1 API enabled |

#### Small/Local Models Warning

✓ verified: "avoid smaller local models as they may not accurately extract data or output the correct
JSON structures required by Graphiti." Small models frequently emit JSON that doesn't match the
Pydantic schema → extraction failures (entities/edges not persisted, no error raised).

**Hard constraint:** Even when using Claude or Ollama for LLM inference, you **still need an OpenAI
API key** for embeddings. Graphiti's embedder is separate from its LLM client and defaults to
`text-embedding-3-small` (OpenAI). No workaround without implementing a custom `EmbedderClient`.

#### Anthropic Claude Integration

✓ verified (getzep/graphiti — `llm_client/anthropic_client.py`):

Install: `pip install graphiti-core[anthropic]`

```python
from graphiti_core.llm_client import AnthropicClient, LLMConfig

llm = AnthropicClient(
    config=LLMConfig(
        api_key="<your-anthropic-api-key>",
        model="claude-sonnet-4-20250514",          # large model
        small_model="claude-3-5-haiku-20241022"    # small model for cheaper ops
    )
)
```

Default model when no config provided: `claude-haiku-4-5-latest`

Supported: Claude 2, 3, 3.5, 3.7, 3.7 (extended thinking), 4.5 (16 total model variants).

Structured output mechanism: **tool-use** — every request is framed as a tool call with the Pydantic
schema as the tool definition. `_create_tool()` converts schema; `tool_choice` forces invocation.
Retry logic built-in for validation errors; `RefusalError` raised on content policy violation (no retry).

#### Ollama / Local Models

✓ verified (official docs): Use `OpenAIGenericClient`, not `OpenAIClient`:

```python
from graphiti_core.llm_client import OpenAIGenericClient, LLMConfig

llm = OpenAIGenericClient(config=LLMConfig(
    api_key="ollama",                        # placeholder — Ollama ignores this
    model="deepseek-r1:7b",
    small_model="deepseek-r1:7b",
    base_url="http://localhost:11434/v1"
))
```

You still need `OPENAI_API_KEY` in env for embeddings even with local LLM.

---

### 2.8 Python API Reference

✓ verified (getzep/graphiti — `graphiti.py`):

#### Async / Event Loop Notes

✓ verified (developer blog): Graphiti has "its own opinions about event loop management" that conflict
with frameworks like Google ADK. Errors: `"RuntimeError: Future attached to a different loop"`,
`"RuntimeError: Event loop is closed"`. Standard `asyncio.to_thread` workarounds fail.

**Recommended production fix for complex async contexts:** wrap Graphiti in a standalone **FastAPI
service** (process isolation). Call it over HTTP. Do not embed directly in another async agent framework.

#### `add_episode()` — Full Signature

```python
async def add_episode(
    self,
    name: str,                                              # episode label
    episode_body: str,                                      # content to ingest
    source_description: str,                                # context about the source
    reference_time: datetime,                               # temporal anchor → EpisodicNode.valid_at
    source: EpisodeType = EpisodeType.message,              # message|text|json|fact_triple
    group_id: str | None = None,                            # multi-tenant isolation key
    uuid: str | None = None,                                # idempotency key
    update_communities: bool = False,                       # rebuild community clusters (expensive)
    entity_types: dict[str, type[BaseModel]] | None = None, # custom entity extraction schemas
    excluded_entity_types: list[str] | None = None,
    previous_episode_uuids: list[str] | None = None,        # explicit context chain
    edge_types: dict[str, type[BaseModel]] | None = None,   # custom relationship schemas
    edge_type_map: dict[tuple[str, str], list[str]] | None = None,  # entity→edge routing
    custom_extraction_instructions: str | None = None,      # freeform LLM guidance
    saga: str | SagaNode | None = None,                     # saga grouping
    saga_previous_episode_uuid: str | None = None,
) -> AddEpisodeResults
```

`AddEpisodeResults`:
```python
class AddEpisodeResults(BaseModel):
    episode: EpisodicNode
    episodic_edges: list[EpisodicEdge]
    nodes: list[EntityNode]
    edges: list[EntityEdge]
    communities: list[CommunityNode]
    community_edges: list[CommunityEdge]
```

#### `search()` — Simple Public API

```python
async def search(
    self,
    query: str,
    center_node_uuid: str | None = None,
    group_ids: list[str] | None = None,
    num_results: int = 10,
    search_filter: SearchFilters | None = None,
    driver: GraphDriver | None = None,
) -> list[EntityEdge]
```

Returns flat `list[EntityEdge]`. Uses `COMBINED_HYBRID_SEARCH_CROSS_ENCODER` internally.

#### `_search()` — Advanced API (returns full breakdown)

```python
async def _search(
    self,
    query: str,
    config: SearchConfig,
    group_ids: list[str] | None = None,
    center_node_uuid: str | None = None,
    bfs_origin_node_uuids: list[str] | None = None,
    search_filter: SearchFilters | None = None,
) -> SearchResults
```

`SearchResults`:
```python
class SearchResults(BaseModel):
    edges: list[EntityEdge]
    edge_reranker_scores: list[float]
    nodes: list[EntityNode]
    node_reranker_scores: list[float]
    episodes: list[EpisodicNode]
    episode_reranker_scores: list[float]
    communities: list[CommunityNode]
    community_reranker_scores: list[float]
```

#### Temporal Queries

✓ verified: `get_entity_edge_history()` **does not exist** in the codebase.
Temporal access is via:
- `EntityEdge.valid_at / invalid_at` — filter in search results
- `retrieve_episodes(reference_time, last_n=3)` — point-in-time episode window
- `SearchFilters` with `valid_at_after/before`, `invalid_at_after/before` date-range parameters

#### Error Types

✓ verified (`graphiti_core/errors.py`):

| Exception | Trigger |
|---|---|
| `GraphitiError` | Base class |
| `EdgeNotFoundError` / `EdgesNotFoundError` | UUID lookup fails |
| `NodeNotFoundError` | Node lookup fails |
| `GroupsEdgesNotFoundError` / `GroupsNodesNotFoundError` | Group filter returns empty |
| `SearchRerankerError` | Reranker error |
| `EntityTypeValidationError` | Custom entity type uses protected attribute names |
| `GroupIdValidationError` | `group_id` contains chars outside `[a-zA-Z0-9_-]` |
| `NodeLabelValidationError` | Node label format invalid |
| `RefusalError` | Anthropic content policy violation (no retry) |

---

### 2.9 Production Issues & Known Bugs

✓ verified (getzep/graphiti GitHub issues tracker):

| Issue # | Description | Severity | Status |
|---|---|---|---|
| **#1021** | `add_episode()` returns success but data NOT persisted in Neo4j. Silent data loss — no error, no detection possible. | CRITICAL | Open |
| **#1166** | No temporal versioning for node attributes. Every node upsert overwrites prior property values permanently. Structural gap — not a bug but a missing feature. | HIGH | Open |
| **#1595** | `lucene_sanitize()` corrupts words containing common letters (O, R, N, T, A, D), breaking full-text search queries silently. | HIGH | Open |
| **#1605** | `EntityEdge.reference_time` returns None silently. Temporal queries broken for recent edges. | HIGH | Open |
| **#760** | Hallucination loop in entity deduplication (runaway LLM dedup). No maintainer response. | MEDIUM | Open |
| **#1574** | MCP queue worker gets garbage-collected under streamable-http transport. **Memory processing silently stops.** Critical for MCP server deployments. | HIGH | Open |
| **#1592** | FalkorDB edge fulltext search timeout at scale (open). | HIGH | Open |
| **#1522** | FalkorDB Cloud auth URI username dropped. **Cloud connection broken.** | HIGH | Open (Jun 2026) |
| **#1526** | JSON serialization fails with datetime attributes. | MEDIUM | Open |
| **#1517** | Default group ID validation rejects underscore chars. | LOW | Open |

**Repo vitals** (✓ verified, Jun 2026): v0.29.2 (June 8, 2026) · 28,000 stars · 2,800 forks ·
245 open issues · 153 open PRs · ~25,000 weekly PyPI downloads · biweekly release cadence.
Security: CVE resolved in v0.28.1 (diskcache removal); Cypher injection hardening in v0.28.2.

**Committer concentration risk:** Single primary committer (Daniel Chalef, Zep CTO).

**Scale fixes (Zep managed cloud, late 2025):**
When scaling 30×, Zep had to:
- Rewrite Python gateway in Go
- Replace LLM deduplication with classical NLP (Shannon entropy, TF-IDF, LSH)
- Result: P95 context retrieval from 600ms → 150–200ms; episode processing ~4s

Takeaway: The open-source library is behind what Zep runs internally. Production safety of the
OSS version is lower than the managed cloud on high-volume or high-accuracy requirements.

---

### 2.10 Community Opinions

#### HackerNews

✓ verified (HN thread #41445445):
- Generally positive on the concept (temporal KG for agents).
- Key criticism from `spothedog1` (persistent): "Schema-agnostic LLM extraction won't reach its potential
  without standardized ontologies (RDF/W3C)." Core concern: non-deterministic extraction produces
  inconsistent graph structure over time. Devs acknowledged but held position (staying schema-agnostic).
- TypeScript support asked repeatedly → "wrap with FastAPI." No native TS SDK.
- Naming conflict with existing `graphiti.dev` project raised.

#### WeavAI Independent Review (May 2026)

✓ verified: 8.5/10 overall.
Specifically flagged: extraction speed 2-3× slower than Mem0, steep learning curve (Episode/Entity/Triplet
abstractions), heavy self-hosting maintenance.

#### Medium ("Battle-tested" review, 2026)

✓ verified (asymptotic-spaghetti-integration article):
> "graphiti by itself isn't a ready-to-use memory system. You'd need significant effort to build a functional solution around it."

The Zep research paper called "one of the most pretentious and least informative 'academic' documents" —
"a superficial marketing piece disguised with equations."

#### Comparison: Graphiti vs Mem0 vs Letta

| Dimension | Graphiti/Zep | Mem0 | Letta (ex-MemGPT) |
|---|---|---|---|
| Temporal reasoning | Best-in-class | Weak | Not the point |
| LongMemEval | 63.8% | 49.0% | N/A |
| Ingestion speed | 2-3× slower | Fast | Moderate |
| Self-hosting complexity | High (graph DB required) | Low (single Docker) | Moderate |
| Production readiness | Mixed | Most mature | Architectural |
| GitHub stars | ~14K | ~47K | ~14K |
| Local model support | Poor (structured output required) | Better | Best |
| Temporal use cases | Perfect fit | Weak | Not designed for |
| Python API maturity | Medium | High | High |
| OpenAI key always required | YES (even with Claude) | No | No |

---

## Part 3: FalkorDB + Graphiti Combined Stack

### 3.1 Docker Compose Setup

✓ verified (FalkorDB Docker Hub + MCP README):

**Option A — Single image (FalkorDB bundled):**
```yaml
services:
  graphiti-falkordb:
    image: falkordb/graphiti-knowledge-graph-mcp:latest
    ports:
      - "6379:6379"   # FalkorDB (Redis protocol)
      - "3000:3000"   # FalkorDB Browser UI
      - "8000:8000"   # Graphiti MCP HTTP endpoint
    volumes:
      - falkordb_data:/var/lib/falkordb/data
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      DATABASE_TYPE: falkordb
      FALKORDB_HOST: localhost
      FALKORDB_PORT: 6379
      GRAPHITI_GROUP_ID: agent_workspace
      GRAPHITI_TELEMETRY_ENABLED: "false"
volumes:
  falkordb_data:
```

**Option B — Multi-service compose (from repo):**
```bash
git clone https://github.com/getzep/graphiti.git
cd graphiti/mcp_server
docker compose up  # starts FalkorDB + MCP server
```

**Environment variables that matter:**
- `OPENAI_API_KEY` — required even with Claude (for embeddings)
- `ANTHROPIC_API_KEY` — if using Claude for LLM inference
- `DATABASE_TYPE=falkordb`
- `GRAPHITI_TELEMETRY_ENABLED=false` — disable telemetry
- `SEMAPHORE_LIMIT=5` — tune down from default 10 for Anthropic Standard tier

---

### 3.2 MCP Server Tools (13 tools)

✓ verified (getzep/graphiti — `mcp_server/README.md`):

| Tool | What it does |
|---|---|
| `add_memory` | Ingest episode (text/json/message) — **fire-and-forget**, background async |
| `add_triplet` | Insert a manual fact (entity–relation–entity), bypass LLM extraction |
| `search_nodes` | Entity search with type filtering |
| `search_memory_facts` | Edge/fact search with bi-temporal date-range (`valid_at_after/before`) |
| `summarize_saga` | Generate/refresh running saga narrative summary |
| `build_communities` | Cluster detection + community summaries (expensive) |
| `get_episode_entities` | Provenance: which nodes/edges came from specific episode UUIDs |
| `get_entity_edge` | Retrieve single fact by UUID |
| `get_episodes` | List recent episodes for a group |
| `delete_entity_edge` | Remove a relationship |
| `delete_episode` | Remove episode + cascade-delete exclusively-created entities |
| `clear_graph` | Wipe all data for specified groups |
| `get_status` | Health check |

**Claude Desktop integration** (Claude Desktop doesn't support HTTP MCP natively):
```json
{
  "mcpServers": {
    "graphiti-memory": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8000/mcp/"]
    }
  }
}
```
Requires `mcp-remote` bridge. Restart Claude Desktop after adding.

---

### 3.3 Performance of Combined Stack

| Metric | Figure | Source |
|---|---|---|
| FalkorDB p99 vs Neo4j p99 | 344× faster | FalkorDB benchmark (SNAP Pokec, 82% read) |
| FalkorDB memory (1M relationships) | ~3GB | FalkorDB benchmark |
| Graphiti P95 context retrieval (Zep Cloud, post-fix) | 150–200ms | Zep internal (late 2025) |
| Graphiti P95 context retrieval (Zep Cloud, pre-fix) | ~600ms | Same source |
| Episode processing time (Zep Cloud) | ~4s | Same source |
| GraphRAG-Bench #1 (FalkorDB SDK) | 63.73 ACC | GraphRAG-Bench (GPT-4o-mini) |
| LongMemEval (Graphiti + GPT-4o) | 63.8% | LongMemEval paper |
| DMR benchmark (Zep self-reported) | 94.8–98.2% | Zep blog |

Note: the 150–200ms P95 is for Zep's Go-rewritten + classical-NLP-dedup managed cloud,
not the raw open-source Graphiti library. Open-source performance on high-volume deployments
is not independently published.

---

### 3.4 Known Incompatibilities & Operational Hazards

✓ verified (GitHub issues):

| Risk | Issue | Mitigation |
|---|---|---|
| Silent episode data loss | #1021 | Verify writes with `get_episodes` after ingestion |
| Node attribute history lost on upsert | #1166 | Store attribute history in separate episodes |
| Fulltext search corrupts common letters | #1595 | Pin to pre-#1595 version; test with "information" queries |
| MCP queue worker GC'd under streamable-http | #1574 | Use stdio transport; restart on signal loss |
| FalkorDB edge fulltext timeout at scale | #1592 | Use semantic search only at scale; monitor query latency |
| FalkorDB Cloud auth broken | #1522 | Use self-hosted FalkorDB (Docker) not cloud; |

**SSPLv1 note:** For internal deployment: no restriction. If you ever expose your FalkorDB instance as
a cloud service to external users, SSPL requires open-sourcing your entire stack.

---

### 3.5 Example Deployment Notes

Considerations for a typical agent deployment (adjust to your own stack):

- **If your primary store is MySQL** (not PostgreSQL), Apache AGE is eliminated as an option.
- **Development:** `falkordb-lite` (no Docker, embedded) or FalkorDB Docker locally
- **Production:** Self-hosted FalkorDB Docker (NOT FalkorDB Cloud — auth bug #1522 is open)
- **LLM:** any provider client for inference; Graphiti still needs `OPENAI_API_KEY` for embeddings
  unless a custom embedder client is implemented
- **Multi-tenancy:** Use `group_id` to isolate by tenant/user
- **Telemetry:** Set `GRAPHITI_TELEMETRY_ENABLED=false`
- **`update_communities=False`** — keep off by default; run community builds as a separate batch job

---

## Part 4: Verdict & Recommendations

### FalkorDB

**⚠ NOT recommended for production in its current state (Jun 2026).**

FalkorDB's performance claims (344× p99 vs Neo4j, #1 GraphRAG-Bench) are real and the
architecture (GraphBLAS CSC, linear algebra traversal) is genuinely differentiated. But:

- **8 critical open bugs** including deadlock under write+vector load (#2129), silent data corruption
  (#2103), and a **CrashLoop on today's release** (v4.18.11, #2152) when full-text indexes exist
- **Scale wall at ~3,300 edges** when using Graphiti (#1592) — 19/20 episodes silently lost
- **FalkorDB Cloud auth broken** (#1522) — Cloud is currently non-functional

**Agent design rule:** Use FalkorDB for development only (`falkordblite` embedded). Use **Neo4j for production**.
**Watch:** When #1592 and #2129 are closed, reassess. Architecture remains compelling.
**SSPL license:** Fine for internal deployment.

### Graphiti

**Best choice when temporal fact validity is the core product requirement.** Bi-temporal model,
conflict resolution by timestamp, full provenance tracking — genuinely differentiated vs Mem0/Letta.

**Not plug-and-play.** Requires:
- OpenAI API key (always — for embeddings)
- Graph DB (FalkorDB or Neo4j)
- Awareness of open bugs (#1021 silent data loss, #1166 no node attribute history)

**Production maturity:** Production-viable on happy path with low-to-medium episode counts.
**Not production-safe** where silent data loss or node attribute history accuracy are unacceptable.

## Sources

- [getzep/graphiti GitHub](https://github.com/getzep/graphiti) — source code, issues
- [Zep Documentation](https://help.getzep.com/graphiti) — official docs
- [Zep arxiv paper 2501.13956v1](https://arxiv.org/abs/2501.13956) — temporal KG architecture
- [FalkorDB GitHub](https://github.com/FalkorDB/FalkorDB)
- [FalkorDB vs Neo4j benchmarks](https://www.falkordb.com/blog/graph-database-performance-benchmarks-falkordb-vs-neo4j/)
- [FalkorDB GraphRAG SDK #1 on GraphRAG-Bench](https://www.falkordb.com/blog/graphrag-sdk-knowledge-graph/)
- [Graphiti + FalkorDB MCP setup](https://docs.falkordb.com/agentic-memory/graphiti-mcp-server.html)
- [WeavAI — Zep 2026 Review (8.5/10)](https://weavai.app/blog/en/2026/05/09/zep-2026-review-ai-agent-temporal-memory-king/)
- [Open-Source AI Agent Memory: Mem0 vs Zep vs Letta 2026](https://rohitraj.tech/en/notes/open-source-ai-agent-memory-mem0-vs-zep-letta-2026)
- [Medium: From Beta to Battle-Tested (Letta, Mem0, Zep)](https://medium.com/asymptotic-spaghetti-integration/from-beta-to-battle-tested-picking-between-letta-mem0-zep-for-ai-memory-6850ca8703d1)
- [HackerNews Show HN: Graphiti](https://news.ycombinator.com/item?id=41445445)
- [getzep/graphiti DeepWiki](https://deepwiki.com/getzep/graphiti)
- [Neo4j blog: Graphiti knowledge graph memory](https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/)
