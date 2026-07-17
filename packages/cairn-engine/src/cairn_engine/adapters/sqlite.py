"""SQLite alias-table adapter — the second live backend (OP-35, M2.2).

Same AliasTableAdapter Protocol and identical behavior to the in-memory adapter
(build-time folding reuses adapters._build), but the frozen closed world lives
in a .db file and reads are served by SQL — so a large corpus (OP-35's 500-50k
tier) need not sit in RAM to be resolved, and the map persists across processes.

    table = SqliteAliasTable.from_entities(entities, path="blog.db")   # build + freeze
    ...later, another process...
    table = SqliteAliasTable.open("blog.db")                            # read-only
    resolve("my Schwab account", table=table)

Stdlib only (sqlite3, json). Build is in-memory + batch (offline); the read path
scales via SQL.
"""

from __future__ import annotations

import sqlite3
from typing import Iterable

from cairn_engine.adapters._build import build_indexes, fold_entities, find_root
from cairn_engine.adapters.jsonfile import dump_entities, load_entities
from cairn_engine.entity.model import Entity, ResolvedEntity

__all__ = ["SqliteAliasTable"]

_SCHEMA_VERSION = 1
_TIER_EXACT = "exact"
_TIER_NORMALIZED = "normalized"

_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE record (canonical_id TEXT PRIMARY KEY, is_representative INTEGER, json TEXT);
CREATE TABLE exact (surface TEXT, canonical_id TEXT);
CREATE TABLE norm  (normalized TEXT, canonical_id TEXT);
CREATE INDEX ix_exact ON exact(surface);
CREATE INDEX ix_norm  ON norm(normalized);
"""


class SqliteAliasTable:
    """Build -> freeze (writes SQL tables) -> read-only lookup via SQL."""

    def __init__(self, path: str = ":memory:") -> None:
        self._path = path
        self._con = sqlite3.connect(path)
        self._frozen = False
        self._entities: dict[str, Entity] = {}
        self._merged: dict[str, str] = {}

    @property
    def path(self) -> str:
        """The SQLite file path backing this table (':memory:' if ephemeral)."""
        return self._path

    # -- build time ------------------------------------------------------

    @classmethod
    def from_entities(cls, entities: Iterable[Entity], *, path: str = ":memory:") -> "SqliteAliasTable":
        table = cls(path)
        for entity in entities:
            table.add(entity)
        return table.freeze()

    @classmethod
    def open(cls, path: str) -> "SqliteAliasTable":
        """Reopen an already-frozen .db read-only (no rebuild)."""
        table = cls.__new__(cls)
        table._path = path
        table._entities = {}
        table._merged = {}
        try:
            table._con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            row = table._con.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()
        except sqlite3.OperationalError as exc:
            raise ValueError(f"cannot open a frozen cairn db at {path!r}: {exc}") from exc
        if row is None or int(row[0]) != _SCHEMA_VERSION:
            raise ValueError(f"not a frozen cairn db (schema_version {row}) at {path!r}")
        table._frozen = True
        return table

    def add(self, entity: Entity) -> None:
        self._require_building()
        if entity.canonical_id in self._entities:
            raise ValueError(f"duplicate canonical_id: {entity.canonical_id}")
        self._entities[entity.canonical_id] = entity

    def merge(self, source_id: str, target_id: str) -> None:
        self._require_building()
        root_src = find_root(source_id, self._merged)
        root_dst = find_root(target_id, self._merged)
        if root_src not in self._entities or root_dst not in self._entities:
            raise KeyError(f"merge of unknown entity: {source_id} -> {target_id}")
        if root_src != root_dst:
            self._merged[root_src] = root_dst

    def freeze(self) -> "SqliteAliasTable":
        """Fold in memory (shared _build), then persist the frozen result to SQL."""
        canonical = fold_entities(self._entities, self._merged)
        exact, norm = build_indexes(canonical)
        representatives = {e.canonical_id for e in canonical}

        self._con.executescript(_SCHEMA)
        with self._con:
            self._con.execute("INSERT INTO meta VALUES ('schema_version', ?)", (str(_SCHEMA_VERSION),))
            # every added record is stored (audit); reps flagged is_representative=1
            for cid in sorted(self._entities):
                is_rep = 1 if cid in representatives else 0
                blob = dump_entities([e for e in canonical if e.canonical_id == cid]) if is_rep else "{}"
                self._con.execute(
                    "INSERT INTO record VALUES (?, ?, ?)", (cid, is_rep, blob)
                )
            self._con.executemany(
                "INSERT INTO exact VALUES (?, ?)",
                [(s, cid) for s, ids in sorted(exact.items()) for cid in ids],
            )
            self._con.executemany(
                "INSERT INTO norm VALUES (?, ?)",
                [(s, cid) for s, ids in sorted(norm.items()) for cid in ids],
            )
        self._frozen = True
        return self

    # -- hot path (read-only) ---------------------------------------------

    def lookup(self, surface: str) -> list[ResolvedEntity]:
        self._require_frozen()
        rows = self._con.execute(
            "SELECT canonical_id FROM exact WHERE surface=? ORDER BY canonical_id", (surface,)
        ).fetchall()
        tier = _TIER_EXACT
        if not rows:
            from cairn_engine.entity.normalize import normalize

            rows = self._con.execute(
                "SELECT canonical_id FROM norm WHERE normalized=? ORDER BY canonical_id",
                (normalize(surface),),
            ).fetchall()
            tier = _TIER_NORMALIZED
        return [
            ResolvedEntity(surface_form=surface, canonical_id=r[0], confidence=1.0, tier=tier)
            for r in rows
        ]

    def normalized_entries(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        self._require_frozen()
        out: dict[str, list[str]] = {}
        for norm_s, cid in self._con.execute(
            "SELECT normalized, canonical_id FROM norm ORDER BY normalized, canonical_id"
        ):
            out.setdefault(norm_s, []).append(cid)
        return tuple((s, tuple(ids)) for s, ids in out.items())

    def canonical_entities(self) -> tuple[Entity, ...]:
        self._require_frozen()
        rows = self._con.execute(
            "SELECT json FROM record WHERE is_representative=1 ORDER BY canonical_id"
        ).fetchall()
        return tuple(load_entities(r[0])[0] for r in rows)

    def has_id(self, canonical_id: str) -> bool:
        self._require_frozen()
        row = self._con.execute(
            "SELECT is_representative FROM record WHERE canonical_id=?", (canonical_id,)
        ).fetchone()
        return bool(row and row[0])

    def has_record(self, canonical_id: str) -> bool:
        self._require_frozen()
        return self._con.execute(
            "SELECT 1 FROM record WHERE canonical_id=?", (canonical_id,)
        ).fetchone() is not None

    # -- guards ----------------------------------------------------------

    def _require_building(self) -> None:
        if self._frozen:
            raise RuntimeError("alias table is frozen — build-time mutations only (OP-35)")

    def _require_frozen(self) -> None:
        if not self._frozen:
            raise RuntimeError(
                "alias table must be frozen before lookup — the determinism boundary is the frozen table"
            )
