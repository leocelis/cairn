# The Entity-Relationship Model and Labeled Property Graphs — Foundations Research

> **For:** Cairn OSS — the theoretical foundation for the SHAPE of the entity map
>   (what an entity is, what a relation is, and why the map is modeled the way it is).
> **Gap closed:** Cairn asserts its entity map "is a labeled property graph" without
>   grounding that claim in data-modeling theory. This doc supplies the formal
>   lineage (ER model → property graph / RDF), defines the labeled-property-graph
>   model precisely, compares it to the RDF triple model, and shows why the LPG —
>   not RDF, not relational tables — is the correct model for Cairn's entity map.
> **Invariants honored:**
>   - Storage-agnostic (the model is logical; it does not dictate a backend)
>   - Deterministic (canonical IDs are explicit, not inferred at query time)
>   - Zero generative-LLM on hot path (the model is structural, queried by traversal)
>   - Local-first (an LPG is representable in-process, no server required)
> **Companion docs:**
>   `ENTITY_GRAPH_TRAVERSAL_RESEARCH_2026.md` (OP-34, how the graph is walked),
>   `ENTITY_RELATIONSHIP_RESOLUTION_RESEARCH_2026.md` (OP-28, resolving to canonical IDs),
>   `ONTOLOGY_AUTHORING_RESEARCH_2026.md` (OP-35, authoring the typed-edge schema),
>   `GRAPH_DATABASES_AND_ENTITY_LIBRARIES_2026.md` (backend options)
> **Date:** 2026-06-26
> **Confidence:** Primary-source-grounded. All five founding sources (Codd 1970,
>   Chen 1976, RDF 1.1 W3C Rec, ISO/IEC 39075:2024 GQL, Angles et al. CSUR 2017)
>   were retrieved and verified against publisher records during research.
> **Version:** 1.0

---

## TL;DR

Cairn's entity map is, formally, a **labeled property graph (LPG)**: entities are
**nodes** carrying a canonical ID, a type/label, and a property map; relations are
**typed, directed edges** that may themselves carry properties. This is one of two
mature graph data models in the literature. The other is the **RDF triple model**
(subject–predicate–object). Both descend from the **Entity-Relationship model**
(Chen, 1976), which itself was a semantic layer proposed over Codd's **relational
model** (Codd, 1970).

✓ verified: The LPG is the model standardized by **ISO/IEC 39075:2024 (GQL)** —
the first new ISO database-language standard since SQL (1987) — which "defines data
structures and basic operations on property graphs."

The LPG is the right model for Cairn because (1) entities need first-class identity
and attributes *on the node*, which RDF only achieves through reification overhead;
(2) edges need their own properties (confidence, valid-time, source) which RDF
triples cannot carry without reification; (3) the model maps 1:1 onto Cairn's
existing operating primitives — OP-28 (the canonical entity record = a node),
OP-35 (the typed-edge ontology = the edge-label set), OP-34 (graph traversal =
walking labeled edges).

---

## 1. The backdrop: Codd's relational model (1970)

✓ verified: E. F. Codd, *"A Relational Model of Data for Large Shared Data Banks,"*
*Communications of the ACM*, Vol. 13, No. 6 (June 1970), pp. 377–387,
DOI `10.1145/362384.362685`.

Codd proposed that data be organized as **relations** (mathematically, sets of
n-tuples over named domains) — what practitioners call tables of rows and columns.
The model's power is *data independence*: applications query data by its logical
shape, not its physical storage. It introduced n-ary relations, normalization, and
the idea of a universal data sublanguage (the lineage that became SQL).

~ inferred: The relational model is the **backdrop** every later model reacts to.
Its limitation, for the entity-map use case, is that **relationships are implicit** —
expressed as shared key values across tables and *materialized only at query time*
by JOINs. There is no first-class "relationship" object; a relationship's existence
is a side effect of matching foreign keys. For a navigation layer whose entire job
is to *follow relations*, this is the wrong primitive: each hop is a JOIN, and a
k-hop path is a k-way self-join whose cost grows combinatorially.

