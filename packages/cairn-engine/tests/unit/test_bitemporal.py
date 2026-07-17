"""Constraint tests for intents/entity_bitemporal_intent.yaml (M2.1, TH-3).

Each test maps 1:1 to a constraint (C-BITEMP-1..5) plus one joint test. Golden
fixtures hand-computed. Stdlib-only, no wall clock.
"""

from __future__ import annotations

import pathlib

from cairn_engine.adapters.jsonfile import dump_entities, load_entities
from cairn_engine.entity.bitemporal import as_at, supersede
from cairn_engine.entity.model import Entity, Relation

_SRC = pathlib.Path(__file__).parents[3] / "cairn-engine" / "src" / "cairn_engine" / "entity"


# --- C-BITEMP-1: four columns exist on both records and round-trip in JSON ----

def test_four_columns_roundtrip() -> None:
    e = Entity(
        canonical_id="c::x", label="X", entity_type="concept",
        valid_from="2026-01-01", valid_until="2026-06-01",
        known_from="2026-01-02", known_until="2026-05-01",
        relations=(
            Relation("mentions", "c::y",
                     valid_from="2026-02-01", valid_until=None,
                     known_from="2026-02-02", known_until=None, weight=3.0),
        ),
    )
    # transaction-time is independent of valid-time on BOTH records
    assert (e.valid_from, e.valid_until) == ("2026-01-01", "2026-06-01")
    assert (e.known_from, e.known_until) == ("2026-01-02", "2026-05-01")
    r = e.relations[0]
    assert (r.valid_from, r.valid_until) == ("2026-02-01", None)
    assert (r.known_from, r.known_until) == ("2026-02-02", None)

    # byte-identical round-trip (both axes survive dump -> load -> dump)
    once = dump_entities([e])
    twice = dump_entities(list(load_entities(once)))
    assert once == twice
    back = load_entities(once)[0]
    assert (back.known_from, back.known_until) == ("2026-01-02", "2026-05-01")
    assert (back.relations[0].known_from, back.relations[0].known_until) == ("2026-02-02", None)


# --- C-BITEMP-2: as_at four-column predicate, per axis --------------------------

def test_as_at_four_column() -> None:
    # valid last Tuesday (Mar 10) but only KNOWN from today (Mar 12)
    f = Entity(
        canonical_id="c::f", label="F", entity_type="concept",
        valid_from="2026-03-10", valid_until=None,
        known_from="2026-03-12", known_until=None,
    )
    facts = [f]
    # known-axis: excluded on Tuesday (not yet learned), included today
    assert as_at(facts, known_as_of="2026-03-10") == ()
    assert as_at(facts, known_as_of="2026-03-12") == (f,)
    # valid-axis: true from Mar 10 onward, not before
    assert as_at(facts, valid_as_of="2026-03-09") == ()
    assert as_at(facts, valid_as_of="2026-03-10") == (f,)
    # both axes together; None on an axis disables just that axis
    assert as_at(facts, valid_as_of="2026-03-10", known_as_of="2026-03-12") == (f,)
    assert as_at(facts, valid_as_of="2026-03-10", known_as_of="2026-03-11") == ()
    assert as_at(facts) == (f,)  # both None -> identity


# --- C-BITEMP-3: None == +inf open-end sentinel, half-open boundary -------------

def test_open_end_sentinel_boundary() -> None:
    r = Relation("rel", "c::t", valid_from="2026-01-01", valid_until="2026-06-01",
                 known_from="2026-01-01", known_until="2026-06-01")
    # half-open [start, end): INCLUDES start, EXCLUDES end
    assert as_at([r], valid_as_of="2026-01-01") == (r,)   # == start -> in
    assert as_at([r], valid_as_of="2026-06-01") == ()     # == end   -> out
    assert as_at([r], valid_as_of="2026-05-31") == (r,)   # < end    -> in
    # same rule on the transaction axis
    assert as_at([r], known_as_of="2026-01-01") == (r,)
    assert as_at([r], known_as_of="2026-06-01") == ()
    # None end == open (+inf): far-future instant still inside
    open_ended = Relation("rel", "c::t", valid_from="2026-01-01", valid_until=None)
    assert as_at([open_ended], valid_as_of="2099-12-31") == (open_ended,)
    # None start == open (-inf): far-past instant still inside
    from_dawn = Relation("rel", "c::t", valid_from=None, valid_until="2026-06-01")
    assert as_at([from_dawn], valid_as_of="1900-01-01") == (from_dawn,)


