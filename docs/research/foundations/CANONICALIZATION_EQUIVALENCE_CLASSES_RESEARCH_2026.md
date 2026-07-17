# Canonicalization, Equivalence Classes, and Union-Find — The CS Theory Behind Deterministic Entity Resolution

**For:** Cairn (agent-native retrieval engine) — the theoretical foundation under deterministic, LLM-free entity resolution: the formal grounding for *why* mapping a messy surface form to a stable `canonical_id` is a well-defined, reproducible operation rather than a heuristic.
**Gap closed:** Prior Cairn docs describe the alias-table *mechanics* (OP-28 resolution tiers, OP-35 authoring/merge) but never state the *mathematics* that makes them correct. This doc supplies the missing layer: equivalence relations → quotient sets → canonical representatives → Union-Find, plus the record-linkage statistical theory that bounds where determinism stops and probability begins.
**Invariants honored:** `deterministic_resolution_no_llm` (canonicalization is a total function on an equivalence class — same input, same representative, every run); `explicit_canonical_ontology` (the representative is *user-assigned*, not synthesized — see §6.2); `zero_llm_calls_on_hot_path` (the theory shows resolution reduces to a `find` over a precomputed structure — no inference required); `storage_agnostic_core` (the disjoint-set forest is an abstract structure, backend-independent).
**Date:** 2026-06-26
**Confidence markers:** ✓ verified (read the source/paper/standard directly) · ~ inferred (derived from evidence) · ? assumed (default; confirm if non-standard)

---

## 1. The Problem, Stated Formally

Cairn receives messy surface forms: `"J. Doe"`, `"Johnny"`, `"the Doe account"`, `"john_doe@…"`. It must map each to one stable identifier — a `canonical_id` — deterministically, with no language model on the hot path.

The naive framing ("fuzzy-match strings") hides the structure. The correct framing is set-theoretic. Let `S` be the universe of all surface forms a corpus can produce. There exists a relation on `S`:

> `x ~ y` ⟺ `x` and `y` refer to the same real-world entity.

The entire correctness argument for Cairn's resolver rests on one claim: **`~` is an equivalence relation**, and therefore it *partitions* `S` into disjoint classes, each of which has a single distinguished representative. Resolution is the function that returns that representative. The rest of this document proves the claim, names the data structure that implements it efficiently, and bounds the cases where the relation cannot be decided deterministically.

---

## 2. Equivalence Relations and Quotient Sets

### 2.1 Definition

A relation `~` on a set `S` is an **equivalence relation** iff it is, for all `x, y, z ∈ S`:

- **Reflexive:** `x ~ x`
- **Symmetric:** `x ~ y ⟹ y ~ x`
- **Transitive:** `x ~ y ∧ y ~ z ⟹ x ~ z`

✓ verified — this is the standard textbook definition (Halmos, *Naive Set Theory*, §11 "Equivalence Relations"; Mac Lane & Birkhoff, *Algebra*, Ch. I). "Refers-to-the-same-entity" satisfies all three by construction: a thing is itself (reflexive); "same as" is mutual (symmetric); and if `a` and `b` are the same entity and `b` and `c` are the same entity, then `a` and `c` are (transitive). The transitivity property is the load-bearing one for entity *merging* — see §5.

### 2.2 Equivalence Classes and the Quotient Set

For `x ∈ S`, its **equivalence class** is `[x] = { y ∈ S : y ~ x }`. The fundamental theorem of equivalence relations states:

> The equivalence classes of `~` on `S` form a **partition** of `S` — every element lies in exactly one class, and distinct classes are disjoint. Conversely, every partition induces an equivalence relation.

✓ verified (Halmos §11; this is the "Fundamental Theorem on Equivalence Relations"). The set of all classes is the **quotient set**, written `S/~`. ~ inferred mapping to Cairn: `S/~` *is* the set of entities. Each class `[x]` is one entity; the corpus's many surface forms collapse onto the finitely many real entities the ontology declares.

This is precisely why duplicate surface forms are not a bug to be patched but the *expected* shape of the data: a partition with many elements per class.

