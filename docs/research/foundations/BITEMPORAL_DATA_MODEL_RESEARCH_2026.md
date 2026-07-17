# The Bitemporal Data Model — Foundations Research

> **For:** Cairn OSS — theoretical foundation for mutable entity/relation state
>   tracking over two independent time axes (per OP-28, OP-22).
> **Gap closed:** Why does Cairn need TWO time axes (valid time + transaction
>   time) instead of a single `updated_at` timestamp? What is the formal CS
>   theory that makes "what did the agent know on date T?" and "what was actually
>   true on date T?" two distinct, separately-answerable queries?
> **Invariants honored:**
>   - Deterministic (same corpus state + same `(valid_t, tx_t)` pair → same result)
>   - Storage-agnostic (the model is schema-level; any backend can carry four columns)
>   - Zero generative-LLM on the hot path (point-in-time selection is a pure predicate)
>   - Append-only history (transaction time is never rewritten — facts are expired, not deleted)
> **Companion docs:**
>   `ENTITY_GRAPH_TRAVERSAL_RESEARCH_2026.md` (traversal step, OP-34),
>   `ENTITY_RELATIONSHIP_RESOLUTION_RESEARCH_2026.md` (resolution, OP-35),
>   `databases/FALKORDB_GRAPHITI_DEEP_RESEARCH_2026.md` (Graphiti/Zep practice)
> **Date:** 2026-06-26
> **Version:** 1.0
> **Confidence:** Primary claims ✓ verified against original papers and the
>   ISO-standard literature; mappings to Cairn schema marked ~ inferred / ? assumed.

---

## TL;DR

A single timestamp cannot answer two different questions at once. "When was this
fact true in the world?" and "when did the system believe this fact?" are
**orthogonal** time axes — collapsing them into one `updated_at` field destroys
the ability to reconstruct what the agent knew at a past moment, separately from
what was actually the case at that moment. The **bitemporal data model**, formally
introduced by Snodgrass & Ahn (1985) and standardized into SQL by SQL:2011, gives
every fact two intervals: **valid time** (`valid_at` / `invalid_at`) and
**transaction time** (`created_at` / `expired_at`). Point-in-time queries become a
pure conjunctive predicate over four columns — deterministic, no generative LLM
required. Allen's interval algebra (1983) supplies the 13 relations used to filter
and reason over the resulting intervals. Graphiti/Zep (arXiv:2501.13956) ship this
exact model in production for agent memory.

---

## 1. The Problem: One Timestamp Is Two Questions Collapsed

Consider an agent that learns on 2026-03-10 that "Acme's contract status became
*active* on 2026-02-01." Later, on 2026-04-05, it learns the contract was
*actually* active starting 2026-01-15 (the earlier ingestion was wrong about the
start date).

Two independent questions now exist:

1. **World question:** "Was Acme's contract active on 2026-01-20?"
   → Answer depends on *valid time*: yes (true start was 2026-01-15).
2. **Knowledge question:** "On 2026-03-15, did the agent believe Acme was active
   on 2026-01-20?"
   → Answer depends on *transaction time*: no — at that moment the system's best
   record said the contract started 2026-02-01.

✓ verified: These two questions have **different answers over the same target
date** (2026-01-20). A single `updated_at` column cannot represent both, because
it conflates "when the world changed" with "when our record changed." This is the
canonical motivation for separating the two axes (Snodgrass & Ahn 1985, §2;
Kulkarni & Michels 2012, §1).

