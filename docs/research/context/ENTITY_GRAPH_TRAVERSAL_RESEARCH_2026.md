# Entity Graph Traversal — Gap 2 Research

> **For:** Cairn OSS — Primitive B (Entity-First Routing), traversal step
> **Gap closed:** Given a resolved canonical entity ID, how does Cairn walk the
>   entity graph to collect the connected documents/facts to return?
> **Invariants honored:**
>   - Storage-agnostic (adapter above any graph backend)
>   - Deterministic (same entity + same corpus state → same traversal result)
>   - Zero generative-LLM on hot path
>   - Local-first (no mandatory cloud)
> **Companion docs:**
>   `ENTITY_RELATIONSHIP_RESOLUTION_RESEARCH_2026.md` (resolution step, Gap 1),
>   `RAG_ROUTING_AND_PARADIGM_SELECTION_2026.md` (when to route to graph vs flat),
>   `GRAPH_DATABASES_AND_ENTITY_LIBRARIES_2026.md` (backend options)
> **Date:** 2026-06-27
> **Version:** 1.0

---

## TL;DR

The traversal step is **structural, not generative.** Given a resolved entity ID,
Cairn fans out across graph edges to a bounded neighborhood, collects the document
references anchored to those entity nodes and edges, deduplicates, and returns a
ranked document set. Default depth: **2 hops**. Flat-store fallback: **inverted
index by entity ID** — no graph backend required. Community detection is a separate
**global query mode**, not part of standard entity-first traversal.

---

## 1. The Retrieval-Graph Distinction

Graph traversal for **analytics** computes reachability, centrality, or aggregate
statistics across millions of nodes. Graph traversal for **retrieval** is narrower:
starting from a small seed set of entity nodes, collect the minimum set of document
references that make the retrieved context complete for a query.

The two differ on what counts as a result:

| Mode | Unit of result | Stopping criterion |
|------|---------------|--------------------|
| Analytics | Node/edge statistics | Full graph exhausted |
| Retrieval | **Document references** anchored to nodes/edges | Budget hit (depth, doc count, token limit) |

~ inferred: Every major GraphRAG system reviewed (GraphRAG, LightRAG, HippoRAG)
stores backward pointers from entity nodes to the source chunk(s) that generated
them. The traversal algorithm itself has no NLP — it follows edges and collects
these pointers. The LLM is only involved in indexing (entity extraction) and
post-retrieval generation, not on the traversal hot path.

---

## 2. Traversal Strategies: BFS, DFS, Beam, PPR

### 2.1 Breadth-First Search (BFS)

BFS visits all neighbors at depth 1 before expanding to depth 2. For retrieval:

- ✓ verified: BFS finds the shortest path to any reachable node, making it
  **optimal for small-depth local neighborhoods** where completeness within a
  radius matters more than path specificity. (Standard graph theory; confirmed
  across multiple survey sources.)
- ~ inferred: For agent retrieval where the goal is "all documents connected
  to this entity within 2 hops," BFS is the natural default — it is guaranteed
  to collect every document reachable within the depth budget before going deeper.
- ? assumed: Memory usage grows as O(b^d) where b is average branching factor
  and d is depth. At depth 2 with branching factor 10, that is 100 candidates.
  At depth 3 it is 1,000. BFS becomes expensive past depth 2 on dense graphs.

**When BFS wins:** shallow expansions (depth 1–2), completeness required,
no edge-weight signal available.

### 2.2 Depth-First Search (DFS)

DFS follows one path as deep as possible before backtracking. For retrieval:

- ✓ verified: DFS uses O(d) memory vs BFS's O(b^d), making it more memory
  efficient at depth. (Standard graph theory.)
- ~ inferred: DFS is poorly suited for entity retrieval because it may exhaust
  the depth budget down one relation chain while missing closer, more relevant
  documents on adjacent branches. The result set is path-shaped rather than
  neighborhood-shaped.
