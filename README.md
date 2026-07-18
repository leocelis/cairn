<p align="center">
  <strong>Cairn</strong><br>
  <em>The deterministic entity / world-model engine for AI agents — resolve entities, decide whether to retrieve, route signals, assemble minimal context.</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/cairn-engine/"><img src="https://img.shields.io/pypi/v/cairn-engine?style=flat-square&label=cairn-engine&color=blue" alt="PyPI — cairn-engine"></a>
  <a href="https://pypi.org/project/cairn-retrieval/"><img src="https://img.shields.io/pypi/v/cairn-retrieval?style=flat-square&label=cairn-retrieval&color=blue" alt="PyPI — cairn-retrieval"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License"></a>
  <a href="https://github.com/leocelis/cairn/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/leocelis/cairn/ci.yml?branch=main&style=flat-square&label=tests" alt="Tests"></a>
  <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue?style=flat-square&logo=python&logoColor=white" alt="Python 3.11–3.13">
  <img src="https://img.shields.io/badge/dependencies-zero-brightgreen?style=flat-square" alt="Zero dependencies">
  <a href="https://ivdframework.dev"><img src="https://img.shields.io/badge/IVD-intent--verified-purple?style=flat-square" alt="IVD"></a>
</p>

---

## What is Cairn?

A **cairn** is a stack of stones left by travelers, marking the way for those who follow. Cairn is the same idea for AI agents: a **navigation layer** of canonical entities and relations that marks the route to context — built offline, human-approved, consulted before every retrieval.

Cairn is a **storage-agnostic routing and composition layer**, not a database. It orchestrates retrieval over stores you already have (files, SQL, vector DB, graph DB). It does **not** own storage, run LLM ingestion on the hot path, or dump an index into the prompt.

**Status:** `cairn-engine` and `cairn-retrieval` are **released on PyPI** (0.1.0) — feature-complete, 120 tests, ruff + mypy strict, zero runtime dependencies, byte-stable output. Next: the benchmark phase (eval vs. agentic-grep / vector-RAG / Graphiti) — quality claims stay honest until it lands. See [`ROADMAP.md`](ROADMAP.md).

## Why

