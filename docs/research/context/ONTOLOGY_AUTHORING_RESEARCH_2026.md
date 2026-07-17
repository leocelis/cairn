# Ontology Authoring — Building and Maintaining the Canonical Alias Table

**For:** Cairn (agent-native retrieval engine) — Gap 3: how a user actually builds, populates, and maintains the canonical entity table that `explicit_canonical_ontology` depends on.
**Gap closed:** The charter names an optional build-time helper and stops there. No prior doc explains the schema, construction strategies, deduplication approach, incremental maintenance, conflict resolution, or serialization story for the alias table. Without this, onboarding Cairn is opaque.
**Invariants honored:** `explicit_canonical_ontology` (entity identity is authored, not hallucinated); `zero_llm_calls_on_hot_path` (the authoring helper is entirely offline/build-time, never on the query path); `storage_agnostic_core` (the alias table must be portable across backends); `local_first_no_mandatory_cloud` (the manual path requires no cloud at all; the LLM-assisted path uses a cloud model offline, not in-band).
**Date:** 2026-06-27
**Confidence markers:** ✓ verified (directly from source/code/paper) · ~ inferred (derived from evidence) · ? assumed (default; confirm if non-standard)

---

## 1. Why This Gap Matters

Cairn's entire entity-first routing premise collapses without a populated alias table. The charter's `explicit_canonical_ontology` invariant says: entities have explicit, stable canonical IDs *supplied/owned by the user* — identity is NOT invented by free-form LLM extraction at query time. The resolver's Tier 1 (exact match) and Tier 2 (deterministic fuzzy) both operate against this table. If the table is missing an entity, resolution silently fails and context assembly degrades to blind retrieval.

The charter explicitly flagged this risk: *"Ontology authoring burden (canonical IDs + aliases) deters adoption for large corpora."* The mitigation named was *"an optional, offline, batched build-time helper (may use an LLM) to bootstrap the alias table — separate from the hot path; never required to query."*

This document supplies the missing concrete design: schema, construction strategies, deduplication, maintenance, conflict resolution, and serialization.

---

## 2. Schema Design for the Canonical Entity Table

### 2.1 Minimal Viable Record

Drawing from Wikidata's data model ✓ ([Wikidata:Data_model](https://www.wikidata.org/wiki/Wikidata:Data_model)), catalogue-pipeline canonical ID design ✓ ([Wellcome Collection catalogue pipeline](https://docs.wellcomecollection.org/catalogue-pipeline/transforming-records-into-a-single-common-model/creating-canonical-identifiers)), and the entity-resolution literature (Christophides et al., "Almost All of Entity Resolution", *Science Advances* 2022, PMC11636688 ✓), a minimal canonical entity record needs:

| Field | Type | Required | Notes |
|---|---|---|---|
| `canonical_id` | `string` | yes | Stable, opaque, user-assigned. Slugged, URL-safe. Example: `person_jane_doe`, `account_savings_boa`. No auto-increment integers — they carry no semantics and break on merge. |
| `label` | `string` | yes | The primary human-readable name. Used for display, not matching. |
| `aliases` | `list[string]` | yes | Every surface form the corpus uses for this entity. This is the matching surface. Should include abbreviations, nicknames, misspellings, and both-language variants for multilingual corpora. |
| `entity_type` | `string` | yes | Coarse ontological class. Example: `person`, `organization`, `account`, `project`, `location`, `document`. Enables type-scoped disambiguation. |
| `description` | `string` | no | Short disambiguating phrase ("savings account at Bank of America, opened 2021"). Helps human review and LLM-assisted disambiguation. |
| `valid_from` | `date` | no | ISO 8601. When this entity began to exist in your corpus. Used for temporal scoping and ordering post-merge. |
| `valid_until` | `date` | no | ISO 8601. When this entity ceased to be active. `null` means still active. Enables temporal filtering without deletion. |
| `source` | `string` | no | Where this record originated: `manual`, `gliner_batch`, `llm_extract`, `import`. Auditable provenance. |
| `merged_from` | `list[string]` | no | List of `canonical_id`s that were absorbed into this record during a merge operation. Maintains backward compatibility: old IDs resolve to this record. |
| `metadata` | `map` | no | Arbitrary domain key-values. Not used by the resolver. Example: `{external_id: "Q80", url: "https://..."}`. |