- ? assumed: DFS may be useful for **relation-chain following** (e.g., "trace the
  provenance chain from document D back to its source entities") but not for
  standard neighborhood expansion.

**When DFS wins:** deep chain-following (provenance, causal chains), memory is
constrained, path structure matters.

### 2.3 Beam Search

Beam search is a heuristic BFS that keeps only the top-k candidates at each layer
(the "beam"), pruning the rest. Think-on-Graph (ICLR 2024) uses this:

- ✓ verified: Think-on-Graph casts the LLM as an agent navigating a KG via beam
  search — at each hop, the model ranks candidate relations/entities and keeps the
  top-N reasoning paths as evidence, not just the single best path. This enables
  multi-hop reasoning without exhaustive BFS. ([openreview.net/forum?id=nnVO1PvbTv])
- ~ inferred: Beam search requires a **scoring function** to rank candidates at
  each layer. In Think-on-Graph that scorer is an LLM, which violates Cairn's
  zero-LLM-on-hot-path invariant. A lightweight non-generative scorer (embedding
  cosine similarity, edge weight, relation-type priority) could preserve the pruning
  benefit without the LLM cost.
- ? assumed: Beam width b=3–5 with depth d=2 is a practical default — this is
  enough to find multi-hop connections while bounding the candidate set to
  ~10–25 nodes.

**When beam search wins:** noisy, dense graphs where full BFS at depth 2 would
surface too many irrelevant documents; relation-type weights are available for
scoring; beam scorer is non-generative (embedding similarity).

### 2.4 Personalized PageRank (PPR)

HippoRAG (NeurIPS 2024) uses PPR as its traversal mechanism:

- ✓ verified: HippoRAG constructs a schemaless entity graph and runs PPR from
  query-linked entity nodes as seeds, spreading probability mass over connected
  nodes. Documents are ranked by the cumulative PPR score of their associated
  entity nodes. "HippoRAG can find a document that contains none of the query words,
  provided it is strongly linked to the query through a chain of intermediate
  entities." ([arxiv.org/abs/2405.14831], DEV community writeup confirmed)
- ✓ verified: HippoRAG "outperforms state-of-the-art RAG methods on multi-hop
  question answering by up to 20%" and is "10–30x cheaper and 6–13x faster" than
  iterative retrieval (IRCoT). ([arXiv:2405.14831 abstract])
- ~ inferred: PPR is inherently global — it assigns scores to ALL nodes in the
  graph, not just a local neighborhood. This is deterministic given fixed graph
  state, but computationally heavier than BFS for small neighborhoods.
- ? assumed: PPR is best suited to corpora where multi-hop indirect connections
  matter and the graph is medium-sized (< ~100K nodes). For very large graphs,
  approximate PPR methods are needed.

**When PPR wins:** multi-hop retrieval on medium-sized graphs; no fixed depth limit
desired; indirect entity connections are expected to be relevant.

### 2.5 Algorithm Selection for Cairn

| Graph size | Depth budget | Relation-type signal | Recommended |
|------------|-------------|----------------------|-------------|
| Any | 1 | None | BFS depth 1 (trivial) |
| Small–medium (< 50K nodes) | 2 | None | BFS depth 2 |
| Small–medium | 2 | Available | Beam (non-LLM scorer) |
| Medium | 2–3, indirect ok | None | PPR |
| Dense/large | 2 | Available | Beam (non-LLM scorer) |

~ inferred: **BFS depth 2 is the right Cairn default.** It covers the
  majority of retrieval-relevant neighborhoods (confirmed by hop-depth research
  below), requires no scoring function, is deterministic, and is straightforward
  to implement above any graph backend via an adapter interface.

---

## 3. Relation Closure: What It Means for Retrieval

**Transitive closure** (formal definition) of a relation R is the smallest
transitive superset R+ — i.e., if (A,B) ∈ R and (B,C) ∈ R, then (A,C) ∈ R+.
Full transitive closure over an entity graph is equivalent to "all nodes reachable
from the seed" — expensive and unbounded.

**Relation closure for retrieval** is a scoped, bounded variant:

```
relation_closure(entity_id, depth, relation_filter, time_filter) →
  Set[DocumentRef]
```

The components:

### 3.1 All-neighbor vs Typed-relation traversal

- ✓ verified: The LogRocket GraphRAG walkthrough demonstrates that typed edges
  enable **selective traversal** — the system only follows edges matching the
  query's semantic intent rather than all edges from a node. Example relation types:
  USES, DEPENDS_ON, GOVERNED_BY, IMPLIES, FORBIDS. This prevents irrelevant
  document bleed from semantically unrelated relations.
- ~ inferred: For Cairn, typed filtering is most valuable when the graph has
  heterogeneous relation types (e.g., a software project graph with AUTHORED_BY,
  DEPENDS_ON, and TESTED_IN edges — a "find all docs about this library" query
  should filter to DEPENDS_ON, not AUTHORED_BY).
- ? assumed: When no relation type signal is available (schemaless graphs),
  all edges should be traversed and post-ranked by edge weight or document relevance.

### 3.2 Edge weighting

- ~ inferred: Weighted edges (co-occurrence frequency, confidence score from
  extraction, or explicit user-set weight) can be used as a pruning signal in
  beam traversal — traverse high-weight edges first, prune when cumulative weight
  drops below a threshold.
- ? assumed: For a first implementation, unweighted BFS is simpler and avoids
  the need for a weighting scheme at indexing time.

### 3.3 Bi-temporal filtering

- ✓ verified: Bi-temporal knowledge graphs (Graphiti, Zep) store two timestamp
  dimensions per edge: (a) valid_from/valid_to — when the fact was true in the
  real world; (b) ingested_at — when it entered the graph. An edge is returned
  only if the query timestamp falls within its valid_from/valid_to window.
  ([neo4j.com/blog/developer/graphiti-knowledge-graph-memory/])
- ✓ verified: When new information contradicts an existing fact, the old edge's
  valid_to is closed rather than deleted. The graph history stays queryable.
  This is a standard bi-temporal pattern in temporal KG literature. ([arXiv:2510.13590])
- ~ inferred: For Cairn, bi-temporal filtering is **optional at depth 1** (most
  entity-to-document edges are atemporal — a document either mentions an entity
  or it does not). It becomes relevant for **relation edges** (entity-to-entity)
  where facts change over time — e.g., "CEO of Acme" should return the current
  CEO, not all historical ones.
- ? assumed: Default: no temporal filter unless query carries an explicit
  `as_of` parameter. Adapter interface should expose `time_filter: Optional[datetime]`.

---

## 4. Depth vs. Cost Tradeoff

### 4.1 Empirical findings on optimal hop depth

- ✓ verified: Research on multi-hop QA benchmarks shows performance **peaks at
  depth 2** for the majority of reasoning tasks. "A depth of 0 or 1 is insufficient
  to connect the bridge entities required by the dataset." For single-hop tasks
  (PopQA), performance converges within 2–3 retrieval steps. For complex multi-hop
  tasks (2WikiMultiHopQA, HotpotQA), 3–5 steps are needed. ([emergentmind.com
  multi-step agentic retrieval topic, arXiv survey on agentic RAG])
- ✓ verified: Agents using structured knowledge graph retrieval "follow links up to
  2 hops deep and make an average of 2.0 tool calls per query." ([arXiv:2603.10700])
- ~ inferred: For **entity-first routing** in Cairn (Primitive B), the query already
  has a resolved entity ID — this is not a multi-hop reasoning task. It is a
  **neighborhood collection** task. The relevant depth is how many relation hops
  away from the seed entity the useful documents live. Two hops covers:
  - Depth 0: documents directly about this entity
  - Depth 1: documents about entities directly related to this entity
  - Depth 2: documents about entities two steps away (e.g., "documents about
    the company that acquired the company that made this product")

### 4.2 The exponential cost problem

At branching factor b and depth d, BFS visits O(b^d) nodes:

| b | d=1 | d=2 | d=3 |
|---|-----|-----|-----|
| 5 | 5 | 25 | 125 |
| 10 | 10 | 100 | 1,000 |
| 20 | 20 | 400 | 8,000 |

- ✓ verified: "Too few hops of graph traversal might overlook critical reasoning
  relations, while too many can introduce unnecessary noise." ([arXiv:2509.21237,
  Query-Centric Graph Retrieval])
