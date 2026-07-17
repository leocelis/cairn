# The Closed World Assumption and the Relational Model — Why Cairn Is Deterministic, Not Generative

**For:** Cairn (agent-native retrieval engine) — the foundational theory layer. This is the document that justifies, at the level of computer-science first principles, *why* Cairn resolves entities deterministically with zero inference and zero LLM calls, and *why* its engine is organized as relations + algorithms rather than as objects with methods.
**Gap closed:** Prior Cairn docs (ontology authoring, entity resolution, graph traversal) describe *how* the alias table and resolver work. None of them ground the two design choices that make the whole "deterministic, not generative" thesis defensible: (A) the Closed World Assumption as the alternative to the inference-based Open World Assumption of classical ontologies, and (B) the Relational Model as the correct paradigm for an engine that sweeps algorithms over many typed records — versus Object-Oriented encapsulation, which is the wrong fit. Without this doc, the invariants `zero_llm_calls_on_hot_path`, `deterministic_resolution`, and `explicit_canonical_ontology` read as engineering preferences rather than as the load-bearing consequences of a coherent theory.
**Invariants honored:** `deterministic_resolution` (resolution is a lookup, not an inference — CWA is its formal name); `zero_llm_calls_on_hot_path` (no entailment/subsumption engine on the query path — representation without inference); `explicit_canonical_ontology` (the alias table is the closed world; what is not in it does not resolve — negation-as-failure); `storage_agnostic_core` (entities are immutable value records, algorithms live in `core/`, separable from any backend — the relational data/behavior split).
**Date:** 2026-06-26
**Confidence markers:** ✓ verified (directly from primary source/paper/standard) · ~ inferred (derived from evidence) · ? assumed (default; confirm if non-standard)

---

## 1. The Thesis in One Paragraph

Cairn is deterministic because it makes two design commitments that are each a named, well-studied position in computer science. First, Cairn adopts the **Closed World Assumption (CWA)**: a fact that is not present in the alias table or the relation graph is treated as *not true* — resolution fails rather than guesses. This is the opposite of the **Open World Assumption (OWA)** that classical ontologies (OWL, the Semantic Web, Description Logic) are built on, where unstated facts *might* be true and must be discovered by an inference engine. The OWA forces inference (subsumption, classification, entailment); the CWA forbids it. ~ Inferred: this single choice is *the* reason Cairn can run with no inference engine and no LLM on the hot path — it is "representation without inference," an ontology used as a lookup structure rather than as a logic. Second, Cairn organizes its data using the **Relational Model**: entities are immutable value records (rows), their attributes are columns, and the algorithms that operate on them live *outside* the records (in `core/`), expressed as sweeps/queries over many records. This is the correct paradigm for "algorithms over many typed records," and it is precisely what Object-Oriented encapsulation — state and behavior bundled inside each object — gets wrong for this workload.

---

# PART A — The Closed World Assumption vs the Open World Assumption

## 2. The Open World Assumption and Why It Demands Inference