Always-on retrieval measurably hurts (SRACG, AAAI 2026: −2.6 to −3.6pp vs. no retrieval; selective: +2.4 to +7.1pp), and context length alone degrades accuracy even with perfect retrieval ([Du et al. 2025, arXiv:2510.05381](https://arxiv.org/abs/2510.05381)). LLM-built knowledge graphs drift — non-deterministic extraction, 3–6 LLM calls per episode. Every design rule Cairn implements is traced to a primary source in [`docs/patterns/`](docs/patterns/). Cairn inverts both problems:

- **The frozen alias table is the determinism boundary.** Entity resolution is a lookup cascade over a human-approved, frozen ontology — same input, byte-identical output, zero LLM.
- **Skipping retrieval is a first-class answer.** A two-stage LLM-free gate decides `none | grep | semantic | graph | composite` *before* any signal runs.
- **Storage stays yours.** Adapters (in-memory, SQLite, openCypher graph DBs) execute Cairn's bounded traversal intent — the agent never writes a graph query, and Cairn never imports a DB driver.

## Packages (monorepo)

| Package | What it is | State |
|---------|-----------|-------|
| **`cairn-engine`** | The deterministic **entity / world-model engine** — resolution cascade (exact → normalized → fuzzy → opt-in semantic → opt-in constrained LLM arbiter), bounded bi-temporal traversal, ontology authoring with a mandatory human gate, cross-system entity index, storage adapters. Pure stdlib, zero dependencies. | [released on PyPI](https://pypi.org/project/cairn-engine/) |
| **`cairn-retrieval`** | The **agent-retrieval layer** on top — adaptive gate (OP-33), lexical BM25 + scan, opt-in semantic signal, RRF fusion, budgeted context assembler with trace manifest, and `retrieve()` end-to-end. Depends only on `cairn-engine`. | [released on PyPI](https://pypi.org/project/cairn-retrieval/), 0.x until benchmarked |

## What's proven — and what's not

Cairn separates what is **test-enforced today** from what still needs the benchmark phase. The determinism and purity claims are structural and verified on every CI run; the *quality* claim is deliberately not asserted until it is measured against baselines.

| Claim | Status | Basis |
|---|---|---|
| Deterministic, byte-stable output — same input → identical bytes across runs | ✅ test-enforced | byte-stability + sockets-disabled tests |
| Zero generative-LLM and zero network on the default path | ✅ test-enforced | hot-path purity test (a counting embedder receives 0 calls) + static import scan of every core file |
| Zero runtime dependencies in `cairn-engine` core | ✅ test-enforced | `dependencies = []`; CI on Python 3.11 / 3.12 / 3.13 |
| Storage-agnostic — identical behavior across ≥ 2 backends | ✅ test-enforced | in-memory ↔ SQLite differential test |
| Closed world — a miss is `unresolved`, never a synthesized ID | ✅ test-enforced | resolution + cross-system-index constraint tests |
| Grounding a consumer with Cairn raises correct-canonical-id accuracy | ✅ measured | **59% → 100%** (errors eliminated) on a public benchmark — [`benchmarks/entity_resolution/`](benchmarks/entity_resolution/) |
| Retrieval **quality** beats agentic-grep / vector-RAG / Graphiti at lower cost | ❌ **not yet measured** | Phase 4 (OP-31 eval) — the honest gap; "best" stays a thesis until then |
| Scales to 100k+ entities | ⚠️ same API proven across backends; large-corpus performance unexercised | adapters exist; no scale benchmark yet |

Full test suite: **120 tests, ruff + mypy strict, byte-stable**, green on 3.11–3.13.

## Quickstart

```bash
pip install cairn-engine cairn-retrieval
```

Or from source, for development:

```bash
git clone https://github.com/leocelis/cairn && cd cairn
make install   # python3.11 venv + editable installs + dev deps
make check     # ruff + mypy strict + full test suite
```

Thirty seconds of the entity engine:

```python
from cairn_engine import Entity, InMemoryAliasTable, InMemoryGraph, Ref, Relation, resolve, traverse

entities = [
    Entity("org::acme", "Acme Inc", "org", aliases=("acme", "ACME Corporation"),
           refs=(Ref(doc_id="doc::acme_overview"),),
           relations=(Relation("supplier_of", "org::beta"),)),
    Entity("org::beta", "Beta LLC", "org", aliases=("beta",),
           refs=(Ref(doc_id="doc::beta_contract"),)),
]
table = InMemoryAliasTable.from_entities(entities)   # build -> freeze -> read-only
graph = InMemoryGraph.from_entities(entities)

resolved, unresolved = resolve("what does ACME Corporation supply?", table=table)
# resolved[0].canonical_id == "org::acme"  (tier: normalized — deterministic, no LLM)

result = traverse("org::acme", graph=graph, depth=2)
# hop-ordered DocumentRefs: doc::acme_overview (hop 0), doc::beta_contract (hop 1)
```

And the retrieval layer in one call:

```python
from cairn_retrieval import DocMeta, LexicalIndex, RetrievalEngine

engine = RetrievalEngine(
    table=table,
    corpus={"doc::acme_overview": DocMeta("Acme overview…", tokens=18),
            "doc::beta_contract": DocMeta("Beta contract…", tokens=22)},
    graph=graph,
    lexical=LexicalIndex.from_documents({"doc::acme_overview": "Acme overview…",
                                         "doc::beta_contract": "Beta contract…"}),
)
result = engine.retrieve("how do acme and beta relate", budget=200)
# gate -> strategy; signals -> RRF fusion -> budgeted, provenance-tagged context.
# A query the gate routes to "none" returns NO context — the skip is the point.
```

Runnable demos for every subsystem live in [`examples/`](examples/) — all self-contained except the WordPress ones, which take your own corpus (see `examples/wordpress_corpus_prep.py`).

## Design invariants (each test-enforced)

Non-negotiable constraints from the [charter](cairn_system_intent.yaml); each maps to an executing test:

- **Zero generative-LLM and zero network on the default hot path** — the gate, resolver, signals, fusion, and assembler are deterministic; LLM/embedder/DB-driver enter only as caller-supplied callables
- **Zero runtime dependencies** in the `cairn-engine` core — pure stdlib
- **Storage-agnostic core** — adapters for in-memory, SQLite, openCypher graph DBs; Cairn never owns the bytes and never exposes a query language
- **Explicit canonical ontology** — stable IDs you supply and approve; a miss is an explicit `unresolved`, never a synthesized ID (closed world)
- **Local-first** — the full default path runs offline with no API key
- **One API, progressive scale** — same call sites for an in-memory corpus and a backend-backed one

Public API: `resolve()` · `traverse()` · `gate()` · `retrieve()` — plus authoring (`author_from_text`, `dedup_candidates`), bi-temporal state (`as_at`, `supersede`), and the cross-system entity index.

## Repository layout

```
cairn/
├── LICENSE · README.md · ROADMAP.md · CHANGELOG.md · CONTRIBUTING.md
├── pyproject.toml                # uv workspace root
├── cairn_system_intent.yaml      # system charter (IVD intent format)
├── packages/
│   ├── cairn-engine/             # entity / world-model engine  (import: cairn_engine)
│   │   ├── src/cairn_engine/{entity,adapters}/
│   │   ├── intents/              # module intents — constraints map 1:1 to tests
│   │   └── tests/{unit,integration}/
│   └── cairn-retrieval/          # gate · signals · fusion · assembler · retrieve()
│       ├── src/cairn_retrieval/
│       ├── intents/
│       └── tests/unit/
├── examples/                     # runnable demos for every subsystem
├── benchmarks/                   # reproducible, honestly-scored evidence
└── docs/
    ├── PRD.md                    # use cases + functional requirements
    ├── architecture/cairn_architecture.svg
    ├── patterns/                 # the distilled design rules (TH-1..5, OP-1..36)
    └── research/                 # foundations/ · context/ · databases/ · tools/
```

**Start here:** [`cairn_system_intent.yaml`](cairn_system_intent.yaml) (thesis + invariants) → [`docs/patterns/`](docs/patterns/) (the design rules the code implements) → [`examples/full_engine_e2e.py`](examples/full_engine_e2e.py) (the whole engine, narrated).

## How it's built

Cairn is developed **intent-first** ([IVD](https://ivdframework.dev)): every module has an intent file declaring its constraints *before* the code, each constraint maps 1:1 to a named test with hand-computed golden fixtures, and joint-satisfaction tests assert all of a module's constraints on the same output. The pattern YAMLs in `docs/patterns/` cite the primary sources (Cormack & Clarke 2009, Snodgrass 1985, Reiter 1978, Mallen 2023, Du 2025, …) each design rule rests on.

Related projects: [IVD](https://github.com/leocelis/ivd) · [Horizon](https://github.com/leocelis/horizon)

## Roadmap

1. Charter + research + patterns + PRD ✅
2. `cairn-engine` 0.1 — entity engine, validated on a real corpus ✅
3. `cairn-engine` 0.2 — bi-temporal state, SQLite + openCypher adapters, cross-system index ✅
4. `cairn-retrieval` 0.1 — gate, signals, fusion, assembler, `retrieve()` ✅
5. **Eval (next)** — benchmark harness (OP-31) vs. agentic-grep / vector-RAG / Graphiti / Mem0 ⏳
6. Hardening & ecosystem — more adapters, reranker tier, docs site 💡

Full detail in [`ROADMAP.md`](ROADMAP.md).

## When Cairn is *not* the right choice

- You want the richest possible graph regardless of drift → an LLM-in-the-loop builder (Graphiti/Zep) extracts more, denser relations.
- Pure document semantic search with no entity/relational structure → a vector DB alone is simpler and sufficient.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). The short version: intent before code, constraint tests with hand-computed fixtures, `make check` must be green, and PRs that add storage engines or dependencies to core will be declined — adapters only.

## Community

- **Ask a question / propose a design:** [GitHub Discussions](https://github.com/leocelis/cairn/discussions)
- **Bug reports:** [GitHub Issues](https://github.com/leocelis/cairn/issues)
- **Security:** please follow the [security policy](SECURITY.md) — do not open a public issue for vulnerabilities

## Author

**Leo Celis** — [leocelis.com](https://leocelis.com)

## Legal

See [`LEGAL.md`](LEGAL.md) for what Cairn is and is not, the scope of the research-cited and pre-benchmark claims, and the standard as-is disclaimer. Security policy: [`SECURITY.md`](SECURITY.md).

## License

[MIT](LICENSE) — Copyright (c) 2026 Leo Celis