- ~ inferred: The research community has converged on adaptive depth — "training
  models to predict the required number of hops for a given query and retrieving
  the relevant graph content accordingly." For Cairn's zero-LLM-on-hot-path
  constraint, a non-learned heuristic must substitute: use the query's
  `complexity_hint` parameter (single-entity vs. multi-hop) to set depth
  dynamically, defaulting to 2.
- ? assumed: A practical cap: at depth 2, collect **at most N_max documents**
  (configurable, default 20). Stop early if budget hit. This bounds cost
  regardless of branching factor.

### 4.3 Summary recommendation

| Query type | Default depth | Rationale |
|-----------|--------------|-----------|
| Single entity lookup | 1 | Documents directly about the entity; depth 2 adds noise |
| Entity + context | 2 | Covers immediate relations and their source docs |
| Multi-hop reasoning | 2–3 | Rare in Primitive B (already resolved entity) |
| Global sensemaking | Community mode | Not depth-based; see Section 6 |

---

## 5. Fallback When No Graph Exists

Many Cairn deployments will not have a graph backend. The fallback path must be
deterministic and produce structurally equivalent output.

### 5.1 The entity-to-document inverted index

- ✓ verified: Standard inverted indexes can map entity mentions to the documents
  that contain them. Systems build "an inverted index that associates entity
  mentions with the pages and sentences they occur in." ([USPTO patent literature;
  confirmed in graph-RAG fallback survey with "BM25 fallback for entity-missing
  queries, triggering for roughly 6–8% of queries and yielding consistent gains"])
