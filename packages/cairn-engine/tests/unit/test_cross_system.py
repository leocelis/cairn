"""Constraint tests for intents/cross_system_index_intent.yaml (M2.4, TH-1/TH-5).

Each test maps 1:1 to a constraint (C-XSYS-1..5) plus one joint test. Golden
fixtures hand-computed. Stdlib-only, closed-world.
"""

from __future__ import annotations

import pathlib

import pytest

from cairn_engine.entity.crosssystem import CrossSystemIndex
from cairn_engine.entity.model import Entity

_SRC = pathlib.Path(__file__).parents[3] / "cairn-engine" / "src" / "cairn_engine" / "entity"


def _entity(cid: str, system_ids: dict[str, object]) -> Entity:
    return Entity(canonical_id=cid, label=cid.split("::")[-1], entity_type="org",
                  metadata={"system_ids": system_ids})


# -- C-XSYS-1: forward lookup ----------------------------------------------------

def test_forward_lookup() -> None:
    idx = CrossSystemIndex.from_entries([
        ("org::acme", "crm", "cus_42"),
        ("org::acme", "slack", "C0299"),
        ("org::beta", "crm", "cus_7"),
    ])
    assert idx.external_ids("org::acme", system="crm") == ("cus_42",)
    assert idx.external_ids("org::acme", system="slack") == ("C0299",)
    assert idx.systems("org::acme") == ("crm", "slack")
    # closed-world misses: unknown canonical, unknown system -> () not error
    assert idx.external_ids("org::acme", system="github") == ()
    assert idx.external_ids("org::nope", system="crm") == ()
    assert idx.systems("org::nope") == ()


# -- C-XSYS-2: reverse lookup is system-scoped -----------------------------------

def test_reverse_lookup_system_scoped() -> None:
    # SAME external id string "123" in two different systems must not collide
    idx = CrossSystemIndex.from_entries([
        ("org::acme", "crm", "123"),
        ("org::beta", "github", "123"),
    ])
    assert idx.canonical_for(system="crm", external_id="123") == "org::acme"
    assert idx.canonical_for(system="github", external_id="123") == "org::beta"
    assert idx.canonical_for(system="slack", external_id="123") is None  # miss -> None


# -- C-XSYS-3: bind cardinality (0 / 1 / many) -----------------------------------

def test_bind_cardinality() -> None:
    idx = CrossSystemIndex.from_entities([
        _entity("org::acme", {"crm": "cus_42", "slack": ["C1", "C2"]}),  # list form
        _entity("org::beta", {"crm": "cus_7"}),
    ])
    assert idx.bind("org::acme", system="crm") == "cus_42"      # exactly one
    assert idx.bind("org::acme", system="github") is None       # none -> None
    with pytest.raises(ValueError):                             # 2+ -> ambiguous
        idx.bind("org::acme", system="slack")
    assert idx.external_ids("org::acme", system="slack") == ("C1", "C2")


# -- C-XSYS-4: reverse one-to-one integrity at freeze ----------------------------

def test_reverse_collision_raises() -> None:
    # two DISTINCT canonicals claiming the same (system, external_id) -> error
    with pytest.raises(ValueError):
        CrossSystemIndex.from_entries([
            ("org::acme", "crm", "cus_42"),
            ("org::acme_dup", "crm", "cus_42"),
        ])
    # idempotent: same (cid, system, id) twice is fine
    idx = CrossSystemIndex.from_entries([
        ("org::acme", "crm", "cus_42"),
        ("org::acme", "crm", "cus_42"),
    ])
    assert idx.external_ids("org::acme", system="crm") == ("cus_42",)


# -- C-XSYS-5: closed world + byte-stable + read-only (conflict_prone) ------------

def test_closed_world_and_byte_stable() -> None:
    # static guard: stdlib-only, no wall clock
    src = (_SRC / "crosssystem.py").read_text()
    for banned in ("import requests", "import time", "import datetime", "from datetime"):
        assert banned not in src, f"crosssystem.py must stay stdlib/clock-free: {banned!r}"

    entries = [("org::acme", "crm", "cus_42"), ("org::acme", "slack", "C0299")]

    def state(idx: CrossSystemIndex) -> tuple:
        return (idx.external_ids("org::acme", system="crm"),
                idx.external_ids("org::acme", system="slack"),
                idx.systems("org::acme"),
                idx.canonical_for(system="crm", external_id="cus_42"))

    # byte-stable across two independent builds
    assert state(CrossSystemIndex.from_entries(entries)) == state(CrossSystemIndex.from_entries(entries))

    idx = CrossSystemIndex.from_entries(entries)
    # closed world: NEVER a synthesized id on a miss
    assert idx.bind("org::acme", system="github") is None
    assert idx.canonical_for(system="crm", external_id="does-not-exist") is None
    # frozen == read-only
    with pytest.raises(RuntimeError):
        idx.add("org::x", system="crm", external_id="y")


# -- joint satisfaction (5 constraints) ------------------------------------------

def test_joint_cross_system() -> None:
    """All constraints on ONE frozen index built from entities, incl. a TH-1 merge
    (one canonical with two crm ids) and a system-scoped reverse."""
    idx = CrossSystemIndex.from_entities([
        # org::acme absorbed a duplicate at merge -> two crm ids (forward 1-to-many)
        _entity("org::acme", {"crm": ["cus_42", "cus_old"], "slack": "C0299"}),
        _entity("org::beta", {"github": "cus_42"}),  # same string, different system
    ])
    # C-1 forward
    assert idx.external_ids("org::acme", system="crm") == ("cus_42", "cus_old")
    # C-2 reverse, system-scoped (crm cus_42 -> acme; github cus_42 -> beta)
    assert idx.canonical_for(system="crm", external_id="cus_42") == "org::acme"
    assert idx.canonical_for(system="github", external_id="cus_42") == "org::beta"
    # C-3 bind: unambiguous slack, ambiguous crm
    assert idx.bind("org::acme", system="slack") == "C0299"
    with pytest.raises(ValueError):
        idx.bind("org::acme", system="crm")
    # C-5 closed world miss + byte-stable
    assert idx.canonical_for(system="slack", external_id="nope") is None
    assert idx.systems("org::acme") == ("crm", "slack")