? assumed: Cairn will sometimes route *to* relational stores as a backend (it is
storage-agnostic), but it does not adopt the relational model as the **logical
model of its own entity map**. This is a modeling decision, confirmable against the
storage-agnostic invariant in `cairn_system_intent.yaml`.

---

## 2. The founding paper: the Entity-Relationship model (Chen, 1976)

✓ verified: Peter Pin-Shan Chen, *"The Entity-Relationship Model — Toward a Unified
View of Data,"* *ACM Transactions on Database Systems (TODS)*, Vol. 1, No. 1
(March 1976), pp. 9–36, DOI `10.1145/320434.320440`. It is among the most-cited
papers in computer science.

Chen's contribution was to add a **semantic layer** that the relational model
lacked. The ER model names three primitives:

1. **Entity** — a "thing" that can be distinctly identified (a person, a project,
   a document). Entities are grouped into **entity sets** (types).
2. **Relationship** — an *association among entities*, first-class and named
   (e.g. an `authored` relationship between a Person and a Document). Crucially,
   in the ER model the relationship is a **modeling object in its own right**, not
   a derived JOIN. This is the conceptual ancestor of the graph edge.
3. **Attribute** — a property value attached to an entity or a relationship,
   drawn from a value set.

~ inferred: The ER model is the **direct conceptual parent of both modern graph
models.** Entity → node; relationship → edge; attribute → property. The two graph
families below are two different *concrete* realizations of Chen's three
primitives — they disagree mainly on *where attributes live* (on the node/edge
itself, vs. as more triples) and on *whether edges have identity*.

✓ verified: Chen also introduced the **ER diagram** (boxes = entities, diamonds =
relationships, ovals = attributes) — the notational ancestor of the entity-map
diagrams Cairn produces.

---

## 3. The labeled property graph (LPG) model

### 3.1 Informal definition

An LPG represents data as:

- **Nodes** (vertices): each has a unique identity, zero or more **labels**
  (its type(s)), and a set of **properties** (key→value pairs).
- **Relationships** (edges): each is **directed**, has exactly one **type**
  (a label), connects a source node to a target node, and — the defining feature —
  may itself carry **properties**.

✓ verified: This is the model behind **Neo4j** and is the model formally
standardized by **ISO/IEC 39075:2024 — *Information technology — Database
languages — GQL***, published by ISO/IEC on **12 April 2024**. Per ISO, GQL
"defines data structures and basic operations on property graphs" and provides
capabilities for "creating, accessing, querying, maintaining, and controlling
property graphs." It was produced by **ISO/IEC JTC 1/SC 32 WG3** — the same
committee responsible for SQL — and is "the first new ISO database language
standard since SQL in 1987." GQL is positioned as SQL's *sibling*, not an
extension: SQL for relational data, GQL for graph-shaped data.

### 3.2 Formal definition (academic treatment)

✓ verified: A precise formalization appears in Angles, Arenas, Barceló, Hogan,
Reutter & Vrgoč, *"Foundations of Modern Query Languages for Graph Databases,"*
*ACM Computing Surveys*, Vol. 50, No. 5 (2017), Article 68,
DOI `10.1145/3104031` (preprint arXiv:1610.06264). The survey distinguishes two
graph data models: **edge-labelled graphs** (nodes connected by directed, labelled
edges — the structural core of RDF) and **property graphs** (where nodes *and*
edges may additionally carry attribute key/value pairs).

~ inferred (standard formalization synthesized from that survey): An LPG is a tuple

```
G = (N, E, ρ, λ, σ)
```

where `N` is a finite set of node identifiers, `E` is a finite set of edge
identifiers (note: edges have **their own identity**), `ρ: E → (N × N)` maps each
edge to its ordered (source, target) pair, `λ: (N ∪ E) → Set(Label)` assigns
labels to nodes and edges, and `σ: (N ∪ E) × Key → Value` assigns properties to
nodes *and* edges. The two features that distinguish the LPG from a bare labelled
graph are (a) **properties on edges** and (b) **edge identity** (the same pair of
nodes can be connected by two distinct edges of the same type).