- ~ inferred: For Cairn, the flat-store fallback is:
  ```
  entity_id → Set[doc_id]   # stored at index time when entity is detected in doc
  ```
  Traversal at depth 1: return all docs where `entity_id` appears.
  Traversal at depth 2: not directly possible without relation edges.
  Fallback gracefully degrades: flat store → depth-1 results only.

### 5.2 Flat-store traversal algorithm

```
function flat_traverse(entity_id, corpus) → Set[DocumentRef]:
    return corpus.entity_index.lookup(entity_id)  # O(1) hash lookup
```

This is the "depth-0" case in graph terms — it returns documents where the entity
is directly mentioned, with no relation traversal. It is:
- Deterministic: same entity_id → same doc set for same corpus state
- Storage-agnostic: works above any key-value store
- Zero-LLM: pure structural lookup
- Local-first: no network calls

- ? assumed: When the flat fallback is used, Cairn should include a
  `traversal_mode: "flat"` flag in the ContextPackage so downstream consumers
  know that relation-based depth was unavailable. This enables the caller to
  decide whether to escalate to a more expensive path.

### 5.3 Upgrade path

Flat → graph is a capability upgrade, not a breaking change:
```
if graph_adapter_available:
    return graph_traverse(entity_id, depth=2, relation_filter, time_filter)
else:
    return flat_traverse(entity_id, corpus)
```

---

## 6. Community Detection: When Cairn Needs It

Community detection is **not part of standard entity-first traversal**. It is a
separate mode for **global sensemaking** queries.

### 6.1 GraphRAG's Leiden-based communities