**Invariant check:** ✓ `explicit_canonical_ontology` — `canonical_id` is user-assigned, never synthesized. ✓ `zero_llm_calls_on_hot_path` — the resolver reads `aliases` deterministically at query time; no LLM is called.

### 2.2 What NOT to Put in the Schema

- **Embeddings in the entity record.** ~ Inferred from production patterns: embeddings for semantic fallback resolution (Tier 3) belong in the vector store adapter, keyed by `canonical_id`, not in the canonical table itself. Storing them in the entity record couples the alias table to a specific embedding model and breaks `storage_agnostic_core`.
- **Relations.** Relations between entities belong in Cairn's relation graph (a separate primitive), not in the alias table. Conflating them bloats the table and complicates incremental updates.
- **Auto-generated IDs.** Integer sequences, UUIDs, or hashes break human readability and make the table unusable without tooling. Slug-style IDs (`org_acme_corp`, `vehicle_honda_hrv`) are self-documenting and survive serialization across backends.

### 2.3 Wikidata-Derived Lessons for Private Corpora

✓ Wikidata entities carry: a Q-identifier (`canonical_id`), a multilingual `label` dict, a `description`, and an `aliases` list per language. The minimal subset for a private corpus is: `canonical_id` + `label` + `aliases` + `entity_type`. The rest is progressive enrichment.

✓ Wikidata uses an "E" identifier for entity schemas (ShEx-based structural constraints), separate from the entity instances themselves. Cairn does not need schema enforcement at this granularity for a first cut; a flat YAML record per entity is sufficient.

### 2.4 Recommended Field Ordering in YAML (Day-1 Format)

```yaml
# entities.yaml — Cairn canonical alias table
entities:
  - canonical_id: person_jane_doe
    label: Jane Doe
    entity_type: person
    aliases:
      - Jane
      - Jane Doe
      - J. Doe
      - "@janedoe"
    description: "Software engineer; example person entity"
    valid_from: "2024-01-01"
    source: manual
    merged_from: []
    metadata: {}

  - canonical_id: org_acme_corp
    label: Acme Corp
    entity_type: organization
    aliases:
      - Acme Corp
      - Acme Inc.
      - the company
    description: "Example software company"
    valid_from: "2023-06-01"
    source: manual
    merged_from: []
    metadata: {}
```

---

## 3. Alias Table Construction Strategies

Three strategies, chosen by corpus size and precision requirements. They are not mutually exclusive — use them in combination.

### 3.1 Manual Curation (Recommended for Small, High-Precision Corpora)

**When to use:** Corpus has fewer than ~200 entities; entities are well-understood by the author; precision is non-negotiable (legal, financial, personal).

**Workflow:**
1. Enumerate entities from a source-of-truth document (e.g., a contacts list, an org chart, a schema definition).
2. Author one YAML record per entity with the `label`, `canonical_id`, and `aliases` populated by hand.
3. For aliases: think about every way you refer to this entity in actual text. Include abbreviations, initials, informal names, and cross-language variants explicitly.
4. Commit the YAML to version control alongside your corpus.

**Why it works:** The community consensus on deterministic entity resolution is clear — a well-maintained alias table achieves ~90%+ resolution accuracy at query time for Tier 1 (exact match) alone (~ inferred from entity-resolution literature; Christophides 2022 ✓). Manual curation produces the highest-quality alias table because the author already knows the entities.

**Limitation:** Does not scale past ~500 entities; alias coverage is only as good as the author's recall.

### 3.2 Semi-Automated: NER + Human Review

**When to use:** Corpus has 200–5,000 entities; entities are named but not fully enumerated; the author wants candidate lists to review rather than a blank slate.