### 3.3 Why edge properties and edge identity matter

~ inferred: These two features are exactly what an *agent-native entity map*
needs. An edge such as `Person --[authored]--> Document` is not enough; Cairn must
attach `confidence`, `valid_from`/`valid_to` (bi-temporal validity — see OP-28),
and `source` *to the relationship itself*. The LPG models this natively: the edge
is an object with properties. (Section 4 shows RDF cannot do this without
reification.)

---

## 4. The RDF triple model (the alternative)

✓ verified: *RDF 1.1 Concepts and Abstract Syntax* is a **W3C Recommendation**,
published **25 February 2014** (superseding the 2004 RDF Recommendations). Its
abstract syntax has two core structures: an **RDF graph** is a set of
**subject–predicate–object triples**, and an **RDF dataset** is a default graph
plus zero or more named graphs.

### 4.1 The triple

Every fact is a single **triple** `(subject, predicate, object)`:

- **subject** — an IRI or a blank node
- **predicate** — an IRI (the relationship type)
- **object** — an IRI, a blank node, or a **literal** (a typed/​language-tagged
  value)

✓ verified: There are no "properties on edges." An attribute of a thing is *itself
another triple* whose object is a literal — e.g. `(:alice, :name, "Alice")`. The
graph is therefore *uniformly* triples all the way down; identity is global
(IRIs), which is RDF's great strength for **cross-dataset linking / Linked Data**
and for layering formal semantics (RDFS, OWL) and the SPARQL query language on top.

### 4.2 The reification cost