- ✓ verified: GraphRAG uses the Leiden algorithm for hierarchical community
  detection. Leiden produces levels: Level 0 = finest-grained clusters (a few
  highly related entities); higher levels aggregate communities into broader
  clusters. An LLM generates a summary for each community at each level.
  At query time, community summaries are scored (map step) and the top summaries
  are assembled into a final answer (reduce step). ([arXiv:2404.16130v2, GraphRAG
  community detection docs at mintlify.com/microsoft/graphrag])
- ✓ verified: GraphRAG's community approach is designed for "global sensemaking
  questions" such as "What are the main themes in this dataset?" — questions that
  require surveying the entire corpus. It does NOT improve over vector-RAG for
  "specific local retrieval." ([arXiv:2404.16130 paper findings, confirmed by the
  ENTITY_RELATIONSHIP_RESOLUTION_RESEARCH_2026.md entry already in the Cairn repo])
- ~ inferred: Cairn's routing layer (OP-28) should distinguish:
  - **Local query** (entity-first): use graph traversal depth 1–2 → Primitive B
  - **Global query** (sensemaking, themes, summaries): use community summaries →
    separate pathway, community mode
  Community detection should run at **index time**, not on the hot path.

### 6.2 LightRAG's dual-level modes

- ✓ verified: LightRAG implements explicit retrieval modes. **Local mode**: LLM
  extracts low-level keywords (specific entity names) → retrieves top_k entities
  by vector similarity → traverses their graph neighborhood. **Global mode**: LLM
  extracts high-level keywords (concepts, themes) → retrieves top_k relations →
  surfaces broader topic context. **Hybrid/Mix mode**: combines both.
  ([lightrag.github.io, HKUDS/LightRAG GitHub])
- ~ inferred: The LightRAG architecture confirms the local/global split is
  architecturally motivated, not ad hoc. For Cairn: entity-first routing IS
  local mode. A future global mode would need community summaries pre-built
  at index time (Leiden or equivalent).

### 6.3 Decision rule for community mode

```
IF query.type == "global_sensemaking":
    return community_retrieve(level=auto, budget=token_limit)
ELIF query.has_resolved_entity:
    return graph_traverse(entity_id, depth=2)  # Primitive B
ELSE:
    fallback to Primitive A (semantic) or Primitive C (lexical)
```

Community detection is **only needed** when:
- The query has no entity anchor (nothing to seed traversal from)
- The query explicitly asks for themes, summaries, or "what's the big picture"
- The corpus has been pre-indexed with community summaries

Without pre-built community summaries, global mode is unavailable. This is
acceptable for v1 of Primitive B — the gap can be flagged in the ContextPackage.

---

## 7. Buildable Spec: Cairn Traversal Algorithm

This section is written to feed directly into a new Operation Pattern (OP) in
the Cairn patterns yaml.

### 7.1 Adapter interface (storage-agnostic)

```python
class GraphAdapter(Protocol):
    def neighbors(
        self,
        entity_id: str,
        relation_types: Optional[list[str]] = None,  # None = all
        time_filter: Optional[datetime] = None,       # None = atemporal
    ) -> list[tuple[str, str, float]]:
        """Returns [(neighbor_entity_id, relation_type, edge_weight), ...]"""
        ...

    def docs_for_entity(self, entity_id: str) -> list[DocumentRef]:
        """Returns all DocumentRef objects anchored to this entity node."""
        ...
```

The adapter is the **only** interface the traversal algorithm calls. Implementations
can back this with NetworkX (in-memory), SQLite (flat-file graph), Neo4j, FalkorDB,
or any graph backend. The traversal algorithm itself has no backend dependency.

### 7.2 Core traversal algorithm

