"""pass^k helper used by the public entity-resolution benchmark."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_benchmark():
    path = (
        Path(__file__).resolve().parents[4]
        / "benchmarks"
        / "entity_resolution"
        / "benchmark.py"
    )
    name = "er_benchmark"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_pass_at_k_requires_all_trials():
    mod = _load_benchmark()
    assert mod.pass_at_k([True, True, True]) is True
    assert mod.pass_at_k([True, False, True]) is False
    assert mod.pass_at_k([]) is False
