# Benchmarks

Reproducible, honestly-scored evidence for Cairn's claims. Each benchmark ships
its dataset and harness, states its method and caveats, and reports errors as
well as accuracy. Datasets are synthetic and public — no private data.

| Benchmark | Measures | Headline (deterministic) |
|---|---|---|
| [`entity_resolution/`](entity_resolution/) | Does Cairn grounding raise correct-canonical-id rate vs. deriving the id? | correct-id accuracy **59% → 100%** (all errors eliminated) |

Not yet here (see repo `ROADMAP.md`): **OP-31 retrieval-quality eval** — end-to-end
answer quality vs. agentic-grep / vector-RAG / Graphiti. Until it lands, Cairn's
*quality* claims stay unproven; these benchmarks cover the deterministic
properties (resolution, determinism, purity) that are testable today.
