# Contributing to Cairn

Thanks for your interest. Both packages are feature-complete and pre-release:
the entity engine (`packages/cairn-engine`) and the retrieval layer
(`packages/cairn-retrieval`). The benchmark phase (OP-31 eval) is next — see
[`ROADMAP.md`](ROADMAP.md).

## Setup

```bash
make install    # python3.11 venv + dev deps + editable installs
make check      # ruff + mypy strict + full test suite — must be green
make demo       # the WordPress-style entity-graph demo
```

## How this project is built (please read before a PR)

Cairn is developed **intent-first** ([IVD](https://ivdframework.dev)):

1. Every module has an intent file in `packages/*/intents/` declaring its
   constraints, each mapped 1:1 to a named test in `tests/unit/`.
2. **Write or update the intent before the code.** If implementation reveals the
   intent was wrong, update the intent (with a changelog entry saying why) and
   then the code — never silently diverge.
3. Constraint tests use hand-computed golden fixtures. If you change behavior,
   recompute the fixture by hand — don't paste the code's output back in.

## Non-negotiable invariants (PRs violating these will be declined)

- **Zero third-party dependencies in the `cairn-engine` core.** Optional accelerators
  and extractors are explicit opt-ins (extras / caller-supplied callables) —
  never auto-detected, never implicitly imported.
- **Zero generative-LLM and zero network on any library path.** Even at build
  time, cairn itself never calls an API; user callables own that boundary.
- **Byte-stable determinism.** Same input → identical output, across runs,
  machines, and rebuilt tables. No wall-clock reads, no hash-seed dependence,
  no environment-dependent behavior.
- **Closed world.** A miss is an explicit `unresolved` — never a synthesized ID.
- **Storage behind adapters.** No concrete storage engine in core — adapters only.
- **The human gate.** Authoring output is staged; nothing enters a frozen table
  without an explicit approval step.

## Layout

```
packages/cairn-engine/
├── intents/        # module intents (constraints + test mapping)
├── src/cairn_engine/
│   ├── entity/     # model · normalize · resolve · ontology · traverse
│   └── adapters/   # protocols + in-memory implementations
└── tests/
    ├── unit/       # constraint tests, 1:1 with intents
    └── integration/# cross-module end-to-end
```

## License

MIT. By contributing you agree your contributions are MIT-licensed.
