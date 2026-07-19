# Legal Notices and Disclaimers

_Last updated: 2026-07-19. This document scopes the claims made in Cairn's README
and documentation and states the terms under which Cairn is provided. It is
deliberately scoped to what Cairn actually is: a deterministic, offline, local
library with **no hosted service and no data processing by the author**, so the
data-transmission and processor-role sections that a networked product would
need do not apply here._

**This document is not legal advice.** It describes how Cairn is designed, what it
does and does not do, and what responsibilities remain with you. If you are
deploying Cairn in a regulated or high-stakes context, consult qualified legal
counsel before proceeding.

By downloading, installing, or using Cairn, you agree to this document and to
the [Terms of Service](TERMS_OF_SERVICE.md). If you do not agree, do not use the
software.

---

## 1. What Cairn Is, and What It Is Not

**Cairn is** a storage-agnostic routing and composition layer for AI agents: it
resolves entity references to canonical IDs, traverses their relations, decides
whether and how to retrieve, and assembles a minimal context package,
deterministically, with zero generative-LLM calls on the default path.

**Cairn is not:**

- **Not a database or storage engine.** It stores the *map* (references), never
  the bytes; it has no replication, sharding, or durability guarantees of its own.
- **Not a graph query language.** The agent never writes Cypher/Gremlin/SPARQL;
  Cairn compiles a bounded traversal intent and delegates execution to an adapter.
- **Not an LLM ingestion pipeline or extractor.** Any generative model, embedder,
  or NER/RE extractor enters only as a caller-supplied callable, opt-in and offline
  by the caller's choice. Cairn ships none and calls none by default.
- **Not a reasoning engine.** Cairn assembles trustworthy context; the agent
  reasons over it.
- **Not a hosted service.** Cairn is a library you run in your own process. The
  author operates no server on your behalf, receives none of your data, and has
  no visibility into your usage.

---

## 2. Intellectual Property, Trademarks, and Patents

**Copyright.** Cairn is © 2026 Leo Celis. All rights reserved except as licensed
under the [MIT License](LICENSE). The MIT License grants you permission to use,
copy, modify, merge, publish, distribute, sublicense, and sell copies of the
software. It does **not** transfer ownership of the underlying IP or the right to
represent third-party forks or derivatives as the official Cairn project.

**Your outputs are yours.** Alias tables, entity graphs, and any files Cairn
produces when operating on your content belong to you. Cairn makes no claim to
your content or the artifacts you generate with it.

**Third-party references.** Academic papers, benchmarks, and systems named in
`docs/` (e.g. SRACG, Graphiti, CA-RAG, Mem0, Neo4j, FalkorDB) are the property of
their respective owners and are cited for design provenance and descriptive
comparison only. Naming them is not affiliation, sponsorship, or endorsement.

**Trademarks and names.** "Cairn," "cairn-engine," "cairn-retrieval," "Leo Celis,"
and "leocelis.com" are used by the author to identify this project and its origin.
The MIT License covers copyright, **not** trademark. You may not use these names,
or confusingly similar names, in a way that implies the author's affiliation with,
sponsorship of, or endorsement of your product, service, fork, or marketing. You
may of course truthfully state that your software "uses Cairn" or "is built on
cairn-engine." No registered trademark currently exists; the author asserts common
law rights in the geographic areas of actual use.

**Patents.** Cairn is licensed under the MIT License, which is silent on patents
and grants **no express patent license**. This is a deliberate choice for
consistency with the sibling projects (IVD, Horizon, EIF), which are all MIT. The
author holds no patents reading on Cairn and asserts none against users. If your
organization requires an express patent grant and patent-retaliation protection,
the standard upgrade path is the Apache License 2.0; open an issue to discuss
before adopting Cairn in a patent-sensitive context. Should you initiate patent
litigation alleging that Cairn infringes a patent, your rights under this
document and the Terms of Service terminate (see `TERMS_OF_SERVICE.md`).

---

## 3. Inherent Limitations

- **Determinism has a boundary.** Byte-stable output is guaranteed for the
  **default path** (exact/normalized/fuzzy resolution, lexical/graph signals,
  fusion, assembly). The **opt-in tiers** (the semantic embedder, the LLM arbiter,
  an external graph backend) are only as deterministic and available as the
  callable you supply. Enabling them moves that boundary; that is your choice and
  your responsibility.
- **Closed world by design.** A reference that is not in your approved ontology
  resolves to `unresolved`, never a guessed ID. Cairn will not invent an entity or
  a cross-system binding to be "helpful." Completeness of the ontology is the
  operator's responsibility.
- **The human gate is load-bearing.** Ontology authoring stages candidates for
  human approval; Cairn does not auto-approve a canonical set. Skipping that review
  is outside the intended design.

---

## 4. Claims: Scope and Limits

- **Research figures are third-party.** Numbers such as "always-on retrieval
  −2.6 to −3.6pp" (SRACG, AAAI 2026) or "context length degrades accuracy 13.9–85%"
  (Du et al. 2025) are quoted from the cited publications, not measured by Cairn.
  They motivate the design; they are not performance claims about your deployment.
