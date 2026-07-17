# Graph Databases & Entity Libraries for AI Agent Systems
## Open Source, Local + Cloud, 2026

**Version:** 1.0
**Date:** 2026-06-25
**Subfolder:** databases/ (new — companion to tools/WORLD_MODEL_TOOL_ROUTING_RESEARCH_2026.md)

---

## ⚠ Critical Finding — Read First

**Kuzu is archived.** Apple acqui-hired the entire Kùzu Inc team (EU Digital Markets Act filing, February 2026). Repo is read-only as of October 10, 2025. Do not start new projects on Kuzu. Community fork: **LadybugDB** (Vela Engineering fork, v0.17.1 June 2026) — retains Cypher dialect, columnar storage, adds DuckDB + Parquet + Arrow interop. Not yet battle-tested in production.

---

## Part 1 — Embedded / Serverless (No Server Required)

### 1.1 LadybugDB (Kuzu community fork)

- **GitHub:** Vela-Engineering/kuzu fork + Arun Sharma's LadybugDB
- **License:** MIT
- **What it is:** Embedded graph DB, SQLite-style, runs inside Python process. Columnar storage, native Parquet ingestion, Cypher queries. Kuzu heir.
- **Historical Kuzu benchmarks (MacBook Pro M2, 100K nodes + 2.5M edges):**
  - Ingestion: 18x faster than Neo4j
  - Simple aggregation: 15.8x faster
  - Path counting (2-hop): **180.5x faster**
  - Filtered path counting: **188.7x faster**
- **Local:** ✓ Fully embedded, zero infrastructure
- **Cloud:** ✗ Embedded only — no server mode
- **MCP:** ✗ No
- **AI/agent native:** ✗ No
- **Python quality:** 4/5
- **Verdict:** Watch for maturity. Best embedded option if you need Cypher and zero infrastructure. Not yet production-proven post-fork.

### 1.2 DuckDB + DuckPGQ

- **GitHub:** duckdb/duckdb — 27,700 stars, MIT
- **Extension:** community extension `duckpgq` (ISO SQL:2023 standard)
- **Query language:** SQL/PGQ — NOT Cypher. MATCH clause syntax similar to Cypher but standard SQL.
- **Performance:** Outperforms Neo4j on pattern matching via multi-core parallel execution and SIMD vectorization. Particularly strong on MS-BFS and shortest path.
- **Python API:** `pip install duckdb` — best-in-class embedded analytics API. 5/5.
- **Local:** ✓ Fully embedded, zero server
- **Cloud:** MotherDuck (extension compatibility with DuckPGQ TBD)
- **MCP:** ✗ No graph-specific MCP
- **AI/agent native:** ✗ No native GraphRAG/agent SDK
- **Key strength:** If data is already tabular (Parquet, CSV, Arrow), adds graph queries with zero additional infrastructure.
- **Key weakness:** DuckPGQ still under active development. No persistent native graph storage — graph is a view over relational tables. No transaction support for graph mutations.
- **Verdict:** Best embedded option for analytics/read-heavy graph queries on tabular data. Not ideal for write-heavy agentic memory.

### 1.3 SQLite + Recursive CTEs

- **License:** Public Domain
- **What it is:** SQLite supports `WITH RECURSIVE` enabling graph traversal without a graph database.
- **Performance reality:**
  - Depth 4, avg branching factor 10 → ~10,000 nodes per query. Manageable.
  - Depth 6, 500K entities → multi-second latency. Painful.
  - No native cycle detection — must track visited path manually in CTE.
  - No native shortest-path — BFS must be implemented manually.
- **Local:** ✓ Fully embedded, single file
- **Cloud:** Turso (libSQL) for edge replication
- **MCP:** ✗ No graph-specific MCP
- **AI/agent native:** ✗ No
- **Verdict:** Acceptable for simple parent-child hierarchies or small entity maps (~200 entities, depth ≤ 3). Not suitable for real knowledge graphs or multi-hop agent memory.

### 1.4 Apache AGE (PostgreSQL Extension)

