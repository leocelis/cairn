"""Scaffold smoke tests — confirm the package imports and the model is immutable.

These lock in the invariants the scaffold already guarantees (immutable value
records; algorithm modules are honest stubs). Algorithm behavior is tested in the
core/entity module intent as each milestone lands.
"""

import dataclasses

import pytest

import cairn_engine
from cairn_engine.adapters import AliasTableAdapter, GraphAdapter
from cairn_engine.entity import ontology, resolve, traverse
from cairn_engine.entity.model import Entity, Ref, Relation, ResolvedEntity


def test_package_exports_version() -> None:
    assert cairn_engine.__version__.startswith("0.1.0")


def test_entity_is_immutable_value_record() -> None:
    """TH-5: entities are immutable value records (frozen), not mutable objects."""
    e = Entity(canonical_id="person::jane_doe", label="Jane Doe", entity_type="person",
               aliases=("Jane", "J. Doe"))
    assert dataclasses.is_dataclass(e)
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.label = "someone else"  # type: ignore[misc]


def test_entity_is_hashable() -> None:
    """Immutable + hashable is required for byte-stable determinism."""
    e = Entity(canonical_id="doc::x", label="X", entity_type="document")
    assert hash(e) == hash(e)


def test_model_types_construct() -> None:
    assert Ref(doc_id="email::1").doc_id == "email::1"
    assert Relation(predicate="owns", target_id="holding::vti").target_id == "holding::vti"
    r = ResolvedEntity(surface_form="Jane", canonical_id="person::jane_doe",
                       confidence=1.0, tier="exact")
    assert r.tier == "exact"


def test_adapter_protocols_importable() -> None:
    assert AliasTableAdapter is not None
    assert GraphAdapter is not None


def test_core_modules_implemented() -> None:
    """All three algorithm modules are implemented: resolve (M1.2),
    ontology authoring (M1.3), traverse (M1.4). Constraint tests live in
    their per-intent unit test files."""
    assert callable(resolve.resolve)                  # unit/test_resolve.py
    assert callable(traverse.traverse)                # unit/test_traverse.py
    assert callable(ontology.author_from_text)        # unit/test_ontology.py
    assert callable(ontology.dedup_candidates)
    assert callable(ontology.with_mirror_edges)
