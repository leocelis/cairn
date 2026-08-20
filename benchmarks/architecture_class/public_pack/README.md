# Architecture-class benchmark — public pack

Head-to-head ruler for **three architecture classes** on the same tasks:

| Contestant | Meaning |
|---|---|
| **A** | Pure LLM |
| **B** | Hybrid (LLM + symbolic) |
| **C** | Symbolic / deterministic only |

This pack is the publishable surface: tasks, harness pointers, sealed offline
scores, and a leaderboard. It does **not** invent a product SKU.

## What's inside

| Path | Contents |
|---|---|
| `tasks/entity_resolution.json` | 22 synthetic entity-resolution items (public fiction names) |
| `tasks/compliance.md` | How to load the ComplyEdge labeled prompt corpus (~60) by pin |
| `leaderboard.json` / `leaderboard.md` | Measured rows from the sealed offline run |
| `seal_snapshot/` | Pinned manifest + results (paths scrubbed) |
| `HARNESS.md` | Reproduce scorecard + sealed harness |

## Headline (sealed offline, contestant C)

| Domain | Result |
|---|---|
| Entity resolution (Cairn resolve, pass^3) | **100%** correct-id (22/22) |
| Compliance (OPA Rego corpus tests) | **218/218 PASS** |
| Compliance (TrustLint vs labeled prompts) | **43.3%** match (60 prompts) — subset of OPA; reported honestly |

A/B arms exist in the harnesses (`--llm`, CE `--engine llm-only|hybrid`) and are
listed as pending in the leaderboard until live artifacts are attached.

## Fair comparison contract

1. Fixed world — same tasks / pins for all contestants
2. Three contestants — A / B / C
3. Machine-checkable success — exact-match or labeled `expected_decision` (not LLM-as-judge)
4. Scorecard columns — correctness, pass^k, policy_pass, path_safety, latency, cost
5. Sealed eval — pins frozen before scoring; agent must not write `seal/`
6. Open publish — this pack

## License / provenance

- Entity-resolution tasks: synthetic public dataset shipped with Cairn
- Compliance prompts & Rego: ComplyEdge public repository
- Scores in `seal_snapshot/` are reproducible from `HARNESS.md`
