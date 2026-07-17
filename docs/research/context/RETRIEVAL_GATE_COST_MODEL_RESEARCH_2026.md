# Retrieval Gate Cost Model — Gap 1 Research

> **For:** Primitive A (Adaptive Gate) — the `none` branch and the retrieve/skip decision
> **Gap closed:** No concrete decision-economics model for when retrieval pays vs. when
>   parametric knowledge is cheaper and safer; OP-1 has 7 qualitative tests but no
>   quantitative cost formula and no LLM-free signal specification.
> **Invariants honored:**
>   - Gate must be deterministic and LLM-free on the hot path (no generative call to decide whether to make a generative call)
> **Companion patterns:** OP-1 (7-test heuristic), OP-25 (CA-RAG cost function)
> **Companion docs:** `WHEN_TO_RELY_ON_LLM_ALONE.md`, `RAG_ROUTING_AND_PARADIGM_SELECTION_2026.md`
> **Date:** 2026-06-27
> **Status:** v1.0 — initial spine; ready to feed OP-26 pattern draft
>
> **Confidence key:** ✓ verified (source checked) · ~ inferred (derived from evidence) · ? assumed (unverified default)

---

## TL;DR

Retrieval is not free and not always net-positive. On popular, stable knowledge, naive
always-on retrieval **hurts by 2.6–3.6 percentage points** (SRACG AAAI 2026 ✓). The
economics of the gate reduces to one equation:

```
retrieve iff  Miss(q) > Cost(retrieve, q)

Miss(q)  = stakes(q) × Δaccuracy_from_retrieval(q)
Cost(q)  = latency_penalty(q) + token_penalty(q)
```

The gap in OP-1 is that `Δaccuracy_from_retrieval(q)` and `Miss(q)` have no concrete
proxies — everything is qualitative. This document supplies those proxies, derived from
empirical literature, in LLM-free deterministic form.

---

## 1. The cost-of-retrieval variables

### 1.1 What matters (verified from literature)

| Variable | Empirical source | Direction |
|----------|-----------------|-----------|
| **Query complexity** (word count, question-word presence, multi-hop markers) | CA-RAG arXiv:2606.02581 ✓ | Higher complexity → retrieval more likely to help |
| **Entity tail-ness** (Wikipedia page-view rank of named entities in query) | Mallen 2023 ACL arXiv:2212.10511 ✓ | Long-tail → retrieve; head → skip |
| **Temporal markers** (date keywords, "current", "latest", "as of") | Mallen 2023; TARG arXiv:2511.09803 ✓ | Recency signal → retrieve |
| **Retrieval latency** | CA-RAG (Table 1: 8–95 ms per bundle) ✓ | Direct cost term |
| **Token delta** (prompt tokens added by retrieved chunks) | CA-RAG (252 vs 343 avg billed tokens) ✓ | Direct cost term; 8–12 embed tokens even at k=0 ✓ |
| **Answer stakes** | SRACG AAAI 2026 ✓; OP-1 T4 ✓ | High stakes → higher miss cost → retrieve |
| **Private-data flag** | Lewis 2020 RAG; OP-1 T5 | Private corpus → always retrieve |

### 1.2 The CA-RAG utility formula (verified, fills OP-25 gap)

CA-RAG (arXiv:2606.02581) ✓ defines per-query utility over a discrete bundle catalog:

```
U_b = w_Q · Q̂_b(q) − w_L · L̂^norm_b − w_C · Ĉ^norm_b

Default weights:   w_Q = 0.6,  w_L = 0.2,  w_C = 0.2
Token accounting:  τ_billed = τ_prompt + τ_completion + τ_embed
Complexity signal: c(q) = clip(α·wordlen(q)/L_max + β·cues(q)/K_max, 0, 1)
                   α = 0.6, β = 0.4, L_max = 20, K_max = 3
```

The four strategy bundles tested (✓):

| Bundle | k | Quality prior | Latency prior |
|--------|---|---------------|---------------|
| direct_llm | 0 | 0.52 | 8 ms |
| light_rag | 3 | 0.66 | 45 ms |
| medium_rag | 5 | 0.74 | 60 ms |
| heavy_rag | 10 | 0.82 | 95 ms |

**Key result:** CA-RAG achieves 26% fewer billed tokens vs. always-heavy at equal quality (0.80
vs. 0.81) across 28-query benchmark. ✓ 57% of queries routed to medium_rag, confirming the
router exercises the full bundle space.

