# Graph Traversal and Transitive Closure — Theoretical Foundation

> **For:** Cairn OSS — Primitive B (Entity-First Routing); the CS theory that
>   grounds OP-34 (relation closure / bounded entity-graph traversal).
> **Gap closed:** What is the formal computer-science theory behind Cairn's
>   "relation closure"? Why is *bounded* (depth-limited) transitive closure the
>   correct model — not full closure, not unbounded reachability — and why does
>   that theory force a deterministic, LLM-free traversal?
> **Invariants honored:**
>   - Storage-agnostic (theory is independent of any graph backend)
>   - Deterministic (same seed + same corpus state → same reachable set)
>   - Zero generative-LLM on hot path (traversal is a graph algorithm, not inference)
>   - Local-first (algorithms are in-process; no mandatory network)
> **Companion docs:**
>   `../context/ENTITY_GRAPH_TRAVERSAL_RESEARCH_2026.md` (the OP-34 buildable spec
>   this foundation grounds), `../tools/ENTITY_RELATIONSHIP_RESOLUTION_RESEARCH_2026.md`
>   (the resolution step that produces the seed), `../databases/GRAPH_DATABASES_AND_ENTITY_LIBRARIES_2026.md`
>   (backend options)
> **Date:** 2026-06-26
> **Confidence:** Citations to Warshall 1962, CLRS, PageRank 1999, and
>   Haveliwala 2002 are ✓ verified against primary sources (DOIs / publisher
>   pages). The applications-to-Cairn claims are marked ~ inferred or ? assumed.

---

## TL;DR

Cairn's "relation closure" is, formally, a **depth-bounded transitive closure**
of the entity relation under a fixed depth k. The full transitive closure (all
nodes reachable from the seed) is the wrong target for retrieval: it is unbounded,
it is dominated by far-away weakly-relevant nodes, and on a connected graph it
degenerates to "the whole component." Bounding the closure to a k-hop neighborhood
(k=2 by default in OP-34) is the standard graph-theoretic primitive that gives
retrieval its locality. The neighborhood is computed by **breadth-first search**
(CLRS, O(V+E)), which is deterministic and contains no inference — that is what
lets OP-34 keep the LLM off the hot path. **Personalized PageRank** (Page–Brin
1999; Haveliwala 2002) is the principled generalization of this same idea —
seed-biased relevance propagation — and is the theory HippoRAG operationalizes;
OP-34's hop-distance discount `1/(hop+1)` is a cheap, deterministic, fixed-depth
approximation of PPR's decay-with-distance.

---

## 1. Reachability and Transitive Closure

### 1.1 The relation and its closure

Model the entity graph as a directed graph G = (V, E), where V is the set of
canonical entity IDs and E ⊆ V × V is the set of typed relation edges. The edge
set defines a binary relation R on V: (u, v) ∈ R iff there is an edge u → v.