- **"Best" is not yet claimed.** Cairn does not assert superior retrieval quality
  over any baseline. That comparison requires the benchmark phase (OP-31), which is
  not yet done. Until then, treat quality as unproven and the determinism / cost /
  auditability properties as the substantiated value.
- **Verify in your domain.** Any figure or behavior in this repository should be
  re-validated on your own corpus before you rely on it for a production decision.

---

## 5. Your Responsibilities and Acceptable Use

Cairn is a general-purpose developer tool. You are solely responsible for how you
use it and for everything you build with it. In particular, you are responsible for:

- **Legal compliance.** Your use, and any system you build with Cairn, must comply
  with all laws and regulations that apply to you, including data-protection law
  (e.g. GDPR, CCPA/CPRA) and AI-specific regulation (e.g. the EU AI Act, the
  Colorado AI Act). Cairn is not a compliance product and does not make your system
  compliant.
- **Your data.** Any content you load into Cairn (entity names, aliases, documents,
  the alias tables you freeze) is yours and stays on your infrastructure. The author
  never receives it. You are responsible for the lawful basis, security, retention,
  and de-identification of any personal or confidential data you process.
- **Fitness for your use case.** You must independently validate Cairn's behavior on
  your own data before relying on it.

**Not intended for high-risk or safety-critical use.** Cairn is provided for general
software development. It is **not** designed, tested, or certified for use in
safety-critical or high-risk systems where a failure could lead to death, personal
injury, or severe physical, environmental, or financial harm (for example medical
devices, life support, vehicle or aircraft control, critical infrastructure, or
weapons systems). Do not use it in such contexts without your own independent
qualification, redundancy, and sign-off, entirely at your own risk.

You must not use Cairn in violation of law, to infringe others' rights, or in a
manner that misrepresents its origin or the author's endorsement (see §2 and the
Terms of Service).

---

## 6. No Professional Relationship

Cairn and its documentation are provided for general informational and engineering
purposes only. Nothing in this repository is legal, compliance, financial, or other
professional advice, and using Cairn creates no professional or advisory relationship
between you and the author. Consult qualified counsel for your own situation.

---

## 7. Indemnification

To the maximum extent permitted by applicable law, you agree to defend, indemnify,
and hold harmless Leo Celis, the Cairn project, and its contributors and maintainers
from and against any and all claims, damages, losses, liabilities, costs, and
expenses (including reasonable legal fees) arising from or related to:

1. Your use of Cairn in any manner;
2. Any AI system, product, or service you build with or on top of Cairn;
3. Your violation of any law or regulation, or of any third party's rights, in
   connection with your use of Cairn;
4. Any content or data you process, generate, store, or publish using Cairn; and
5. Your misrepresentation of Cairn's capabilities, origin, or the author's
   endorsement to any third party.

This obligation survives your discontinuation of use of Cairn.

---

## 8. Disclaimer of Warranty

Cairn is provided "as is" and "as available," without warranty of any kind, express
or implied, including but not limited to the warranties of merchantability, fitness
for a particular purpose, title, and non-infringement (see the [MIT License](LICENSE)).
The author does not warrant that Cairn will be uninterrupted, error-free, accurate,
or that it will meet your requirements. You assume the entire risk of using it.

---

## 9. Limitation of Liability

To the maximum extent permitted by applicable law, in no event shall Leo Celis or
the Cairn contributors be liable for any indirect, incidental, special,
consequential, exemplary, or punitive damages, or for any loss of profits, revenue,
data, goodwill, or business, arising out of or related to your use of or inability
to use Cairn, whether in contract, tort (including negligence), strict liability, or
any other theory, even if advised of the possibility of such damages. To the extent a
jurisdiction does not allow the exclusion of certain damages, the author's total
cumulative liability arising from or related to Cairn shall not exceed the greater of
(a) the amount you paid for Cairn (which for the MIT-licensed software is USD $0) or
(b) USD $100. This allocation of risk is reflected in the fact that Cairn is provided
free of charge, and is an essential basis of the bargain.

---

## 10. Governing Law and Jurisdiction

This document and any dispute arising from your use of Cairn are governed by the laws
of the **State of Florida, United States**, without regard to its conflict-of-law
provisions. Any legal action arising from this document or your use of Cairn must be
brought exclusively in the state or federal courts located in **Broward County,
Florida, United States**, and you consent to the personal jurisdiction and venue of
those courts. Nothing here limits mandatory consumer or data-subject rights that
apply to you under your local law (for example, rights under GDPR or the EU AI Act
for EU-resident users), which you retain regardless of this clause.

---

## 11. Changes to This Document

The author may update this document as Cairn evolves. Material changes are recorded
in `CHANGELOG.md`. Your continued use of Cairn after a change constitutes acceptance
of the updated terms. The version in the repository at the tag or commit you are
using governs your use of that version.