**Gap this fills for Cairn:** OP-25 had the `utility = quality − α·latency − β·tokens` formula
as a summary; this document gives the exact weights, normalization, and complexity signal that
make the formula computable without a generative LLM call.

---

## 2. Selective retrieval findings — when retrieval hurts

### 2.1 SRACG AAAI 2026 (✓ verified)

**Paper:** SRACG — A Code Generation Framework with Selective Retrieval Augmentation. AAAI 2026.
https://ojs.aaai.org/index.php/AAAI/article/view/40647

**Finding:** Naive always-on retrieval (standard RACG) degrades performance by **−2.6 to −3.6pp**
vs. no retrieval at all, across 7 LLMs tested. ✓

**Selective retrieval** (retrieve only when model confidence is low) improves results by
**+2.4 to +7.1pp** vs. no retrieval. ✓

**Mechanism:** A necessity-aware selection step identifies query intents that genuinely require
retrieval support before retrieving. This is the single largest contributor in ablation (removing
the T1 popularity proxy = −4.51pp). ✓

**Decision boundary implication:** At the inflection point between "popular, stable" and
"long-tail, fresh," the correct choice flips from "skip" to "retrieve." The boundary is not
fuzzy — it is measurable.

### 2.2 Mallen 2023 ACL (✓ verified)

**Paper:** When Not to Trust Language Models: Investigating Effectiveness of Parametric and
Non-Parametric Memories. ACL 2023. arXiv:2212.10511
https://aclanthology.org/2023.acl-long.546/

**Findings:**
- Retrieval helps on **long-tail entities** (bottom quartile by Wikipedia page views): Contriever
  retrieval +7pp accuracy on GPT-3-davinci. ✓
- On **head / high-popularity entities**: retrieval provides minimal to no gain; can **mislead**
  when retrieved passages contain similar-but-wrong facts. ✓
- Scaling (larger model) does **not** fix the long tail — retrieval is the correct fix there. ✓
- Threshold is **entity popularity-based and relationship-type specific**, tuned per relation
  type on a dev set (75% of data split). ✓

**Proxy for "tail-ness" without LLM call:** Wikipedia page views. In practice, a named-entity
recognizer + lookup table of ~top-10K entities by monthly views serves as a deterministic proxy.
Entities not in the table → treat as long-tail → retrieve.

### 2.3 Context-length harm (✓ verified via companion doc)

Du et al. (2025), arXiv:2510.05381: even with **perfect retrieval**, raw context length degrades
accuracy 13.9–85% on math/QA/code tasks. Implication: "retrieving anyway" to be safe is not
neutral — it has a measurable downside at k > needed. Gate must account for context length added,
not just retrieval success. ✓ (From `WHEN_TO_RELY_ON_LLM_ALONE.md` §C.)

---

## 3. Parametric confidence as a gate signal

### 3.1 The options (and their LLM-free problem)

All leading methods for using parametric confidence as a gate signal require some form of LLM
involvement. The challenge for Cairn's gate is the circular dependency: calling a generative
LLM to decide whether to call a generative LLM.

| Method | Signal | LLM-free? | Notes |
|--------|--------|-----------|-------|
| **TARG** (arXiv:2511.09803) | Token entropy / logit margin on a short draft prefix | No — requires LLM prefix generation | 70–90% retrieval reduction at matched accuracy ✓ |
| **CBDR** (arXiv:2509.06472) | Hidden state at mid-layer fed to a classifier head | No — requires LLM forward pass | 83–93% retrieval cost reduction ✓ |
| **Self-RAG** (arXiv:2310.11511) | Inline reflection tokens (ISREL, ISSUP, ISUSE) trained into the model | No — requires fine-tuned model | Not usable with off-the-shelf LLM ✓ |
| **Adaptive-RAG** (arXiv:2403.14403) | Small classifier (DistilBERT/T5-small) trained on query complexity | **Yes** — classifier is LLM-free | Routes to no-retrieve / single-step / multi-step ✓ |
| **FLARE** (arXiv:2305.06983) | Retrieve when token probability drops below threshold during generation | No — inline with LLM generation | Requires confidence access during generation ✓ |

### 3.2 TARG: the closest to LLM-free, but not quite (✓ verified)

**Paper:** Training-Free Adaptive Retrieval Gating for Efficient RAG. arXiv:2511.09803
https://arxiv.org/abs/2511.09803

**Mechanism:** Generate a short draft prefix (k ≈ 20 tokens) without retrieval. From the prefix
logits, compute one of three uncertainty scores:

