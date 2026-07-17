# Context Assembly & Packing — Research (2026)

**For:** Cairn (agent-native retrieval engine) — primitive **C (Signal Orchestration)**, final stage: the **context assembler**.
**Gap closed:** existing corpus covered gate / resolver / routing / fusion but had no *buildable* spec for assembling the minimal context package after signals return candidates.
**Invariants honored:** zero LLM on retrieve hot path · deterministic · storage-agnostic · local-first.
**Date:** 2026-06-26 · **Confidence:** ✓ verified (from source) · ~ inferred

---

## 0. What was already covered (no duplication)

[CONTEXT_BUILDING_AND_MAINTENANCE_RESEARCH_2026.md](CONTEXT_BUILDING_AND_MAINTENANCE_RESEARCH_2026.md) has **conceptual** coverage but **no buildable algorithm/formulas** (✓ verified by read):
- Pipeline shape (Part 5.2): `dense top-k + BM25 top-k → RRF → dedupe → cross-encoder rerank → top-k_r (1–3) → necessity check → inject START/END`.
- Token-budget allocation as % of window (Part 13.1): retrieved evidence 25–30%, hard cap, k=1–3.
- Lost-in-the-middle cited (Liu); dedup mentioned but **no method/threshold/MMR**; flags typical context assemblers lacks a token-budget enforcer + trace manifest.

This doc supplies the missing **formulas, thresholds, and the deterministic algorithm**.

---

## 1. Buildable spec — deterministic, LLM-free assembler

Pipeline: **budget → select (MMR) → dedup → order → emit**. Every step is a pure function of candidate text + scores + precomputed embeddings + token counts. Zero LLM, zero network.

**Inputs:** candidates `D = {d_i}`, each with `text`, `rel_i` (retrieval/rerank score, normalized 0–1), `e_i` (embedding computed at index time — **reuse, never re-embed on hot path**), `tok_i` (token count from a local tokenizer, e.g. `tiktoken`).

### Step A — Budget
`B = window − reserved(system + tools + history + response_headroom)`. Cairn emits only the retrieved-evidence slice; cap via config knob `evidence_budget_tokens` (default 25–30% of window, per CONTEXT_BUILDING).

### Step B — Select via MMR (relevance + diversity; the core formula)
Maximal Marginal Relevance (Carbonell & Goldstein 1998, SIGIR) — canonical, fully deterministic:

```
MMR = argmax_{d_i ∈ D\S} [ λ · Sim1(d_i, q) − (1−λ) · max_{d_j ∈ S} Sim2(d_i, d_j) ]
```
- `Sim1 = rel_i` (reuse retrieval/rerank score); `Sim2 = cos(e_i, e_j)`.
- **λ presets:** 0.5 default · 0.7 fact-lookup (relevance-heavy) · 0.3 exploratory/multi-aspect (diversity-heavy). λ=1 → pure relevance; λ=0 → pure diversity. (✓ formula · ~ λ presets, tune per corpus.)
- **Greedy packing:** iteratively pick highest-MMR candidate whose `tok_i` still fits remaining budget; add to `S`; repeat until budget exhausted or nothing fits. Greedy is deterministic; a true knapsack is unnecessary and non-deterministic on ties. **Tie-break: `rel_i` desc, then candidate id** (guarantees byte-stable output → satisfies determinism invariant).

### Step C — Dedup (near-duplicate removal)
MMR's `(1−λ)·max sim` term already suppresses near-dups; add a hard gate: **drop any candidate with `cos(e_i, e_j) ≥ 0.95` vs an already-selected chunk** (keep higher `rel`). For lexical exact-dup, a MinHash/Jaccard ≥ 0.9 shingle check is also LLM-free. (~ threshold 0.95 = common near-dup cutoff; tune.)

### Step D — Order (defeat lost-in-the-middle)
Liu et al. 2023: U-shaped accuracy curve — **20–30 point drop** when the relevant doc sits in the middle vs the edges (✓ verified). Buildable **edge-load / fold ordering**: sort selected set by `rel` desc, then place rank-1 FIRST, rank-2 LAST, rank-3 second, rank-4 second-to-last, … — strongest items at the two edges, weakest buried in the middle. (LongLLMLingua independently reorders by importance for the same reason.) (✓ Liu · ~ the specific fold rule is the standard operationalization.)