**Tool: GLiNER** ✓ ([urchade/GLiNER](https://github.com/urchade/GLiNER), NAACL 2024):
- Zero-shot open-vocabulary NER. You supply natural-language entity type labels at inference time — no retraining.
- 50M–300M parameter models; CPU-viable. GLiNER2 (arXiv:2507.18546 ✓) extends to multi-task IE in one 205M-parameter model.
- Batch process all corpus documents: `gliner.predict_entities(texts, labels=["person", "organization", "project", "account"])`.
- Output: span detections with type labels. GLiNER does NOT resolve to canonical IDs — that is the next step.

**Workflow:**
1. Run GLiNER over the full corpus (offline batch, CPU).
2. Collect all detected spans + their entity_type labels.
3. Group by surface form (normalized, lowercased, stripped of punctuation).
4. Produce a candidate draft YAML: one entry per unique surface form cluster, `source: gliner_batch`.
5. Human review: merge obvious duplicates, assign `canonical_id`s, add known aliases the detector missed, and flag ambiguous entries.
6. Output: a reviewed, curated YAML table.

**What GLiNER does NOT do:** It does not resolve spans to canonical IDs, extract relations, or deduplicate across documents. Detection only. Resolution and deduplication are done in step 4–5. ✓ from ENTITY_RELATIONSHIP_RESOLUTION_RESEARCH_2026.md §2.7.

**Alternative for relation-enriched tables:** GLiNER-Relex (arXiv:2605.10108 ✓) or ReLiK (arXiv:2408.00103 ✓) can extract (entity, relation, entity) triples in one pass, allowing the entity table and the relation graph to be co-bootstrapped.

### 3.3 LLM-Assisted Batch (For Domain-Specific or Hard-to-Enumerate Entities)

**When to use:** Entity types are unusual for the domain (personal nicknames, project codenames, informal references); the corpus is large enough that manual enumeration is impractical; LLM-free NER misses too many entities; the author can run an offline batch job.

**Key principle:** The LLM runs ONCE at authoring/build time, producing a candidate alias table. It is never called again at query time. This satisfies `zero_llm_calls_on_hot_path` and `local_first_no_mandatory_cloud` (a cloud LLM is optional and used offline, not in-band). ✓ derived from the charter's constraint satisfiability note: *"Building the canonical ontology/alias table MAY use an LLM offline at authoring/ingest time."*

**Workflow (EntGPT pattern, arXiv:2510.20345 survey ✓):**
1. Chunk the corpus (500–1,000 token windows with 100-token overlap to avoid boundary misses).
2. For each chunk, run an LLM extraction prompt:
   ```
   List all entities mentioned. For each entity, output:
   canonical_id (slugged), label, entity_type, and every surface form used.
   Format: JSON array. Known entity types: person, organization, project,
   account, document, location, other.
   ```
   Use Instructor (✓ [567-labs/instructor](https://github.com/567-labs/instructor)) to enforce Pydantic schema compliance and get typed, validated output. No freeform prose.
3. Collect all candidate entities from all chunks into a flat list.
4. Deduplicate (see §4 — this is the critical step).
5. Human review of deduplicated candidates: correct mistakes, assign final `canonical_id`s, remove hallucinations.
6. Output: reviewed, curated YAML table.

**Why human review is mandatory:** LLMs exhibit "phantom entity generation" — inventing spans not in source text. A post-hoc span verification (verify extracted surface form appears verbatim in the source chunk) catches the worst cases. ✓ documented in ENTITY_RELATIONSHIP_RESOLUTION_RESEARCH_2026.md §3.3 as failure mode #1.

**Cost reality:** ~ Inferred: for a 1,000-document personal corpus (~500K tokens), one extraction pass using Claude Haiku or GPT-4o-mini costs under $1 in 2026. This is a one-time build-time cost, not a recurring per-query cost.

---

## 4. Entity Deduplication During Authoring

The core problem: the LLM-assisted batch (§3.3) and the NER semi-automated path (§3.2) will produce multiple candidate records for the same entity. "Jane", "Jane Doe", "J. Doe", and "@janedoe" must collapse to one record, not four.

### 4.1 The Three-Tier Dedup Stack (Build-Time)

Adapted from the Graphiti/Zep production approach (arXiv:2501.13956 ✓, and Zep blog 2025 ✓) for Cairn's authoring phase. At build time, dedup is not on the hot path — cost and latency constraints are relaxed. Use the full three-tier stack.

**Tier 1 — Exact String Match (normalized)**
- Normalize all candidate surface forms: lowercase, strip punctuation, collapse whitespace.
- Group candidates that share any normalized surface form. These are exact duplicates.
- Cost: O(n), sub-millisecond over thousands of candidates.
- Accuracy: deterministic, zero false positives.

**Tier 2 — MinHash/LSH Fuzzy Match**
- For candidates that did not collapse in Tier 1, compute MinHash signatures over character n-grams (n=3 recommended for short entity names).
- Use LSH banding to find approximate matches at Jaccard similarity ≥ 0.7 (tunable).
- MinHash compresses each candidate to a compact signature; LSH groups likely matches by hashing signature bands into shared buckets — candidates sharing a bucket are candidate duplicates. ✓ ([Milvus MinHash LSH blog](https://milvus.io/blog/minhash-lsh-in-milvus-the-secret-weapon-for-fighting-duplicates-in-llm-training-data.md); [Preferred Networks MinHash LSH implementation](https://tech.preferred.jp/en/blog/improve-minhashlsh-for-deduplication-on-large-scale-dataset/))
- Apply RapidFuzz `token_set_ratio` ≥ 0.85 within each bucket for confirmation. RapidFuzz runs at ~2,500 pairs/second, 20–100× faster than FuzzyWuzzy. ✓ (IJEEDU 2025)
- **Entropy gate (from Graphiti production, ✓ Zep blog 2025):** Short, low-entropy strings ("Amy", "Bob") generate too many MinHash false positives. If a candidate's label has Shannon entropy below a threshold (empirically ~1.5 bits/char for names under 8 chars), skip MinHash and route directly to the human review queue or Tier 3.

**Tier 3 — LLM Judgment (Build-Time Only)**
- For candidate pairs that Tiers 1–2 flagged as possible duplicates but did not resolve with confidence, present them to an LLM with context:
  ```
  Are these two entities the same? Show the surface forms and any surrounding
  document context. Answer: SAME or DIFFERENT. If SAME, which canonical_id wins?
  ```
- This is a build-time, offline, batched call — not a per-query call. Run it once after the extraction pass.
- Expected frequency of Tier 3 invocation: < 10% of candidate pairs on a well-curated corpus of ~500 entities. ~ Inferred from MDPI 2024 multi-agent ER results (94.3% accuracy at Tier 1–2 combined).

**Output of dedup:** A merged candidate list where each entry has a single `canonical_id`, a full `aliases` list (union of all surface forms from collapsed candidates), and `merged_from` populated if any collapse occurred.

### 4.2 RapidFuzz over MinHash for Small Corpora

~ Inferred from prior entity-resolution research: for corpora with fewer than ~1,000 candidate entities, the MinHash/LSH pipeline is over-engineered. Running RapidFuzz `token_set_ratio` directly over all pairs is O(n²) but completes in under 1 second at n=500. MinHash/LSH becomes worthwhile above ~5,000 candidates where O(n²) pairwise comparison is no longer tractable.

---

## 5. Incremental Maintenance

### 5.1 Adding New Entities

When new documents arrive, new entities may appear that are not in the existing alias table.

**Detection:** Run the same GLiNER batch (§3.2) or LLM extraction (§3.3) over new documents. Compare detected spans against the current alias table using Tier 1 exact match. Any span with no match is a candidate new entity.

**Workflow:**
1. Batch-detect entities in new documents.
2. Tier 1 exact match against existing `aliases`. Matched → skip (already known).
3. Tier 2 fuzzy match against existing `aliases`. Close match → candidate alias for an existing entity (add to `aliases` list, do not create a new record).
4. No match → candidate new entity. Add to a "pending review" staging file, not directly to the live table.
5. Human reviews pending entries: promote to the live table with a `canonical_id`, or mark as aliases for existing entities.

**Invariant:** Never add a new `canonical_id` without human confirmation on the default path. The pending review step is the enforcement point for `explicit_canonical_ontology`. Automated promotion is an opt-in (for high-volume, lower-stakes corpora).

### 5.2 Adding Aliases to Existing Entities

If a new document uses a surface form not in the current `aliases` list for an entity that is otherwise resolved (Tier 2 fuzzy match identifies the entity with confidence ≥ 0.85), the surface form can be added to `aliases` without rebuilding the table. This is an additive O(1) operation — append the new alias and rewrite the entity's record in the YAML/SQLite/Parquet representation.

**No full rebuild required.** The resolver's lookup structure (a flat dict of `alias → canonical_id`) is regenerated from the YAML at startup, or on a triggered reload. This is cheap even for 10,000-entry tables.

### 5.3 Entity Merging (Two IDs That Turn Out to Be the Same Entity)

This is the highest-risk maintenance operation because it is destructive: one `canonical_id` disappears.

**Safe merge procedure:**
1. Identify the pair: `canonical_id_A` and `canonical_id_B` are the same entity.
2. Choose the winner — the `canonical_id` that survives. Prefer the one with more existing corpus references (more stable). Document the choice.
3. In the loser's record: set `merged_from` to record the merge event, set `valid_until` to today's date.
4. In the winner's record: union the aliases from both records into `aliases`; append `canonical_id_B` to `merged_from`.
5. In the resolver's lookup dict: add all of `canonical_id_B`'s former aliases as keys pointing to `canonical_id_A`.
6. In the relation graph: repoint all edges that referenced `canonical_id_B` to `canonical_id_A`.
7. Do NOT delete the loser's record immediately — keep it with `valid_until` set for backward compatibility. A query using a stale `canonical_id_B` should resolve to `canonical_id_A` via the `merged_from` chain.

**Backward compatibility rule:** ✓ Derived from catalogue-pipeline patterns (Wellcome Collection docs): old IDs must continue to resolve. The `merged_from` field is Cairn's answer to this — it is a forwarding pointer.

### 5.4 Entity Splitting (One ID That Turns Out to Be Two Entities)

Less common but possible: `org_acme_corp` was used for two distinct legal entities in the corpus.

**Safe split procedure:**
1. Create two new `canonical_id`s: `org_acme_us` and `org_acme_ca`.
2. Divide the aliases between the two new records based on which entity they actually refer to.
3. Mark the original `org_acme_corp` record with `valid_until: today` and a note in `metadata` indicating it was split.
4. Add both new IDs to the original's `merged_from` field (reverse pointer, for audit).
5. The resolver: the original `org_acme_corp` alias now requires disambiguation at query time (it maps to two candidates). This creates a conflict — see §6.

---

## 6. Conflict Resolution

A conflict occurs when a single surface form maps to two different `canonical_id`s. This is the hardest problem in alias table authoring.

### 6.1 Authoring-Time Resolution (Preferred)

The best time to resolve a conflict is when authoring the table, not at query time. If "Apple" maps to both `org_apple_inc` and `fruit_apple`, the table must not contain a naked "Apple" alias on both records.

**Resolution strategies at authoring time:**

**a) Scoped aliases:** Add context-scoped surface forms. Instead of "Apple" as an alias on both records, use "Apple the company" and "Apple Inc." for `org_apple_inc`, and "apple" (lowercase, a product/ingredient) for `fruit_apple`. The resolver's exact-match tier will correctly route based on capitalization.

**b) Type-scoped resolution:** If the resolver knows the `entity_type` expected by the query context (e.g., a product query vs. a corporate filing query), it can resolve ambiguous surface forms by type. This requires the query routing layer to pass a type hint to the resolver.

**c) Explicit disambiguation marker:** Add a `disambiguates: true` flag to any alias that is known to be ambiguous. The resolver, on encountering this flag, escalates directly to Tier 4 (LLM disambiguation or user confirmation) rather than returning a confident match.

**d) Remove the ambiguous alias entirely:** If no resolution strategy cleanly separates the two entities, remove the ambiguous surface form from both alias lists. Document which surface forms are considered "too ambiguous to resolve deterministically" in a `conflicts.yaml` companion file.

### 6.2 Query-Time Fallback (When Authoring-Time Resolution Was Insufficient)

If a surface form at query time matches two `canonical_id`s (because the authoring step missed the conflict), the resolver must not silently pick one.

**Correct behavior:**
- Tier 1 exact match returns two candidates → escalate to disambiguation.
- The resolver returns both candidates with confidence = 0.5 each (tied) and an `ambiguous: true` flag.
- The routing layer decides: either ask the agent for clarification context, or use the `entity_type` of the surrounding query to break the tie.
- If the tie cannot be broken deterministically, the resolver logs the ambiguity and returns both candidates. The context assembly layer uses both (union) or neither (abstain), depending on the configured ambiguity policy.

**The ambiguity policy is a user-level configuration, not a default.** Default: return both candidates, mark as ambiguous, let the agent decide.

### 6.3 Corpus-Level Conflict Audit

At authoring time, run a conflict audit before finalizing the table:
```python
# pseudocode — detect conflicts
alias_to_ids = {}
for entity in entities:
    for alias in entity.aliases:
        key = normalize(alias)
        alias_to_ids.setdefault(key, []).append(entity.canonical_id)

conflicts = {alias: ids for alias, ids in alias_to_ids.items() if len(ids) > 1}
```
Any entry in `conflicts` is a surface form that will cause an ambiguous resolution. Resolve them all at authoring time before deploying the table. This audit should be part of the build pipeline's CI gate.

---

## 7. Portability and Serialization

Cairn is storage-agnostic. The alias table must be portable across backends without changing the resolver's interface.

### 7.1 The Three Target Formats

| Format | Corpus size | Use case | Tooling |
|---|---|---|---|
| **Flat YAML** | < ~500 entities | Personal use, development, version-controlled | Human-readable, git-diffable, no tooling required |
| **SQLite** | 500–50,000 entities | Team use, production local, single-process | Single file, full SQL queries, no server, DuckDB-compatible |
| **Parquet** | 50,000+ entities | Large-scale, batch pipelines, columnar analytics | Columnar compression, pandas/polars/Arrow-native, MLflow-compatible |

✓ BioBricks.ai (arXiv:2408.17320) uses exactly this three-format tiering (Parquet, SQLite, HDT) for versioned life-sciences data assets — direct precedent for format-agnostic portability.

~ Inferred: a Parquet alias table at 100,000 entities stays under 20MB compressed (entity records are narrow — ~10 string fields). SQLite at 50,000 entities with a `canonical_id` index runs sub-millisecond lookups.

### 7.2 The Right Abstraction: An Adapter Interface

The resolver must not know which format backs the table. The correct abstraction:

```python
class AliasTableAdapter(Protocol):
    def lookup(self, surface_form: str) -> list[CandidateMatch]: ...
    def get_entity(self, canonical_id: str) -> Entity | None: ...
    def list_entities(self) -> list[Entity]: ...
    def upsert_entity(self, entity: Entity) -> None: ...
```

Three adapter implementations: `YAMLAliasTable`, `SQLiteAliasTable`, `ParquetAliasTable`. The resolver calls the Protocol — never a concrete class. Switching backends is a configuration change, not a code change. ✓ Satisfies `storage_agnostic_core`.

### 7.3 YAML → SQLite Migration Path

As a corpus grows past the YAML threshold, migration is a one-time build step:

```python
# pseudocode — YAML to SQLite migration
entities = load_yaml("entities.yaml")
conn = sqlite3.connect("entities.db")
conn.execute("""
    CREATE TABLE entities (
        canonical_id TEXT PRIMARY KEY,
        label TEXT,
        entity_type TEXT,
        description TEXT,
        valid_from DATE,
        valid_until DATE,
        source TEXT
    )
""")
conn.execute("CREATE TABLE aliases (alias TEXT, canonical_id TEXT REFERENCES entities)")
conn.execute("CREATE INDEX idx_aliases ON aliases(alias)")
for e in entities:
    conn.execute("INSERT INTO entities VALUES (?, ?, ?, ?, ?, ?, ?)", ...)
    for alias in e.aliases:
        conn.execute("INSERT INTO aliases VALUES (?, ?)", (normalize(alias), e.canonical_id))
```

The resolver's `SQLiteAliasTable.lookup(surface_form)` is then a single indexed query: `SELECT canonical_id FROM aliases WHERE alias = ?`. O(log n), sub-millisecond.

### 7.4 Alias Table Versioning

The alias table is a build-time artifact. It should be versioned alongside the corpus, not the code:
- For YAML: commit to git with the corpus. Git diff shows every alias added, removed, or changed.
- For SQLite: use a `schema_version` table + a migration log. The file is binary — not git-diffable — so keep a human-readable changelog alongside it.
- For Parquet: use a versioned path convention (`entities/v3/entities.parquet`) and a `_metadata` file with build timestamp and corpus hash.

---

## 8. Buildable Spec: Day-1 Authoring Workflow

### 8.1 The Manual Path (No tooling required, works offline, no cloud)

Follows `local_first_no_mandatory_cloud`. ✓

1. **Start with a source of truth.** Pull your entity list from the most authoritative source you have: a contacts export, a schema definition, a README listing the project's key concepts.

2. **Create `entities.yaml`.** One record per entity, following the schema in §2.4. Start with `canonical_id`, `label`, `entity_type`, and `aliases`. Leave `description`, `valid_from`, and `metadata` empty until you need them.

3. **Run the conflict audit** (§6.3 pseudocode). Fix every conflict before deploying.

4. **Mount the table into Cairn.** Pass the YAML path to the `YAMLAliasTable` adapter. The resolver builds a flat `dict[str, str]` (normalized alias → canonical_id) at startup. Done.

**Time estimate:** ~ For a corpus with 50–100 well-understood entities, this takes 30–60 minutes of focused authoring. The ROI: deterministic, auditable entity resolution for the lifetime of the corpus.

### 8.2 The Assisted Path (For Larger or Unfamiliar Corpora)

1. **Install GLiNER:** `pip install gliner`. No cloud account required.

2. **Run batch detection over your corpus:**
   ```python
   from gliner import GLiNER
   model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")
   entities = model.predict_entities(
       texts=corpus_chunks,
       labels=["person", "organization", "project", "account", "location"]
   )
   ```
   ✓ GLiNER runs on CPU, 50M–300M parameters, batch-capable.

3. **Generate a candidate YAML draft** from the detected spans (group by normalized surface form, one record per cluster).

4. **Run MinHash dedup** (§4.1 Tier 2) over the candidate list to collapse near-duplicates.

5. **Human review.** Review the deduplicated candidate YAML. Assign `canonical_id`s, correct entity types, add aliases the detector missed, remove hallucinations.

6. **Run conflict audit** (§6.3). Fix conflicts.

7. **Mount the table.** Same as step 4 of the manual path.

**Optional LLM assist (for step 3 or 4):** If GLiNER misses domain-specific entity types (project codenames, informal nicknames), run an LLM extraction pass (§3.3) on a subset of documents where NER fails. This is an offline, one-time call — not a recurring cost.

---

## 9. Tech-Spec Constraints This Research Produces

The following new operations (OPs) and constraints are candidates for the patterns YAML and/or module-level intents in the tech-spec phase:

1. **`alias_table_schema`** — canonical entity record schema (§2.1). Fields: `canonical_id`, `label`, `aliases`, `entity_type`, `description`, `valid_from`, `valid_until`, `source`, `merged_from`, `metadata`. Constraint: `canonical_id` is user-assigned, slug-style, never auto-generated.

2. **`alias_table_adapter`** — the Protocol interface (§7.2). All three adapters (YAML, SQLite, Parquet) must implement it. Constraint: the resolver core imports the Protocol only, no concrete adapter.

3. **`conflict_audit_gate`** — a CI-runnable script that fails if any normalized alias maps to more than one `canonical_id`. Must pass before the table is deployed. Constraint: zero conflicts in the deployed table.

4. **`dedup_three_tier_build_time`** — the MinHash/LSH + RapidFuzz + LLM-arbiter dedup pipeline (§4.1). Lives in `ontology/dedup.py`. Constraint: LLM tier is build-time only, never called by the resolver at query time.

5. **`merge_procedure`** — the safe entity merge workflow (§5.3). Constraint: `merged_from` is always populated; old IDs resolve via forwarding; no `canonical_id` is hard-deleted without a deprecation cycle.

6. **`incremental_add_alias`** — the O(1) alias append operation (§5.2). Constraint: adding an alias to an existing entity does not require a full table rebuild.

7. **`authoring_helper`** — the optional offline batch build tool (`cairn ontology build --corpus ./docs`). Uses GLiNER + optional LLM pass. Constraint: tool is entirely optional; `cairn retrieve` works without it; the helper never runs at query time.

---

## Sources

- [Wikidata:Data_model](https://www.wikidata.org/wiki/Wikidata:Data_model) — entity schema fields (Q-identifier, labels, aliases, descriptions)
- [Wikidata:Identifiers](https://www.wikidata.org/wiki/Wikidata:Identifiers) — identifier design principles
- [Wellcome Collection — Creating Canonical Identifiers](https://docs.wellcomecollection.org/catalogue-pipeline/transforming-records-into-a-single-common-model/creating-canonical-identifiers) — source/canonical one-to-one mapping, ID design (short, unambiguous, URL-safe)
- [GLiNER — NAACL 2024](https://aclanthology.org/2024.naacl-long.300.pdf) — zero-shot NER, bi-encoder architecture, CPU inference
- [GLiNER GitHub (urchade/GLiNER)](https://github.com/urchade/GLiNER) — batch processing, torch.compile, Ray Serve integration
- [GLiNER2 — arXiv:2507.18546](https://arxiv.org/html/2507.18546v1) — multi-task IE, 205M parameters, schema-driven interface
- [GLiNER-Relex — arXiv:2605.10108](https://arxiv.org/html/2605.10108v1) — joint NER + relation extraction
- [REBEL (Babelscape/rebel) — EMNLP 2021](https://aclanthology.org/2021.findings-emnlp.204/) — seq2seq relation extraction baseline
- [ReLiK — ACL 2024 (arXiv:2408.00103)](https://arxiv.org/abs/2408.00103) — retriever-reader EL + RE, 40x faster
- [Instructor (567-labs/instructor)](https://github.com/567-labs/instructor) — Pydantic-enforced LLM extraction schema
- [Christophides et al. — "(Almost) All of Entity Resolution", Science Advances 2022 (PMC11636688)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11636688/) — four-stage ER pipeline; blocking cascade failure
- [Zep/Graphiti — arXiv:2501.13956](https://arxiv.org/abs/2501.13956) — production temporal KG, entity extraction + dedup architecture
- [Zep blog 2025 — Graphiti entropy gate](https://blog.getzep.com/graphiti-hits-20k-stars-mcp-server-1-0/) — entropy gate for short-string MinHash false positives
- [LLM-Empowered KG Construction Survey — arXiv:2510.20345](https://arxiv.org/abs/2510.20345) — EntGPT two-phase extraction pattern; schema-supervised vs schema-inductive split
- [Milvus — MinHash LSH for deduplication](https://milvus.io/blog/minhash-lsh-in-milvus-the-secret-weapon-for-fighting-duplicates-in-llm-training-data.md) — MinHash/LSH mechanics, banding, bucket collision
- [Preferred Networks — MinHash LSH at scale](https://tech.preferred.jp/en/blog/improve-minhashlsh-for-deduplication-on-large-scale-dataset/) — production MinHash implementation guidance
- [IJEEDU 2025 — Python Text Matching Libraries Comparison](https://ijeedu.com/index.php/ijeedu/article/view/188) — RapidFuzz 2,500 pairs/sec vs FuzzyWuzzy (20–100× slower)
- [MDPI 2024 — Multi-Agent RAG for Entity Resolution](https://www.mdpi.com/2073-431X/14/12/525) — 94.3% accuracy on name variation matching with specialized agents
- [BioBricks.ai — arXiv:2408.17320](https://arxiv.org/pdf/2408.17320) — Parquet/SQLite/HDT tiered serialization for versioned data registries
- [ParquetDB — arXiv:2502.05311](https://arxiv.org/html/2502.05311v1) — columnar storage, nested type support, portability
- [AnyMatch — arXiv:2409.04073](https://arxiv.org/abs/2409.04073) — SLM for entity matching, 3,899× cheaper than GPT-4 for Tier 4 arbiter
- [ARTER — arXiv:2510.20098](https://arxiv.org/abs/2510.20098) — adaptive LLM routing for EL; +2.53% accuracy, 58.25% token reduction
- [Entity Resolution at Scale (Medium, Shereshevsky 2026)](https://medium.com/@shereshevsky/entity-resolution-at-scale-deduplication-strategies-for-knowledge-graph-construction-7499a60a97c3) — enterprise deduplication strategy overview
- [Entity Linking — Wikipedia](https://en.wikipedia.org/wiki/Entity_linking) — surface form disambiguation definition
- Cairn system intent (cairn_system_intent.yaml) — charter invariants, constraint satisfiability, planned `ontology/` module
- Cairn ENTITY_RELATIONSHIP_RESOLUTION_RESEARCH_2026.md — alias table construction, 5-layer hybrid stack, GLiNER/ReLiK/REBEL capabilities summary, failure modes