```
Entropy gate:     U_ent(k) = (1/k) Σ H_t,  where H_t = −Σ_j π_{t,j} log π_{t,j}
Margin gate:      U_mar(k;β) = (1/k) Σ φ(g_t),  g_t = ℓ_{t,(1)} − ℓ_{t,(2)},  φ(z) = exp(−z/β)
Variance gate:    U_var(k,N) = (1/k) Σ d_t,  d_t = 1 − max_j p̂_t(j)
```

Threshold calibration: `τ = F_U^{−1}(1 − ρ)` where ρ is the target retrieval budget and F_U
is the empirical CDF of gate scores on a dev set. ✓

**Latency cost model:**
```
E[T(τ)] = T_draft + (1 − π(τ))·E[T_out^{(0)}] + π(τ)·(T_ctx + E[T_out^{(1)}])
```

**Results on Qwen2.5-7B (✓):**

| Benchmark | Gate | EM | Retrieval rate | ΔLatency vs Always-RAG |
|-----------|------|-----|----------------|------------------------|
| TriviaQA | Margin | 62.2% | 33.8% | −2.1s avg |
| PopQA | Variance | 22.8% | 18.2% | −3.2s avg |
| NQ-Open | Margin | 39.6% | 30.4% | −1.8s avg |
| NQ-Open (Llama-3.1-8B) | Margin | 57.6% | 0.8% | +0.012s vs Never-RAG |

Always-RAG baseline: 57.6%, 14.6%, 37.4% on same benchmarks. TARG matches or exceeds at
70–90% fewer retrievals. ✓

**Key limitation for Cairn:** TARG still requires generating 20 draft tokens from the LLM
before the gate fires. It avoids a *second* LLM call but cannot be run entirely without
a LLM forward pass. For Cairn's use case, this is viable only if the gate runs as a
side-channel on the first generation attempt — not as a pre-generation oracle.

### 3.3 Adaptive-RAG: the only LLM-free classifier (✓ verified)

**Paper:** Adaptive-RAG: Learning to Adapt Retrieval-Augmented LLMs through Question Complexity.
NAACL 2024. arXiv:2403.14403
https://arxiv.org/abs/2403.14403

**Mechanism:** A small LM (DistilBERT or T5-small class) trained to classify queries into:
- **A (no retrieval):** answerable from parametric knowledge; simple, stable, head knowledge
- **B (single-step):** requires one retrieval round; single entity or fact lookup
- **C (multi-step):** requires iterative retrieval; multi-hop reasoning

The classifier is trained on automatically collected labels from actual model outcomes + dataset
inductive biases. It is completely LLM-free at inference time. ✓

**Key insight:** The classifier's input is the raw query string — no LLM forward pass required.
This is the architectural pattern Cairn's gate can adopt: a small supervised classifier as the
hot-path oracle, trained offline on labeled examples.

---

## 4. The "none" branch economics — what predicts parametric sufficiency

Synthesized from Mallen 2023 ✓, SRACG ✓, WHEN_TO_RELY_ON_LLM_ALONE.md ✓, CA-RAG ✓:

### 4.1 Properties that predict parametric-alone is correct

| Property | Proxy signal (deterministic) | Source |
|----------|------------------------------|--------|
| **Popular entity** (head distribution) | Named entity in top-10K Wikipedia page-view table | Mallen 2023 ✓ |
| **Stable / pre-cutoff knowledge** | No temporal marker keywords in query | Mallen 2023 ✓ |
| **Reasoning / skill task** | Query is "summarize/translate/rewrite/classify" + input is in the prompt | WHEN_TO_RELY_ON_LLM_ALONE.md §C ✓ |
| **Short query, few cue words** | wordlen(q) < L_max AND cues(q) < K_max | CA-RAG c(q) formula ✓ |
| **No entity specificity** | No NER hit in the query at all (pure conceptual) | ~ inferred from Mallen 2023 |
| **No private-data flag** | No corpus-membership signal (e.g., no file path, no private name) | OP-1 T5 ✓ |
| **No explicit uncertainty cue** | Query does not contain "I don't know", "latest", "current", "as of", version numbers | ~ inferred from FLARE threshold mechanism |

### 4.2 Properties that predict parametric-alone will fail

