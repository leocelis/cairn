#!/usr/bin/env python3
"""Storage-agnostic, proven: the SAME corpus on two backends, identical results.

Builds one entity map, freezes it into BOTH the in-memory adapter and a
persisted SQLite .db, then shows resolve() returns byte-identical results
through either — and that the SQLite map survives being closed and reopened
in a fresh object (persistence). This is storage_agnostic_core made concrete.

Run:  .venv/bin/python examples/two_backends_identical.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from cairn_engine import Entity, InMemoryAliasTable, Ref, Relation, SqliteAliasTable, resolve

ENTITIES = [
    Entity(canonical_id="concept::llm", label="LLM", entity_type="concept",
           aliases=("large language model",), refs=(Ref(doc_id="post::intro"),)),
    Entity(canonical_id="concept::llms", label="LLMs", entity_type="concept",
           refs=(Ref(doc_id="post::deep_dive"),)),
    Entity(canonical_id="tool::copilot", label="GitHub Copilot", entity_type="tool",
           aliases=("Copilot",)),
    Entity(canonical_id="post::a", label="Why We Ship With Copilot", entity_type="document",
           relations=(Relation("mentions", "concept::llms", weight=2.0),
                      Relation("mentions", "tool::copilot"))),
]


def _build(cls, path=":memory:"):  # type: ignore[no-untyped-def]
    table = cls(path) if cls is SqliteAliasTable else cls()
    for e in ENTITIES:
        table.add(e)
    table.merge("concept::llms", "concept::llm")   # LLMs is the same concept as LLM
    return table.freeze()


def main() -> None:
    tmp = Path(tempfile.mkdtemp()) / "corpus.db"

    mem = _build(InMemoryAliasTable)
    sql = _build(SqliteAliasTable, str(tmp))

    query = "the LLMs question and GitHub Copilot"
    print("query:", repr(query), "\n")
    print(f"{'surface':22} {'in-memory':22} {'sqlite':22}")
    print("-" * 66)
    for surface in ("LLM", "LLMs", "large language model", "Copilot", "unknown"):
        m = [h.canonical_id for h in mem.lookup(surface)] or ["(unresolved)"]
        q = [h.canonical_id for h in sql.lookup(surface)] or ["(unresolved)"]
        flag = "OK" if m == q else "DIFF!"
        print(f"{surface:22} {m[0]:22} {q[0]:22} {flag}")

    same_resolve = repr(resolve(query, table=mem)) == repr(resolve(query, table=sql))
    same_graph = mem.canonical_entities() == sql.canonical_entities()
    print(f"\nresolve() identical across backends : {same_resolve}")
    print(f"canonical_entities() identical      : {same_graph}")

    # persistence: reopen the .db in a brand-new object, no rebuild
    reopened = SqliteAliasTable.open(str(tmp))
    reopened_ok = reopened.normalized_entries() == mem.normalized_entries()
    print(f"reopened .db == in-memory           : {reopened_ok}")
    print(f"\n(db persisted at {tmp}, {tmp.stat().st_size:,} bytes — survives the process)")


if __name__ == "__main__":
    main()
