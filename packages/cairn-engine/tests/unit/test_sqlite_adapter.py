"""Constraint tests for intents/sqlite_adapter_intent.yaml.

The headline test is DIFFERENTIAL: the SQLite backend must be byte-identical to
the in-memory backend for the same corpus + merges — that equivalence IS the
storage_agnostic_core proof.
"""

from __future__ import annotations

import pytest

from cairn_engine.adapters.base import AliasTableAdapter
from cairn_engine.adapters.memory import InMemoryAliasTable
from cairn_engine.adapters.sqlite import SqliteAliasTable
from cairn_engine.entity.model import Entity, Ref, Relation
from cairn_engine.entity.resolve import resolve


def _corpus() -> list[Entity]:
    return [
        Entity(canonical_id="concept::llm", label="LLM", entity_type="concept",
               aliases=("large language model",), refs=(Ref(doc_id="post::intro"),)),
        Entity(canonical_id="concept::llms", label="LLMs", entity_type="concept",
               refs=(Ref(doc_id="post::deep_dive"),)),
        Entity(canonical_id="tool::copilot", label="GitHub Copilot", entity_type="tool",
               aliases=("Copilot",)),
        Entity(canonical_id="post::a", label="Post A", entity_type="document",
               relations=(Relation("mentions", "concept::llms", weight=2.0),
                          Relation("mentions", "tool::copilot"))),
    ]


def _build(cls: type, path: str = ":memory:"):  # type: ignore[no-untyped-def]
    table = cls(path) if cls is SqliteAliasTable else cls()
    for e in _corpus():
        table.add(e)
    table.merge("concept::llms", "concept::llm")   # LLMs folds into LLM
    return table.freeze()


# -- constraint: satisfies_protocol_same_behavior (DIFFERENTIAL) --------------

def test_matches_inmemory_behavior() -> None:
    mem, sql = _build(InMemoryAliasTable), _build(SqliteAliasTable)

    # both satisfy the Protocol at runtime
    assert isinstance(mem, AliasTableAdapter) and isinstance(sql, AliasTableAdapter)

    surfaces = ["LLM", "LLMs", "large language model", "github copilot", "Copilot", "nope"]
    for s in surfaces:
        m = [(h.canonical_id, h.tier) for h in mem.lookup(s)]
        q = [(h.canonical_id, h.tier) for h in sql.lookup(s)]
        assert m == q, s
    assert mem.normalized_entries() == sql.normalized_entries()
    assert mem.canonical_entities() == sql.canonical_entities()
    for cid in ("concept::llm", "concept::llms", "tool::copilot", "ghost"):
        assert mem.has_id(cid) == sql.has_id(cid)
        assert mem.has_record(cid) == sql.has_record(cid)

    # end-to-end resolve() gives identical results through either backend
    q = "the LLMs and GitHub Copilot"
    assert repr(resolve(q, table=mem)) == repr(resolve(q, table=sql))


# -- constraint: folding_reuses_shared_build ----------------------------------

def test_merge_folds_like_inmemory() -> None:
    sql = _build(SqliteAliasTable)
    # merged surface resolves to the representative; refs folded onto it
    assert [h.canonical_id for h in sql.lookup("LLMs")] == ["concept::llm"]
    rep = {e.canonical_id: e for e in sql.canonical_entities()}["concept::llm"]
    assert {r.doc_id for r in rep.refs} == {"post::intro", "post::deep_dive"}
    # merged id: audit record kept, but not a resolvable id
    assert sql.has_record("concept::llms") and not sql.has_id("concept::llms")
    assert sql.has_id("concept::llm")


# -- constraint: persists_and_reopens_frozen ----------------------------------

def test_persist_and_reopen(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = str(tmp_path / "corpus.db")
    _build(SqliteAliasTable, db)                       # build + freeze to file
    reopened = SqliteAliasTable.open(db)               # fresh instance, no rebuild
    assert [h.canonical_id for h in reopened.lookup("LLMs")] == ["concept::llm"]
    assert reopened.canonical_entities()[0].canonical_id  # reads work
    # reopened is read-only
    with pytest.raises(Exception):
        reopened.add(Entity(canonical_id="x::y", label="y", entity_type="concept"))
    with pytest.raises(ValueError):
        SqliteAliasTable.open(str(tmp_path / "not_a_db.db"))


# -- constraint: deterministic_stdlib_offline ---------------------------------

def test_deterministic_stdlib_freeze_gate() -> None:
    q = "LLMs GitHub Copilot large language model"
    assert repr(resolve(q, table=_build(SqliteAliasTable))) == \
        repr(resolve(q, table=_build(SqliteAliasTable)))
    # freeze gate: reads before freeze raise
    t = SqliteAliasTable()
    t.add(Entity(canonical_id="c::x", label="x", entity_type="concept"))
    with pytest.raises(RuntimeError):
        t.lookup("x")
    # stdlib only (sqlite3 + json are stdlib; cairn is first-party)
    import pathlib

    import cairn_engine.adapters.sqlite as mod

    text = pathlib.Path(mod.__file__).read_text()
    for banned in ("sqlalchemy", "psycopg", "numpy", "requests", "httpx", "pandas"):
        assert f"import {banned}" not in text and f"from {banned}" not in text


# -- joint --------------------------------------------------------------------

def test_joint_sqlite_adapter(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = str(tmp_path / "joint.db")
    sql = _build(SqliteAliasTable, db)
    mem = _build(InMemoryAliasTable)
    # matches in-memory + persists + deterministic, all at once
    assert sql.canonical_entities() == mem.canonical_entities()          # same behavior
    assert sql.has_id("concept::llm") and not sql.has_id("concept::llms")  # fold
    reopened = SqliteAliasTable.open(db)                                  # reopens
    assert reopened.normalized_entries() == mem.normalized_entries()      # persisted == in-memory
