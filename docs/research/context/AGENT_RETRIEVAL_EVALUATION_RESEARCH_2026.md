# Agent Retrieval Evaluation & Benchmark — Research (2026)

**For:** Cairn (agent-native retrieval engine) — the **eval/benchmark harness** behind the charter's `success_metric`.
**Gap closed:** no prior doc defined how to evaluate an agent-retrieval engine or what corpus to test against.
**Charter claim under test:** Cairn's assembled context yields answer quality ≥ baselines (agentic grep, vector-RAG) at lower token + latency cost.
**Invariants honored:** evaluation core is deterministic + LLM-free (classic IR metrics from gold labels); LLM judges stay offline.
**Date:** 2026-06-26 · **Confidence:** ✓ verified · ~ inferred

---

## 1. Metrics tier (LLM-free core first)

Given gold relevance labels (qrels), the retrieval harness is **100% deterministic, no LLM**. Use `pytrec_eval` rather than reimplementing (DCG-variant + binarization conventions are the usual silent-disagreement bugs). ✓ [pytrec_eval](https://arxiv.org/pdf/1805.01597).

| Metric | Formula (terse) | Measures | Labels | LLM? |
|---|---|---|---|---|
| **Recall@k** | (#rel in top-k)/(total rel) | coverage | binary | No ✓ |
| **Precision@k** | (#rel in top-k)/k | purity | binary | No ✓ |
| **MRR** | mean(1/rank of first rel) | first-hit height (≈1 right answer) | binary | No ✓ |
| **MAP** | mean AP; AP=Σ(P@k·rel_k)/#rel | full-list ordering | binary | No ✓ |
| **nDCG@k** | DCG/IDCG, DCG=Σ(2^rel−1)/log₂(i+1) | position-weighted graded quality | **graded** | No ✓ |

- **Primary metric:** `nDCG@10` (BEIR's primary) — the only one natively using graded relevance + full ordering, exactly what an entity-join retriever needs.
- **Pair with `Recall@k`** for multi-hop ("did top-k contain *all* hops' support").
- **Cairn-specific (~ inferred, from MuSiQue/HotpotQA design): join-set Recall@k** — for each multi-hop query store the full gold join path (set of docs); score = did top-k contain **ALL** required supporting docs. This captures the interconnected-retrieval property Cairn targets, which no classic single metric covers.

---

## 2. Held-out corpus structure (queries + gold labels)

- **Scale:** target **50 queries** (TREC norm ~50 topics), defensible floor **30**. Below ~25 = directional only. Report paired significance (paired-t or bootstrap) + effect size — never raw point deltas at this N. ✓ (TREC) / ~ (30 floor).
- **Stratify** across query types so each stratum is readable: single-entity lookup / multi-hop-join / temporal / unanswerable(abstention). Coverage taxonomy borrowed from **FRAMES** (numerical, multi-constraint, temporal, post-processing). ✓
- **Relevance scale:** graded **0–3** (TREC: not / marginal / relevant / perfect) to feed nDCG. Write a 1-page rubric + one worked example per grade — graded inter-annotator agreement ~20% vs ~48% binary without tight guidelines. ✓ [TripJudge](https://arxiv.org/pdf/2208.06936).
- **Gold-label construction (pooling, anti-bias):** build the candidate pool by unioning top-k from 2–4 retrievers (BM25 + embedding + hybrid), judge the union **blind to which system surfaced each doc**, treat unjudged-in-pool as non-relevant, record pool depth. Avoids "judged only what my own model found." ✓ (TREC pooling) / ~ (multi-retriever bootstrap for cold start).
- **Multi-hop design — copy MuSiQue, not HotpotQA:** HotpotQA is "largely solvable via shortcuts." MuSiQue chains single-hop Qs where hop N needs hop N-1's answer, verified not single-doc-answerable. For Cairn: queries that *require* joining doc-A(entity X) → doc-B(entity Y mentioning X), plus a shortcut-control check that no single doc answers it. ✓ [MuSiQue](https://aclanthology.org/2022.tacl-1.31/).
- **Leakage firewall:** eval queries + gold docs stay entirely out of any index-tuning/prompt/fine-tune set. RAGAS-style synthetic generation derives queries *from* the corpus — that's the leakage risk to firewall. ✓
- **Synthetic queries + mandatory human gate:** use LLM/RAGAS only to *draft* candidate queries (speed); a human verifies **every** gold label. An LLM-generated label = model-under-test as its own oracle (ratifies, doesn't catch). Matches IVD Rule 3 provenance gate: ai_generated alone = NEEDS_EXTERNAL_ORACLE. ✓

---

## 3. Cost/latency vs the two baselines (agentic grep, vector-RAG)

Hold everything constant except the approach under test (BEIR procedure: fix corpus, query set, hardware, generation model). ✓ [BEIR](https://arxiv.org/abs/2104.08663).

Per-query protocol:
1. **Latency** — measure retrieval and generation **separately** (retrieval feeds context size → inflates generation TTFT). Report **p50/p95/p99**, not mean — tail dominates fan-out systems. ✓ [Tail at Scale](https://www.barroso.org/publications/TheTailAtScale.pdf), [vLLM bench](https://docs.vllm.ai/en/latest/contributing/benchmarks.html).
2. **Token cost** — tokenize the **exact final assembled context** (system + chunks + separators + query), not raw docs, with the **target model's own tokenizer** (tiktoken `o200k_base`/`cl100k_base`; native HF tokenizer otherwise). ✓ [tiktoken cookbook](https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb).
3. **Warmup** — exclude warmup iters (caches/index-into-RAM/JIT); report cold-start separately. ✓
4. **N & stability** — ≥1k queries for stable p99 (≥10k for p99.9); report N next to every percentile; pin hardware, no co-located load, repeat. ~
5. **Win condition** — report quality (nDCG@k / join-set recall) **alongside** cost; token reduction is valid **only at equal quality**. Cairn's claim is provable only as **tokens-in-context per query at fixed quality**. ~
6. **Also report** index size (GB, in-memory) and QPS — BEIR omits both; add them.

---

## 4. Borrow vs build

**Borrow (the LLM-free harness + label schema, not the data):**
- ✓ **BEIR / MTEB** — borrow qrels + nDCG/Recall/MRR scoring harness to validate Cairn's retriever component in isolation, deterministically.
- ✓ **HotpotQA** — borrow the eval *structure* (sentence-level gold supports → clean recall@k, no judge).
- ✓ **MuSiQue** — borrow the `paragraph_support_idx` compositional gold-label schema + shortcut-resistant construction.
- ✓ **LongMemEval** — borrow the *ability taxonomy* (temporal reasoning, knowledge updates, abstention, multi-session) as the question types Cairn's set must cover. Only benchmark targeting personal-memory-agent failure modes — but its data is synthetic-conversational and GPT-4o-judged, so don't adopt wholesale.

**Build custom (required):** MS MARCO, NQ, FRAMES, RAGRouter family are public web/Wikipedia/general-QA. None has Cairn's load-bearing property: an **interconnected private entity graph** (notes↔email↔calendar↔contacts) with (a) entity-centric private data + real cross-entity graph, (b) gold labels for deterministic LLM-free scoring, (c) temporal/knowledge-update/abstention abilities. Closest (LongMemEval) is synthetic + judge-scored. → **A custom entity-centric held-out set is required**, built with HotpotQA/MuSiQue-style gold supports, organized by LongMemEval's taxonomy. ✓

**Name disambiguation (✓):** RouterBench ([2403.12031](https://arxiv.org/abs/2403.12031)) = LLM model-routing; RAGRouter ([2505.23052](https://arxiv.org/abs/2505.23052)) = a method, not a dataset; "RAGRouter-Bench" ([2602.00296](https://arxiv.org/abs/2602.00296)) = RAG-paradigm routing, LLM-judged, no gold relevance labels. None fit Cairn.

---

## 5. LLM-judge boundary — deterministic vs needs-a-judge

**Purely deterministic given gold labels (Cairn's hot-path-aligned core — NO LLM):**
- ✓ Recall@k, Precision@k, MRR, MAP, nDCG (classic IR — same rankings + same qrels → same score).
- ✓ RAGAS **Non-LLM / ID-based** Context Precision & Context Recall (string-similarity or doc-ID; need gold reference contexts/IDs).
- ✓ Traditional NLP (BLEU, ROUGE, CHRF, ExactMatch, StringPresence, embedding Semantic Similarity) — LLM-free but generation-side (need a gold *answer*; off Cairn's retrieve path).

**Requires an LLM judge (keep OFFLINE — never on serving path):**
- ✓ RAGAS **LLM-based** Context Precision/Recall, Faithfulness, Answer Relevancy, Context Entities Recall, Noise Sensitivity.
- ✓ **TruLens RAG Triad** (Context Relevance, Groundedness, Answer Relevance) — entirely LLM-judge.
- ✓ **ARES** — worst fit: fine-tuned LM judges + PPI + ~150 human-labeled points + in-domain few-shot.

**Bottom line:** retrieval-only eval with zero LLM is fully achievable — classic IR metrics from gold labels (✓ [Stanford IR Book ch.8](https://nlp.stanford.edu/IR-book/pdf/08eval.pdf)). Caveat (~): if gold labels were LLM-drafted, the LLM moved *offline* (Cairn's goal) but not out of the label pipeline — hence the mandatory human verification gate (§2). Use LLM-judge scoring only to audit gold labels offline, never on the serving path.

---

## 6. Tech-spec constraints this produces (for Cairn eval module intent)

1. Retrieval eval is deterministic: `(rankings, qrels) → scores` via `pytrec_eval`, no LLM.
2. Held-out set: ≥30 (target 50) queries, stratified, graded 0–3 labels, pooled + blind-judged, human-verified.
3. Primary = nDCG@10; secondary = join-set Recall@k for multi-hop.
4. Cost/latency: p50/p95/p99, model's own tokenizer on the final assembled context, warmup excluded, quality reported alongside.
5. LLM judges (if any) run offline for label audit only — never on Cairn's retrieve path.

---

## 7. Sources

Metrics: [pytrec_eval 1805.01597](https://arxiv.org/pdf/1805.01597) ✓ · [Stanford IR Book ch.8](https://nlp.stanford.edu/IR-book/pdf/08eval.pdf) ✓ · [DCG / Wikipedia](https://en.wikipedia.org/wiki/Discounted_cumulative_gain) ✓ · [RAGAS metrics](https://docs.ragas.io/en/stable/concepts/metrics/) ✓
Benchmarks: [BEIR 2104.08663](https://arxiv.org/abs/2104.08663) ✓ · [MTEB 2210.07316](https://arxiv.org/abs/2210.07316) ✓ · [MS MARCO 1611.09268](https://arxiv.org/abs/1611.09268) ✓ · [HotpotQA 1809.09600](https://arxiv.org/abs/1809.09600) ✓ · [MuSiQue 2108.00573](https://arxiv.org/abs/2108.00573) ✓ · [FRAMES 2409.12941](https://arxiv.org/abs/2409.12941) ✓ · [LongMemEval 2410.10813](https://arxiv.org/abs/2410.10813) ✓ · [RouterBench 2403.12031](https://arxiv.org/abs/2403.12031) ✓
Eval-set construction: [TripJudge 2208.06936](https://arxiv.org/pdf/2208.06936) ✓ · [Cheap IR Eval 2011.00479](https://arxiv.org/pdf/2011.00479) ✓
Frameworks: [TruLens RAG Triad](https://www.trulens.org/getting_started/core_concepts/rag_triad/) ✓ · [ARES 2311.09476](https://arxiv.org/abs/2311.09476) ✓
Cost/latency: [Tail at Scale CACM 2013](https://www.barroso.org/publications/TheTailAtScale.pdf) ✓ · [tiktoken cookbook](https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb) ✓ · [vLLM benchmarks](https://docs.vllm.ai/en/latest/contributing/benchmarks.html) ✓
