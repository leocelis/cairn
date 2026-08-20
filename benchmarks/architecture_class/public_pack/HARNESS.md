# Harness — reproduce the architecture-class pack

Run from the Cairn repo root (or `benchmarks/architecture_class/`).

## Entity resolution

```bash
cd benchmarks/entity_resolution
python benchmark.py --repeat 3                 # C vs derive baseline
python benchmark.py --repeat 3 --llm gpt-4o-mini   # A/B with a model (needs OPENAI_API_KEY)
```

## Unified scorecard

```bash
cd benchmarks/architecture_class
python scorecard.py --domains entity_resolution --repeat 3
python scorecard.py --domains entity_resolution --repeat 3 --llm gpt-4o-mini
```

Compliance rows need ComplyEdge runtime JSON artifacts:

```bash
python scorecard.py --domains compliance \
  --ce-json-a /path/to/runtime_benchmark_llm_only_latest.json \
  --ce-json-b /path/to/runtime_benchmark_latest.json \
  --ce-json-c /path/to/runtime_benchmark_opa_latest.json
```

## Sealed offline path (anti-cheat)

```bash
cd benchmarks/architecture_class
python sealed_harness.py --repeat 3 --model none --force
python sealed_harness.py --verify
```

Requires `opa` and `trustlint` on PATH for compliance steps. Pins are written to
`seal/manifest.json` **before** scoring; do not give the agent under test write
access to `seal/`.

## Rebuild this public pack

```bash
cd benchmarks/architecture_class
python build_public_pack.py
```

Then run the pack integrity gate (must pass):

```bash
python build_public_pack.py   # re-runs assert_grep_clean
```
