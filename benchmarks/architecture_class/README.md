# Architecture-class scorecard

Unified **A / B / C** rows across domains for the symbolic-vs-LLM category ruler.

| Contestant | Meaning |
|---|---|
| **A** | Pure LLM |
| **B** | Hybrid (LLM + symbolic) |
| **C** | Symbolic / deterministic only |

## Domains (v0)

| Domain | Source harness |
|---|---|
| `entity_resolution` | [`../entity_resolution/`](../entity_resolution/) |
| `compliance` | ComplyEdge `scripts/benchmark/runtime_benchmark.py` JSON artifacts |

## Columns

`correctness` · `pass_at_k` · `policy_pass` · `path_safety` · `latency_ms_p99` · `cost_tokens`

## Reproduce

```bash
# Entity-resolution C (offline, deterministic)
python scorecard.py --domains entity_resolution --repeat 3

# Entity-resolution A/B/C (needs OPENAI_API_KEY)
python scorecard.py --domains entity_resolution --repeat 3 --llm gpt-4o-mini

# Compliance rows from existing CE benchmark JSON
python scorecard.py --domains compliance \
  --ce-json-a /path/to/runtime_benchmark_llm_only_latest.json \
  --ce-json-b /path/to/runtime_benchmark_latest.json \
  --ce-json-c /path/to/runtime_benchmark_opa_latest.json
```

Outputs land in `results/leaderboard_latest.json` and `results/leaderboard_latest.md`.

## Sealed offline harness

```bash
# Pin corpus/model, then score into scorer-owned seal/ (Cairn C + opa test + TrustLint)
python sealed_harness.py --repeat 3 --force
python sealed_harness.py --verify

# Optional: CE tree (defaults to ../../complyedge/complyedge when present)
python sealed_harness.py --ce-root /path/to/complyedge --repeat 3 --force
```

Requires on PATH for the CE steps: `opa`, `trustlint`. Entity-resolution C needs only Cairn. For CE prompt loading, install `PyYAML` in the Cairn venv (`pip install PyYAML`).

Anti-cheat: pins go to `seal/manifest.json` **before** scoring; agents under test must not write `seal/`.
