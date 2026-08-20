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

## What this is not

- Not a product SKU or procurement line
- Not LLM-as-judge scoring (success is exact-match / labeled expected_decision)
- Not a substitute for sealed offline eval (separate harness step)
