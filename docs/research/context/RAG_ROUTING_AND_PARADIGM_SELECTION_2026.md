# RAG Routing & Paradigm Selection — 2026

> **Status:** Living document — v1.0 (2026-06-25)
> **For:** Cairn primitive A (Adaptive Gate) — paradigm + depth before any signal runs.
> **Companion spine:** `CONTEXT_BUILDING_AND_MAINTENANCE_RESEARCH_2026.md` (context packaging).
> **Companions:** `RAG_SEMANTIC_INDEXING_OUTPUT_QUALITY_RESEARCH_2025_2026.md`,
>   `OPENAI_EMBEDDINGS_COMPREHENSIVE_RESEARCH_2026.md`, `WHEN_TO_RELY_ON_LLM_ALONE.md`.

---

## TL;DR

**RAG routing** = pick retrieval **paradigm + depth** per query×corpus — not "always hybrid" and not "always k=10."

No universal winner (RAGRouter-Bench). Route **before** choosing GPT-5.4 vs mini. Wrong RAG makes every model look dumb.

---

## 1. The decision (three knobs)

| Knob | Options | What it controls |
|------|---------|------------------|
| **Paradigm** | LLM-only, Naive, Graph, Hybrid, Iterative | Architecture of retrieval |
| **Depth** | k=0 (skip), shallow k, deep k, iterative rounds | Token budget into context |
| **Corpus signal** | hubness, dispersion, connectivity | Which paradigm fits this index |

**CA-RAG** (arXiv:[2606.02581](https://arxiv.org/abs/2606.02581)): utility = quality − α·latency − β·tokens. **26% fewer tokens** vs always-heavy at equal quality on a 28-query benchmark.

---

## 2. RAGRouter-Bench findings (arXiv:[2602.00296](https://arxiv.org/abs/2602.00296))

7,727 queries × 21,460 documents; five paradigms × multiple LLM backbones.

| Finding | Implication |
|---------|-------------|
| No one-size-fits-all | Fixed pipeline is a blind spot |
| **HybridRAG** wins most slices | Default when corpus is mixed/relational |
| Query×corpus compatibility | Same query type needs different RAG on different corpora |
| DeepSeek-V3 >> LLaMA-8B on same RAG | **Generation model** still matters after RAG choice |
| Structural + semantic corpus features predict paradigm | Router features ≠ query length alone |

**Eval oracles:** response quality metrics + resource consumption (tokens, latency).

---

## 3. Routing rules (production)

```
IF answerable from parametric knowledge AND no private corpus:
    SKIP retrieval → LLM-only (T2 mini)
ELIF single-fact lookup in flat index:
    NaiveRAG, shallow k
ELIF relational / entity-heavy corpus (high connectivity):
    GraphRAG or HybridRAG
ELIF analytical / multi-hop:
    IterativeRAG or deep Hybrid
ELSE:
    HybridRAG shallow → escalate depth on verifier fail
```

**Milvus SOP (~2026):** routing queries that don't need retrieval is highest-ROI single change for many prod systems.

---

## 4. Interaction with downstream LLM tier

| RAG mistake | Symptom | Wrong fix | Right fix |
|-------------|---------|-----------|-----------|
| Over-retrieve | Noise, cost | Bigger LLM | Shallow k / compress (LongLLMLingua) |
| Under-retrieve | Hallucination | Bigger LLM | Deeper or Hybrid RAG |
| Wrong paradigm | Missed relations | Opus | Graph/Hybrid |
| Stale index | Wrong facts | 5.5-pro | Reindex + embedding version lock |

**Order:** RAG router → context packaging → **then** LLM tier selection.

---

## 6. Verdict

| Question | Answer |
|----------|--------|
| RAG before LLM? | **Yes** |
| Always Hybrid? | **No** — corpus-dependent |
| Router features? | Query type + corpus structure, not query length alone |
| Eval? | RAGRouter-Bench protocol or per-corpus slice eval |

---

## Sources

- RAGRouter-Bench (2026). arXiv:[2602.00296](https://arxiv.org/abs/2602.00296)
- CA-RAG (2026). arXiv:[2606.02581](https://arxiv.org/abs/2606.02581)
- Milvus RAG routing: https://milvus.io/blog/build-smarter-rag-routing-hybrid-retrieval.md

## Changelog

- **v1.0 — 2026-06-25** — Initial spine; closes corpus gap in paradigm-selection research.