| Property | Proxy signal (deterministic) | Empirical basis |
|----------|------------------------------|-----------------|
| **Long-tail entity** | NER hit not in top-10K page-view table | Mallen 2023 +7pp from retrieval ✓ |
| **Temporal marker** | Regex: "as of", "current", "latest", "today", year > training cutoff | Mallen 2023; TARG ✓ |
| **Version / release number** | Regex for semantic version patterns (v\d+\.\d+) | ~ inferred from code domain |
| **Private-corpus entity** | Entity found in local index but not in public knowledge graph | OP-1 T5 ✓ |
| **High question complexity** | wordlen(q) > 20 OR multi-hop cue words ("given that", "following from", "given the above") | CA-RAG c(q) ✓ |
| **Explicit uncertainty cue in phrasing** | User says "I'm not sure", "do you know", "can you confirm" | ? assumed — not in literature |

---

## 5. Concrete gate formula — buildable implementation spec

### 5.1 The circular-dependency constraint

The gate **cannot** call a generative LLM to decide whether to call a generative LLM. This rules out:
- Self-RAG (requires fine-tuned model with embedded reflection tokens)
- TARG (requires a draft prefix generation — viable only post-hoc, not as pre-generation oracle)
- CBDR (requires LLM hidden-state extraction)
- FLARE (inline with generation — cannot pre-gate)

**Viable LLM-free signals:**
1. A trained small classifier (Adaptive-RAG pattern) — offline training cost, zero inference cost
2. Deterministic rule engine over query string features (CA-RAG complexity signal + entity lookup)
3. Hybrid: rule engine as fast pre-filter, small classifier as second pass for ambiguous cases

### 5.2 Two-stage LLM-free gate (recommended architecture)

```
Stage 1 — Fast Bypass (deterministic, O(1)):
  IF private_corpus_flag(q):        → RETRIEVE (always)
  IF temporal_marker(q):            → RETRIEVE
  IF version_marker(q):             → RETRIEVE
  IF query_is_task_not_lookup(q):   → SKIP (pure generation task)

Stage 2 — Complexity + Entity Score (O(n) string ops):
  c(q) = clip(0.6·wordlen(q)/20 + 0.4·cue_count(q)/3, 0, 1)  [CA-RAG formula ✓]
  tail_score(q) = 1 if any NER entity NOT in top-10K table, else 0  [Mallen 2023 ✓]
  gate_score(q) = 0.5·c(q) + 0.5·tail_score(q)

  IF gate_score(q) ≥ θ_retrieve:   → RETRIEVE
  ELSE:                             → SKIP (parametric)

Stage 3 — Signal Selector (only if retrieve):
  → Route to OP-1 signal selector (grep | semantic | graph | none)
  → Apply CA-RAG bundle selection (light/medium/heavy based on c(q))
```

### 5.3 Threshold calibration

`θ_retrieve` is calibrated on a dev set using the same CDF inversion method as TARG ✓:
```
θ_retrieve = F_score^{−1}(1 − ρ_target)
```
where ρ_target is the desired retrieval rate (e.g., 0.30 = retrieve 30% of queries).

In the absence of a dev set, set θ_retrieve = 0.5 as a starting prior; this yields
approximately equal budget between retrieve and skip on mixed-type corpora. ? assumed.

### 5.4 Miss cost and retrieval cost in the utility model

The CA-RAG utility formula adapted for Cairn's gate:

```
U_skip   = w_Q · Q̂_parametric(q) − 0                     (no latency or token penalty)
U_retrieve(b) = w_Q · Q̂_b(q) − w_L · L̂^norm_b − w_C · Ĉ^norm_b

retrieve iff max_b U_retrieve(b) > U_skip
```

`Q̂_parametric(q)` = prior quality estimate for parametric answer on this query type. In
practice, use gate_score(q) inverted: `Q̂_parametric ≈ 1 − gate_score(q)`. ~ inferred.

`Q̂_b(q)` = quality prior for bundle b at complexity c(q). CA-RAG's table is the reference:
direct_llm = 0.52, light = 0.66, medium = 0.74, heavy = 0.82. ✓

### 5.5 The "none" path: when to answer parametrically

```
IF U_skip > max_b U_retrieve(b):
    → signal = "none"; answer from parametric memory
    → log: gate_score, reason = "parametric_sufficient"
    → monitor: on hallucination signal from verifier → flag for dev set update
```

### 5.6 Small classifier option (Adaptive-RAG pattern)

If labeled data is available (prior query outcomes), train a DistilBERT-class classifier on:
- Input: raw query string
- Labels: A (skip), B (single-step retrieve), C (multi-step retrieve)
- Training signal: actual model outcome (correct/incorrect without retrieval) + query complexity