- ✓ verified: The **transitive closure** R⁺ of a relation R is the smallest
  transitive relation containing R: (u, w) ∈ R⁺ iff there exists a directed path
  u → … → w of length ≥ 1. Equivalently, R⁺ encodes **reachability** — (u, w) ∈ R⁺
  iff w is reachable from u. This is the textbook definition (CLRS, *Introduction
  to Algorithms*, transitive-closure section of the all-pairs shortest-paths
  chapter). ([CLRS, MIT Press](https://mitpress.mit.edu/9780262046305/introduction-to-algorithms/))

- ✓ verified: **Warshall's algorithm** (1962) computes the transitive closure of
  a relation represented as a Boolean adjacency matrix in Θ(n³) time via dynamic
  programming over intermediate vertices: t⁽ᵏ⁾_ij = t⁽ᵏ⁻¹⁾_ij ∨ (t⁽ᵏ⁻¹⁾_ik ∧
  t⁽ᵏ⁻¹⁾_kj). This is the canonical "compute reachability for all pairs" result.
  (Warshall, S. "A Theorem on Boolean Matrices," *Journal of the ACM* 9(1):11–12,
  January 1962.) ([JACM, doi:10.1145/321105.321107](https://dl.acm.org/doi/10.1145/321105.321107))

### 1.2 Why *full* closure is the wrong target for retrieval

- ~ inferred: Full transitive closure answers "is w reachable from u at *any*
  distance?" On a connected (or strongly-connected) component, the reachable set
  from any seed is the entire component. For an entity graph where most real-world
  entities are eventually linked, full closure returns ~everything — it has no
  discriminative power as a retrieval filter. Retrieval needs the *near* part of
  the closure, not the closure itself.

- ~ inferred: Warshall's Θ(n³) / O(V·E) all-pairs cost is also unjustified for
  retrieval. Retrieval is **single-source** (one resolved seed entity per query),
  not all-pairs. Computing all-pairs reachability to answer a single-source query
  is the wrong complexity class. The right primitive is a single-source traversal
  bounded by depth — see §3.

- ? assumed: For Cairn's typical corpora (entity graphs in the 10³–10⁵ node range),
  even single-source full reachability would routinely touch tens of thousands of
  nodes, which exceeds any sane context budget. The depth bound is what keeps the
  returned set inside the token budget.

---

## 2. Bounded / Depth-Limited Closure: the k-hop Neighborhood

### 2.1 Definition

- ✓ verified: The **k-hop neighborhood** (or k-th-order ego network) of a seed
  vertex s is N_k(s) = { v ∈ V : d(s, v) ≤ k }, where d is the shortest-path
  (hop) distance. This is standard graph theory: the **ego network** of s is the
  subgraph induced by s and the vertices within distance k of it; k=1 is the
  immediate neighborhood, k=2 adds neighbors-of-neighbors. (Ego-network /
  neighborhood definitions are standard across social-network and graph-theory
  texts.)

- ~ inferred: "Relation closure to depth k" in Cairn is exactly the restriction of
  the transitive closure R⁺ to pairs (s, v) with d(s, v) ≤ k. It is a **bounded
  transitive closure**: transitive up to length k, then cut off. This is the
  formal object OP-34 computes. It is not "approximate" closure — it is the *exact*
  closure of the relation under the constraint "path length ≤ k."

### 2.2 Why bounding is the correct retrieval model

- ~ inferred: Relevance in an entity graph decays with hop distance. A document
  about the seed entity (hop 0) is more relevant than a document about an entity
  two relations away (hop 2). The k-hop bound encodes this decay as a hard cutoff;
  the hop-distance discount (§5) encodes it as a soft ranking. Both rest on the
  same premise: distance in the relation graph is a proxy for relevance distance.

- ✓ verified: This locality premise is what GraphRAG, LightRAG, and HippoRAG all
  exploit — local/entity-first retrieval expands a *bounded* neighborhood around
  query-linked entities rather than computing global reachability. GraphRAG
  explicitly separates *local* (entity-neighborhood) retrieval from *global*
  (community-summary) retrieval. ([GraphRAG, arXiv:2404.16130](https://arxiv.org/abs/2404.16130))

- ? assumed: k=2 is the empirically supported default (see the depth/cost analysis
  in the companion OP-34 spec). The foundation here only claims that *some* finite
  k is theoretically mandatory; the specific value is an empirical tuning question
  resolved in `ENTITY_GRAPH_TRAVERSAL_RESEARCH_2026.md`.

---

## 3. BFS and DFS: the Canonical Traversal Algorithms

### 3.1 Breadth-first search

- ✓ verified: **BFS** explores G from a source s in order of non-decreasing hop
  distance: it discovers all vertices at distance 1, then all at distance 2, and
  so on, computing d(s, v) for every reachable v. It runs in **O(V + E)** time
  (each vertex enqueued/dequeued once; each edge examined once) using a FIFO queue.
  BFS computes shortest paths in unweighted graphs. (CLRS, breadth-first-search
  section.) ([CLRS, MIT Press](https://mitpress.mit.edu/9780262046305/introduction-to-algorithms/))

- ~ inferred: BFS is the natural algorithm for a k-hop neighborhood because it
  *already* visits vertices in hop-distance order. Stopping BFS after the layer at
  distance k yields exactly N_k(s). The hop distance BFS computes is the same
  number OP-34 uses for its `1/(hop+1)` discount — BFS gives the neighborhood and
  the ranking signal in one pass.

### 3.2 Depth-first search

- ✓ verified: **DFS** explores as far as possible along each branch before
  backtracking, also in **O(V + E)**, classifying edges into tree/back/forward/cross
  edges and yielding discovery/finish times (the basis for topological sort and
  SCC algorithms). (CLRS, depth-first-search section.) ([CLRS, MIT Press](https://mitpress.mit.edu/9780262046305/introduction-to-algorithms/))

- ~ inferred: DFS is the wrong default for neighborhood retrieval: it does not
  visit in hop-distance order, so it can spend the traversal budget chasing one
  deep relation chain while missing closer, more relevant entities on adjacent
  branches. The result is path-shaped, not neighborhood-shaped. DFS is appropriate
  for *chain-following* sub-queries (provenance, causal chains), not for
  collecting a k-hop neighborhood.

### 3.3 Why this is deterministic and LLM-free

- ✓ verified: BFS and DFS are pure graph algorithms — their output is a function
  of (G, s) and the edge-iteration order alone. There is no learned component and
  no stochasticity. (Direct consequence of the CLRS pseudocode.)

- ~ inferred: This is the load-bearing property for OP-34's "zero generative-LLM
  on hot path" invariant. Because the traversal is a deterministic O(V+E) graph
  walk, no model inference is on the retrieval path; the only requirement for
  reproducibility is that the adapter iterate a vertex's neighbors in a **stable
  order** (e.g., lexicographic by entity ID). With that, same seed + same corpus
  state → byte-identical reachable set and ranking.

---

## 4. Personalized / Topic-Sensitive PageRank: Seed-Biased Relevance Propagation

### 4.1 PageRank and its personalization

- ✓ verified: **PageRank** models a random surfer on the web graph; the stationary
  distribution of the surfer's position is the PageRank vector, with a damping
  factor (typically d ≈ 0.85) governing the probability of following a link vs.
  teleporting to a node drawn from a distribution. The original formulation uses a
  *uniform* teleport distribution, giving a query-independent global importance
  score. (Page, L., Brin, S., Motwani, R., Winograd, T. "The PageRank Citation
  Ranking: Bringing Order to the Web." Stanford InfoLab Technical Report 1999-66,
  1999.) ([Stanford InfoLab 1999-66](http://ilpubs.stanford.edu:8090/422/))

- ✓ verified: **Personalized / Topic-Sensitive PageRank** replaces the uniform
  teleport vector with one concentrated on a chosen seed set, biasing the
  stationary distribution toward nodes near the seeds. Haveliwala computes a set
  of PageRank vectors each biased toward a representative topic, then combines them
  at query time for query-sensitive ranking. (Haveliwala, T. "Topic-Sensitive
  PageRank." *Proc. 11th International World Wide Web Conference (WWW 2002)*,
  Honolulu, pp. 517–526.) ([WWW 2002, doi:10.1145/511446.511513](https://dl.acm.org/doi/10.1145/511446.511513))

### 4.2 PPR as the principled generalization of bounded closure

- ~ inferred: Personalized PageRank (PPR) is the "soft, weighted, unbounded-but-
  decaying" version of the bounded k-hop closure. The teleport-to-seed mechanism
  makes probability mass concentrate near the seed; the damping factor makes mass
  decay geometrically with hop distance. Where BFS-to-depth-k applies a *hard*
  distance cutoff, PPR applies a *soft* distance decay. Both implement
  "seed-biased, distance-discounted relevance."

- ✓ verified: HippoRAG operationalizes exactly this: it seeds PPR at query-linked
  entity nodes and ranks documents by the cumulative PPR mass on their associated
  entities — letting it surface a document that shares *no query terms* but is
  strongly connected through intermediate entities. ([HippoRAG,
  arXiv:2405.14831](https://arxiv.org/abs/2405.14831))

- ~ inferred: The trade-off PPR carries, relative to bounded BFS: PPR is a
  **global** computation (it assigns mass to all nodes, then ranks), so its cost
  scales with the graph, not with the local neighborhood. It is deterministic
  given fixed graph state (power iteration converges to a unique stationary vector),
  but heavier than a depth-2 BFS. For Cairn's local-first / cheap-hot-path
  invariants, a fixed-depth BFS with a hop discount is the right default; PPR is
  the upgrade for medium graphs where indirect multi-hop connections must be
  scored, not merely collected.

---

## 5. Beam Search: Bounded Best-First Traversal

- ✓ verified: **Beam search** is a heuristic graph search that, at each expansion
  layer, retains only the top-b candidates ("the beam") ranked by a scoring
  function and prunes the rest. It is a bounded-width best-first traversal — a BFS
  whose frontier is capped at width b. (Standard AI-search definition.)

- ✓ verified: **Think-on-Graph** casts an LLM as an agent that runs beam search
  over a knowledge graph: at each hop the model scores candidate relations/entities
  and keeps the top-N reasoning paths, iterating until the answer is found or a
  maximum depth is reached. (Sun et al., "Think-on-Graph: Deep and Responsible
  Reasoning of Large Language Model on Knowledge Graph," ICLR 2024.)
  ([arXiv:2307.07697](https://arxiv.org/abs/2307.07697))

- ~ inferred: Beam search is the bridge between BFS (b = ∞: keep the whole layer)
  and greedy best-first (b = 1: keep only the single best). For Cairn it is
  attractive on *dense* graphs where a full depth-2 BFS would surface too many
  weakly-relevant documents — capping the frontier bounds the candidate set
  regardless of branching factor.

- ~ inferred: The theoretical caveat for Cairn: beam search needs a **scoring
  function** at each layer. In Think-on-Graph that scorer is an LLM, which would
  violate the zero-LLM-on-hot-path invariant. The invariant-preserving form uses a
  *non-generative* scorer (edge weight, relation-type priority, embedding cosine) —
  preserving the pruning benefit while keeping the traversal deterministic and
  inference-free.

---

## 6. Tying the Theory to Cairn's Design

This section is the load-bearing argument: *why these specific theory choices are
correct for agent retrieval*, and how they ground OP-34.

### 6.1 Bounded, not full, transitive closure

- ~ inferred: Agent retrieval needs the *locally relevant* slice of the relation
  closure, not the closure. Full closure (§1.2) degenerates to the connected
  component and has no discriminative power; it also forces all-pairs complexity
  (Warshall Θ(n³)) on a single-source problem. Bounding to N_k(s) (§2) restores
  both discrimination (near ≫ far) and the correct complexity class (single-source
  O(V+E) BFS truncated at depth k). **This is why OP-34 computes a depth-bounded
  closure and never materializes R⁺.**

### 6.2 Why depth = 2 is the principled default

- ~ inferred: Depth 0 returns documents directly about the seed; depth 1 adds
  documents about directly-related entities; depth 2 adds documents two relations
  out (e.g., "the company that acquired the maker of this product"). Depth 2 is the
  smallest bound that captures *bridge* relations (seed → intermediate → target)
  while keeping the neighborhood size O(b²) rather than O(b³). The theory says
  "pick a finite k and discount by distance"; the empirical work in the companion
  spec fixes k = 2.

### 6.3 Why the hop-distance discount `1/(hop+1)` is principled

- ~ inferred: OP-34 scores a document found at hop h with `1/(h+1)` (hop 0 → 1.0,
  hop 1 → 0.5, hop 2 → 0.33). This is a **deterministic, closed-form approximation
  of PPR's decay-with-distance** (§4.2): both encode "relevance falls off
  monotonically with hop distance from the seed." The discount is the cheap
  fixed-depth surrogate for PPR's damping-driven geometric decay — it buys the same
  near-beats-far ranking without running power iteration over the whole graph.
  BFS hands the hop number to the discount for free, since BFS visits in
  hop-distance order (§3.1).

### 6.4 Why traversal is deterministic and LLM-free

- ✓ verified: BFS/DFS/bounded-closure are pure graph algorithms with no learned or
  stochastic component (§3.3). ([CLRS](https://mitpress.mit.edu/9780262046305/introduction-to-algorithms/))

- ~ inferred: This is *why* OP-34 can guarantee its two hardest invariants
  simultaneously. **Determinism**: output is a function of (G, seed, stable
  iteration order) — so same corpus state → identical results, which is testable
  and cacheable. **Zero-LLM-on-hot-path**: there is no inference to remove because
  the algorithm never had any — the LLM's only role is upstream (entity extraction
  at index time, resolution producing the seed) and downstream (generation over the
  returned set), never inside the walk. Contrast Think-on-Graph (§5), which puts an
  LLM scorer *inside* the traversal loop; OP-34 deliberately does not, and the
  beam variant uses a numeric scorer to keep it that way.

### 6.5 PPR and beam as the documented upgrade path

- ~ inferred: The foundation does not reject PPR or beam — it places them on a
  complexity ladder. Fixed-depth BFS + hop discount is the deterministic,
  local-first default. Beam (numeric scorer) is the upgrade for dense graphs where
  the frontier must be capped. PPR (HippoRAG-style) is the upgrade for medium
  graphs where indirect multi-hop connections must be *scored* rather than merely
  collected. All three share the same theoretical core — seed-biased,
  distance-discounted relevance over a directed relation graph — so moving up the
  ladder is a tuning change, not an architectural break.

---

## Tech-spec constraints this produces

These constraints flow from the *theory* and should hold for any OP-34
implementation:

1. **Single-source, depth-bounded — never all-pairs.** The traversal MUST be a
   single-source walk truncated at depth k. Materializing the full transitive
   closure R⁺ (Warshall-style all-pairs) is forbidden — it is the wrong complexity
   class (§1.2, §6.1).

2. **BFS is the default neighborhood algorithm.** Use BFS (O(V+E), hop-ordered)
   for k-hop neighborhood collection; reserve DFS for explicit chain-following
   sub-queries. Truncate BFS after the layer at distance k = depth (§3, §6.2).

3. **Hop distance is a first-class output.** The traversal MUST emit the hop
   distance per discovered node (BFS provides it free) so the `1/(hop+1)` discount
   is computed from a real shortest-path distance, not estimated (§3.1, §6.3).

4. **Discount is monotone-decreasing in hop distance.** Any ranking discount MUST
   be a monotonically non-increasing function of hop distance (the PPR-decay
   analogue). `1/(hop+1)` is the default closed form (§6.3).

5. **Stable neighbor iteration order is required for determinism.** Adapters MUST
   return a vertex's neighbors in a stable, defined order (e.g., lexicographic by
   entity ID). Determinism of the reachable set depends on it (§3.3, §6.4).

6. **No inference inside the traversal loop.** No model call may sit on the
   per-hop expansion path. If beam pruning is enabled, its scorer MUST be numeric
   (edge weight / relation-type priority / embedding cosine), never generative
   (§5, §6.4).

7. **PPR and beam are opt-in upgrades, not the default.** A PPR or beam mode MAY
   be offered for dense/medium graphs, but the deterministic fixed-depth BFS path
   MUST remain the default and MUST remain available (local-first, cheap hot path)
   (§4.2, §6.5).

---

## Sources

- Warshall, S. "A Theorem on Boolean Matrices." *Journal of the ACM* 9(1):11–12,
  January 1962. [doi:10.1145/321105.321107](https://dl.acm.org/doi/10.1145/321105.321107)
- Cormen, T. H., Leiserson, C. E., Rivest, R. L., Stein, C. *Introduction to
  Algorithms* (CLRS). MIT Press. BFS, DFS (O(V+E)) and the transitive-closure
  section of the all-pairs shortest-paths chapter. [MIT Press](https://mitpress.mit.edu/9780262046305/introduction-to-algorithms/)
- Page, L., Brin, S., Motwani, R., Winograd, T. "The PageRank Citation Ranking:
  Bringing Order to the Web." Stanford InfoLab Technical Report 1999-66, 1999.
  [Stanford InfoLab](http://ilpubs.stanford.edu:8090/422/)
- Haveliwala, T. H. "Topic-Sensitive PageRank." *Proc. 11th International World
  Wide Web Conference (WWW 2002)*, Honolulu, pp. 517–526.
  [doi:10.1145/511446.511513](https://dl.acm.org/doi/10.1145/511446.511513)
- Edwards, J., et al. "From Local to Global: A Graph RAG Approach to
  Query-Focused Summarization" (GraphRAG). [arXiv:2404.16130](https://arxiv.org/abs/2404.16130)
- Gutiérrez, B. J., et al. "HippoRAG: Neurobiologically Inspired Long-Term Memory
  for Large Language Models." NeurIPS 2024. [arXiv:2405.14831](https://arxiv.org/abs/2405.14831)
- Sun, J., et al. "Think-on-Graph: Deep and Responsible Reasoning of Large
  Language Model on Knowledge Graph." ICLR 2024. [arXiv:2307.07697](https://arxiv.org/abs/2307.07697)
