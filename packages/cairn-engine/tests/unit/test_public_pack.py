"""Public pack builder — grep-clean publish surface."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

CAIRN_ROOT = Path(__file__).resolve().parents[4]
BUILD_PATH = CAIRN_ROOT / "benchmarks" / "architecture_class" / "build_public_pack.py"
PACK = CAIRN_ROOT / "benchmarks" / "architecture_class" / "public_pack"


def _load():
    name = "build_public_pack_mod"
    spec = importlib.util.spec_from_file_location(name, BUILD_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_build_public_pack_writes_required_files():
    mod = _load()
    assert mod.main() == 0
    required = [
        PACK / "README.md",
        PACK / "HARNESS.md",
        PACK / "leaderboard.json",
        PACK / "leaderboard.md",
        PACK / "tasks" / "entity_resolution.json",
        PACK / "tasks" / "compliance.md",
        PACK / "seal_snapshot" / "manifest.json",
        PACK / "seal_snapshot" / "results.json",
    ]
    for path in required:
        assert path.is_file(), path
    board = (PACK / "leaderboard.json").read_text()
    assert "architecture_class_public_leaderboard.v1" in board
    assert len((PACK / "tasks" / "entity_resolution.json").read_text()) > 100


def test_public_pack_grep_clean():
    mod = _load()
    mod.assert_grep_clean(PACK)
