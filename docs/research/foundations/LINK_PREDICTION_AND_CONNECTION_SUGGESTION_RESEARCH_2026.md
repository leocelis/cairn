# Link Prediction & Connection Suggestion — Research (2026)

Foundational research grounding a new `cairn-retrieval` capability: **given a
CANDIDATE node that is not yet in the entity graph (e.g. a table/module about to
be created), recommend which EXISTING entities it should connect to.**

This is the deterministic complement to `traverse()`. `traverse()` answers *"what
is entity X already connected to?"* (relation closure over an existing node).
Connection suggestion answers *"entity X does not exist yet — which existing
nodes is it most related to, and therefore should it link to?"* That is a
**link-prediction** problem, and specifically the **cold-start** variant.

---

## 1. The problem, precisely

An agent asked to design a new `news` table has no map of the 148 existing
tables and their 270 implicit relationships, so it designs in isolation. The
missing capability is: score a *not-yet-existing* node against the existing graph
and return the ranked set of nodes it should attach to, with evidence — offline,
deterministic, zero generative-LLM.

Two regimes, from the literature:

- **Warm** — the node already has some edges. Structural proximity indices apply.
- **Cold-start** — the node has **no edges yet** (exactly our case: the table
  does not exist). Structural indices degenerate to zero; **content/attribute
  similarity is the primary signal**.

---

## 2. Prior art — structural similarity indices (warm regime)

Canonical survey: **Lü & Zhou, "Link Prediction in Complex Networks: A Survey,"
Physica A 390(6):1150–1170, 2011** (arXiv:1010.0725). Local similarity indices
score a pair (x, y) by their neighbourhoods Γ(x), Γ(y):

| Index | Definition | Intuition |
|---|---|---|
| **Common Neighbors (CN)** | \|Γ(x) ∩ Γ(y)\| | more shared neighbours → more likely to link |
| **Jaccard** | \|Γ(x) ∩ Γ(y)\| / \|Γ(x) ∪ Γ(y)\| | CN normalised by union size |
| **Adamic–Adar (AA)** | Σ_{z ∈ Γ(x)∩Γ(y)} 1/log \|Γ(z)\| | rare shared neighbours count more (Adamic & Adar 2003) |
| **Resource Allocation (RA)** | Σ_{z ∈ Γ(x)∩Γ(y)} 1/\|Γ(z)\| | as AA but 1/deg; often beats AA empirically (Zhou, Lü & Zhang 2009) |

All are **deterministic, O(neighbourhood), no learning** — a good fit for Cairn's
zero-dep, byte-stable posture. AA and RA both down-weight hub neighbours (a
neighbour shared by everything is uninformative — the same idf intuition as IDF
in `link_ranking`).

**Limitation for us:** every structural index is **0 for a brand-new node** — it
has no Γ. So structural indices only help *once the candidate is provisionally
attached to at least one seed* (e.g. the user says "news relates to article").

---

## 3. Cold-start link prediction — the candidate-node case

Because a new node has no edges, the field treats this as a distinct sub-problem.
The consistent finding across the cold-start literature: **use nodal *content /
attribute* similarity — "similar nodes are more likely to be linked"** — since
structure is unavailable. (Weighted symmetric NMF with graph regularisation,
CSSE 2023; multi-NMF integrating community info, Chaos Solitons & Fractals 2022;
content-based graph reconstruction for cold-start items, SIGIR 2024.)

Those papers reach for **matrix factorisation / graph autoencoders** — powerful
but **learned, non-deterministic, and dependency-heavy**. For Cairn's default
path we take the **content-similarity core they all rest on** and implement it
deterministically: represent the candidate by its tokens/attributes/concepts and
rank existing nodes by **TF-IDF cosine** (Salton & McGill 1983, the vector-space
model). MF/GNN remain a documented opt-in acceleration, not the default — the
same stance as the semantic signal and the lexical accelerators.

This is a direct generalisation of Cairn's existing **`link_ranking` (M3.0)**,
which already scores *existing* node↔node pairs by TF-IDF cosine over shared
concepts. Connection suggestion scores a *candidate* against the whole corpus.

---

## 4. Schema matching — the domain instance

The "which existing table should a new table connect to" instance is classic
**schema matching**: **Rahm & Bernstein, "A Survey of Approaches to Automatic
Schema Matching," VLDB Journal 10(4):334–350, 2001.** Their taxonomy:

- **element-level vs structure-level** — match a single element (a table/column)
  vs a combination (a subgraph/neighbourhood).
- **linguistic / name-based vs constraint-based** — match on *names and textual
  descriptions* vs on keys/types/structure.