```python
def entity_traverse(
    seed_entity_id: str,
    adapter: GraphAdapter,
    depth: int = 2,
    relation_filter: Optional[list[str]] = None,
    time_filter: Optional[datetime] = None,
    max_docs: int = 20,
    beam_width: Optional[int] = None,  # None = full BFS; int = beam BFS
) -> TraversalResult:
    """
    Deterministic BFS (or beam-BFS) from a resolved entity ID.
    Returns ranked DocumentRef set + traversal metadata.
    Zero LLM calls. Storage-agnostic via GraphAdapter.
    """
    visited_entities: set[str] = set()
    doc_scores: dict[str, float] = {}     # doc_id → score
    frontier: list[str] = [seed_entity_id]

    for hop in range(depth + 1):  # +1 includes hop=0 (the seed itself)
        next_frontier: list[str] = []

        for entity_id in frontier:
            if entity_id in visited_entities:
                continue
            visited_entities.add(entity_id)

            # Collect documents anchored to this entity node
            for doc_ref in adapter.docs_for_entity(entity_id):
                score = 1.0 / (hop + 1)  # discount by hop distance
                if doc_ref.id not in doc_scores or doc_scores[doc_ref.id] < score:
                    doc_scores[doc_ref.id] = score
                if len(doc_scores) >= max_docs:
                    break

            if hop < depth:  # don't expand on final hop
                nbrs = adapter.neighbors(entity_id, relation_filter, time_filter)
                # Optional beam pruning (non-LLM: by edge weight)
                if beam_width is not None:
                    nbrs = sorted(nbrs, key=lambda t: t[2], reverse=True)[:beam_width]
                next_frontier.extend(nbr_id for nbr_id, _, _ in nbrs)

        frontier = next_frontier
        if len(doc_scores) >= max_docs:
            break  # early stop: budget hit

    ranked_docs = sorted(doc_scores.items(), key=lambda kv: kv[1], reverse=True)

    return TraversalResult(
        seed_entity_id=seed_entity_id,
        documents=[DocumentRef(id=doc_id) for doc_id, _ in ranked_docs],
        traversal_depth=depth,
        entities_visited=len(visited_entities),
        traversal_mode="beam_bfs" if beam_width else "bfs",
        fallback=False,
    )
```

### 7.3 Flat-store fallback path

```python
def flat_traverse(
    entity_id: str,
    entity_index: dict[str, list[DocumentRef]],  # built at index time
) -> TraversalResult:
    docs = entity_index.get(entity_id, [])
    return TraversalResult(
        seed_entity_id=entity_id,
        documents=docs,
        traversal_depth=0,
        entities_visited=1,
        traversal_mode="flat",
        fallback=True,
    )
```

### 7.4 Dispatch function

```python
def traverse(
    entity_id: str,
    adapter: Optional[GraphAdapter],
    entity_index: dict[str, list[DocumentRef]],
    config: TraversalConfig,
) -> TraversalResult:
    if adapter is not None:
        return entity_traverse(entity_id, adapter, **config.graph_params)
    else:
        return flat_traverse(entity_id, entity_index)
```

### 7.5 TraversalConfig shape

```yaml
# cairn traversal config (per-deployment)
traversal:
  depth: 2                    # default hop depth (1 or 2 for most cases)
  max_docs: 20                # stop collecting after this many documents
  beam_width: null            # null = full BFS; int = beam-BFS (needs edge weights)
  relation_filter: null       # null = all relations; list = typed filter
  time_filter: null           # null = atemporal; ISO datetime = as_of filter
  fallback_mode: "flat"       # "flat" | "error" when no graph adapter
```

---

## 8. Properties Audit Against Charter Invariants

| Invariant | How the algorithm satisfies it |
|-----------|-------------------------------|
| **Storage-agnostic** | Traversal only calls `GraphAdapter.neighbors()` and `docs_for_entity()`. Adapter is swapped per backend. |
| **Deterministic** | BFS visit order is deterministic (frontier is a list, not a set, processed in stable order). Same entity + same corpus state → same ranked doc list. |
| **Zero generative-LLM on hot path** | No LLM calls in traversal. Beam scoring uses edge weight (numeric), not an LLM. |
| **Local-first** | No network calls in the algorithm. Backend adapter may use a local file or in-process DB. |