✓ verified (consequence of the triple model): To say something *about a
relationship* (e.g. "the `authored` link between Alice and Doc-7 has confidence
0.9, asserted by source S, valid since 2024"), RDF must **reify** the statement —
introduce a stand-in resource representing the triple and hang further triples off
it. Classic reification turns one fact into four-plus triples and is widely
criticized as verbose and hard to query.

~ inferred: This is the decisive modeling difference for Cairn. The properties
Cairn must put on *every* edge (confidence, bi-temporal validity, provenance) are
edge-native in an LPG and reification overhead in RDF. (RDF-star / RDF 1.2 reduces
this pain by allowing a triple to be the subject of another triple, but it is a
later extension layered to *recover* a capability the LPG had from the start.)

---

## 5. Property graph vs RDF — side-by-side

✓ verified against Angles et al. (CSUR 2017) and the two standards (RDF 1.1,
ISO/IEC 39075:2024):

| Dimension | Labeled Property Graph (LPG) | RDF triple model |
|---|---|---|
| Unit of data | Node / edge objects | Triple (S, P, O) |
| Node identity | Internal node ID + user keys | Global IRI (or blank node) |
| Edge identity | **Yes** — edges are first-class objects | No — a predicate is just an IRI in a triple |
| Attributes on nodes | Native (property map) | More triples (object = literal) |
| **Attributes on edges** | **Native** | Requires **reification** (or RDF-star) |
| Schema/semantics | Optional; label set + app constraints (GQL) | Rich, standardized: RDFS/OWL ontologies |
| Standard query language | **GQL** (ISO/IEC 39075:2024); Cypher | **SPARQL** (W3C Rec) |
| Sweet spot | Operational graphs, traversal, edges-with-data | Data integration, Linked Data, formal inference |
| Global interoperability | Weaker (no universal node IRI) | **Strong** (IRIs are global) |

~ inferred (the trade in one line): **RDF optimizes for global interoperability
and formal semantics; the LPG optimizes for first-class, attribute-rich edges and
operational traversal.** Cairn's entity map is an operational, local-first,
edge-attribute-heavy structure consulted on the retrieval hot path — squarely the
LPG's sweet spot.

---

## 6. Why the LPG is the right model for Cairn's entity map

This section ties the theory to Cairn's design. The decision is **LPG, not RDF,
not relational tables.**

### 6.1 Not relational tables

~ inferred: Relationships in the relational model are implicit (foreign keys
materialized by JOINs at query time). Cairn's whole purpose is to *follow*
relations cheaply and deterministically; a k-hop path as a k-way self-join is the
wrong cost curve, and there is no first-class place to store edge attributes.
Cairn may *route to* relational backends, but its logical entity map is a graph.

### 6.2 Not RDF

~ inferred: Three Cairn requirements make RDF a poor fit as the *primary* model:
1. **Edge properties are mandatory, not optional.** Confidence, bi-temporal
   validity (OP-28), and provenance live on every edge. RDF needs reification;
   the LPG stores them natively.
2. **Determinism + local-first over global IRIs.** Cairn's identity is a
   *canonical ID owned by the user* (OP-35 ontology), resolved deterministically
   (OP-28). RDF's value is global IRI linking — a benefit Cairn does not need on
   its hot path and that adds authoring burden.
3. **Hot-path traversal, not inference.** Cairn does structural traversal (OP-34),
   not OWL entailment. RDF's formal-semantics advantage is unused weight here.

(? assumed: an **RDF export adapter** remains worthwhile for interop, since
storage-agnosticism is an invariant. That is an output format, not the internal
model.)

### 6.3 The 1:1 mapping onto Cairn's operating primitives

✓ verified (OP definitions read from `docs/patterns/patterns_retrieval_knowledge.yaml`):

| LPG construct | Cairn primitive | Role |
|---|---|---|
| **Node** = canonical ID + label(s) + property map | **OP-28** — the canonical entity record / resolution cascade | Resolution produces the `canonical_id` that *is* a node identity; the node's label is its `entity_type` |
| **Edge label set** (typed, directed relations) | **OP-35** — ontology authoring (the typed-edge schema, aliases, entity_type) | The authored ontology *is* the LPG's label vocabulary and edge-type catalog |
| **Edge properties** (confidence, valid-time, source) | **OP-28** bi-temporal model (valid_at/invalid_at; created_at/expired_at) | Edge-native attributes — the feature RDF lacks without reification |
| **Graph traversal** over labeled edges | **OP-34** — entity graph traversal (BFS depth=2, typed-relation filtering) | Walking labeled, directed edges; "typed-relation filtering" *is* querying by edge label |

~ inferred: The mapping is exact because Cairn's primitives were designed against
graph semantics already; this doc supplies the formal name and lineage for what
OP-28/34/35 collectively implement. The "store both directions / mirror-edge"
note in OP-28 (the reversal-curse fix) is precisely an LPG **directed-edge**
concern — directionality is a first-class property of `ρ: E → (N × N)`.

---

## 7. Open questions / boundaries

- ? assumed: Whether Cairn permits **multiple labels per node** (LPG allows it;
  GQL supports it). Recommendation: allow a primary `entity_type` plus optional
  secondary labels, deferred to the OP-35 schema in the tech-spec phase.
- ? assumed: Whether **multi-edges** (two `authored` edges between the same pair,
  distinct provenance/time) are kept distinct or merged. The LPG's edge-identity
  feature *permits* keeping them distinct; bi-temporal modeling (OP-28) suggests
  doing so. To be fixed as a tech-spec constraint.
- ~ inferred: An **RDF/SPARQL export** path is a future interop adapter, not a
  change to the internal model (§6.2).

---

## Tech-spec constraints this produces

1. **The entity map's logical model is a labeled property graph.** Nodes carry a
   canonical ID, one or more labels (`entity_type`), and a property map; edges are
   directed, single-typed, identity-bearing, and carry properties. (Source: §3,
   ISO/IEC 39075:2024; Angles et al. 2017.)
   *Test path (tech-spec):* `tests/test_model.py::test_edge_carries_properties` —
   an edge round-trips with `confidence`, `valid_from`, `source` intact.
2. **Edges are directed and identity-bearing.** Direction is stored; the same node
   pair may hold ≥2 distinct edges. Reverse traversal uses stored/mirror edges,
   never inferred symmetry (OP-28 reversal-curse fix). (Source: §3.2, §6.3.)
   *Test path:* `tests/test_model.py::test_directed_edge_and_multiedge`.
3. **Edge attributes are model-native, never reified.** Confidence, bi-temporal
   validity, and provenance are first-class edge properties; the internal model
   MUST NOT require RDF-style reification to store facts about a relationship.
   (Source: §4.2, §6.2.) *Test path:*
   `tests/test_model.py::test_no_reification_for_edge_metadata`.
4. **Canonical identity is explicit and user-owned, not a global IRI and not
   query-time-invented.** Node identity = the OP-28 canonical_id from the OP-35
   ontology. (Source: §6.2; `explicit_canonical_ontology` invariant.)
   *Test path:* `tests/test_resolve.py::test_aliases_map_to_declared_canonical_id`.
5. **The ontology (OP-35) defines the edge-label vocabulary and node-label set.**
   Traversal (OP-34) filters by these labels; an edge type absent from the
   ontology is invalid. (Source: §6.3.) *Test path:*
   `tests/test_ontology.py::test_unknown_edge_type_rejected`.
6. **RDF interop is an export adapter, not the internal model.** Any RDF/SPARQL
   surface is a serialization boundary; it MUST NOT change node/edge identity or
   property semantics. (Source: §6.2.) *Test path:*
   `tests/test_export.py::test_rdf_export_is_lossless_roundtrip_of_lpg`.

---

## Sources

**Founding / standard sources (primary, verified):**

1. E. F. Codd, "A Relational Model of Data for Large Shared Data Banks,"
   *Communications of the ACM* 13(6):377–387, 1970. DOI: 10.1145/362384.362685.
   <https://dl.acm.org/doi/10.1145/362384.362685>
2. Peter Pin-Shan Chen, "The Entity-Relationship Model — Toward a Unified View of
   Data," *ACM Transactions on Database Systems* 1(1):9–36, 1976.
   DOI: 10.1145/320434.320440. <https://dl.acm.org/doi/abs/10.1145/320434.320440>
   (Author copy: <https://www.csc.lsu.edu/~chen/pdf/erd-5-pages.pdf>)
3. W3C, "RDF 1.1 Concepts and Abstract Syntax," W3C Recommendation, 25 Feb 2014.
   <https://www.w3.org/TR/rdf11-concepts/>
4. ISO/IEC, "ISO/IEC 39075:2024 — Information technology — Database languages —
   GQL," published 12 Apr 2024. <https://www.iso.org/standard/76120.html>
   (Online text: <https://www.iso.org/obp/ui/en/#!iso:std:76120:en>)

**Academic comparison / formalization (verified):**

5. R. Angles, M. Arenas, P. Barceló, A. Hogan, J. Reutter, D. Vrgoč,
   "Foundations of Modern Query Languages for Graph Databases," *ACM Computing
   Surveys* 50(5):68, 2017. DOI: 10.1145/3104031.
   <https://dl.acm.org/doi/10.1145/3104031> (Preprint: arXiv:1610.06264,
   <https://arxiv.org/pdf/1610.06264>)

**Background (verified, supporting):**

6. N. Francis et al., "Cypher: An Evolving Query Language for Property Graphs,"
   *SIGMOD* 2018. DOI: 10.1145/3183713.3190657.
   <https://dl.acm.org/doi/10.1145/3183713.3190657>
7. Neo4j, "Creating the GQL database language standard" (context on GQL/Cypher
   lineage and the SC 32 WG3 committee).
   <https://neo4j.com/blog/cypher-and-gql/gql-database-language-standard/>

**Internal cross-references:**

- `cairn_system_intent.yaml` — invariants (storage-agnostic, deterministic,
  zero-LLM hot path, local-first; `explicit_canonical_ontology`).
- `docs/patterns/patterns_retrieval_knowledge.yaml` — OP-28 (entity resolution /
  canonical record + bi-temporal model), OP-34 (entity graph traversal),
  OP-35 (ontology authoring / typed-edge schema).
