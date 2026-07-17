# When Can We Rely on the LLM Alone?

> **Status:** Living document — v0.1 (2026-06-17)
> **Companion to:** `CONTEXT_BEATS_MODEL_SEMANTIC_VS_GREP.md` (context vs model-power boundary).
> **Question:** When is parametric memory (weights only, no retrieval / no injected
> context) *sufficient or even preferable*?
> **Sourcing rule:** Every paper has a verified arXiv ID + venue, confirmed on 2026-06-17,
> not recalled from model memory.

---

## The answer in one paragraph

Rely on the weights alone when the task draws on **head (popular) knowledge that is
stable over time**, or is a **reasoning/skill task where the input itself is the context**
(math, code, summarize/translate/rewrite the provided text), **the stakes don't demand
provenance**, **no private/post-cutoff data is involved**, and **the model's own
calibrated confidence is high**. Outside that envelope, supply the knowledge. Crucially,
retrieval is *not free*: on head knowledge it can **mislead**, and irrelevant or merely
**long** context measurably **degrades** answers — so "use the model alone" is sometimes
the actively better engineering choice, not a fallback. This is exactly why state-of-the-art
RAG is now **adaptive** (retrieve only when needed), not reflexive.

---

## The decision framework (actionable)

Rely on parametric-only when **all** of these hold; retrieve/ground when **any** fails:

| # | Test | Rely on LLM alone if… | Else → supply context | Evidence |
|---|------|------------------------|------------------------|----------|
| 1 | **Popularity** | fact is common/head-distribution | long-tail / obscure entity | Mallen 2023 |
| 2 | **Recency / stability** | knowledge is stable, pre-cutoff | time-sensitive / post-cutoff / changing | Lewis 2020; Mallen 2023 |
| 3 | **Task type** | reasoning/skill; input *is* the data (math, code, summarize, translate, rewrite, classify) | fact lookup the model must supply from memory | (see §C) |
| 4 | **Stakes / provenance** | low-stakes, no citation needed | auditable / high-stakes / must cite | RAG 2020; hallucination work |
| 5 | **Private / proprietary** | answer lives in general knowledge | depends on your/user's private data | Lewis 2020 (non-parametric) |
| 6 | **Self-knowledge** | model's calibrated P(IK)/P(True) is high | model signals uncertainty | Kadavath 2022 |
| 7 | **Retrieval risk** | good context isn't reliably available; noise/length would hurt | clean, relevant context is available | Yoran 2023; Du 2025 |

Heuristic: **head + stable + reasoning + low-stakes + confident → trust the weights.**
**tail + fresh + private + high-stakes + uncertain → ground it.**

---

## A. The popularity / long-tail boundary (the core "when")

