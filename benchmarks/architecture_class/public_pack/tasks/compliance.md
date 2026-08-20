# Compliance tasks

Labeled prompts live in the **ComplyEdge** public tree:

`scripts/benchmark/prompts/*.yaml` (~60 prompts across article5, article50,
gpai, safe_harbor, us_corpus, edge, prompt_security).

Each prompt carries `expected_decision` (`allow` | `block`) and optional
`expected_rule_id_pattern`.

## Pin (from sealed manifest)

Use the sealed snapshot pin rather than copying prompts into this pack:

- `compliance_prompt_corpus_sha` — see `../seal_snapshot/manifest.json`
- `opa_rules_sha` — Rego tree under `rules/rego/`

## Engines

| Contestant | Command |
|---|---|
| A | `python scripts/benchmark/runtime_benchmark.py --engine llm-only --repeat 3` |
| B | `python scripts/benchmark/runtime_benchmark.py --engine hybrid --repeat 3` |
| C | `python scripts/benchmark/runtime_benchmark.py --engine opa --repeat 3` |
| C offline | `opa test rules/rego` and TrustLint via `sealed_harness.py` |