~ inferred: For an agent-native retrieval engine this is not academic. Audit
("why did you act on stale data?"), reproducibility ("re-run the decision as of
last Tuesday"), and correctness of point-in-time retrieval **all** require the
knowledge axis to be recoverable independently of the world axis.

---

## 2. The Two Time Axes — Formal Definitions

### 2.1 Valid time (application time)

✓ verified: The **valid time** of a fact is the time when the fact is true in the
modeled reality. Valid times are typically supplied by the user / source, and may
extend into the future or be revised in the past (Snodgrass & Ahn 1985). It is
the "real-world" or "application" axis. In SQL:2011 this is realized as an
**application-time period table** with a user-named period (e.g. `PERIOD FOR
business_time (valid_from, valid_to)`) (Kulkarni & Michels 2012, §2).

In Cairn terms: `valid_at` / `invalid_at`.

### 2.2 Transaction time (system time / ingestion time)

✓ verified: The **transaction time** of a fact is the time when the fact is
*current in the database* — i.e., when the system stored and believed it. Two
properties are structural, not stylistic (Snodgrass & Ahn 1985):

- Transaction time **cannot extend into the future** (you cannot record what you
  have not yet learned).
- Past transaction time **cannot be changed** ("it is impossible to change the
  past"). History is therefore **append-only**: a fact is *expired*, never
  deleted or rewritten.

In SQL:2011 this is the **system-versioned table** with the reserved
`PERIOD FOR SYSTEM_TIME` period, where the DBMS — not the user — sets the start
and end columns (Kulkarni & Michels 2012, §3).

In Cairn terms: `created_at` / `expired_at`.

### 2.3 Bitemporal = both, independently

✓ verified: A relation that supports **both** valid time and transaction time is a
**bitemporal relation** (Snodgrass & Ahn 1985 propose the taxonomy: snapshot,
valid-time, transaction-time, bitemporal). SQL:2011 calls the combined form a
**system-versioned application-time period table** (Kulkarni & Michels 2012, §4).
The two axes are mathematically independent: a fact occupies a *rectangle* in the
`(valid_time × transaction_time)` plane, not a point or a line.

? assumed: Snodgrass & Ahn's taxonomy also names a third, non-temporal axis —
**user-defined time** (arbitrary date attributes with no special semantics, e.g.
"date_of_birth"). Cairn does not need to treat user-defined time specially; it is
just an ordinary attribute. Flag if a future OP requires it.

---

## 3. Why Bitemporal Is *Required* for Deterministic Point-in-Time Queries

### 3.1 The query reduces to a four-column predicate

✓ verified: Once both intervals are stored as half-open ranges (SQL:2011 uses
closed-open `[start, end)` period semantics; Kulkarni & Michels 2012, §2), a
point-in-time query is a pure conjunction:

```
SELECT * FROM facts
WHERE valid_at   <= :as_of_world      AND :as_of_world      < invalid_at   -- world axis
  AND created_at <= :as_of_knowledge  AND :as_of_knowledge  < expired_at   -- knowledge axis
```

- "What was *true* on date T (best current knowledge)?" → fix `:as_of_world = T`,
  set `:as_of_knowledge = now()`.
- "What did the agent *know* on date T?" → fix `:as_of_knowledge = T`, set
  `:as_of_world = T` (or any world date of interest).
- "As of what we knew last Tuesday, what was true in January?" → fix BOTH
  independently.

~ inferred: Because this is a deterministic predicate over four columns with no
ranking, no embedding, and no generation, it satisfies Cairn's "zero generative-LLM
on the hot path" and "deterministic" invariants directly. The same `(world,
knowledge)` pair against the same corpus state yields a byte-identical row set.

### 3.2 Why a single timestamp cannot be patched into this

✓ verified: With one `updated_at` column you can express *either* "latest version"
*or* "as-of-world" — never both — because an update **overwrites** the prior value.
The information needed to answer the knowledge question is physically gone. Append-
only transaction time is what preserves it: corrections create a *new* row and
*expire* the old one rather than mutating it (Snodgrass & Ahn 1985; this is the
"cannot change the past" property in §2.2).

This is the load-bearing reason the model is two axes and not "a timestamp plus a
convention."

---

## 4. Allen's Interval Algebra — Reasoning Over the Intervals

✓ verified: Allen (1983), "Maintaining Knowledge about Temporal Intervals" (CACM
26(11):832–843), defines **13 mutually exclusive, jointly exhaustive** qualitative
relations between two intervals, derived from the orderings of their endpoints:
`before / after`, `meets / met-by`, `overlaps / overlapped-by`, `starts /
started-by`, `during / contains`, `finishes / finished-by`, and `equals`.

Relevance to Cairn (~ inferred unless noted):

- **Temporal edge filtering (OP-34 traversal):** when collecting facts/edges
  whose validity must intersect a query window `[q_start, q_end)`, the test "does
  edge interval `[valid_at, invalid_at)` overlap the query window?" is exactly the
  disjunction of Allen's `overlaps / during / contains / starts / finishes /
  equals` (i.e., NOT `before` and NOT `after`). Implementing it as the simple
  endpoint predicate `valid_at < q_end AND q_start < invalid_at` is the standard,
  index-friendly reduction of that disjunction. ✓ verified (this is the textbook
  interval-overlap identity).
- **Contradiction / supersession:** Allen's `meets` (one interval's end equals the
  next's start) is the right relation for expressing "fact B took over exactly
  when fact A ended" — which is how Graphiti closes an invalidated edge (see §5).
- **Qualitative reasoning without exact stamps:** Allen's algebra was designed for
  *imprecise / relative* temporal knowledge ("A happened during B") where exact
  timestamps are unavailable — useful when source text gives only relative order.
  ? assumed: Cairn may need this only at indexing time; the hot-path filter stays
  numeric. Flag if relative-time inference moves onto the query path.

---

## 5. How Graphiti / Zep Implement Bitemporal in Practice

✓ verified (arXiv:2501.13956, Rasmussen et al., "Zep: A Temporal Knowledge Graph
Architecture for Agent Memory"): Graphiti (the open-source engine inside Zep)
implements **exactly** the two-axis model on graph *edges*, with four timestamps:

- Event timeline **T** (≈ valid time): **`t_valid`** and **`t_invalid`** —
  "track the temporal range during which facts held true."
- Transaction timeline **T′** (≈ transaction/ingestion time): **`t'_created`** and
  **`t'_expired`** — "monitor when facts are created or invalidated in the system."

✓ verified: On detecting a contradiction, Zep invalidates the superseded edge by
**setting its `t_invalid` to the `t_valid` of the invalidating edge** — i.e., the
new fact `meets` the old one on the valid-time axis (Allen relation), while the old
edge is `t'_expired` on the transaction axis rather than deleted. This preserves
"both current relationship states and historical records of relationship evolution"
(paper, §3).

✓ verified: The motivating example in the surrounding literature — "What was the
contract status in March?" — is precisely the point-in-time query that pure vector
retrieval cannot answer, and that the bitemporal model makes a deterministic
predicate.

~ inferred: Cairn's `valid_at/invalid_at/created_at/expired_at` is a direct rename
of Graphiti's `t_valid/t_invalid/t'_created/t'_expired`. The naming aligns with
SQL:2011 column-pair conventions, which is the more durable standard to anchor on
than any single library's field names.

---

## 6. Mapping to Cairn's Design

### 6.1 Entity / relation record schema (OP-35)

~ inferred: Every mutable entity record and every relation/edge carries four
temporal columns plus its payload:

| Column        | Axis              | Set by        | Semantics                                  |
|---------------|-------------------|---------------|--------------------------------------------|
| `valid_at`    | valid (world)     | source/user   | when the fact became true in the world     |
| `invalid_at`  | valid (world)     | source/user   | when it stopped being true (`+∞` = current)|
| `created_at`  | transaction       | system        | when Cairn ingested/believed it            |
| `expired_at`  | transaction       | system        | when Cairn superseded it (`+∞` = believed) |

? assumed: Open ends are represented as a sentinel (`NULL` or `+∞`); the predicate
in §3.1 treats an open `invalid_at`/`expired_at` as "still in effect." Confirm the
sentinel choice in the OP-35 schema spec — it must be consistent with the
half-open `[start, end)` comparison so boundary instants are not double-counted.

✓ verified: Corrections are **append-only**: a superseding fact inserts a new row
(new `created_at`), and the prior row's `expired_at` is set to the correction's
`created_at`. The prior row is never mutated or deleted (Snodgrass & Ahn 1985,
transaction-time immutability). This is what makes "what did the agent know on
date T?" reconstructable forever.

### 6.2 Traversal temporal filtering (OP-34)

~ inferred: The traversal step (per `ENTITY_GRAPH_TRAVERSAL_RESEARCH_2026.md`) is
already structural and LLM-free. Bitemporal filtering slots in as an additional
**edge predicate** evaluated during fan-out: an edge is admissible at hops only if
its `(valid, transaction)` rectangle contains the query's `(as_of_world,
as_of_knowledge)` point (§3.1 predicate). This keeps determinism and adds no
generative step.

~ inferred: Default behavior — if the caller specifies no temporal point — is
`as_of_world = as_of_knowledge = now()`, i.e., "current truth, current knowledge,"
which collapses to the familiar non-temporal traversal. Bitemporality is therefore
**zero-cost when unused** and fully available when needed.

---

## Tech-spec constraints this produces

1. **Four temporal columns, not one.** Every mutable entity record and relation
   MUST carry `valid_at`, `invalid_at`, `created_at`, `expired_at`. A single
   `updated_at` is prohibited for mutable state — it is provably insufficient for
   point-in-time reconstruction (§3.2). (OP-35)
2. **Append-only transaction time.** Corrections MUST insert a new row and set the
   prior row's `expired_at`; they MUST NOT mutate or delete the prior row.
   Transaction time is immutable and never future-dated (§2.2, §6.1).
3. **Half-open interval semantics.** All four columns use closed-open `[start,
   end)` comparison (SQL:2011 period semantics), with a single agreed open-end
   sentinel, so boundary instants are counted exactly once (§3.1, §6.1).
4. **Point-in-time query = pure 4-column predicate.** The as-of query MUST be a
   deterministic conjunction over the four columns with no ranking, embedding, or
   generation on the path (§3.1). Same inputs + same corpus state → identical rows.
5. **Two independent query parameters.** The retrieval API MUST expose
   `as_of_world` and `as_of_knowledge` as *separate* parameters; defaulting both to
   `now()` MUST reproduce non-temporal behavior exactly (§6.2).
6. **Edge temporal filter via interval-overlap identity.** Traversal edge
   admissibility MUST use the endpoint-overlap reduction of Allen's overlap class
   (`valid_at < q_end AND q_start < invalid_at`, analogously for the transaction
   axis), not a per-relation case analysis on the hot path (§4, §6.2).
7. **Supersession = `meets` on valid time + `expired` on transaction time.** When a
   new fact contradicts an old one, the old edge's `invalid_at` is set to the new
   edge's `valid_at` (Allen `meets`) and its `expired_at` is set to the new edge's
   `created_at` — mirroring Graphiti's invalidation (§5).

---

## Sources

Primary papers and standards (all verified against original sources):

- Snodgrass, R., & Ahn, I. (1985). *A Taxonomy of Time in Databases.* Proc. ACM
  SIGMOD Int'l Conf. on Management of Data, pp. 236–246. Original PDF:
  https://www2.cs.arizona.edu/people/rts/pubs/SIGMOD85.pdf — defines valid time,
  transaction time, user-defined time; the snapshot/valid/transaction/bitemporal
  taxonomy; transaction-time immutability.
- Kulkarni, K., & Michels, J.-E. (2012). *Temporal features in SQL:2011.* ACM
  SIGMOD Record 41(3):34–43. https://sigmodrecord.org/publications/sigmodRecord/1209/pdfs/07.industry.kulkarni.pdf
  (overview: https://en.wikipedia.org/wiki/SQL:2011) — ISO/IEC 9075:2011
  application-time period tables, system-versioned tables, bitemporal tables;
  `PERIOD FOR` declarations; closed-open period semantics.
- Allen, J. F. (1983). *Maintaining Knowledge about Temporal Intervals.*
  Communications of the ACM 26(11):832–843. — the 13 interval relations
  (before/after, meets/met-by, overlaps/overlapped-by, starts/started-by,
  during/contains, finishes/finished-by, equals).
- Rasmussen, P., et al. (2025). *Zep: A Temporal Knowledge Graph Architecture for
  Agent Memory.* arXiv:2501.13956. https://arxiv.org/abs/2501.13956 (HTML:
  https://arxiv.org/html/2501.13956v1) — Graphiti's bitemporal edges
  `t_valid/t_invalid` (event timeline T) and `t'_created/t'_expired` (transaction
  timeline T′); contradiction handling via setting `t_invalid` to the invalidating
  edge's `t_valid`.

Reference encyclopedia entries (definitions cross-checked):

- *Valid Time* / *Transaction Time*, in Encyclopedia of Database Systems
  (Springer): https://link.springer.com/referenceworkentry/10.1007/978-0-387-39940-9_1066
  and https://link.springer.com/referenceworkentry/10.1007/978-0-387-39940-9_1064
- *Temporal database* (overview): https://en.wikipedia.org/wiki/Temporal_database
