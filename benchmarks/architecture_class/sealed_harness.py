#!/usr/bin/env python3
"""Sealed offline harness for the architecture-class A/B/C ruler.

Anti-cheat contract
-------------------
1. Pins are written to ``seal/manifest.json`` *before* any scoring.
2. Scores land only under ``seal/`` (scorer-owned). The agent under test
   must not be given write access to ``seal/`` during an eval.
3. Corpus and rules are hashed; ``--verify`` recomputes and fails on drift.
4. Offline by default: Cairn C + ``opa test`` + TrustLint on labeled prompts.
   Live CE HTTP / OpenAI arms are *not* part of the sealed path.

Pins
----
- model (explicit; ``none`` when LLM arms are skipped)
- entity_resolution corpus sha
- compliance prompt corpus sha (when --ce-root is set)
- opa rules tree sha (when --ce-root is set)
- opa / trustlint tool versions
- optional git SHAs for cairn + complyedge trees

Reproduce
---------
    python sealed_harness.py --repeat 3
    python sealed_harness.py --ce-root /path/to/complyedge --repeat 3
    python sealed_harness.py --verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
SEAL_DIR = HERE / "seal"
MANIFEST_PATH = SEAL_DIR / "manifest.json"
RESULTS_PATH = SEAL_DIR / "results.json"

# workspace/cairn/benchmarks/architecture_class → workspace
_WORKSPACE = HERE.parents[2]
_DEFAULT_CE = _WORKSPACE / "complyedge" / "complyedge"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_tree(root: Path, pattern: str = "**/*") -> str:
    """Stable hash of file contents under root (path-relative, sorted)."""
    h = hashlib.sha256()
    files = sorted(
        p for p in root.glob(pattern) if p.is_file() and p.name != ".DS_Store"
    )
    for p in files:
        rel = p.relative_to(root).as_posix()
        h.update(rel.encode())
        h.update(b"\x00")
        h.update(_sha256_file(p).encode())
        h.update(b"\x00")
    return h.hexdigest()


def _git_sha(repo: Path) -> str | None:
    if not (repo / ".git").exists() and not (repo / ".git").is_file():
        # export trees sometimes still have .git
        pass
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _tool_version(cmd: list[str]) -> str | None:
    exe = shutil.which(cmd[0])
    if not exe:
        return None
    try:
        out = subprocess.check_output(
            [exe, *cmd[1:]], stderr=subprocess.STDOUT, text=True, timeout=30
        )
        line = out.strip().splitlines()[0] if out.strip() else ""
        return line[:200] or "ok"
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def entity_resolution_corpus_sha() -> tuple[str, int]:
    """Hash ER dataset ids+names (same stability idea as CE corpus_sha)."""
    # Import via scorecard loader to avoid duplicating DATASET.
    sys.path.insert(0, str(HERE))
    from scorecard import _load_er_benchmark  # noqa: WPS433

    mod = _load_er_benchmark()
    h = hashlib.sha256()
    for it in sorted(mod.DATASET, key=lambda x: x.canonical_id):
        h.update(it.kind.encode())
        h.update(b"\x00")
        h.update(it.canonical_id.encode())
        h.update(b"\x00")
        h.update(it.name.encode())
        h.update(b"\x00")
    return h.hexdigest()[:16], len(mod.DATASET)


def compliance_prompt_corpus_sha(ce_root: Path) -> tuple[str, int]:
    prompts_dir = ce_root / "scripts" / "benchmark" / "prompts"
    if not prompts_dir.is_dir():
        raise FileNotFoundError(f"CE prompts not found: {prompts_dir}")
    # Prefer importing CE corpus_sha if available; else hash YAML ids+text.
    runtime = ce_root / "scripts" / "benchmark" / "runtime_benchmark.py"
    if runtime.is_file():
        import importlib.util

        name = "ce_runtime_benchmark_sealed"
        spec = importlib.util.spec_from_file_location(name, runtime)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        # runtime_benchmark imports httpx/yaml at module level — ok if installed
        try:
            spec.loader.exec_module(mod)
            prompts = mod.load_corpus("all")
            return mod.corpus_sha(prompts), len(prompts)
        except Exception:
            pass

    h = hashlib.sha256()
    total = 0
    for path in sorted(prompts_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        for p in data.get("prompts") or []:
            total += 1
            h.update(str(p.get("id", "")).encode())
            h.update(b"\x00")
            h.update(str(p.get("text", "")).encode())
            h.update(b"\x00")
    return h.hexdigest()[:16], total


def build_manifest(
    *,
    model: str,
    repeat: int,
    ce_root: Path | None,
    cairn_root: Path,
) -> dict[str, Any]:
    er_sha, er_n = entity_resolution_corpus_sha()
    manifest: dict[str, Any] = {
        "schema": "architecture_class_seal.v1",
        "sealed_at": datetime.now(UTC).isoformat(),
        "pins": {
            "model": model,
            "repeat": repeat,
            "entity_resolution_corpus_sha": er_sha,
            "entity_resolution_n": er_n,
            "compliance_prompt_corpus_sha": None,
            "compliance_prompt_n": None,
            "opa_rules_sha": None,
            "cairn_git_sha": _git_sha(cairn_root),
            "complyedge_git_sha": _git_sha(ce_root) if ce_root else None,
            "opa_version": _tool_version(["opa", "version"]),
            "trustlint_version": _tool_version(["trustlint", "--version"])
            or _tool_version(["trustlint", "version"]),
        },
        "paths": {
            "seal_dir": "benchmarks/architecture_class/seal",
            "ce_root": "complyedge/complyedge" if ce_root else None,
            "cairn_root": ".",
        },
        "anti_cheat": {
            "scorer_owned_dir": "benchmarks/architecture_class/seal",
            "rule": (
                "Agent under test must not write to seal/. "
                "Pins are frozen before scoring; --verify detects corpus/rules drift."
            ),
        },
    }
    if ce_root:
        c_sha, c_n = compliance_prompt_corpus_sha(ce_root)
        rules = ce_root / "rules" / "rego"
        manifest["pins"]["compliance_prompt_corpus_sha"] = c_sha
        manifest["pins"]["compliance_prompt_n"] = c_n
        manifest["pins"]["opa_rules_sha"] = (
            _sha256_tree(rules, "**/*.rego")[:16] if rules.is_dir() else None
        )
    manifest["manifest_sha"] = _sha256_text(
        json.dumps(
            {k: v for k, v in manifest.items() if k != "manifest_sha"},
            sort_keys=True,
            default=str,
        )
    )[:16]
    return manifest


def run_cairn_c(repeat: int) -> dict[str, Any]:
    from scorecard import rows_entity_resolution

    rows = rows_entity_resolution(repeat=repeat, llm_model=None)
    row = rows[0].to_dict()
    return {"ok": True, "contestant": "C", "row": row}


def run_opa_test(ce_root: Path) -> dict[str, Any]:
    rules = ce_root / "rules" / "rego"
    if not rules.is_dir():
        return {"ok": False, "error": f"missing {rules}"}
    if not shutil.which("opa"):
        return {"ok": False, "error": "opa binary not found on PATH"}
    proc = subprocess.run(
        ["opa", "test", str(rules), "-v"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    # Summary line like: PASS: 218/218
    m = re.search(r"PASS:\s*(\d+)/(\d+)", proc.stdout + proc.stderr)
    passed = failed = None
    if m:
        passed, total = int(m.group(1)), int(m.group(2))
        failed = total - passed
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "passed": passed,
        "failed": failed,
        "tail": (proc.stdout + proc.stderr)[-1500:],
    }


def run_trustlint_corpus(ce_root: Path, limit: int | None = None) -> dict[str, Any]:
    """Score expected=block prompts with TrustLint offline (contestant C proxy)."""
    if not shutil.which("trustlint"):
        return {"ok": False, "error": "trustlint not found on PATH", "skipped": True}

    prompts_dir = ce_root / "scripts" / "benchmark" / "prompts"
    items: list[dict[str, Any]] = []
    for path in sorted(prompts_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        cat = data.get("category") or path.stem
        for p in data.get("prompts") or []:
            items.append(
                {
                    "id": p["id"],
                    "category": cat,
                    "expected": p.get("expected_decision"),
                    "text": p.get("text", ""),
                    "jurisdiction": p.get("jurisdiction", "EU"),
                }
            )
    if limit is not None:
        items = items[:limit]

    scored = 0
    matched = 0
    errors = 0
    details: list[dict[str, Any]] = []
    for it in items:
        if it["expected"] not in {"block", "allow"}:
            continue
        scored += 1
        cmd = [
            "trustlint",
            "check",
            "--text",
            it["text"],
            "-j",
            str(it["jurisdiction"]),
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60
            )
        except OSError as e:
            errors += 1
            details.append({"id": it["id"], "error": str(e)})
            continue
        # TrustLint exits non-zero on findings (block). Treat findings as block.
        actual = "block" if proc.returncode != 0 else "allow"
        # Some versions always exit 0 — parse stdout for "violation" / "PASS"
        out = (proc.stdout + proc.stderr).lower()
        if proc.returncode == 0 and (
            "violation" in out or "blocked" in out or "fail" in out
        ):
            actual = "block"
        if proc.returncode == 0 and "no violation" in out:
            actual = "allow"
        ok = actual == it["expected"]
        if ok:
            matched += 1
        details.append(
            {
                "id": it["id"],
                "expected": it["expected"],
                "actual": actual,
                "passed": ok,
                "returncode": proc.returncode,
            }
        )

    rate = round(100.0 * matched / scored, 1) if scored else 0.0
    return {
        "ok": errors == 0 and scored > 0,
        "scored": scored,
        "matched": matched,
        "errors": errors,
        "correctness": rate,
        "details": details[:20],  # cap artifact size
    }


def write_seal(manifest: dict[str, Any], results: dict[str, Any]) -> None:
    SEAL_DIR.mkdir(parents=True, exist_ok=True)
    # Manifest first (anti-cheat: pins frozen before results are authoritative).
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    RESULTS_PATH.write_text(json.dumps(results, indent=2) + "\n")
    # Best-effort: make seal dir owner-writable only (agent should not share UID).
    try:
        os.chmod(SEAL_DIR, 0o755)
        os.chmod(MANIFEST_PATH, 0o644)
        os.chmod(RESULTS_PATH, 0o644)
    except OSError:
        pass


def verify_seal(ce_root: Path | None, cairn_root: Path) -> dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        return {"ok": False, "error": f"missing {MANIFEST_PATH}"}
    manifest = json.loads(MANIFEST_PATH.read_text())
    pins = manifest.get("pins") or {}
    er_sha, _ = entity_resolution_corpus_sha()
    checks = {
        "entity_resolution_corpus_sha": er_sha == pins.get("entity_resolution_corpus_sha"),
    }
    if ce_root and pins.get("compliance_prompt_corpus_sha"):
        c_sha, _ = compliance_prompt_corpus_sha(ce_root)
        checks["compliance_prompt_corpus_sha"] = (
            c_sha == pins.get("compliance_prompt_corpus_sha")
        )
        rules = ce_root / "rules" / "rego"
        if pins.get("opa_rules_sha") and rules.is_dir():
            checks["opa_rules_sha"] = (
                _sha256_tree(rules, "**/*.rego")[:16] == pins.get("opa_rules_sha")
            )
    ok = all(checks.values())
    return {"ok": ok, "checks": checks, "pins": pins}


def main() -> int:
    p = argparse.ArgumentParser(description="Sealed offline A/B/C harness")
    p.add_argument("--repeat", type=int, default=1, metavar="K")
    p.add_argument(
        "--model",
        default="none",
        help="Pinned model id for the seal (use 'none' for offline C-only)",
    )
    p.add_argument(
        "--ce-root",
        type=Path,
        default=None,
        help="ComplyEdge public/platform tree (enables opa test + TrustLint + CE corpus pin)",
    )
    p.add_argument(
        "--no-ce",
        action="store_true",
        help="Skip ComplyEdge even if default path exists",
    )
    p.add_argument(
        "--trustlint-limit",
        type=int,
        default=None,
        help="Optional cap on TrustLint prompts (smoke)",
    )
    p.add_argument(
        "--verify",
        action="store_true",
        help="Recompute pins vs seal/manifest.json; do not re-score",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing seal/manifest.json + results.json",
    )
    args = p.parse_args()

    if args.repeat < 1:
        print("ERROR: --repeat must be >= 1", file=sys.stderr)
        return 2

    cairn_root = HERE.parents[1]  # …/cairn
    ce_root = None
    if not args.no_ce:
        ce_root = args.ce_root or (_DEFAULT_CE if _DEFAULT_CE.is_dir() else None)

    if args.verify:
        report = verify_seal(ce_root, cairn_root)
        print(json.dumps(report, indent=2))
        return 0 if report.get("ok") else 1

    if MANIFEST_PATH.exists() and not args.force:
        print(
            f"ERROR: {MANIFEST_PATH} exists. Pass --force to overwrite, "
            f"or --verify to check pins.",
            file=sys.stderr,
        )
        return 2

    # 1) Pin first
    manifest = build_manifest(
        model=args.model,
        repeat=args.repeat,
        ce_root=ce_root,
        cairn_root=cairn_root,
    )
    SEAL_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")

    # 2) Score into scorer-owned results
    results: dict[str, Any] = {
        "schema": "architecture_class_seal_results.v1",
        "completed_at": datetime.now(UTC).isoformat(),
        "manifest_sha": manifest.get("manifest_sha"),
        "steps": {},
    }

    print("Sealed step: Cairn entity_resolution C …", flush=True)
    results["steps"]["cairn_entity_resolution_C"] = run_cairn_c(args.repeat)

    if ce_root:
        print(f"Sealed step: opa test ({ce_root}) …", flush=True)
        results["steps"]["opa_test"] = run_opa_test(ce_root)
        print("Sealed step: TrustLint corpus …", flush=True)
        results["steps"]["trustlint_corpus"] = run_trustlint_corpus(
            ce_root, limit=args.trustlint_limit
        )
    else:
        results["steps"]["opa_test"] = {"ok": False, "skipped": True, "reason": "no --ce-root"}
        results["steps"]["trustlint_corpus"] = {
            "ok": False,
            "skipped": True,
            "reason": "no --ce-root",
        }

    results["ok"] = all(
        s.get("ok") or s.get("skipped")
        for s in results["steps"].values()
    ) and results["steps"]["cairn_entity_resolution_C"].get("ok") is True

    # Re-write manifest+results together (manifest already pinned)
    write_seal(manifest, results)

    print(json.dumps({"manifest": str(MANIFEST_PATH), "results": str(RESULTS_PATH), "ok": results["ok"]}, indent=2))
    # Non-zero if a required step failed (not skipped)
    if not results["steps"]["cairn_entity_resolution_C"].get("ok"):
        return 1
    if ce_root and not results["steps"]["opa_test"].get("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
