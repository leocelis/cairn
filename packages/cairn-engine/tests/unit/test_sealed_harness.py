"""Sealed harness — pin before score; verify corpus/rules drift."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

CAIRN_ROOT = Path(__file__).resolve().parents[4]
SEALED_PATH = CAIRN_ROOT / "benchmarks" / "architecture_class" / "sealed_harness.py"


def _load():
    name = "architecture_class_sealed_harness"
    spec = importlib.util.spec_from_file_location(name, SEALED_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_entity_resolution_corpus_sha_stable():
    mod = _load()
    a, n1 = mod.entity_resolution_corpus_sha()
    b, n2 = mod.entity_resolution_corpus_sha()
    assert a == b
    assert n1 == n2 == 22
    assert len(a) == 16


def test_build_manifest_pins_model_and_er(tmp_path, monkeypatch):
    mod = _load()
    # Keep seal paths under tmp for isolation
    monkeypatch.setattr(mod, "SEAL_DIR", tmp_path / "seal")
    monkeypatch.setattr(mod, "MANIFEST_PATH", tmp_path / "seal" / "manifest.json")
    monkeypatch.setattr(mod, "RESULTS_PATH", tmp_path / "seal" / "results.json")
    cairn_root = CAIRN_ROOT
    manifest = mod.build_manifest(
        model="none",
        repeat=3,
        ce_root=None,
        cairn_root=cairn_root,
    )
    assert manifest["schema"] == "architecture_class_seal.v1"
    assert manifest["pins"]["model"] == "none"
    assert manifest["pins"]["repeat"] == 3
    assert manifest["pins"]["entity_resolution_n"] == 22
    assert manifest["pins"]["entity_resolution_corpus_sha"]
    assert "Agent under test must not write" in manifest["anti_cheat"]["rule"]


def test_verify_seal_roundtrip(tmp_path, monkeypatch):
    mod = _load()
    seal = tmp_path / "seal"
    monkeypatch.setattr(mod, "SEAL_DIR", seal)
    monkeypatch.setattr(mod, "MANIFEST_PATH", seal / "manifest.json")
    monkeypatch.setattr(mod, "RESULTS_PATH", seal / "results.json")
    manifest = mod.build_manifest(
        model="none", repeat=1, ce_root=None, cairn_root=CAIRN_ROOT
    )
    mod.write_seal(manifest, {"ok": True, "steps": {}})
    report = mod.verify_seal(None, CAIRN_ROOT)
    assert report["ok"] is True
    assert report["checks"]["entity_resolution_corpus_sha"] is True


def test_run_cairn_c_offline():
    mod = _load()
    out = mod.run_cairn_c(repeat=2)
    assert out["ok"] is True
    assert out["row"]["contestant"] == "C"
    assert out["row"]["correctness"] == 100.0