- **GitHub:** apache/age — 4,600 stars, Apache-2.0, v1.7.0 January 2026
- **What it is:** Adds openCypher graph queries inside PostgreSQL as a first-class extension. Graph + relational in the same DB.
- **Python API:** `pip install apache-age-python` — wraps psycopg2. Functional but rough edges vs native graph DB drivers. 3/5.
- **Cypher support:** Full openCypher inside PostgreSQL `SELECT * FROM cypher(...)` syntax.
- **Performance:** Bulk edge creation for large datasets (83K edges) can take 1+ hour without tuning. With `use_copy=True` and proper indexing: 725K nodes + 2.8M edges loads in 83 seconds.
- **Local:** ✓ Runs inside existing PostgreSQL — zero new servers if already on Postgres.
- **Cloud:** Azure Database for PostgreSQL. NOT supported on AWS RDS. Any self-hosted Postgres.
- **MCP:** Via any PostgreSQL MCP server (not graph-specific)
- **AI/agent native:** ✗ No native GraphRAG SDK. Community tutorials for LangChain/semantic-kernel.
- **Key strength:** If you already run PostgreSQL, this is the least-friction option — no new database. Apache license, truly open.
- **Key weakness:** Not a native graph engine — Cypher compiles to PostgreSQL planner, limiting deep-traversal optimization. Not on AWS RDS.
- **Verdict:** Best for PostgreSQL shops wanting occasional graph queries without new infrastructure. **Relevant for projects already running PostgreSQL.**

---

## Part 2 — Client-Server (Local Docker + Cloud)

### 2.1 FalkorDB ⭐ RECOMMENDED for AI agents

- **GitHub:** FalkorDB/FalkorDB — 4,700 stars, SSPLv1
- **What it is:** Redis module (successor to RedisGraph). Uses GraphBLAS sparse matrix. In-memory with Redis AOF/RDB persistence.
- **Query language:** OpenCypher + FalkorDB extensions
- **Performance (SNAP Pokec, 16-CPU 32GB Linux, 82% read / 18% write):**

| Metric | FalkorDB | Neo4j | Factor |
|---|---|---|---|
| Cold start | 1.1ms | 90ms | 82× faster |
| First query | 0.4ms | 274ms | 685× faster |
| p50 latency | 55ms | 577ms | 10× faster |
| p90 latency | 108ms | 4,784ms | 44× faster |
| p99 latency | 136ms | 46,924ms | **344× faster** |

- **Load 1M relationships:** 12 seconds
- **Memory:** ~3GB for 1M relationships
- **License:** SSPLv1 ⚠ — not OSI-approved. If you offer FalkorDB as a cloud service, must open-source entire stack. For internal AI agents: fine.
- **Docker:** `docker run -d -p 6379:6379 -p 3000:3000 falkordb/falkordb:latest`
- **Embedded:** `pip install falkordb-lite` — embedded mode, no server
- **Python driver:** `pip install falkordb` — official, Redis protocol (RESP + Bolt). 4/5.
- **Local:** ✓ Docker or falkordb-lite (embedded)
- **Cloud:** FalkorDB Cloud (managed)
- **MCP:** ✓ YES — official `code-graph` MCP server. 7 tools: `index_repo`, `search_code`, `find_symbol`, `get_neighbors`, `get_file_neighbors`, `impact_analysis`, `find_path`. Install: `claude mcp add-json code-graph`.
- **AI/agent native:** ✓ YES — GraphRAG SDK 1.0 (`pip install graphrag-sdk[litellm]`, v1.3.0 June 4 2026)
- **GraphRAG-Bench results (Novel dataset, GPT-4o-mini, M3 24GB):**
  - FalkorDB GraphRAG SDK: **63.73 ACC** 🥇
  - MS-GraphRAG: 50.93
  - LightRAG: 45.09
- **Graphiti integration:** ✓ Default and recommended backend. `pip install graphiti-core-falkordb`. Ships FalkorDB + Graphiti in a single Docker compose with MCP.
- **Verdict:** **Best AI agent stack in 2026.** Fastest latency, #1 GraphRAG benchmark, MCP native, Graphiti default. SSPL license — verify legal for your context.

### 2.2 Memgraph

- **GitHub:** memgraph/memgraph — 4,200 stars, BSL (→ Apache-2.0 after 4 years), v3.11.0 June 2026
- **What it is:** In-memory C++ graph database, Cypher-compatible, real-time streaming focus.
- **Performance:**
  - Load 1M relationships: **8 seconds** (fastest loader)
  - p95 query latency: ~5ms
  - Throughput: 100K+ writes/second with streaming
  - Memory: ~4GB for 1M relationships
