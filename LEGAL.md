# Legal Notices and Disclaimers

_Last updated: 2026-07-12. This document scopes the claims made in Cairn's
README and documentation. It is intentionally short: Cairn is a deterministic,
offline, local library with no hosted service and no data processing, so most of
the legal surface of a networked or LLM-calling product does not apply._

---

## 1. What Cairn Is — and Is Not

**Cairn is** a storage-agnostic routing and composition layer for AI agents: it
resolves entity references to canonical IDs, traverses their relations, decides
whether and how to retrieve, and assembles a minimal context package —
deterministically, with zero generative-LLM calls on the default path.

**Cairn is not:**

- **Not a database or storage engine.** It stores the *map* (references), never
  the bytes; it has no replication, sharding, or durability guarantees of its own.
- **Not a graph query language.** The agent never writes Cypher/Gremlin/SPARQL;
  Cairn compiles a bounded traversal intent and delegates execution to an adapter.
- **Not an LLM ingestion pipeline or extractor.** Any generative model, embedder,
  or NER/RE extractor enters only as a caller-supplied callable, opt-in and offline
  by the caller's choice — Cairn ships none and calls none by default.
- **Not a reasoning engine.** Cairn assembles trustworthy context; the agent
  reasons over it.

---

## 2. Intellectual Property

Cairn is © 2026 Leo Celis, released under the [MIT License](LICENSE). Academic
papers, benchmarks, and third-party systems cited in `docs/` (e.g. SRACG,
Graphiti, CA-RAG, and the works named in `docs/patterns/`) are the property of
their respective authors and are referenced for design provenance only. Naming a
third-party system (Graphiti, Mem0, Neo4j, FalkorDB, …) is descriptive
comparison, not affiliation or endorsement.

---

## 3. Inherent Limitations

- **Determinism has a boundary.** Byte-stable output is guaranteed for the
  **default path** (exact/normalized/fuzzy resolution, lexical/graph signals,
  fusion, assembly). The **opt-in tiers** — the semantic embedder, the LLM
  arbiter, an external graph backend — are only as deterministic and available as
  the callable you supply. Enabling them moves that boundary; that is your choice
  and your responsibility.
- **Closed world by design.** A reference that is not in your approved ontology
  resolves to `unresolved`, never a guessed ID. Cairn will not invent an entity or
  a cross-system binding to be "helpful" — completeness of the ontology is the
  operator's responsibility.
- **The human gate is load-bearing.** Ontology authoring stages candidates for
  human approval; Cairn does not auto-approve a canonical set. Skipping that review
  is outside the intended design.

---

## 4. Claims — Scope and Limits

- **Research figures are third-party.** Numbers such as "always-on retrieval
  −2.6 to −3.6pp" (SRACG, AAAI 2026) or "context length degrades accuracy 13.9–85%"
  (Du et al. 2025) are quoted from the cited publications, not measured by Cairn.
  They motivate the design; they are not performance claims about your deployment.
- **"Best" is not yet claimed.** Cairn does not assert superior retrieval quality
  over any baseline. That comparison requires the benchmark phase (OP-31), which
  is not yet done. Until then, treat quality as unproven and the determinism /
  cost / auditability properties as the substantiated value.
- **Verify in your domain.** Any figure or behavior in this repository should be
  re-validated on your own corpus before you rely on it for a production decision.

---

## 5. Disclaimer of Warranty

Cairn is provided "as is", without warranty of any kind, express or implied,
including but not limited to the warranties of merchantability, fitness for a
particular purpose, and non-infringement (see the [MIT License](LICENSE)). In no
event shall the author be liable for any claim, damages, or other liability
arising from the use of the software.
