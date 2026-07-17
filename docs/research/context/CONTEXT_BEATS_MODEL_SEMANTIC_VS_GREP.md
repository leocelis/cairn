# Context Engineering vs Model Power — and Semantic Index vs Grep

> **Status:** Living document — v0.1 (2026-06-17)
> **Companion to:** `WHEN_TO_RELY_ON_LLM_ALONE.md` (retrieval gate boundary) and the other
> companion research docs in this corpus.
> **Thesis under test:** *An agent with good knowledge-collection tools + a **semantic
> index** (Cursor-style) + strong context-building tools, on a **regular** model, will
> **outperform** a **premium** model with weaker context tools and **no semantic index**
> (grep-like lexical retrieval only).*
> **Sourcing rule:** Every paper has a verified arXiv ID/venue; practitioner claims are
> attributed. Confirmed 2026-06-17, not recalled from model memory.

---

## Verdict up front (calibrated — this one splits)

The thesis bundles **two** claims. They do not get the same grade.

- **Claim (i): context/tools can make a cheaper model beat a premium model with poor
  context — ✓ strongly supported.** This is the load-bearing, economically important part,
  and the evidence is hard: retrieval lets models **25–50× smaller** match or beat the giants.
- **Claim (ii): a *semantic index* specifically beats *grep-like* lexical retrieval —
  ⚠️ contested, and in the code/agentic domain cited in the thesis, the best current evidence
  leans the *other way*.** Anthropic removed the vector index from Claude Code because
  **agentic grep outperformed it "by a lot."** Cursor uses a semantic index; Claude Code
  refuses one — two leading coding agents made *opposite* calls, which by itself refutes
  "semantic index always wins."

**Net:** the *strategic* thesis is right — **context quality beats raw model power.** The
*mechanism* claim is too specific — the lever is **retrieval/context quality + agentic tool
use**, which a semantic index *can* provide but so can well-driven grep. Do not bet an architecture
solely on "semantic index = the differentiator."

---

## Part A — Context + a cheaper model beats a bigger model alone ✓