- **Docker:** `docker run -p 7687:7687 memgraph/memgraph`
- **Python driver:** `pip install gqlalchemy` (OGM) or `pip install pymgclient` (low-level). 4/5.
- **Local:** ✓ Docker
- **Cloud:** Memgraph Cloud
- **MCP:** ✓ YES — `mcp-memgraph` server. Integrated into AI Toolkit monorepo.
- **AI/agent native:** ✓ YES — Memgraph AI Toolkit (LangChain, LlamaIndex, LangGraph integrations). **40+ built-in graph algorithms via MAGE** (PageRank, community detection, shortest path, betweenness centrality).
- **Key strength:** Fastest ingest, best LangGraph integration, 40+ algorithms, full Cypher compatibility with Neo4j (migration-friendly).
- **Key weakness:** BSL license. Fully in-memory — RAM is hard limit. No disk offload in Community.
- **Verdict:** Best for real-time, streaming, write-heavy workloads. Strong LangChain/LangGraph story.

### 2.3 Neo4j Community Edition

- **GitHub:** neo4j/neo4j — 16,800 stars, GPL/AGPL
- **What it is:** Market leader. Native graph database, disk-persisted, JVM-based.
- **Performance:**
  - Cold start: 90ms, first query: 274ms
  - Load 1M relationships: 45 seconds (slowest)
  - JVM pre-allocates 4GB heap — process memory ~5.2GB regardless of data size
  - p99 under heavy load: 46,924ms (see FalkorDB comparison)
- **Docker:** `docker run -p 7687:7687 -p 7474:7474 neo4j:community`
- **Python driver:** `pip install neo4j` — official, excellent, async support, connection pooling. **5/5.**
- **Local:** ✓ Docker
- **Cloud:** **AuraDB Free** — 200K nodes / 400K relationships. Best free managed cloud tier in this space.
- **MCP:** ✓ YES — official `neo4j/mcp` (792 stars) + `neo4j-contrib/mcp-neo4j` (graph database + graph memory + Cypher generation).
- **AI/agent native:** ✓ YES — LangChain (mature, widely used), LlamaIndex, Graphiti 5.26+. Largest ecosystem.
- **Key strength:** Best ecosystem, best documentation, best Python tooling, AuraDB Free for quick cloud start, broadest framework integrations.
- **Key weakness:** JVM footprint (5GB+ process), slowest under load, GPL/AGPL licensing, no embedded mode.
- **Verdict:** Best choice if ecosystem maturity, documentation, and AuraDB Free cloud tier matter most. Not ideal for latency-critical agents.

### 2.4 ArangoDB

- **GitHub:** arangodb/arangodb — 14,200 stars, **Apache-2.0** (Community)
- **What it is:** Multi-model — documents + graphs + key-value in one engine.
- **Query language:** AQL (ArangoDB Query Language) — NOT Cypher. Steeper learning curve.
- **Local:** ✓ Docker
- **Cloud:** ArangoGraph (managed, free trial)
- **MCP:** ✗ No dedicated MCP
- **AI/agent native:** ✓ LangChain (`pip install langchain-arangodb`), LlamaIndex. No native GraphRAG SDK.
- **Key strength:** Truly free Apache-2.0. Multi-model flexibility. 14K+ community.
- **Key weakness:** AQL lock-in — no reuse with Neo4j/Memgraph/FalkorDB Cypher knowledge. No GraphRAG SDK out of the box.
- **Verdict:** Best for teams already on ArangoDB wanting graph. Not recommended greenfield for AI agents due to AQL.

### 2.5 TypeDB

- **GitHub:** typedb/typedb — 4,400 stars, MPL-2.0
- **Query language:** TypeQL — proprietary, not Cypher, not SQL. Unique paradigm.
- **MCP:** ✗ No
- **AI/agent native:** ✗ No native GraphRAG, LangChain, or LlamaIndex integration
- **Verdict:** Only consider if domain has rich type hierarchies. Not recommended for standard GraphRAG/agent-memory use cases.

---

## Part 3 — Python Libraries for Entity/Object Modeling

### 3.1 Graphiti (getzep/graphiti) ⭐ RECOMMENDED for agent memory