✓ Verified: The W3C Web Ontology Language (OWL) — the canonical Semantic Web ontology language — is *semantically based on Description Logics*, "a family of logics that are decidable fragments of first-order predicate logic" ([W3C OWL](https://www.w3.org/OWL/); [Heflin, *Intro to OWL*](https://www.cse.lehigh.edu/~heflin/IntroToOWL.pdf)). OWL DL corresponds to the description logic SHOIN(D); OWL Lite to SHIF(D) ([Horrocks et al., IEEE](https://ieeexplore.ieee.org/document/1236278/)).

✓ Verified: OWL adopts the **Open World Assumption**. In the standard's own framing, "a fact which has not been stated to be true cannot be assumed to be false" — knowledge about the world is treated as *incomplete*, so things not known to be true are *not necessarily false* ([W3C OWL Reference](https://www.w3.org/TR/owl-ref/); [Heflin, *Intro to OWL*](https://www.cse.lehigh.edu/~heflin/IntroToOWL.pdf)).

✓ Verified: Under OWA, answering a query is a *theorem-proving* problem, not a lookup. "The OWL formal semantics specifies how to derive its logical consequences, i.e. facts not literally present in the ontology, but entailed by the semantics" ([W3C OWL](https://www.w3.org/OWL/)). This is **entailment**. The companion reasoning services in Description Logic are **subsumption** (is class A necessarily a subclass of B?) and **classification** (place every concept in the inferred hierarchy) ([Baader et al., *The Description Logic Handbook*, CUP, 2003/2007](https://www.cambridge.org/core/books/description-logic-handbook/4D4CB19D49A1BB8D6E5F1F21FF2A56B6)).

**Consequence for an engine.** ~ Inferred: An OWA system *cannot* answer "does X hold?" by checking a table — because absence from the table is not evidence of falsehood. It must run a reasoner (a tableau or consequence-based algorithm) to compute the closure of what is entailed. That reasoner is a non-trivial, sometimes intractable, and inherently *generative* component: it manufactures facts that were never written down. For Cairn, which needs to return the *same* resolution for the *same* input every time with no model in the loop, an entailment engine is exactly the wrong dependency.

## 3. The Closed World Assumption — Reiter 1978

✓ Verified: The Closed World Assumption was formalized by Raymond Reiter in **"On Closed World Data Bases,"** in H. Gallaire & J. Minker (eds.), *Logic and Data Bases*, Plenum Press, New York, 1978, pp. 55–76 (originating as Univ. of British Columbia Technical Report 77-16, 1977) ([UBC TR-77-16 PDF](https://www.cs.ubc.ca/sites/default/files/tr/1977/TR-77-16.pdf); [Springer chapter](https://link.springer.com/chapter/10.1007/978-1-4684-3384-5_3); [ACM Guide](https://dl.acm.org/doi/10.5555/902066)).

✓ Verified — the core rule: under the CWA, "certain answers are admitted as a result of *failure to find a proof*. More specifically, if no proof of a positive ground literal exists, then the negation of that literal is assumed true" ([Reiter 1978, via UBC TR-77-16](https://www.cs.ubc.ca/sites/default/files/tr/1977/TR-77-16.pdf)). Reiter explicitly contrasts this with the OWA, where "the only answers to Q are those which obtain from proofs of Q given DB as hypotheses" — i.e., the OWA never concludes a negative from absence.

✓ Verified — two results from the paper that bound the technique:
1. **Reducibility.** Closed-world evaluation of an arbitrary query reduces to open-world evaluation of *atomic* queries — i.e., the closed world is a thin shell of negation-by-absence over ordinary fact lookup ([UBC TR-77-16](https://www.cs.ubc.ca/sites/default/files/tr/1977/TR-77-16.pdf)).
2. **Consistency for Horn databases.** The CWA can introduce inconsistency *in general*, but **for Horn databases no such inconsistency arises** ([UBC TR-77-16](https://www.cs.ubc.ca/sites/default/files/tr/1977/TR-77-16.pdf)). ~ Inferred: this is directly relevant to Cairn — an alias/relation table of ground facts (no disjunction in the heads) is a Horn database, so the CWA is provably safe to apply there.

**Why this is the determinism lever.** ~ Inferred: CWA turns "is X true?" from a proof search into a membership test. Membership in a fixed table is O(1) (hash) or O(log n), total, repeatable, and model-free. The OWA's "is X entailed?" is a search over an inference closure. Cairn chooses CWA precisely to replace search-with-inference by lookup-with-failure.

## 4. Negation as Failure — Clark 1978

✓ Verified: The operational cousin of the CWA is **Negation as Failure (NAF)**, formalized by Keith Clark in **"Negation as Failure,"** in *Logic and Data Bases* (Gallaire & Minker, eds.), Plenum, 1978, pp. 293–322 ([Springer chapter, DOI 10.1007/978-1-4684-3384-5_11](https://link.springer.com/chapter/10.1007/978-1-4684-3384-5_11)).

✓ Verified — the rule: "¬P can be inferred if *every possible proof of P fails*." Clark's contribution was to make this rule *sound* by interpreting the program against its **completion**: the database of "if" rules is replaced by "iff" rules (the "completed data base"), so NAF concludes only negations that follow from that completion ([Clark 1978, Springer](https://link.springer.com/chapter/10.1007/978-1-4684-3384-5_11); [Negation as failure, HandWiki](https://handwiki.org/wiki/Negation_as_failure)).

✓ Verified — the relationship to Reiter: the two are deliberately compared in the literature; NAF over Clark's completed database and Reiter's CWA are closely related accounts of "treat the unprovable as false" ([Shepherdson, "Negation as failure: a comparison of Clark's completed data base and Reiter's closed world assumption," *J. Logic Programming*, 1984](https://www.sciencedirect.com/science/article/pii/0743106684900232)).

**Mapping to Cairn.** ~ Inferred: Cairn's resolver *is* negation-as-failure made concrete. When a surface form is not found in the alias table after the deterministic tiers (exact, normalized, deterministic-fuzzy), the resolver concludes "this entity does not resolve" — it does not fall through to a generative guess. The alias table + relation graph *is* the completed database: it is read as "these and only these facts hold." ? Assumed: Cairn never silently invents a canonical ID to satisfy a query — confirm this is enforced at the resolver boundary, not merely conventional.

## 5. Representation Without Inference — the Defensible Position

Putting §2–§4 together yields the precise theoretical claim:

> Cairn uses an ontology as a **representation** (a lookup structure of authored facts) rather than as a **logic** (a set of axioms closed under inference).

~ Inferred, grounded in §2–§4:
- Classical ontology stack (OWL/DL): OWA → unstated-might-be-true → requires entailment/subsumption/classification → needs a reasoner → non-deterministic-feeling, generative, and a heavyweight dependency.
- Cairn stack: CWA + NAF → unstated-is-false → resolution is membership + failure → no reasoner, no LLM on the path → deterministic and model-free.

This is *not* a claim that the CWA is "better" than the OWA in general. ✓ Verified caveat from Reiter: the CWA is only safe without inconsistency for the right class of databases (Horn). The claim is narrower and defensible: **for an agent-native retrieval engine whose ground truth is an authored, finite set of entities and relations, the CWA is the correct semantics, and it is what buys determinism.** OWA is the right choice when the world is genuinely open and incomplete (the public Semantic Web); Cairn's world is a curated, closed corpus, and modeling it as open would import an inference engine it does not need and cannot make deterministic.

---

# PART B — The Relational Model vs Object-Oriented Encapsulation

## 6. Codd 1970 — Data Separated From Behavior

✓ Verified: The Relational Model is E. F. Codd, **"A Relational Model of Data for Large Shared Data Banks,"** *Communications of the ACM* 13(6):377–387, June 1970 ([CACM](https://cacm.acm.org/research/a-relational-model-of-data-for-large-shared-data-banks-2/); [IBM Research](https://research.ibm.com/publications/a-relational-model-of-data-for-large-shared-data-banks); [dblp, DOI 10.1145/362384.362685](https://dblp.org/rec/journals/cacm/Codd70.html); [Grinnell PDF](https://rebelsky.cs.grinnell.edu/Courses/CS302/2007S/Readings/codd-1970.pdf)).

✓ Verified: Codd's model stores data as **n-ary relations** — simple tables of rows (tuples) and columns — rather than in hierarchical/navigational structures, and introduces a **normal form** and a **universal data sublanguage** for operating on them ([CACM](https://cacm.acm.org/research/a-relational-model-of-data-for-large-shared-data-banks-2/); [History of Information](https://www.historyofinformation.com/detail.php?id=94)).

The structural point that matters for Cairn: ~ inferred from Codd — the relational model **separates the data (relations/tuples) from the operations on it (relational algebra)**. Operations are not methods bundled inside a row; they are general functions/queries applied *from outside* to whole relations. A relation is a passive, immutable-by-value set of tuples; the algebra is the behavior, and it lives elsewhere.

## 7. The Object-Relational Impedance Mismatch — Naming the Tension

✓ Verified: The **object-relational impedance mismatch** is the well-documented set of conceptual and technical difficulties that arise when an object-oriented program is served by a relational store, "because objects or class definitions must be mapped to database tables defined by a relational schema" ([Object–relational impedance mismatch, Wikipedia](https://en.wikipedia.org/wiki/Object%E2%80%93relational_impedance_mismatch); [MDPI Encyclopedia](https://encyclopedia.pub/entry/29754)).

✓ Verified — the root of the mismatch is a paradigm clash: "OO mathematically is directed graphs where objects reference each other, whereas relational uses tuples in tables with relational algebra"; the OO paradigm rests on software-engineering principles while the relational paradigm rests on mathematical ones ([HandWiki](https://handwiki.org/wiki/Object-relational_impedance_mismatch); [agiledata.org](https://agiledata.org/essays/impedancemismatch.html)).

~ Inferred — what this names for Cairn: the friction is not an accident of ORMs; it is the structural cost of forcing **encapsulated state+behavior (objects)** onto **data-as-relations**. An engine whose job is "sweep an algorithm over many typed records" lives natively on the relational side. Adopting OOP for the entities would re-introduce the impedance mismatch *inside Cairn's own core* — every algorithm would have to thread through per-object method boundaries instead of operating over flat collections of records.

## 8. ECS / Data-Oriented Design — the Relational Model Rediscovered

✓ Verified: An **Entity-Component-System (ECS)** is "a software architectural pattern consisting of entities composed of data components, along with systems that operate on those components" ([Entity component system, Wikipedia](https://en.wikipedia.org/wiki/Entity_component_system)). The defining move is that *components hold data only* and *systems hold behavior only* — state and behavior are deliberately *not* encapsulated together.

~ Inferred (the structural isomorphism, widely observed in the DOD community): ECS is the relational model under different names —
- **Entity = row** (a stable identity/key),
- **Component = column** (a typed attribute set, stored together across entities),
- **System = query** (an algorithm that selects entities with the required components and sweeps over them).
([Sebastian Schöner, "Data-Oriented Design — An Interpretation"](https://blog.s-schoener.com/2019-06-09-data-oriented-design/); [hexops devlog, "Let's build an ECS"](https://devlog.hexops.org/2022/lets-build-ecs-part-1/)).

✓ Verified: **Data-Oriented Design (DOD)** was popularized by Mike Acton (CppCon 2014, later Unity). The DOD community is careful that DOD ≠ ECS: ECS is one architecture; DOD is the broader discipline of "let data be data" — organize for the data and the transformations over it, not for a domain model of objects ([Unity Learn, "Understand data-oriented design"](https://learn.unity.com/course/dots-best-practices/tutorial/part-1-understand-data-oriented-design); ["Data Oriented Design is not ECS"](https://yoyo-code.com/data-oriented-design-is-not-ecs/)). The relevant overlap: both insist that behavior operates over collections of plain records *from the outside*, which is exactly Codd's data/algebra split.

## 9. Why Cairn Entities Are Immutable Value Records With Algorithms in `core/`

Combining §6–§8 gives the design rule:

> Cairn entities are **immutable value records** (relations/rows). The algorithms that resolve, traverse, rank, and assemble live **outside** the records, in `core/`, as functions that sweep over collections — not as methods on objects.

~ Inferred consequences, each tied to an invariant:
- **`storage_agnostic_core`.** Because behavior is not welded into the records, `core/` depends only on the record *shape* (a Protocol/dataclass), not on any backend. The same algorithm runs over records from a YAML adapter, a SQLite adapter, or a Parquet adapter. Objects-with-methods would couple behavior to a particular materialization and break this.
- **`deterministic_resolution` + `zero_llm_calls_on_hot_path`.** Pure functions over immutable value records are referentially transparent: same input → same output, no hidden mutable object state, nothing to invoke a model. This is the relational-algebra discipline applied to retrieval.
- **Concurrency and reasoning.** ~ Inferred from DOD/value-semantics literature: immutable records can be shared across threads with no locking, and an algorithm reading flat collections is far easier to test, reason about, and reproduce than one chasing references through a mutable object graph (the OO directed-graph model in §7).

? Assumed: Cairn's core already follows this (dataclasses/records + free functions in `core/`, no behavior-bearing entity classes). Confirm there are no entity classes carrying resolution/traversal methods — if any exist, they are the OO impedance mismatch reappearing inside the engine and should be refactored to free functions over records.

---

## 10. The Two Theories, Joined — Why "Deterministic, Not Generative" Holds

The two parts are not independent; together they form the full justification:

| Choice | Classical alternative | What Cairn picks | What it buys |
|---|---|---|---|
| Semantics of "unstated" | OWA — might be true → entailment engine (subsumption/classification) | **CWA + NAF** — unstated is false → membership + failure | No reasoner, no LLM on the hot path; deterministic resolution |
| Ontology as | a **logic** (axioms closed under inference) | a **representation** (authored lookup structure) | Repeatable O(1)/O(log n) lookups; `explicit_canonical_ontology` |
| Data organization | OOP — state+behavior encapsulated per object | **Relational / ECS** — immutable records + algorithms in `core/` | `storage_agnostic_core`, pure functions, referential transparency |
| Behavior location | methods inside objects | free functions sweeping over typed records | testability, concurrency, backend-portability |

~ Inferred, the joined claim: CWA makes *resolution* deterministic (no inference); the relational/ECS split makes the *engine* deterministic and portable (no hidden object state, no backend coupling). Remove either and the thesis weakens — an OWA Cairn would need a reasoner (non-deterministic dependency); an OOP Cairn would re-import the impedance mismatch and bind behavior to state and storage. "Deterministic, not generative" is therefore not a slogan; it is the direct, named consequence of Reiter/Clark (Part A) plus Codd/ECS (Part B).

---

## Tech-spec constraints this produces

These are candidates for the patterns YAML / module-level intents in the tech-spec phase:

1. **`cwa_resolution_semantics`** — resolution operates under the Closed World Assumption: a surface form absent from the alias table and relation graph resolves to *not-found*, never to a generated/guessed canonical ID. Constraint: the resolver boundary returns an explicit "unresolved" result on miss; no fallback path may synthesize an identity. (Reiter 1978; Clark 1978 NAF.)

2. **`no_inference_engine_on_path`** — the query path contains no entailment, subsumption, or classification step and no model call. Constraint: `core/` imports no reasoner and no LLM client; resolution is membership + deterministic tiers only. (OWA→reasoner is the thing being excluded.)

3. **`ontology_is_representation_not_logic`** — the alias table / graph is read as a closed set of ground facts (a Horn database), not as axioms to be closed under inference. Constraint: no rule-expansion or transitive-closure inference is performed implicitly at query time; any closure is precomputed and stored as data.

4. **`entities_are_immutable_value_records`** — entities are frozen dataclasses / value records (Entity=row, attributes=columns). Constraint: no entity class carries resolution/traversal/ranking methods; entities expose data only.

5. **`algorithms_live_in_core_as_free_functions`** — resolve/traverse/rank/assemble are free functions over collections of records (System=query). Constraint: behavior is never encapsulated on the record type; `core/` functions are pure (same input → same output, no model, no hidden mutation).

6. **`core_depends_on_record_shape_only`** — `core/` depends on a record Protocol/shape, never on a concrete backend adapter. Constraint: enforces `storage_agnostic_core`; the same sweep runs over YAML/SQLite/Parquet-sourced records unchanged. (Avoids the object-relational impedance mismatch inside the engine.)

7. **`horn_safety_check`** — the authored fact base must remain Horn-shaped (ground facts / definite relations, no disjunctive heads) so CWA application is provably consistency-preserving. Constraint: the build/validate step rejects constructs that would break Horn safety. (Reiter 1978 consistency result.)

---

## Sources

- [Reiter, R. (1978). "On Closed World Data Bases." In *Logic and Data Bases* (Gallaire & Minker, eds.), Plenum, pp. 55–76 — UBC TR-77-16 PDF](https://www.cs.ubc.ca/sites/default/files/tr/1977/TR-77-16.pdf) — CWA: failure-to-prove ⇒ negation; OWA contrast; reducibility to atomic queries; Horn consistency result.
- [Reiter 1978 — Springer chapter](https://link.springer.com/chapter/10.1007/978-1-4684-3384-5_3) · [ACM Guide entry](https://dl.acm.org/doi/10.5555/902066) — canonical bibliographic record.
- [Clark, K. (1978). "Negation as Failure." In *Logic and Data Bases*, Plenum, pp. 293–322 — Springer (DOI 10.1007/978-1-4684-3384-5_11)](https://link.springer.com/chapter/10.1007/978-1-4684-3384-5_11) — NAF rule; soundness via the completed database (if → iff).
- [Shepherdson, J. C. (1984). "Negation as failure: a comparison of Clark's completed data base and Reiter's closed world assumption." *J. Logic Programming* — ScienceDirect](https://www.sciencedirect.com/science/article/pii/0743106684900232) — relationship between NAF and CWA.
- [W3C — OWL (Web Ontology Language)](https://www.w3.org/OWL/) — DL foundation; entailment ("facts not literally present … but entailed").
- [W3C — OWL Web Ontology Language Reference](https://www.w3.org/TR/owl-ref/) — OWA: unstated facts cannot be assumed false.
- [Heflin, J. — *An Introduction to the OWL Web Ontology Language* (Lehigh)](https://www.cse.lehigh.edu/~heflin/IntroToOWL.pdf) — OWA statement; OWL Lite/DL ↔ SHIF(D)/SHOIN(D).
- [Horrocks, Patel-Schneider, van Harmelen — "OWL and its description logic foundation" (IEEE)](https://ieeexplore.ieee.org/document/1236278/) — DL semantics of OWL.
- [Baader, Calvanese, McGuinness, Nardi, Patel-Schneider (eds.) — *The Description Logic Handbook*, Cambridge University Press](https://www.cambridge.org/core/books/description-logic-handbook/4D4CB19D49A1BB8D6E5F1F21FF2A56B6) — subsumption, classification, entailment as DL reasoning services.
- [Codd, E. F. (1970). "A Relational Model of Data for Large Shared Data Banks." *CACM* 13(6):377–387 — Communications of the ACM](https://cacm.acm.org/research/a-relational-model-of-data-for-large-shared-data-banks-2/) — relations/tuples; data separated from relational algebra.
- [Codd 1970 — IBM Research record](https://research.ibm.com/publications/a-relational-model-of-data-for-large-shared-data-banks) · [dblp (DOI 10.1145/362384.362685)](https://dblp.org/rec/journals/cacm/Codd70.html) · [full-text PDF (Grinnell)](https://rebelsky.cs.grinnell.edu/Courses/CS302/2007S/Readings/codd-1970.pdf).
- [Object–relational impedance mismatch — Wikipedia](https://en.wikipedia.org/wiki/Object%E2%80%93relational_impedance_mismatch) — definition; mapping objects↔tables friction.
- [Object-relational impedance mismatch — HandWiki](https://handwiki.org/wiki/Object-relational_impedance_mismatch) · [MDPI Encyclopedia entry](https://encyclopedia.pub/entry/29754) — OO-as-directed-graphs vs relational-as-tuples; engineering vs mathematical paradigms.
- [Entity component system — Wikipedia](https://en.wikipedia.org/wiki/Entity_component_system) — entities=data components + systems operating on them; ECS overlaps with DOD.
- [Schöner, S. — "Data-Oriented Design: An Interpretation"](https://blog.s-schoener.com/2019-06-09-data-oriented-design/) · [hexops devlog — "Let's build an ECS (part 1)"](https://devlog.hexops.org/2022/lets-build-ecs-part-1/) — Entity=row / Component=column / System=query isomorphism.
- [Unity Learn — "Understand data-oriented design"](https://learn.unity.com/course/dots-best-practices/tutorial/part-1-understand-data-oriented-design) · ["Data Oriented Design is not ECS"](https://yoyo-code.com/data-oriented-design-is-not-ecs/) — Mike Acton / DOD lineage; DOD ≠ ECS distinction ("let data be data").
- Cairn `cairn_system_intent.yaml` — invariants: `deterministic_resolution`, `zero_llm_calls_on_hot_path`, `explicit_canonical_ontology`, `storage_agnostic_core`.
- Cairn `ONTOLOGY_AUTHORING_RESEARCH_2026.md` — the alias table this CWA semantics operates over.