# --- C-BITEMP-4: supersession is append-only + immutable -----------------------

def test_supersede_append_only() -> None:
    v1 = Entity(canonical_id="c::x", label="X v1", entity_type="concept",
                known_from="2026-01-01", known_until=None)
    v2 = Entity(canonical_id="c::x", label="X v2", entity_type="concept")

    result = supersede([v1], v2, at="2026-03-01")

    # nothing dropped; old object NOT mutated (still open)
    assert len(result) == 2
    assert v1.known_until is None
    # the superseded version is closed exactly at `at`; the new one opens there
    closed, new = result
    assert closed.label == "X v1" and closed.known_until == "2026-03-01"
    assert new.label == "X v2" and new.known_from == "2026-03-01"
    assert new.known_until is None  # now the current knowledge

    # audit chain reconstructable with as_at: what did I know, and when?
    assert [e.label for e in as_at(result, known_as_of="2026-02-01")] == ["X v1"]
    assert [e.label for e in as_at(result, known_as_of="2026-03-15")] == ["X v2"]


# --- C-BITEMP-5: no wall clock, byte-stable (conflict_prone) --------------------

def test_no_wall_clock_byte_stable() -> None:
    # static guard: a wall-clock read requires importing time/datetime — neither
    # module may. (Guard the IMPORTS, not prose: the docstrings legitimately name
    # now()/today() to state the prohibition.)
    for name in ("bitemporal.py", "model.py"):
        src = (_SRC / name).read_text()
        for banned in ("import time", "import datetime", "from time", "from datetime"):
            assert banned not in src, f"{name} must not read the wall clock: {banned!r}"

    # differential: identical inputs -> byte-identical output across two runs
    def run() -> str:
        v1 = Entity(canonical_id="c::x", label="v1", entity_type="concept",
                    known_from="2026-01-01", known_until=None)
        v2 = Entity(canonical_id="c::x", label="v2", entity_type="concept")
        hist = supersede([v1], v2, at="2026-03-01")
        kept = as_at(hist, known_as_of="2026-03-15")
        return dump_entities(list(kept))

    assert run() == run()


# --- joint satisfaction (5 constraints) ----------------------------------------

def test_joint_bitemporal() -> None:
    """All constraints on the SAME output: build with both axes (C-1), correct it
    append-only (C-4), query three (valid, known) points (C-2) across the None
    open-end (C-3), byte-stable with no clock (C-5)."""
    v1 = Entity(
        canonical_id="c::policy", label="retry: 3x", entity_type="concept",
        valid_from="2026-01-01", valid_until=None,   # true in the world from Jan 1
        known_from="2026-01-05", known_until=None,   # we learned it Jan 5
    )
    v2 = Entity(
        canonical_id="c::policy", label="retry: 5x", entity_type="concept",
        valid_from="2026-01-01", valid_until=None,   # correction: it was 5x all along
    )
    # correction recorded on Apr 2 (explicit instant, C-5)
    hist = supersede([v1], v2, at="2026-04-02")

    # C-1: both axes survived into the corrected history and round-trip
    assert dump_entities(list(hist)) == dump_entities(list(load_entities(dump_entities(list(hist)))))

    # C-2 + C-3: "what did we know, and when" — three point-in-time slices
    before_learning = as_at(hist, known_as_of="2026-01-01")        # knew nothing yet
    after_first = as_at(hist, known_as_of="2026-02-01")            # knew 3x
    after_correction = as_at(hist, known_as_of="2026-05-01")       # know 5x (None open end, C-3)
    assert [e.label for e in before_learning] == []
    assert [e.label for e in after_first] == ["retry: 3x"]
    assert [e.label for e in after_correction] == ["retry: 5x"]

    # correctness axis: what was TRUE on Mar 1, as best known on May 1 (post-correction)?
    true_mar1_known_today = as_at(hist, valid_as_of="2026-03-01", known_as_of="2026-05-01")
    assert [e.label for e in true_mar1_known_today] == ["retry: 5x"]
    # ...but as known on Feb 1 (pre-correction), the same question answered "3x"
    true_mar1_known_feb = as_at(hist, valid_as_of="2026-03-01", known_as_of="2026-02-01")
    assert [e.label for e in true_mar1_known_feb] == ["retry: 3x"]

    # C-5: byte-stable across repeated evaluation
    assert dump_entities(list(after_correction)) == dump_entities(list(after_correction))