- **GitHub:** getzep/graphiti — **27,900 stars**, 2,800 forks, Apache-2.0
- **Paper:** arXiv:2501.13956, cited at ICLR 2026 MemAgents Workshop
- **What it is:** Temporal knowledge graph library for AI agent memory. Builds bi-temporal graphs (valid time + system time) from conversational episodes, JSON, or freeform text.
- **Backends:** Neo4j 5.26+, FalkorDB 1.1.2+, Amazon Neptune, Kuzu 0.11.2 (deprecated)
- **Key operation:** `add_episode(content)` → LLM extracts entities + relationships → stored with temporal validity windows + provenance.
- **Hybrid retrieval:** Semantic embeddings + BM25 keyword + graph traversal — all three combined.
- **LLM support:** OpenAI, Anthropic, Google Gemini, Groq, Azure OpenAI, any OpenAI-compatible endpoint.
- **MCP:** ✓ YES — built-in MCP server (`mcp_server/`). FalkorDB + Graphiti in one Docker compose. Compatible with Claude Desktop, Cursor, VS Code + Copilot.
- **Install:** `pip install graphiti-core` or `pip install graphiti-core-falkordb`
- **Key strength:** Only library purpose-built for agent memory with temporal reasoning. 27.9K stars. Apache-2.0.
- **Key weakness:** Requires LLM call per episode ingestion (cost + latency). Requires running graph DB backend. Structured Output LLM required (OpenAI/Gemini/Anthropic; smaller local models may fail).
- **Python quality:** 5/5
- **Verdict:** If building AI agent memory, start here.

### 3.2 LlamaIndex PropertyGraphIndex

- **GitHub:** run-llama/llama_index — 39,000+ stars, MIT
- **Three extractors:**
  - `SimpleLLMPathExtractor` — freeform, no schema, flexible but inconsistent
  - `SchemaLLMPathExtractor` — predefined schema, consistent, rigid
  - `DynamicLLMPathExtractor` — hybrid: schema-guided + flexible
- **Storage backends:** Neo4j, Memgraph, FalkorDB, NetworkX (in-memory), Nebula, TigerGraph
- **MCP:** ✗ No dedicated (backends have their own MCPs)
- **AI/agent native:** ✓ Core value proposition
- **Python quality:** 4/5
- **Verdict:** Best if already on LlamaIndex. Multi-backend flexibility. FalkorDB or Neo4j as backends.

### 3.3 FalkorDB GraphRAG SDK

- **GitHub:** FalkorDB/GraphRAG-SDK — Apache-2.0
- **Install:** `pip install graphrag-sdk[litellm]` — v1.3.0, June 4 2026
- **What it is:** End-to-end GraphRAG: ingest documents → extract knowledge graph → store in FalkorDB → serve multi-hop queries.
- **GraphRAG-Bench:** #1 on Novel (63.73) and Medical (75.73) corpora.
- **Cost:** ~$5–6 LLM tokens for 1,000-document ingestion (GPT-4o-mini). ~$0.001 per query.
- **MCP:** ✓ Via FalkorDB MCP
- **Verdict:** Best pure GraphRAG pipeline, benchmarked against real evaluation datasets.

### 3.4 NetworkX

- **GitHub:** networkx/networkx — 15,000+ stars, BSD-3
- **What it is:** Pure Python in-memory graph library. De-facto standard for graph algorithms.
- **Performance:** Single-threaded, Python GIL-bound. Practical limit: ~100K nodes / 1M edges.
- **Persistence:** ✗ None — in-memory only, must serialize manually.
- **Python quality:** 5/5 — best Python API of any graph library
- **Verdict:** Use for prototyping and small-scale analytics. Do not use as production persistence layer.

### 3.5 Py2neo — DEAD

- **Status:** EOL. Creator officially deprecated. No further maintenance.
- **Migration:** Switch to `neo4j` (official driver) + `neomodel`.
- **Verdict:** Do not use.

### 3.6 neomodel

- **GitHub:** neo4j-contrib/neomodel — Neo4j Labs, actively maintained since 2023
- **What it is:** Django ORM-style Object Graph Mapper for Neo4j. Define nodes as Python classes.
- **Local:** Neo4j Docker. **Cloud:** AuraDB. **MCP:** ✗ No.
- **Python quality:** 4/5
- **Verdict:** Use for Django-ORM feel on Neo4j. Not standalone for AI agents — pair with Graphiti or LangChain.

---

## Part 4 — Performance Benchmarks

### Load Performance (1M relationships)

| Database | Load Time |
|---|---|
| Memgraph | 8 seconds |
| FalkorDB | 12 seconds |
| Neo4j | 45 seconds |

### Latency Under Load (SNAP Pokec, 16-CPU 32GB Linux)