### A1. Retrieval ≈ 25× the parameters
- **Borgeaud, Mensch, Hoffmann, et al. (DeepMind, 2021)** — *Improving Language Models by
  Retrieving from Trillions of Tokens (RETRO).* ICML 2022. arXiv:[2112.04426](https://arxiv.org/abs/2112.04426)
- **Finding:** A **7.5B** model with retrieval matches **GPT-3 (175B)** and Jurassic-1 (178B)
  on the Pile — **25× fewer parameters.**

### A2. Retrieval beats a 540B model with 50× less compute
- **Izacard, Lewis, Lomeli, et al. (Meta/Inria/UCL, 2022)** — *Atlas: Few-shot Learning with
  Retrieval Augmented Language Models.* JMLR 2023. arXiv:[2208.03299](https://arxiv.org/abs/2208.03299)
- **Finding:** An **11B** retrieval-augmented model beats **PaLM (540B)** on NaturalQuestions
  (64-shot) by ~3 points — **50× less pretraining compute.**

### A3. Retrieval *quality* moves end-to-end accuracy
- **Karpukhin, Oğuz, Min, et al. (2020)** — *Dense Passage Retrieval for Open-Domain QA.*
  EMNLP 2020. arXiv:[2004.04906](https://arxiv.org/abs/2004.04906)
- **Finding:** Dense retrieval beats Lucene-**BM25** by **9–19%** top-20 accuracy and lifts
  the whole QA system to SOTA. Better retrieval → better answers, holding the model fixed.

**A-takeaway:** The economic core of the thesis holds firmly. A regular model with strong
retrieval/context can outperform a premium model that's flying with poor context. (Note these
wins used *dense/semantic* retrieval — so semantic retrieval is clearly powerful; A-claims do
**not**, however, pit it against agentic grep.)

---

## Part B — Semantic index vs grep-like lexical: contested ⚠️

### B1. Lexical (BM25) is a stubbornly strong, better-generalizing baseline
- **Thakur, Reimers, Rücklé, et al. (2021)** — *BEIR: A Heterogeneous Benchmark for Zero-shot
  Evaluation of IR.* NeurIPS 2021 D&B. arXiv:[2104.08663](https://arxiv.org/abs/2104.08663)
- **Finding:** Across 17–18 datasets, **BM25 is a robust, highly competitive zero-shot
  baseline; dense retrievers often *underperform* out-of-domain** without domain adaptation.
  Semantic's edge is largest **in-domain / after tuning**, and **generalizes worse** than
  assumed. (Best zero-shot = re-rankers/late-interaction, but at high cost.)

### B2. In code, the evidence is mixed — and skews to lexical for the common cases
- **Wang, Asai, Yu, et al. (2024)** — *CodeRAG-Bench: Can Retrieval Augment Code Generation?*
  NAACL Findings 2025. arXiv:[2406.14497](https://arxiv.org/abs/2406.14497)
- **Finding:** Retrieval helps code generation **in some scenarios, not universally**; gains
  are source- and task-dependent.
- **Qualitative consensus (code search):** specialized *code* embeddings can beat BM25
  **in-domain**, but **BM25 is more reliable for keyword/identifier/API/config queries** —
  exactly the exact-symbol lookups that dominate real coding work, where lexical overlap is
  the signal.

### B3. The natural experiment: Cursor vs Claude Code made *opposite* choices
- **Cursor — uses a semantic index.** Syntax/AST-aware chunking → embeddings → cloud vector
  store (Turbopuffer, combining vector + full-text), Merkle-tree incremental re-indexing.
  Source: [Cursor Docs — Semantic & Agentic Search](https://cursor.com/docs/agent/tools/search);
  [Securely indexing large codebases](https://cursor.com/blog/secure-codebase-indexing).
- **Claude Code — refuses a semantic index.** It uses **agentic search** (Glob + Grep/ripgrep
  + Read) on demand. Per Anthropic, early versions *did* use a local vector DB and they
  **removed it** — a Claude engineer reported agentic search "**outperformed [it] by a lot,
  and this was surprising.**" (Reported via Boris Cherny / Anthropic on Hacker News; see
  writeups: [vadim.blog](https://vadim.blog/claude-code-no-indexing/),
  [rust-trends](https://rust-trends.com/posts/ripgrep-claude-code/).)
- **Implication:** Two state-of-the-art coding agents reached **opposite** conclusions. That
  is decisive evidence that "semantic index strictly beats grep" is **false as a general law.**
  The converged industry pattern is **layered retrieval**: grep/rg for broad, cheap coverage +
  symbol-precise tools (LSP) for confirmation — and a capable agent *driving* that search.

**B-takeaway:** Semantic index wins on **conceptual / fuzzy / natural-language-over-knowledge**
queries and in-domain corpora; lexical/agentic wins on **exact-symbol, keyword, fresh, or
out-of-domain** retrieval and avoids index staleness + setup. The decider is **how well the
agent retrieves**, not the index type per se.

---

## The reframe (what the thesis should say)

The thesis conflates **"semantic index"** with **"good context building."** The research
separates them:

- ✓ **Good context building is the real lever** (Part A). Bet on it.
- ⚠️ **Semantic index is *one means* to it, not the differentiator** (Part B). Agentic grep is
  a proven, sometimes-superior alternative — per the Cursor-vs-grep comparison above.

**Corrected, defensible form:** *An agent with strong context-building and retrieval — semantic
index **and/or** well-driven agentic search — on a regular model can outperform a premium model
with weak context tooling.* That holds. "Semantic index beats grep" does not.

---

## Caveats / honest boundary

1. **It's never "model vs index" in isolation** — the agent's *search policy* (iterative grep,
   query reformulation, reranking) often matters more than the index. A premium model can also
   be a *better agentic searcher*, partly offsetting a context disadvantage.
2. **Semantic index has real costs**: chunking (esp. code), embedding staleness, infra, and
   poor OOD generalization (BEIR). Grep has zero index lag and perfect freshness.
3. **Hybrid usually wins** retrieval benchmarks (lexical + dense + rerank) — the honest answer
   is rarely "pick one."
4. **Premium models aren't only "more knowledge"** — they also reason and *use tools* better;
   a premium model with grep may out-search a regular model with a semantic index. The clean
   "regular+index > premium+grep" ordering is **not guaranteed**; it depends on the gap sizes.

---

## Agent design implication

- ✓ **Invest in retrieval/context quality first** — it's the proven lever (Part A), and it's
  cheaper than chasing premium model upgrades.
- ⚠️ **Don't treat a Cursor-style semantic index as mandatory.** a vector index (embeddings) is
  right for **conceptual/NL queries over the knowledge base**; but for exact lookups, fresh
  data, and code, pair it with **strong agentic search tools** (grep/symbol/file tools) — the
  Claude Code lesson. Default to **hybrid + layered retrieval**, not index-only.
- `[to-develop]` Make the agent a better *agentic searcher* (query reformulation, iterative
  retrieve-read, rerank) — that may beat upgrading either the model or the index.
- `[test]` The thesis is empirically checkable on any agent system: regular-model + vector index + tools vs
  premium-model + grep-only, on a real agent task set with a metric. Worth running before
  before committing to an architecture — validate empirically on a representative task set.

---

## Verdict mapping

| Sub-claim | Verdict | Key evidence |
|---|---|---|
| Cheaper model + good context beats premium model + poor context | ✓ supported | RETRO; Atlas; DPR |
| Retrieval quality drives end-to-end accuracy | ✓ supported | DPR |
| Semantic index strictly beats grep-like lexical | ✗ not supported (contested) | BEIR; Claude Code vs Cursor; CodeRAG-Bench |
| Semantic wins on conceptual/fuzzy/in-domain queries | ✓ supported | DPR; code-embedding results |
| Lexical/agentic wins on exact-symbol/fresh/OOD | ✓ supported | BEIR; Claude Code agentic search |
| "regular+index > premium+grep" as a law | ⚠️ depends on gap sizes | (reasoned; test empirically) |

---

## Changelog
- **v0.1 — 2026-06-17** — Initial. Split verdict: context-beats-model ✓ (RETRO/Atlas/DPR);
  semantic-index-beats-grep ✗/contested (BEIR; Cursor-vs-Claude-Code natural experiment;
  CodeRAG-Bench). Reframe to "retrieval/context quality, by index *and/or* agentic search," +
  hybrid/layered-retrieval implication and an empirical test to run. Verified sources:
  [2112.04426](https://arxiv.org/abs/2112.04426),
  [2208.03299](https://arxiv.org/abs/2208.03299),
  [2004.04906](https://arxiv.org/abs/2004.04906),
  [2104.08663](https://arxiv.org/abs/2104.08663),
  [2406.14497](https://arxiv.org/abs/2406.14497); Cursor docs/blog; Claude Code agentic-search
  writeups (Anthropic via HN).
