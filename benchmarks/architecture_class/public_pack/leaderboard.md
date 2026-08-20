# Architecture-class leaderboard

_Generated 2026-08-20T16:22:21.526715+00:00_

| domain | contestant | n | correctness | pass^k | policy_pass | path_safety | notes |
|---|---|---:|---:|---:|---:|---:|---|
| entity_resolution | symbolic (Cairn resolve) | 22 | 100.0 | 100.0 | 100.0 | 100.0 | deterministic; latency not timed in this harness |
| compliance | symbolic (OPA corpus tests) | 218 | 100.0 | 100.0 | 100.0 | 100.0 | offline sealed; machine-checkable Rego corpus |
| compliance | symbolic (TrustLint offline) | 60 | 43.3 | 43.3 | 43.3 | 100.0 | offline proxy vs labeled expected_decision; TrustLint rule subset ≠ full OPA path |

Contestants: **A** pure LLM · **B** hybrid · **C** symbolic-only. Sealed offline pack currently reports **C** rows with pins; A/B arms are runnable via the harness docs and listed under `pending_arms`.