- **Mallen, Asai, Zhong, et al. (2023)** — *When Not to Trust Language Models.* ACL 2023.
  arXiv:[2212.10511](https://arxiv.org/abs/2212.10511)
- **Finding:** Unassisted LMs are **competitive on high-popularity entities**; scaling does
  *not* fix the long tail; retrieval helps the tail but can **mislead on popular facts**.
  → Retrieve adaptively, only when needed.
- **Takeaway:** The single clearest empirical line for "weights alone are enough" =
  **popular, frequently-attested knowledge.**

---

## B. SOTA confirms it: state-of-the-art RAG is *adaptive*, not reflexive

That "rely on the model alone when you can" is the right call is endorsed by the systems
that *win* — they explicitly include a **no-retrieval** path.

- **Asai, Wu, Wang, et al. (2023)** — *Self-RAG: Learning to Retrieve, Generate, and
  Critique through Self-Reflection.* ICLR 2024. arXiv:[2310.11511](https://arxiv.org/abs/2310.11511)
  — Trains the model to **retrieve on demand or skip entirely**; notes that indiscriminate
  retrieval "diminishes versatility or leads to unhelpful generation."
- **Jeong, Baek, Cho, et al. (2024)** — *Adaptive-RAG: Learning to Adapt RA-LLMs through
  Question Complexity.* NAACL 2024. arXiv:[2403.14403](https://arxiv.org/abs/2403.14403)
  — A classifier routes queries to **no-retrieval / single-step / multi-step**. Explicitly
  treats "no retrieval" as the right strategy for simple queries.
- **Jiang, Xu, Gao, et al. (2023)** — *Active Retrieval Augmented Generation (FLARE).*
  EMNLP 2023. arXiv:[2305.06983](https://arxiv.org/abs/2305.06983)
  — Retrieve only when the model is **about to generate low-confidence tokens**; otherwise
  let it generate from parametric memory. Confidence-gated reliance.
- **Takeaway:** "When to rely on the LLM alone" is a *first-class design decision* in
  modern systems, gated by query complexity and model confidence.

---

## C. When retrieval actively HURTS (so parametric-only is *better*)

- **Yoran, Wolfson, Ram, Berant (2023)** — *Making Retrieval-Augmented Language Models
  Robust to Irrelevant Context.* arXiv:[2310.01558](https://arxiv.org/abs/2310.01558)
  — Irrelevant retrieved passages **degrade** performance; robustness requires learning to
  *ignore* bad context. If retrieval can't be kept clean, not retrieving can win.
- **Du, Tian, et al. (2025)** — *Context Length Alone Hurts LLM Performance Despite Perfect
  Retrieval.* ACL Findings (EMNLP) 2025. arXiv:[2510.05381](https://arxiv.org/abs/2510.05381)
  — Even with **perfect retrieval and no distractors**, raw input length degrades accuracy
  **13.9%–85%** (math/QA/code), within claimed context limits. Mitigation: keep context
  *short*. → Prefer the minimal context (sometimes none) the task actually needs.
- **(Context)** *Lost in the Middle* (Liu 2023, arXiv:2307.03172; see CONTEXT_BEATS_MODEL_SEMANTIC_VS_GREP.md) —
  position bias compounds the length problem.
- **Takeaway:** More context ≠ better. When clean, relevant context isn't cheaply
  available, **parametric-only is the lower-risk path.**

---

## D. The deciding mechanism: does the model know that it knows?

- **Kadavath, Conerly, Askell, et al. (Anthropic, 2022)** — *Language Models (Mostly) Know
  What They Know.* arXiv:[2207.05221](https://arxiv.org/abs/2207.05221)
- **Finding:** Larger models are **well-calibrated** on multiple-choice/true-false; can
  estimate **P(True)** of their own answers and **P(IK)** ("probability I know") with
  encouraging calibration (weaker on novel tasks).
- **Takeaway:** Calibrated self-confidence is the **runtime trigger** for the framework
  above: high P(IK) → answer from weights; low P(IK) → retrieve. This is the
  mechanism that makes adaptive reliance possible.

---

## E. Why the weights are a real (if bounded) knowledge store

Reused from WHEN_TO_RELY_ON_LLM_ALONE.md — the basis for trusting head knowledge:
- **Petroni et al. (2019)** — *Language Models as Knowledge Bases?* (LAMA). EMNLP 2019.
  arXiv:[1909.01066](https://arxiv.org/abs/1909.01066) — strong unassisted factual recall.
- **Allen-Zhu & Li (2024)** — *Physics of LMs 3.3, Knowledge Capacity.* ICLR 2025.
  arXiv:[2404.05405](https://arxiv.org/abs/2404.05405) — ~2 bits/param; real, large capacity.
- **Caveat:** *Hallucination is Inevitable* (Xu 2024, arXiv:2401.11817) — residual risk
  never hits zero, so "rely on the LLM alone" is always a *risk-tolerance* decision, never
  a guarantee.

---

## F. Agent design implication

Agents should treat retrieval as **adaptive**, mirroring §B:
- ✓ A procedural-command fast-path (skip episodic retrieval when the turn is clearly
  action-oriented — addresses, action verbs + IDs) is an instance of this. It is
  "rely on the model/handler directly when the task isn't a fact-lookup."
- `[to-develop]` Generalize it into an explicit **retrieval gate**: classify each turn by
  (popularity, recency, task-type, stakes, private-data, confidence) → choose
  none / corpus-only / corpus+personal / web. Self-RAG/Adaptive-RAG/FLARE are the templates;
  Kadavath gives the confidence signal.
- `[open]` Does the orchestrator have a usable calibrated-confidence signal, or does
  the gate have to be heuristic (query features) until one exists?

---

## Verdict mapping

| Question | Answer | Key papers |
|---|---|---|
| Can the weights ever be enough? | ✓ yes — head + stable knowledge | Mallen 2023; Petroni 2019 |
| For which tasks? | reasoning/skill, input-is-context, low-stakes | §C task types; Self-RAG |
| Is retrieval always safer? | ✗ no — it can mislead and length alone hurts | Yoran 2023; Du 2025; Mallen 2023 |
| How to decide at runtime? | calibrated confidence + query complexity | Kadavath 2022; Jeong 2024; Jiang 2023 |
| Any guarantee when relying alone? | ✗ no — residual hallucination is structural | Xu 2024 |

---

## Changelog
- **v0.1 — 2026-06-17** — Initial. 7-test decision framework; evidence grouped
  popularity-boundary / adaptive-SOTA / retrieval-harms / self-knowledge / parametric-store;
  Agent retrieval-gate implication. New verified papers:
  [2310.11511](https://arxiv.org/abs/2310.11511),
  [2403.14403](https://arxiv.org/abs/2403.14403),
  [2305.06983](https://arxiv.org/abs/2305.06983),
  [2207.05221](https://arxiv.org/abs/2207.05221),
  [2310.01558](https://arxiv.org/abs/2310.01558),
  [2510.05381](https://arxiv.org/abs/2510.05381); reuses 2212.10511, 1909.01066,
  2404.05405, 2401.11817 from WHEN_TO_RELY_ON_LLM_ALONE.md.