| Metric | FalkorDB | Memgraph | Neo4j |
|---|---|---|---|
| Cold start | 1.1ms | ~10ms | 90ms |
| p50 | 55ms | ~5ms | 577ms |
| p90 | 108ms | ~15ms | 4,784ms |
| p99 | 136ms | ~50ms | 46,924ms |

### Memory (1M relationships)

| Database | RAM |
|---|---|
| Neo4j | 2GB data + 5.2GB JVM process |
| FalkorDB | ~3GB |
| Memgraph | ~4GB |

### GraphRAG-Bench (Novel, 2,010 questions, GPT-4o-mini, M3 24GB)

| System | Accuracy |
|---|---|
| **FalkorDB GraphRAG SDK** | **63.73** 🥇 |
| MS-GraphRAG | 50.93 |
| LightRAG | 45.09 |

---

## Part 5 — Local vs Cloud Matrix

| Tool | Embedded | Local Docker | Free Cloud | Data stays local |
|---|---|---|---|---|
| LadybugDB | ✓ | ✗ | ✗ | ✓ |
| DuckDB + DuckPGQ | ✓ | ✗ | MotherDuck (TBD) | ✓ |
| SQLite + CTE | ✓ | ✗ | Turso | ✓ |
| Apache AGE | ✗ | ✓ (Postgres) | Azure Postgres | ✓ (self-hosted) |
| FalkorDB | Lite (pip) | ✓ | FalkorDB Cloud | ✓ (local) |
| Memgraph | ✗ | ✓ | Memgraph Cloud | ✓ (local) |
| Neo4j CE | ✗ | ✓ | **AuraDB Free** (200K nodes) | ✓ (local) |
| ArangoDB | ✗ | ✓ | ArangoGraph (trial) | ✓ (local) |
| TypeDB | ✗ | ✓ | TypeDB Cloud | ✓ (local) |
| Graphiti | Via backend | Via backend | Via backend | ✓ (local backend) |
| NetworkX | ✓ (in-memory) | ✗ | ✗ | ✓ |

---

## Part 6 — AI Agent / MCP Integration Matrix