? assumed: Determinism in BFS requires that `adapter.neighbors()` returns
edges in a stable order (by entity_id lexicographic, for example). The adapter
spec should require this and implementations should sort output.

---

## Tech-Spec Constraints This Produces

These feed directly into the OP for Gap 2:

1. **`GraphAdapter` protocol** — two methods (`neighbors`, `docs_for_entity`);
   implementations for SQLite, NetworkX, Neo4j, FalkorDB are separate adapter
   modules. Adapter output MUST be lexicographically sorted for determinism.

2. **Default depth = 2** — configurable; depth 1 for performance-sensitive
   single-entity lookups; depth 3 only when the query complexity_hint signals
   multi-hop.

3. **max_docs cap** — required parameter (not optional). Prevents unbounded
   result sets at high branching factor.

4. **Hop-distance discount** — score = 1/(hop+1). Depth-0 docs score 1.0,
   depth-1 score 0.5, depth-2 score 0.33. This provides a deterministic ranking
   without an LLM.

5. **Flat fallback** — always available. The entity index (entity_id → list[doc_id])
   is built at index time alongside the graph. Cairn deployments with no graph
   backend get depth-0 results automatically.

6. **Traversal mode tag** — `TraversalResult.traversal_mode` carries "bfs",
   "beam_bfs", or "flat". Downstream ContextPackage includes this so callers
   can log or escalate.

7. **Community mode is NOT part of this OP** — global sensemaking queries route
   to a separate pathway (future OP). The traversal OP covers local entity-first
   queries only.

8. **Bi-temporal filter is optional** — `time_filter: Optional[datetime]` in both
   the adapter interface and config. Atemporal by default; activated by the
   caller passing an `as_of` timestamp.

---

## Sources

- [arXiv:2404.16130 — GraphRAG: From Local to Global](https://arxiv.org/abs/2404.16130)
- [arXiv:2404.16130v2 — GraphRAG (full HTML)](https://arxiv.org/html/2404.16130v2)
- [arXiv:2410.05779 — LightRAG](https://arxiv.org/abs/2410.05779)
- [LightRAG project page](https://lightrag.github.io/)
- [HKUDS/LightRAG GitHub (EMNLP 2025)](https://github.com/HKUDS/LightRAG)
- [arXiv:2405.14831 — HippoRAG (NeurIPS 2024)](https://arxiv.org/abs/2405.14831)
- [Think-on-Graph — ICLR 2024](https://openreview.net/forum?id=nnVO1PvbTv)
- [arXiv:2501.00309v2 — Retrieval-Augmented Generation with Graphs (survey)](https://arxiv.org/html/2501.00309v2)
- [arXiv:2510.13590 — RAG Meets Temporal Graphs](https://arxiv.org/html/2510.13590v1)
- [Graphiti knowledge graph memory — Neo4j blog](https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/)
- [GraphRAG community detection — Mintlify/Microsoft docs](https://www.mintlify.com/microsoft/graphrag/concepts/community-detection)
- [Graph RAG Relationship Retrieval — LogRocket](https://blog.logrocket.com/graph-rag-relationship-retrieval/)
- [Emergent Mind: Multi-Step Agentic Retrieval](https://www.emergentmind.com/topics/multi-step-agentic-retrieval)
- [arXiv:2603.10700 — Structured Linked Data as Agent Memory](https://arxiv.org/html/2603.10700)
- [arXiv:2509.21237 — Query-Centric Graph Retrieval](https://arxiv.org/pdf/2509.21237)
- [HippoRAG — DEV Community writeup](https://dev.to/shrsv/about-hipporag-3mf6)
- [GraphRAG Implementation Guide 2026 — Premia.io](https://blog.premai.io/graphrag-implementation-guide-entity-extraction-query-routing-when-it-beats-vector-rag-2026/)
