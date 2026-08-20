"""Architecture-class scorecard — normalize harness outputs into A/B/C rows."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

CAIRN_ROOT = Path(__file__).resolve().parents[4]
SCORECARD_PATH = CAIRN_ROOT / "benchmarks" / "architecture_class" / "scorecard.py"


def _load_scorecard():
    name = "architecture_class_scorecard"
    spec = importlib.util.spec_from_file_location(name, SCORECARD_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_entity_resolution_c_row_offline():
    mod = _load_scorecard()
    rows = mod.rows_entity_resolution(repeat=3, llm_model=None)
    assert len(rows) == 1
    row = rows[0]
    assert row.contestant == "C"
    assert row.domain == "entity_resolution"
    assert row.n_tasks == 22
    assert row.correctness == 100.0
    assert row.pass_at_k == 100.0
    assert row.repeat == 3


def test_ce_artifact_normalization(tmp_path):
    mod = _load_scorecard()
    artifact = {
        "run_id": "abc12345-ffff",
        "engine": "opa",
        "corpus_sha": "deadbeef",
        "repeat": 3,
        "aggregate": {
            "total_prompts": 4,
            "passed": 3,
            "detection_rate_blocked_categories": 100.0,
            "false_positive_rate_safe_harbor": 0.0,
            "pass_at_k_rate": 75.0,
            "api_latency_ms": {"p99": 42.0},
        },
        "results": [
            {"engine_path": "opa", "passed": True},
            {"engine_path": "opa", "passed": True},
            {"engine_path": "opa", "passed": True},
            {"engine_path": "http_error", "passed": False},
        ],
    }
    path = tmp_path / "runtime_benchmark_opa_latest.json"
    path.write_text(json.dumps(artifact))
    row = mod.row_from_ce_artifact(path, "C", "symbolic (CE --engine opa)")
    assert row.domain == "compliance"
    assert row.contestant == "C"
    assert row.correctness == 75.0
    assert row.pass_at_k == 75.0
    assert row.policy_pass == 100.0
    assert row.path_safety == 75.0
    assert row.latency_ms_p99 == 42.0
    assert "deadbeef" in row.corpus_or_run_ref


def test_leaderboard_schema_and_markdown():
    mod = _load_scorecard()
    rows = mod.rows_entity_resolution(repeat=1)
    board = mod.build_leaderboard(rows)
    assert board["schema"] == "architecture_class_scorecard.v1"
    assert board["contestants"]["A"] == "pure LLM"
    assert len(board["rows"]) == 1
    md = mod.render_markdown(rows, board["generated_at"])
    assert "Architecture-class scorecard" in md
    assert "| entity_resolution |" in md


def test_compliance_requires_artifact_paths(tmp_path, monkeypatch):
    mod = _load_scorecard()
    monkeypatch.setattr(
        sys,
        "argv",
        ["scorecard.py", "--domains", "compliance", "--output", "terminal"],
    )
    assert mod.main() == 2