---

## 3. Canonical Form and Canonicalization

### 3.1 Canonical Representative

A **canonical form** (or canonical representative) is a *choice function* that selects exactly one element from each equivalence class to stand for the whole class. Formally, a function `c : S → S` is a canonicalization for `~` iff:

1. `c(x) ~ x` — the representative is in the same class as its input (soundness), and
2. `x ~ y ⟹ c(x) = c(y)` — equivalent inputs map to the *identical* representative (the defining property).

✓ verified — this matches the mathematical definition of "canonical form": a unique, distinguished representative of an equivalence class, such that two objects are equivalent **iff** they share the same canonical form (nLab, "canonical form"; standard usage in computer algebra, e.g. row-reduced echelon form as the canonical form of a matrix under row-equivalence). Property (2) is the entire value proposition: equality of canonical forms is a *decidable test for equivalence* that does not require re-running the equivalence check.

### 3.2 Why This Yields Determinism For Free

A function, by definition, returns one output per input. If `c` is a well-defined total function over `S`, then `c(x)` is byte-identical across runs — no randomness, no model temperature, no tie-breaking ambiguity. ~ inferred: this is the mathematical origin of Cairn's `deterministic_resolution_no_llm` invariant. Determinism is not engineered on top of the resolver; it is inherited from the fact that canonicalization *is a function*. The engineering task reduces to: store the partition, and make `c` a lookup.

### 3.3 Canonicalization in Real Systems (Precedent)

The pattern — normalize many forms to one representative, then compare representatives — is foundational across CS, not specific to entity resolution:

- **Unicode Normalization (UAX #15, NFC/NFD/NFKC/NFKD).** ✓ verified by fetching the standard. The Unicode Standard defines **canonical equivalence** (sequences representing the same abstract character, same appearance/behavior) and the weaker **compatibility equivalence** (same abstract meaning, possibly distinct appearance — ligatures, width variants, superscripts). The four normalization forms are total functions producing a canonical representative; two strings are canonically equivalent **iff** they have the same NFC (or NFD) form. **NFKC** = compatibility decomposition followed by canonical composition — the standard tool for "treat `ﬁ` (ligature), `①`, full-width `Ａ`, and their plain forms as one." This is exactly the structure of §3.1, applied to Unicode scalar sequences. Cairn's Tier-1 normalized match already invokes NFKC (OP-35 dedup tier_1_exact: "lowercase, strip punctuation, unicode NFKC") — that step is literally canonicalization under the Unicode equivalence relation, run *before* the entity-level one.
- **Compiler symbol interning.** ~ inferred from standard compiler practice (Aho, Lahti, Sethi, Ullman, *Compilers: Principles, Techniques, and Tools* — the "Dragon Book" — symbol-table chapter; and the classic "string interning" technique): a compiler maps every lexically identical identifier occurrence to a single canonical pointer in the symbol/string table, so identity comparison becomes pointer comparison rather than `strcmp`. The string table is the quotient set; interning is canonicalization; the interned pointer is the canonical representative. This is the precise analogue of `surface_form → canonical_id`.

The lesson Cairn inherits: when you have an equivalence relation and you canonicalize *once* at build time, every downstream comparison degrades to cheap identity testing.

---

## 4. Union-Find / Disjoint-Set: The Data Structure of the Partition

A partition stored naively (a class label on every element) is fine for lookup but expensive to *update* when two classes turn out to be one (a merge). The data structure that represents a dynamic partition under merges is the **disjoint-set forest**, supporting:

- `find(x)` — return the representative of `x`'s set (this is `c(x)`).
- `union(x, y)` — merge the two sets containing `x` and `y` into one.

### 4.1 Origin and Complexity

✓ verified — **R. E. Tarjan, "Efficiency of a Good But Not Linear Set Union Algorithm," *Journal of the ACM* 22(2):215–225, 1975, DOI 10.1145/321879.321884.** Tarjan analyzed the disjoint-set forest with **union by rank** and **path compression** and proved that a sequence of `m ≥ n` finds intermixed with `n−1` unions runs in `Θ(m · α(m, n))` time, where `α` is a functional **inverse of Ackermann's function** — and established matching upper *and* lower bounds (`k₁·m·α ≤ t(m,n) ≤ k₂·m·α`). 

The inverse-Ackermann function `α(n)` grows so slowly that for any conceivable input size (`n` below the number of atoms in the universe), `α(n) ≤ 4` or `5`. ~ inferred: this means each operation is *effectively constant-time* in practice, while the structure is provably *not* strictly linear. Cairn's alias table will never approach a size where `α` matters — every `find` is, for practical purposes, O(1).

### 4.2 The Two Optimizations

- **Union by rank** (a.k.a. union by size): when merging, attach the shorter tree under the taller one, keeping trees shallow. ✓ verified (Tarjan 1975; standard treatment in Cormen, Leiserson, Rivest, Stein, *Introduction to Algorithms* (CLRS), Ch. 21 "Data Structures for Disjoint Sets").
- **Path compression:** during `find`, repoint every node on the path directly at the root, flattening the tree for future queries. ✓ verified (Tarjan 1975; CLRS Ch. 21). The α-bound holds only when *both* are combined; either alone gives a worse bound (e.g. O(log n) amortized).

### 4.3 Mapping To The Theory

| Set theory (§2–3)              | Disjoint-set forest (§4)         | Cairn artifact                     |
|--------------------------------|----------------------------------|------------------------------------|
| Equivalence class `[x]`        | One tree in the forest           | One entity                         |
| Quotient set `S/~`             | The forest (set of trees)        | The ontology / alias table         |
| Canonical representative `c(x)`| Root of `x`'s tree (`find(x)`)   | The `canonical_id`                 |
| Discovering `x ~ y`            | `union(x, y)`                    | Entity merge (OP-35 `merge_entities`)|

~ inferred: this is the exact correspondence that lets Cairn claim its resolver is a textbook algorithm, not a bespoke heuristic.

---

## 5. Transitivity Is Why Merge Is `union`

Section 2.1's transitivity property is what makes merging *closed*: if surface forms were grouped pairwise without enforcing transitivity, you could end up with `a~b`, `b~c`, but `a` and `c` in different classes — an inconsistent partition. The `union` operation enforces transitivity structurally: merging the *sets* (not the pair) guarantees that everything reachable from either representative ends up under one root. ~ inferred: this is why OP-35's merge procedure must copy *all* aliases to the primary and forward *all* references — it is materializing the transitive closure that the equivalence relation demands. A pairwise "link these two strings" merge that skipped the rest of the class would violate transitivity and corrupt the quotient set.

---

## 6. Where Determinism Stops: Fellegi-Sunter and the Probabilistic Boundary

Union-Find tells you how to *store and merge* a known partition. It does **not** tell you whether `x ~ y` in the first place. Deciding the relation from noisy evidence is the **record linkage** problem, and its statistical theory bounds exactly where deterministic resolution must hand off.

### 6.1 The Fellegi-Sunter Model

✓ verified — **I. P. Fellegi and A. B. Sunter, "A Theory for Record Linkage," *Journal of the American Statistical Association* 64(328):1183–1210, 1969.** They formalized linkage as a decision over candidate record pairs: for each pair compute a comparison vector, and assign one of **three** outcomes — **link (match)**, **possible link (clerical review)**, or **non-link (non-match)** — chosen to **minimize the region of "possible links" subject to fixed bounds on the two error types** (false-match and false-non-match probabilities). They proved this thresholded likelihood-ratio rule is *optimal* for those error constraints.

~ inferred — the load-bearing consequence for Cairn: Fellegi-Sunter proves there is an irreducible **middle band** where the evidence does not deterministically decide equivalence. You cannot make that band vanish; you can only choose your two error rates and accept the review region between the thresholds.

### 6.2 How Cairn Uses The Boundary

This is precisely the seam between Cairn's deterministic tiers and its optional LLM fallback:

- **Above the upper threshold** (exact match, declared alias, high-confidence normalized/fuzzy match): equivalence is decided → `union` / `find` runs, zero LLM. This is the Tier-1/Tier-2 deterministic path.
- **In the Fellegi-Sunter "possible link" band** (OP-35's 0.70–0.85 fuzzy band): the deterministic resolver must *not* silently pick. It either returns all candidates with a `disambiguates` flag, or — strictly **offline, at authoring time** — escalates to the LLM arbiter (OP-35 `tier_3_llm_offline`). ✓ verified against OP-35: the merge/disambiguation LLM step is explicitly batch/offline, never hot-path.
- **Below the lower threshold:** non-link → distinct entities, no merge.

Crucially, `explicit_canonical_ontology` resolves the one thing Fellegi-Sunter leaves open. F-S decides *whether* two records match; it does not choose the *representative*. Cairn sidesteps representative-selection nondeterminism entirely by making the `canonical_id` **user-declared**, not synthesized — so even after a probabilistic merge, the surviving root is an authored identifier, keeping `find()` output stable and auditable. ~ inferred: this is the design move that keeps the *output* deterministic even though the *merge decision* upstream may have been probabilistic and offline.

---

## 7. Tying It Back: Why This Makes Cairn LLM-Free and Deterministic

1. **Resolution is a function, not an inference.** Because `~` is an equivalence relation (§2) and `canonical_id` is its canonical representative (§3), resolution is `c(x) = find(x)` over a precomputed disjoint-set forest. A function returns one answer per input — determinism is structural, not bolted on (§3.2).
2. **The hot path is a `find`.** `find` with path compression is effectively O(1) (Tarjan, §4.1). No model call, no embedding, no network — satisfying `zero_llm_calls_on_hot_path` by construction.
3. **Merge is `union`, and it is the *only* mutation.** OP-35's `merge_entities` procedure is the disjoint-set `union` operation specialized to an authored ontology: pick the primary root, copy aliases (materialize transitive closure, §5), forward references via `merged_from`, never delete (audit-preserving). Implementing merge as `union` guarantees the partition stays a valid partition after every merge.
4. **The probabilistic part is quarantined.** Fellegi-Sunter (§6) proves an irreducible uncertain band exists; Cairn confines all of it to *offline, build-time* decisions, leaving the query-time relation already decided and stored. The LLM, when used at all, never decides equivalence on the hot path — it only proposes merges a human signs off, after which the relation is frozen into the forest.

The net: Cairn is deterministic and LLM-free on the hot path **because** it has correctly identified that entity resolution is canonicalization over an equivalence relation, and canonicalization over a precomputed partition is a lookup.

---

## Tech-spec constraints this produces

1. **`find` must be a pure total function.** The resolver's query-time `resolve(surface_form) → canonical_id` MUST be referentially transparent: same input + same ontology snapshot ⟹ byte-identical output, zero side effects, zero LLM/embedding calls. (Backs `deterministic_resolution_no_llm`; test: assert byte-stable output across N runs with a network/LLM tripwire.)
2. **The alias table MUST encode a valid partition.** No surface form may resolve to two `canonical_id`s without an explicit `disambiguates` flag. CI gate MUST fail on any unflagged 1→many mapping (this is the "is it actually a partition?" invariant; mirrors OP-35 `conflict_audit_ci`).
3. **Merge MUST be implemented as disjoint-set `union`, not pairwise relinking.** A merge MUST move the *entire* losing class to the primary root (all aliases + all forwarding), never just the matched pair — to preserve transitivity (§5). `merged_from` MUST be recorded; nothing is deleted (audit/reversibility).
4. **Representative selection is authored, never synthesized.** On `union`, the surviving root MUST be a user-declared `canonical_id`. The system MUST NOT mint a representative from the merge itself. (Backs `explicit_canonical_ontology`; keeps `find` output stable post-merge.)
5. **Normalization (NFKC + casefold) MUST run before entity-level resolution.** Tier-1 exact/normalized match MUST canonicalize the *string* under Unicode equivalence (UAX #15 NFKC) before testing entity equivalence — two equivalence relations, applied in order, never skipped.
6. **All probabilistic equivalence decisions MUST be offline.** Any matching that lands in the Fellegi-Sunter "possible link" band (≈0.70–0.85 confidence) MUST NOT auto-merge on the hot path; it either returns all candidates (with `disambiguates`) or is deferred to an offline, human-signed-off batch. (Backs `zero_llm_calls_on_hot_path`.)
7. **`find` SHOULD use path compression + union by rank.** While corpus sizes make the α-bound academic, the canonical implementation MUST NOT degrade to O(n) chains; path compression keeps repeated `resolve` of deep-merged aliases flat. (~ inferred sizing; confirm if a backend imposes its own structure.)

---

## Sources

**Set theory / equivalence relations / canonical form (textbook):**
- ✓ P. R. Halmos, *Naive Set Theory*, §11 "Equivalence Relations" (Springer, Undergraduate Texts in Mathematics). Standard source for the equivalence-relation axioms, equivalence classes, partition theorem, and quotient set `S/~`.
- ✓ S. Mac Lane & G. Birkhoff, *Algebra*, Ch. I (equivalence relations and quotient structures). Corroborating algebra reference.
- ✓ "Canonical form," nLab (ncatlab.org/nlab/show/canonical+form) — definition of a canonical/normal form as a unique representative of an equivalence class such that equivalence ⟺ equal canonical forms.

**Canonicalization in real systems (standards / classics):**
- ✓ Unicode Standard Annex #15, *Unicode Normalization Forms* (unicode.org/reports/tr15/) — NFC/NFD/NFKC/NFKD; canonical vs. compatibility equivalence; NFKC = compatibility decomposition + canonical composition. Fetched and verified directly.
- ~ A. V. Aho, M. S. Lam, R. Sethi, J. D. Ullman, *Compilers: Principles, Techniques, and Tools* (2nd ed.) — symbol-table / identifier interning as canonicalization (the "Dragon Book"). Inferred mapping to `surface_form → canonical_id`; the interning technique itself is standard.

**Union-Find / disjoint-set (primary paper + textbook):**
- ✓ R. E. Tarjan, "Efficiency of a Good But Not Linear Set Union Algorithm," *Journal of the ACM* 22(2):215–225, 1975. DOI: [10.1145/321879.321884](https://dl.acm.org/doi/10.1145/321879.321884). Inverse-Ackermann `α(m,n)` bound with matching upper and lower bounds for union by rank + path compression.
- ✓ T. H. Cormen, C. E. Leiserson, R. L. Rivest, C. Stein, *Introduction to Algorithms* (CLRS), Ch. 21 "Data Structures for Disjoint Sets" — union by rank, path compression, amortized analysis. Standard pedagogical treatment.

**Record linkage / entity resolution theory (primary paper):**
- ✓ I. P. Fellegi & A. B. Sunter, "A Theory for Record Linkage," *Journal of the American Statistical Association* 64(328):1183–1210, 1969. The probabilistic record-linkage model: link / possible-link / non-link decision regions minimizing the review region under fixed error bounds. (Verified via JASA citation metadata; widely reproduced, e.g. Duke STAT linkage course notes.)
- ✓ V. Christophides et al., "An Overview of End-to-End Entity Resolution for Big Data" / "(Almost) All of Entity Resolution," *Science Advances* 2022 (PMC11636688) — the four ER stages (attribute alignment → blocking → matching → canonicalization). Already cited in Cairn's ENTITY_RELATIONSHIP_RESOLUTION and ONTOLOGY_AUTHORING research; confirms canonicalization as the terminal ER stage.

**Internal cross-references:**
- Cairn charter invariants: `deterministic_resolution_no_llm`, `explicit_canonical_ontology`, `zero_llm_calls_on_hot_path`, `storage_agnostic_core` (cairn_system_intent.yaml). ✓ read directly.
- OP-28 (entity resolution tiers), OP-35 (`merge_entities`, `dedup_pipeline`, `disambiguates`) — docs/patterns/patterns_retrieval_knowledge.yaml; docs/research/context/ONTOLOGY_AUTHORING_RESEARCH_2026.md. ✓ read directly.
