# Feeding the Embedding Corpus: Does More Data → More Precise?

> **Status:** Optional adjacent research — v0.2 (2026-06-27)  
> **Tier:** Not Cairn core canon — personalization / exemplar-corpus dynamics.  
> **For Cairn corpus hygiene:** see `CONTEXT_BUILDING_AND_MAINTENANCE_RESEARCH_2026.md` Part 20.2  
>   and `patterns_retrieval_knowledge.yaml` OP-10.  
> **Companion:** `CONTEXT_BEATS_MODEL_SEMANTIC_VS_GREP.md` (corpus dynamics).  
> **Hypothesis:** *Does adding more curated documents to a retrieval corpus improve precision,
>   or does quality + retrieval strategy dominate raw volume?*  
> **Sourcing rule:** Every paper has a verified arXiv ID/venue — not recalled from model memory.

---

## Verdict up front (calibrated)

**✅ The mechanism is validated, and "more data helps" has direct support — but reframe
"more → more precise" to "more *good* data + good retrieval → more precise."**

- ✓ **The chain works:** retrieve semantically relevant exemplars → inject as demonstrations
  → better output. Well-established *retrieval-of-exemplars* result (KATE, EPR) and
  *retrieval-augmented personalization* (LaMP).
- ✓ **Growing the corpus genuinely helps:** datastore size **monotonically improves** downstream
  performance *without obvious saturation* (MassiveDS) — and updating it keeps it **fresh**
  without retraining (FreshLLMs).
- ⚠️ **But precision is not a function of raw volume.** Adding **redundant, noisy, stale, or
  biased** documents *degrades* output (Power of Noise; corpus-quality work; lost-in-the-middle).
  Precision comes from **data quality + retrieval/curation quality**, with corpus growth as a
  *multiplier on top* — not a substitute.

**One line:** *yes — grow the corpus, but precision comes from **diverse, representative, fresh,
clean** documents and **retrieving them well**, not from volume alone.*

---

## Part 1 — Growing the corpus genuinely helps (the pro-hunch evidence)

- **Shao, He, Asai, et al. (UW/AI2, 2024)** — *Scaling Retrieval-Based LMs with a Trillion-Token
  Datastore (MassiveDS).* NeurIPS 2024. arXiv:[2407.12854](https://arxiv.org/abs/2407.12854)
  — Increasing **inference-time datastore size monotonically improves** language modeling and
  knowledge-intensive tasks **without obvious saturation**; a **smaller model + larger datastore
  beats a larger model alone.**
- **Vu, Iyyer, Wang, et al. (Google, 2023)** — *FreshLLMs: Refreshing LLMs with Search-Engine
  Augmentation.* arXiv:[2310.03214](https://arxiv.org/abs/2310.03214)
  — Updating the retrieved evidence keeps answers **current**; **both the number and the order**
  of retrieved evidence drive correctness. → RAG's freshness advantage (cf. Ovadia: RAG > fine-tuning
  for new knowledge).

---

## Part 2 — The mechanism: exemplars → retrieve → prompt → better output

- **Liu, Shen, Zhang, et al. (2021)** — *What Makes Good In-Context Examples for GPT-3? (KATE).*
  DeeLIO 2022. arXiv:[2101.06804](https://arxiv.org/abs/2101.06804)
  — Retrieving examples **semantically similar to the input** (vs random) gives large gains.
- **Rubin, Herzig, Berant (2021)** — *Learning to Retrieve Prompts for In-Context Learning (EPR).*
  NAACL 2022. arXiv:[2112.08633](https://arxiv.org/abs/2112.08633)
  — A **learned dense retriever** for prompt examples beats heuristic selection.
- **Salemi, Mysore, Bendersky, Zamani (2023)** — *LaMP: When LLMs Meet Personalization.*
  arXiv:[2304.11406](https://arxiv.org/abs/2304.11406)
  — **Retrieval-augmenting from a user's own profile** improves personalized generation across 7
  tasks.

Fidelity scales with conditioning on **real** domain data — retrieval puts the *right* evidence
in front of the model for *this* query.

---

## Part 3 — Why precision ≠ volume (the honest caveats)

- **Cuconasu, Trappolini, et al. (2024)** — *The Power of Noise: Redefining Retrieval for RAG.*
  SIGIR 2024. arXiv:[2401.14887](https://arxiv.org/abs/2401.14887)
- **Coverage & diversity:** arXiv:2305.14907; arXiv:2505.19426 — naively top-similar examples are
  **redundant and low-coverage**; balance similarity and diversity.
- **Corpus quality / noise:** arXiv:2507.08862 — a few poisoned docs can corrupt outputs. **Curate**
  before embed.
- **Context limits:** arXiv:2307.03172 + arXiv:2510.05381 — more retrieved chunks ≠ better;
  retrieve a **bounded, well-ordered** set.

---

## Part 4 — What "more precise" actually requires (the recipe)

Precision = **good data × good retrieval**, with corpus growth as the multiplier:

1. **Relevant** — semantic match + rerank (KATE/EPR)
2. **Diverse & representative** — coverage-aware selection (coverage papers)
3. **Fresh** — ingest new docs; decay stale ones (FreshLLMs)
4. **Clean** — ingestion gate against noise/poisoning
5. **Bounded & ordered** — small well-positioned set beats a flood
6. **Grow the pool** — a *larger, clean* datastore monotonically helps recall (MassiveDS)

---

## Cairn relevance (minimal)

For Cairn adopters building a **semantic signal backend**, these papers justify:

- **Corpus ingestion gates** before embed (OP-10 / Part 20.2)
- **Incremental re-index** when the pool grows (OP-26)
- **Not** a separate product feature — Cairn routes over the store; corpus quality is the
  adopter's responsibility

---

## Verdict mapping

| Sub-claim | Verdict | Key papers |
|---|---|---|
| Exemplars → retrieve → prompt → better output | ✓ supported | KATE; EPR; LaMP |
| Feeding **more** data helps | ✓ supported (if clean/relevant) | MassiveDS |
| Constantly updating keeps it current | ✓ supported | FreshLLMs |
| Raw volume alone → more precise | ⚠️ no — quality + retrieval gate it | Power of Noise; coverage; lost-in-middle |
| Redundant near-duplicates help | ✗ low value | Coverage/Diversity papers |
| Any documents are fine to ingest | ✗ curate — noise/poisoning degrade | arXiv:2507.08862 |

---

## Changelog

- **v0.2 — 2026-06-27** — Marked optional/adjacent; removed persona/VoC-specific framing; generic
  exemplar-corpus language; Cairn relevance section only.
- **v0.1 — 2026-06-17** — Initial research synthesis (MassiveDS, FreshLLMs, KATE, EPR, LaMP,
  Power of Noise, coverage/diversity, poisoning).