| Tool | MCP | GraphRAG SDK | LangChain | LlamaIndex | Graphiti backend | LangGraph |
|---|---|---|---|---|---|---|
| **FalkorDB** | ✓ (7 tools) | ✓ (#1 bench) | ✓ | ✓ | ✓ (default) | ~ |
| **Neo4j** | ✓ (official) | ~ via LangChain | ✓ (mature) | ✓ | ✓ | ✓ |
| **Memgraph** | ✓ | ~ via AI Toolkit | ✓ (AI Toolkit) | ✓ | ✗ | ✓ (AI Toolkit) |
| ArangoDB | ✗ | ✗ | ✓ | ✓ | ✗ | ✗ |
| TypeDB | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Apache AGE | via PG MCP | ✗ | community | ✗ | ✗ | ✗ |
| **Graphiti** | ✓ (built-in) | N/A (IS the lib) | ✗ | ✗ | N/A | ✗ |
| LlamaIndex PGI | ✗ | ✓ (GraphRAG v2) | ~ | N/A | ✗ | ✗ |
| DuckPGQ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

---

## Final Comparison Matrix

| Tool | Stars | License | Python | Embedded | MCP | AI-Native | Verdict |
|---|---|---|---|---|---|---|---|
| **FalkorDB** | 4.7K | SSPL | 4/5 | Lite | ✓ | ✓ | **Best AI agent stack** |
| **Graphiti** | 27.9K | Apache-2.0 | 5/5 | No | ✓ | ✓ | **Best agent memory lib** |
| **Neo4j CE** | 16.8K | GPL/AGPL | 5/5 | No | ✓ | ✓ | **Best ecosystem + AuraDB Free** |
| **Memgraph** | 4.2K | BSL | 4/5 | No | ✓ | ✓ | **Best real-time/streaming** |
| Apache AGE | 4.6K | Apache-2.0 | 3/5 | No | via PG | ✗ | **Best if already on Postgres** |
| LadybugDB | — | MIT | 4/5 | ✓ | ✗ | ✗ | Watch for maturity |
| DuckDB+PGQ | 27.7K | MIT | 5/5 | ✓ | ✗ | ✗ | Best embedded analytics |
| ArangoDB | 14.2K | Apache-2.0 | 4/5 | No | ✗ | ~ | Multi-model; AQL lock-in |
| LlamaIndex PGI | 39K+ | MIT | 4/5 | NetworkX | ✗ | ✓ | Best LlamaIndex integration |
| NetworkX | 15K+ | BSD-3 | 5/5 | ✓ | ✗ | ✗ | Prototyping only |
| neomodel | ~2K | MIT | 4/5 | No | ✗ | ✗ | Neo4j OGM only |
| Kuzu (orig) | 4K | MIT | — | — | — | — | **ARCHIVED — do not use** |
| py2neo | — | MIT | — | — | — | — | **DEAD — do not use** |
| SQLite+CTE | — | PD | 5/5 | ✓ | ✗ | ✗ | Not a real graph DB |
| TypeDB | 4.4K | MPL-2.0 | 3/5 | No | ✗ | ✗ | Niche |

---

## Recommendations by Use Case

**New AI agent system (GraphRAG + agent memory):**
FalkorDB + Graphiti + FalkorDB GraphRAG SDK. FalkorDB Lite for dev, Docker for staging, FalkorDB Cloud for managed.

**Already on LlamaIndex:**
LlamaIndex PropertyGraphIndex with FalkorDB or Neo4j backend. AuraDB Free for quick cloud.

**LangChain/LangGraph framework:**
Memgraph + Memgraph AI Toolkit. Fastest ingest, 40+ algorithms, best LangGraph story.

**Embedded / no-server mandatory:**
DuckDB + DuckPGQ (analytics/read-heavy). LadybugDB (Cypher, watch maturity). NetworkX (prototyping only).

**Already on PostgreSQL:**
Apache AGE — zero new infrastructure, add graph queries to existing Postgres. Acceptable for small-scale entity maps; not for high-throughput agent memory.

**License-first (truly open source):**
ArangoDB (Apache-2.0), LadybugDB (MIT), Apache AGE (Apache-2.0), Graphiti (Apache-2.0), Neo4j CE (AGPL — verify terms). Avoid FalkorDB (SSPL) and Memgraph (BSL) if OSI-approval required.

---

## Sources

- [Kuzu GitHub (archived)](https://github.com/kuzudb/kuzu)
- [LadybugDB / Vela fork](https://github.com/Vela-Engineering/kuzu)
- [Kuzu benchmark — The Data Quarry](https://thedataquarry.com/blog/embedded-db-2/)
- [FalkorDB GitHub](https://github.com/FalkorDB/FalkorDB)
- [FalkorDB vs Neo4j benchmarks](https://www.falkordb.com/blog/graph-database-performance-benchmarks-falkordb-vs-neo4j/)
- [FalkorDB GraphRAG SDK #1 on GraphRAG-Bench](https://www.falkordb.com/blog/graphrag-sdk-knowledge-graph/)
- [FalkorDB GraphRAG SDK GitHub](https://github.com/FalkorDB/GraphRAG-SDK/)
- [Graphiti GitHub](https://github.com/getzep/graphiti)
- [Graphiti paper arXiv:2501.13956](https://arxiv.org/abs/2501.13956)
- [Graphiti MCP + FalkorDB](https://www.falkordb.com/blog/mcp-knowledge-graph-graphiti-falkordb/)
- [Memgraph GitHub](https://github.com/memgraph/memgraph)
- [Memgraph AI Toolkit](https://github.com/memgraph/ai-toolkit)
- [Memgraph MCP server](https://memgraph.com/blog/introducing-memgraph-mcp-server)
- [Neo4j GitHub](https://github.com/neo4j/neo4j)
- [Neo4j official MCP](https://github.com/neo4j/mcp)
- [Apache AGE GitHub](https://github.com/apache/age)
- [Apache AGE on Azure](https://learn.microsoft.com/en-us/azure/postgresql/azure-ai/generative-ai-age-overview)
- [DuckPGQ extension](https://duckdb.org/community_extensions/extensions/duckpgq)
- [LlamaIndex PropertyGraphIndex](https://www.llamaindex.ai/blog/introducing-the-property-graph-index-a-powerful-new-way-to-build-knowledge-graphs-with-llms)
- [Py2neo EOL](https://medium.com/neo4j/py2neo-is-end-of-life-a-basic-migration-guide-9f11c10d76a3)
- [Neo4j alternatives 2026](https://arcadedb.com/blog/neo4j-alternatives-in-2026-a-fair-look-at-the-open-source-options/)
- [Knowledge graph comparison](https://workforceplaybook.ai/platform-guides/knowledge-graph-comparison-neo4j-vs-memgraph-vs-falkordb)