The **linguistic (name-based) element matcher** is exactly a deterministic
token-similarity over entity names/columns — no learning required — and it is the
standard baseline. Combined with a **structure-level** signal (the candidate's
provisional neighbourhood), it is precisely the content-plus-structure recipe
above, mapped onto the schema domain.

---

## 5. Synthesis — the deterministic method for Cairn

`suggest_connections(candidate, existing, *, graph=None)`:

1. **Content signal (always available, primary).** Represent the candidate by its
   tokens/concepts (name + optional attributes/columns). Score every existing
   entity by **TF-IDF cosine** over the shared concept space (IDF from the corpus
   document-frequency; reuses `link_ranking`'s `concept_idf`/`tfidf`). Purely
   content → works even with zero edges (cold start).
2. **Structural signal (optional, when seeds given).** If the caller supplies one
   or more seed entities the candidate provisionally relates to, add an
   **Adamic–Adar / Resource-Allocation** term over the seeds' neighbourhoods from
   the graph. Absent seeds, this term is 0 (honest cold start).
3. **Fuse** content + structural with fixed weights (content-dominant by default),
   **rank descending, deterministic tie-break by entity id**, return
   `top_k` with the **shared evidence** (which concepts/seeds drove the score) —
   provenance, so the agent (or a human) can see *why* a connection is suggested.
4. **Closed world:** an empty candidate or no overlap returns `[]` — never a
   fabricated connection. The agent decides whether to create the edge; Cairn only
   supplies the ranked, evidenced map.

**Boundary:** this is **ranking/relevance → it lives in `cairn-retrieval`**, not
in the entity engine (whose `traverse()` does only structural bounded closure).
Same split as `link_ranking`. The engine supplies the graph; retrieval weighs it.

---

## 6. Design consequences

- Deterministic, zero-dep, zero-LLM by default; byte-stable. MF/GNN/embeddings are
  opt-in accelerators, never the default (consistent with OP-3 / OP-30 stance).
- Reuses `link_ranking` primitives (`concept_idf`, TF-IDF cosine) — connection
  suggestion is the candidate-vs-corpus generalisation of node↔node ranking.
- Structural indices (CN/AA/RA) are **only meaningful once a seed edge exists** —
  the API must not pretend to structural evidence a cold node cannot have.
- Output must carry **provenance** (shared concepts/seeds): a suggested connection
  the agent cannot see the reason for is not actionable.
- **Cairn suggests; the caller decides.** It ranks and evidences candidate
  connections; it never creates an edge or asserts one "should" exist as fact.

---

## Sources

- Lü, L. & Zhou, T. *Link Prediction in Complex Networks: A Survey.* Physica A 390(6):1150–1170 (2011). [arXiv:1010.0725](https://ar5iv.labs.arxiv.org/html/1010.0725v1)
- *Link Prediction on Complex Networks: An Experimental Survey.* Data Science and Engineering, Springer (2022). [link.springer.com](https://link.springer.com/article/10.1007/s41019-022-00188-2)
- Adamic, L. & Adar, E. *Friends and Neighbors on the Web.* Social Networks 25(3):211–230 (2003).
- Zhou, T., Lü, L. & Zhang, Y-C. *Predicting missing links via local information (Resource Allocation).* Eur. Phys. J. B 71:623–630 (2009).
- *A new link prediction method to alleviate the cold-start problem…* Physica A (2023). [sciencedirect](https://www.sciencedirect.com/science/article/abs/pii/S0378437123001012)
- *Cold-Start Link Prediction via Weighted Symmetric NMF with Graph Regularization.* CSSE 43(3) (2023). [techscience](https://www.techscience.com/csse/v43n3/47706)
- *Content-based Graph Reconstruction for Cold-start Item Recommendation.* ACM SIGIR (2024). [dl.acm.org](https://dl.acm.org/doi/10.1145/3626772.3657801)
- Rahm, E. & Bernstein, P. A. *A Survey of Approaches to Automatic Schema Matching.* VLDB Journal 10(4):334–350 (2001). [microsoft.com/research (TR-2001-17)](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/tr-2001-17.pdf)
- Bernstein, P. A., Madhavan, J. & Rahm, E. *Generic Schema Matching, Ten Years Later.* PVLDB 4(11) (2011). [vldb.org](https://vldb.org/pvldb/vol4/p695-bernstein_madhavan_rahm.pdf)
- Salton, G. & McGill, M. *Introduction to Modern Information Retrieval.* McGraw-Hill (1983) — vector-space model / TF-IDF cosine.