### Step E — Emit
Concatenate selected chunks with **per-chunk provenance tags** (path/id/score) + a **trace manifest** (`source, path, tokens, rel, mmr, position`). Deterministic given inputs. The manifest is the auditability artifact CONTEXT_BUILDING flagged as missing.

---

## 2. The "smallest sufficient package" justification (size the budget down)

Du et al. 2025 (EMNLP Findings): even with **100% perfect retrieval and irrelevant tokens masked**, accuracy degrades **13.9%–85% as input length grows — from length alone** (✓ verified, arXiv:2510.05381). Implication: prefer **fewer chunks (k=1–3)**; length itself is a cost, not just noise. This is Cairn's strongest published basis for the minimal-context invariant — lead the assembler spec with it.

---

## 3. LLM-free (hot-path OK) vs LLM-dependent (off-path / build-time)

| Technique | Generative LLM on hot path? | Cairn placement |
|---|---|---|
| MMR selection | ✗ (cosine on precomputed embeddings) | ✓ hot path |
| Cosine / MinHash dedup | ✗ | ✓ hot path |
| Edge-load ordering | ✗ (sort on existing scores) | ✓ hot path |
| Greedy budget packing | ✗ (local tokenizer counts) | ✓ hot path |
| BM25 / lexical rerank | ✗ deterministic, local | ✓ hot path |
| Cross-encoder reranker (bge-reranker, MiniLM) | ✗ **not generative** — local discriminative transformer, deterministic given fixed weights | ✓ hot path *if Cairn permits a neural reranker*; else fall back to BM25+RRF |
| **LLMLingua / LongLLMLingua** | ⚠️ uses small **causal LM** (GPT-2/LLaMA-7B) for perplexity scoring | ✗ off hot path — build-time/async only. 2x–6x compression; +21.4% NaturalQuestions; 94% cost cut LooGLE |
| **LLMLingua-2** | ⚠️ small **encoder classifier** (xlm-roberta-large 355M / mBERT) — NOT generative | borderline (cross-encoder class); hot-path-admissible only if neural rerankers allowed; else build-time. 2x–5x, 3x–6x faster than v1 |
| Generative summarization / compaction | ⚠️ full LLM call | ✗ never on hot path — build-time index compaction only |

**Decision rule for Cairn:** the entire `budget→select→dedup→order→emit` core is LLM-free and deterministic. The only *truly free* "compression" is **selection/dedup/truncation** (dropping chunks), not **token-level compression** (LLMLingua family needs a model).
- If the invariant is strictly **"no generative LLM / no API"** → a cross-encoder reranker and LLMLingua-2's encoder are admissible (local, deterministic).
- If the invariant is **"no neural net at all on hot path"** → restrict to **BM25 + RRF + MMR + cosine-dedup**.
This is an explicit charter knob to resolve in the tech spec: **"zero-LLM" vs "zero-ML" on the hot path.**

---

## 4. Tech-spec constraints this produces (for Cairn module intent)

1. `assembler` is a pure function: same `(candidates, query, budget, λ)` → byte-identical package (determinism invariant).
2. No embedding/LLM call inside the assembler; embeddings are read from candidates (hot-path purity invariant).
3. MMR(λ) + cosine-dedup(≥0.95) + edge-load ordering + greedy budget packing with deterministic tie-break.
4. Emit a trace manifest per package (auditability).
5. LLMLingua-family compression is build-time/optional, never on the retrieve path.

---

## 5. Sources

- ✓ Liu et al. 2023, *Lost in the Middle* — [arXiv:2307.03172](https://arxiv.org/abs/2307.03172) (U-curve; 20–30pt middle penalty).
- ✓ Du et al. 2025, *Context Length Alone Hurts LLM Performance Despite Perfect Retrieval* (EMNLP Findings) — [arXiv:2510.05381](https://arxiv.org/abs/2510.05381) (13.9%–85% from length alone).
- ✓ Jiang et al. 2023, *LongLLMLingua* — [arXiv:2310.06839](https://arxiv.org/abs/2310.06839).
- ✓ Pan et al. 2024, *LLMLingua-2* — [arXiv:2403.12968](https://arxiv.org/abs/2403.12968).
- ~ Carbonell & Goldstein 1998, *MMR* (SIGIR) — canonical formula + λ trade-off.
- Internal: [CONTEXT_BUILDING_AND_MAINTENANCE_RESEARCH_2026.md](CONTEXT_BUILDING_AND_MAINTENANCE_RESEARCH_2026.md) (Parts 3, 5, 6, 13, 30, 34).