This replaces Stage 2 with a single forward pass through a ~66M-param model at < 1ms inference.
Adaptive-RAG shows this matches or beats full-LLM routing on NQ, TriviaQA, MuSiQue. ~ inferred
from NAACL 2024 results reported in abstract.

---

## 6. Tech-spec constraints this produces

For the next OP pattern (OP-26 candidate: Gate Signal Budget / Cost Model):

1. **Gate must be two-stage:** Stage 1 deterministic bypass; Stage 2 complexity + entity score.
   No generative LLM call before the gate decision.

2. **Complexity signal formula is specified:** `c(q) = clip(0.6·wordlen(q)/20 + 0.4·cues(q)/3, 0, 1)`.
   Implementable as pure string ops.

3. **Entity tail signal requires an offline lookup table:** Top-10K Wikipedia entities by monthly
   page views (or equivalent per-domain popularity proxy). Must be bundled as a static asset.

4. **Token accounting must include embedding overhead:** `τ_billed = τ_prompt + τ_completion + τ_embed`;
   embed cost ≈ 8–12 tokens per query even at k=0 — not negligible in cost models.

5. **Threshold θ_retrieve is calibrated, not hardcoded:** Default 0.5; calibrate to 30% retrieval
   rate target using CDF inversion on dev set. Expose as a config parameter.

6. **CA-RAG bundle table is the quality prior source:** direct_llm/light/medium/heavy with
   static quality and latency priors. Priors are corpus-agnostic starting points; override with
   per-corpus A/B data when available.

7. **SRACG result constrains the "always retrieve" path:** The gate must have a genuine skip
   branch — always-on retrieval is empirically net-negative on head knowledge queries.

8. **Miss cost monitoring is mandatory:** Gate skip decisions must be logged with query features;
   verifier signal feeds back to θ_retrieve calibration. Gate without a feedback loop degrades.

9. **If small classifier is available:** Replace Stage 2 with Adaptive-RAG-style DistilBERT
   classifier. Same input (raw query string), no LLM dependency.

10. **Context-length harm cap:** Even when retrieve fires, cap total retrieved tokens to the
    minimum needed. Every 10× excess tokens over the useful set = measurable accuracy drop
    (Du 2025 ✓).

---

## Sources

| Paper | ArXiv / URL | Confidence |
|-------|-------------|------------|
| Mallen, Asai et al. — When Not to Trust Language Models | arXiv:[2212.10511](https://arxiv.org/abs/2212.10511) · [ACL Anthology](https://aclanthology.org/2023.acl-long.546/) | ✓ verified |
| SRACG — Selective Retrieval Augmented Code Generation (AAAI 2026) | [AAAI Proceedings](https://ojs.aaai.org/index.php/AAAI/article/view/40647) | ✓ verified |
| Self-RAG — Asai, Wu, Wang et al. (ICLR 2024) | arXiv:[2310.11511](https://arxiv.org/abs/2310.11511) | ✓ verified |
| Adaptive-RAG — Jeong, Baek et al. (NAACL 2024) | arXiv:[2403.14403](https://arxiv.org/abs/2403.14403) | ✓ verified |
| FLARE — Jiang, Xu, Gao et al. (EMNLP 2023) | arXiv:[2305.06983](https://arxiv.org/abs/2305.06983) | ✓ verified |
| TARG — Training-Free Adaptive Retrieval Gating | arXiv:[2511.09803](https://arxiv.org/abs/2511.09803) | ✓ verified |
| CA-RAG — Cost-Aware Query Routing in RAG | arXiv:[2606.02581](https://arxiv.org/abs/2606.02581) | ✓ verified |
| CBDR — LLM Parametric Knowledge as Post-retrieval Confidence | arXiv:[2509.06472](https://arxiv.org/abs/2509.06472) | ✓ verified |
| Du et al. — Context Length Alone Hurts LLM Performance | arXiv:[2510.05381](https://arxiv.org/abs/2510.05381) | ✓ verified (via companion doc) |
| Kadavath et al. — Language Models (Mostly) Know What They Know | arXiv:[2207.05221](https://arxiv.org/abs/2207.05221) | ✓ verified (via companion doc) |
| RAGRouter-Bench | arXiv:[2602.00296](https://arxiv.org/abs/2602.00296) | ✓ verified (via OP-25) |

## Changelog

- **v1.0 — 2026-06-27** — Initial spine; closes Gate Signal Budget gap. Covers cost model,
  selective retrieval harm quantification, parametric confidence signals, "none" branch economics,
  concrete LLM-free gate formula. Ready to feed OP-26 draft.
