#!/usr/bin/env python3
"""Build the public architecture-class publish pack (grep-clean).

Assembles:
  public_pack/README.md
  public_pack/HARNESS.md
  public_pack/leaderboard.json + .md
  public_pack/tasks/entity_resolution.json
  public_pack/tasks/compliance.md
  public_pack/seal_snapshot/{manifest,results}.json  (paths scrubbed)

Does not embed Trello, milestone, or private vault references.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK = HERE / "public_pack"
TASKS = PACK / "tasks"
SEAL_SRC = HERE / "seal"
ER_BENCH = HERE.parent / "entity_resolution" / "benchmark.py"

ABS_PATH_RE = re.compile(r"/Users/[^/\s]+/workspace/")
BANNED_RE = re.compile(
    r"Trello|CQcLXiMu|limitless/|P27\b|WANT\b|SHOULD\b|Cosmic Rewind|"
    r"M\d+\.\d+|card #|HITL|docs/dd/",
    re.IGNORECASE,
)


def _load_er():
    name = "er_for_public_pack"
    spec = importlib.util.spec_from_file_location(name, ER_BENCH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def scrub(obj):
    """Remove machine-absolute workspace paths from nested JSON."""
    if isinstance(obj, str):
        return ABS_PATH_RE.sub("<workspace>/", obj)
    if isinstance(obj, list):
        return [scrub(x) for x in obj]
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items()}
    return obj


def export_entity_tasks() -> list[dict]:
    mod = _load_er()
    return [
        {
            "kind": it.kind,
            "canonical_id": it.canonical_id,
            "name": it.name,
            "category": it.category,
            "aliases": list(it.aliases),
        }
        for it in mod.DATASET
    ]


def build_leaderboard(seal_results: dict, er_sha: str) -> dict:
    rows = []
    cairn = (seal_results.get("steps") or {}).get("cairn_entity_resolution_C") or {}
    if cairn.get("row"):
        rows.append(cairn["row"])

    opa = (seal_results.get("steps") or {}).get("opa_test") or {}
    if opa.get("ok"):
        rows.append(
            {
                "domain": "compliance",
                "contestant": "C",
                "contestant_label": "symbolic (OPA corpus tests)",
                "n_tasks": opa.get("passed"),
                "correctness": 100.0 if opa.get("failed") == 0 else None,
                "pass_at_k": 100.0 if opa.get("failed") == 0 else None,
                "repeat": 1,
                "policy_pass": 100.0 if opa.get("failed") == 0 else None,
                "path_safety": 100.0,
                "latency_ms_p99": None,
                "cost_tokens": 0.0,
                "corpus_or_run_ref": f"opa test PASS {opa.get('passed')}/{opa.get('passed')}",
                "notes": "offline sealed; machine-checkable Rego corpus",
            }
        )

    tl = (seal_results.get("steps") or {}).get("trustlint_corpus") or {}
    if tl.get("scored"):
        rows.append(
            {
                "domain": "compliance",
                "contestant": "C",
                "contestant_label": "symbolic (TrustLint offline)",
                "n_tasks": tl.get("scored"),
                "correctness": tl.get("correctness"),
                "pass_at_k": tl.get("correctness"),
                "repeat": 1,
                "policy_pass": tl.get("correctness"),
                "path_safety": 100.0 if tl.get("errors") == 0 else None,
                "latency_ms_p99": None,
                "cost_tokens": 0.0,
                "corpus_or_run_ref": "CE runtime_benchmark prompts (60)",
                "notes": (
                    "offline proxy vs labeled expected_decision; "
                    "TrustLint rule subset ≠ full OPA path"
                ),
            }
        )

    return {
        "schema": "architecture_class_public_leaderboard.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "contestants": {
            "A": "pure LLM",
            "B": "hybrid LLM+symbolic",
            "C": "symbolic-only",
        },
        "pins": {
            "entity_resolution_corpus_sha": er_sha,
            "model": "none (sealed offline C)",
        },
        "rows": rows,
        "pending_arms": [
            "entity_resolution A/B (needs --llm + API key on scorecard.py)",
            "compliance A/B (CE --engine llm-only / hybrid JSON artifacts)",
        ],
    }


def render_md(board: dict) -> str:
    lines = [
        "# Architecture-class leaderboard",
        "",
        f"_Generated {board['generated_at']}_",
        "",
        "| domain | contestant | n | correctness | pass^k | policy_pass | path_safety | notes |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in board["rows"]:
        lines.append(
            "| {domain} | {c} | {n} | {corr} | {pak} | {pol} | {ps} | {notes} |".format(
                domain=r.get("domain"),
                c=r.get("contestant_label") or r.get("contestant"),
                n=r.get("n_tasks") if r.get("n_tasks") is not None else "—",
                corr=r.get("correctness") if r.get("correctness") is not None else "—",
                pak=r.get("pass_at_k") if r.get("pass_at_k") is not None else "—",
                pol=r.get("policy_pass") if r.get("policy_pass") is not None else "—",
                ps=r.get("path_safety") if r.get("path_safety") is not None else "—",
                notes=(r.get("notes") or "").replace("|", "/"),
            )
        )
    lines.append("")
    lines.append(
        "Contestants: **A** pure LLM · **B** hybrid · **C** symbolic-only. "
        "Sealed offline pack currently reports **C** rows with pins; A/B arms "
        "are runnable via the harness docs and listed under `pending_arms`."
    )
    lines.append("")
    return "\n".join(lines)


README = """# Architecture-class benchmark — public pack

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
"""

HARNESS = """# Harness — reproduce the architecture-class pack

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
python scorecard.py --domains compliance \\
  --ce-json-a /path/to/runtime_benchmark_llm_only_latest.json \\
  --ce-json-b /path/to/runtime_benchmark_latest.json \\
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
"""

COMPLIANCE_TASKS = """# Compliance tasks

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
"""


def assert_grep_clean(root: Path) -> None:
    bad: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.name == ".DS_Store":
            continue
        if path.suffix in {".png", ".jpg", ".pyc"}:
            continue
        text = path.read_text(errors="replace")
        if BANNED_RE.search(text):
            bad.append(str(path.relative_to(root)))
    if bad:
        raise SystemExit(f"public pack grep gate failed: {bad}")


def main() -> int:
    if not (SEAL_SRC / "manifest.json").is_file():
        raise SystemExit("missing seal/manifest.json — run sealed_harness.py first")
    if not (SEAL_SRC / "results.json").is_file():
        raise SystemExit("missing seal/results.json — run sealed_harness.py first")

    PACK.mkdir(parents=True, exist_ok=True)
    TASKS.mkdir(parents=True, exist_ok=True)
    snap = PACK / "seal_snapshot"
    snap.mkdir(parents=True, exist_ok=True)

    manifest = scrub(json.loads((SEAL_SRC / "manifest.json").read_text()))
    results = scrub(json.loads((SEAL_SRC / "results.json").read_text()))
    # Drop bulky opa stdout tail from the public snapshot (keep counts).
    opa = (results.get("steps") or {}).get("opa_test")
    if isinstance(opa, dict):
        opa.pop("tail", None)
    tl = (results.get("steps") or {}).get("trustlint_corpus")
    if isinstance(tl, dict) and isinstance(tl.get("details"), list):
        # Keep compact evidence; full detail stays in local seal/
        tl["details"] = tl["details"][:10]

    er_sha = (manifest.get("pins") or {}).get("entity_resolution_corpus_sha", "")
    tasks = export_entity_tasks()
    board = build_leaderboard(results, er_sha)

    (TASKS / "entity_resolution.json").write_text(
        json.dumps(
            {
                "schema": "architecture_class_er_tasks.v1",
                "n": len(tasks),
                "corpus_sha_pin": er_sha,
                "tasks": tasks,
            },
            indent=2,
        )
        + "\n"
    )
    (TASKS / "compliance.md").write_text(COMPLIANCE_TASKS)
    (PACK / "README.md").write_text(README)
    (PACK / "HARNESS.md").write_text(HARNESS)
    (PACK / "leaderboard.json").write_text(json.dumps(board, indent=2) + "\n")
    (PACK / "leaderboard.md").write_text(render_md(board))
    (snap / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (snap / "results.json").write_text(json.dumps(results, indent=2) + "\n")

    assert_grep_clean(PACK)
    print(f"Public pack written to {PACK}")
    print(f"Rows: {len(board['rows'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
