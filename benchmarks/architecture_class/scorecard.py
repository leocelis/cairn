#!/usr/bin/env python3
"""Architecture-class scorecard — unified A/B/C rows across domains.

Contestants (fixed labels):
  A  pure LLM
  B  hybrid (LLM + symbolic)
  C  symbolic / deterministic only

Domains (v0):
  entity_resolution  — Cairn benchmarks/entity_resolution
  compliance         — ComplyEdge runtime_benchmark JSON artifacts

Scorecard columns (machine-checkable):
  correctness, pass_at_k, policy_pass, path_safety, latency_ms_p99, cost_tokens

This runner does not invent a product SKU. It normalizes existing harness
outputs into one leaderboard so an article can cite measured tables.

Reproduce (no network for entity_resolution C):
    python scorecard.py --domains entity_resolution --repeat 3

With CE artifacts already on disk:
    python scorecard.py --domains compliance \\
      --ce-json-a path/to/runtime_benchmark_llm_only_latest.json \\
      --ce-json-b path/to/runtime_benchmark_latest.json \\
      --ce-json-c path/to/runtime_benchmark_opa_latest.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BENCH_ROOT = HERE.parent
ER_BENCH_PATH = BENCH_ROOT / "entity_resolution" / "benchmark.py"
RESULTS_DIR = HERE / "results"
DEFAULT_LEADERBOARD = RESULTS_DIR / "leaderboard_latest.json"
DEFAULT_MARKDOWN = RESULTS_DIR / "leaderboard_latest.md"

CONTESTANTS = ("A", "B", "C")
DOMAINS = ("entity_resolution", "compliance")


@dataclass
class ScoreRow:
    domain: str
    contestant: str  # A | B | C
    contestant_label: str
    n_tasks: int
    correctness: float | None  # 0–100
    pass_at_k: float | None  # 0–100; same as correctness when pass^k applied
    repeat: int
    policy_pass: float | None  # 0–100
    path_safety: float | None  # 0–100
    latency_ms_p99: float | None
    cost_tokens: float | None
    corpus_or_run_ref: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_er_benchmark():
    name = "er_benchmark_for_scorecard"
    spec = importlib.util.spec_from_file_location(name, ER_BENCH_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {ER_BENCH_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _pct(numer: int, denom: int) -> float:
    return round(100.0 * numer / denom, 1) if denom else 0.0


def rows_entity_resolution(
    repeat: int = 1,
    llm_model: str | None = None,
) -> list[ScoreRow]:
    """Build A/B/C rows for the entity-resolution domain.

    C always runs (deterministic Cairn resolve).
    A/B require llm_model + OPENAI_API_KEY (caller checks).
    """
    mod = _load_er_benchmark()
    table = mod.build_table()
    n = len(mod.DATASET)
    rows: list[ScoreRow] = []

    # --- C symbolic ---
    c_ok = 0
    for it in mod.DATASET:
        truth = it.canonical_id.lower()
        oks = [
            mod.cairn_resolve(it, table).lower() == truth for _ in range(repeat)
        ]
        if mod.pass_at_k(oks):
            c_ok += 1
    rows.append(
        ScoreRow(
            domain="entity_resolution",
            contestant="C",
            contestant_label="symbolic (Cairn resolve)",
            n_tasks=n,
            correctness=_pct(c_ok, n),
            pass_at_k=_pct(c_ok, n),
            repeat=repeat,
            policy_pass=100.0,  # closed-world exact-match is the policy
            path_safety=100.0,
            latency_ms_p99=None,
            cost_tokens=0.0,
            corpus_or_run_ref=f"entity_resolution n={n}",
            notes="deterministic; latency not timed in this harness",
        )
    )

    if not llm_model:
        return rows

    client = mod._llm_client()
    a_ok = 0
    b_ok = 0
    for it in mod.DATASET:
        a_pass, b_pass, _, _ = mod.evaluate_item(
            it, table, client, llm_model, repeat
        )
        # evaluate_item: baseline=A (LLM alone), cairn column=B (LLM+candidates)
        if a_pass:
            a_ok += 1
        if b_pass:
            b_ok += 1

    rows.insert(
        0,
        ScoreRow(
            domain="entity_resolution",
            contestant="A",
            contestant_label=f"pure LLM ({llm_model})",
            n_tasks=n,
            correctness=_pct(a_ok, n),
            pass_at_k=_pct(a_ok, n),
            repeat=repeat,
            policy_pass=None,
            path_safety=100.0,
            latency_ms_p99=None,
            cost_tokens=None,
            corpus_or_run_ref=f"entity_resolution n={n}",
            notes="LLM alone; cost_tokens not metered in this harness",
        ),
    )
    rows.insert(
        1,
        ScoreRow(
            domain="entity_resolution",
            contestant="B",
            contestant_label=f"hybrid LLM+Cairn ({llm_model})",
            n_tasks=n,
            correctness=_pct(b_ok, n),
            pass_at_k=_pct(b_ok, n),
            repeat=repeat,
            policy_pass=100.0,
            path_safety=100.0,
            latency_ms_p99=None,
            cost_tokens=None,
            corpus_or_run_ref=f"entity_resolution n={n}",
            notes="model picks among Cairn candidates",
        ),
    )
    return rows


def _error_path(path: str | None) -> bool:
    if not path:
        return True
    return path in {"http_error", "exception"} or path.startswith("error")


def row_from_ce_artifact(
    path: Path,
    contestant: str,
    contestant_label: str,
) -> ScoreRow:
    """Normalize a runtime_benchmark JSON artifact into one scorecard row."""
    data = json.loads(path.read_text())
    agg = data.get("aggregate") or {}
    results = data.get("results") or []
    total = int(agg.get("total_prompts") or len(results) or 0)
    passed = int(agg.get("passed") or 0)
    repeat = int(data.get("repeat") or agg.get("repeat") or 1)
    pass_at_k = agg.get("pass_at_k_rate")
    if pass_at_k is None:
        pass_at_k = _pct(passed, total)

    detection = float(agg.get("detection_rate_blocked_categories") or 0.0)
    fp = float(agg.get("false_positive_rate_safe_harbor") or 0.0)
    # policy_pass: both demo thresholds as a single 0–100 score
    policy_pass = round(
        0.5 * detection + 0.5 * max(0.0, 100.0 - fp),
        1,
    )

    safe_n = sum(1 for r in results if not _error_path(r.get("engine_path")))
    path_safety = _pct(safe_n, len(results)) if results else None

    api = agg.get("api_latency_ms") or {}
    latency = api.get("p99")
    if latency is None:
        wall = agg.get("wall_ms") or agg.get("latency_ms") or {}
        latency = wall.get("p99")

    return ScoreRow(
        domain="compliance",
        contestant=contestant,
        contestant_label=contestant_label,
        n_tasks=total,
        correctness=_pct(passed, total),
        pass_at_k=float(pass_at_k),
        repeat=repeat,
        policy_pass=policy_pass,
        path_safety=path_safety,
        latency_ms_p99=latency,
        cost_tokens=None,
        corpus_or_run_ref=str(data.get("corpus_sha") or path.name),
        notes=f"engine={data.get('engine', '?')} run_id={data.get('run_id', '')[:8]}",
    )


def rows_compliance_from_artifacts(
    json_a: Path | None,
    json_b: Path | None,
    json_c: Path | None,
) -> list[ScoreRow]:
    rows: list[ScoreRow] = []
    mapping = [
        (json_a, "A", "pure LLM (CE --engine llm-only)"),
        (json_b, "B", "hybrid (CE --engine hybrid)"),
        (json_c, "C", "symbolic (CE --engine opa)"),
    ]
    for path, contestant, label in mapping:
        if path is None:
            continue
        if not path.is_file():
            raise FileNotFoundError(f"CE artifact not found: {path}")
        rows.append(row_from_ce_artifact(path, contestant, label))
    return rows


def render_markdown(rows: list[ScoreRow], generated_at: str) -> str:
    lines = [
        "# Architecture-class scorecard",
        "",
        f"_Generated {generated_at}_",
        "",
        "| domain | contestant | n | correctness | pass^k | policy_pass | path_safety | p99 ms | cost_tokens | notes |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        lines.append(
            "| {domain} | {c} ({label}) | {n} | {corr} | {pak} | {pol} | {ps} | {lat} | {cost} | {notes} |".format(
                domain=r.domain,
                c=r.contestant,
                label=r.contestant_label,
                n=r.n_tasks,
                corr=_fmt(r.correctness),
                pak=_fmt(r.pass_at_k),
                pol=_fmt(r.policy_pass),
                ps=_fmt(r.path_safety),
                lat=_fmt(r.latency_ms_p99),
                cost=_fmt(r.cost_tokens),
                notes=r.notes.replace("|", "/"),
            )
        )
    lines.append("")
    lines.append(
        "Contestants: **A** pure LLM · **B** hybrid · **C** symbolic-only. "
        "pass^k = all K trials must pass."
    )
    lines.append("")
    return "\n".join(lines)


def _fmt(v: float | None) -> str:
    if v is None:
        return "—"
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v)


def build_leaderboard(rows: list[ScoreRow]) -> dict[str, Any]:
    generated_at = datetime.now(UTC).isoformat()
    return {
        "generated_at": generated_at,
        "schema": "architecture_class_scorecard.v1",
        "contestants": {
            "A": "pure LLM",
            "B": "hybrid LLM+symbolic",
            "C": "symbolic-only",
        },
        "columns": [
            "correctness",
            "pass_at_k",
            "policy_pass",
            "path_safety",
            "latency_ms_p99",
            "cost_tokens",
        ],
        "rows": [r.to_dict() for r in rows],
    }


def main() -> int:
    p = argparse.ArgumentParser(
        description="Unified A/B/C architecture-class scorecard"
    )
    p.add_argument(
        "--domains",
        default="entity_resolution",
        help="Comma list: entity_resolution,compliance (default: entity_resolution)",
    )
    p.add_argument("--repeat", type=int, default=1, metavar="K", help="pass^k")
    p.add_argument(
        "--llm",
        metavar="MODEL",
        default=None,
        help="Enable entity_resolution A/B with this model (needs OPENAI_API_KEY)",
    )
    p.add_argument("--ce-json-a", type=Path, default=None, help="CE llm-only JSON")
    p.add_argument("--ce-json-b", type=Path, default=None, help="CE hybrid JSON")
    p.add_argument("--ce-json-c", type=Path, default=None, help="CE opa JSON")
    p.add_argument(
        "--output",
        choices=["terminal", "json", "markdown", "all"],
        default="all",
    )
    p.add_argument(
        "--json-out",
        type=Path,
        default=DEFAULT_LEADERBOARD,
        help="Leaderboard JSON path",
    )
    p.add_argument(
        "--md-out",
        type=Path,
        default=DEFAULT_MARKDOWN,
        help="Leaderboard markdown path",
    )
    args = p.parse_args()

    if args.repeat < 1:
        print("ERROR: --repeat must be >= 1", file=sys.stderr)
        return 2

    domains = [d.strip() for d in args.domains.split(",") if d.strip()]
    for d in domains:
        if d not in DOMAINS:
            print(f"ERROR: unknown domain {d!r}; choose from {DOMAINS}", file=sys.stderr)
            return 2

    rows: list[ScoreRow] = []
    if "entity_resolution" in domains:
        rows.extend(rows_entity_resolution(repeat=args.repeat, llm_model=args.llm))

    if "compliance" in domains:
        if not any([args.ce_json_a, args.ce_json_b, args.ce_json_c]):
            print(
                "ERROR: compliance domain needs at least one of "
                "--ce-json-a/--ce-json-b/--ce-json-c",
                file=sys.stderr,
            )
            return 2
        rows.extend(
            rows_compliance_from_artifacts(
                args.ce_json_a, args.ce_json_b, args.ce_json_c
            )
        )

    # Stable order: domain then A,B,C
    order = {c: i for i, c in enumerate(CONTESTANTS)}
    rows.sort(key=lambda r: (r.domain, order.get(r.contestant, 9)))

    board = build_leaderboard(rows)
    md = render_markdown(rows, board["generated_at"])

    if args.output in ("terminal", "all"):
        print(md)

    if args.output in ("json", "all"):
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(board, indent=2) + "\n")
        print(f"JSON: {args.json_out}", file=sys.stderr)

    if args.output in ("markdown", "all"):
        args.md_out.parent.mkdir(parents=True, exist_ok=True)
        args.md_out.write_text(md)
        print(f"Markdown: {args.md_out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
