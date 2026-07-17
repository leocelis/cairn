"""Constraint tests for intents/ontology_authoring_intent.yaml.

Each test maps 1:1 to a constraint. Golden fixtures hand-computed. Stdlib-only.
"""

from __future__ import annotations

import socket

import pytest

from cairn_engine.adapters.jsonfile import dump_entities, load_entities
from cairn_engine.adapters.memory import InMemoryAliasTable
from cairn_engine.entity.model import Entity, Ref, Relation
from cairn_engine.entity.ontology import (
    Candidate,
    author_from_text,
    dedup_candidates,
    with_mirror_edges,
)
from cairn_engine.entity.resolve import resolve

_TEXT = (
    'Most teams automate labor. The Decision Layer sits above the tools, and '
    '"entity resolution" is the foundation. Ask World Models anything.'
)


# -- constraint: heuristic_extractor_deterministic -----------------------------

def test_heuristic_extractor_deterministic() -> None:
    cands = author_from_text(_TEXT, source="post::demo")
    surfaces = [c.surface for c in cands]
    # golden (hand-computed, EXACT): capitalized runs stopword-trimmed
    # ('Most' rejected; 'The Decision Layer' -> 'Decision Layer';
    # 'Ask World Models' -> 'World Models') + the quoted phrase, in order.
    assert surfaces == ["Decision Layer", "World Models", "entity resolution"]
    # deterministic: same text -> byte-identical candidates
    assert repr(cands) == repr(author_from_text(_TEXT, source="post::demo"))
    # provenance recorded
    assert all(c.extractor == "heuristic" and c.source == "post::demo" for c in cands)
    # stopword filter (Rule-5): pronouns, contractions AND sentence-start
    # function words are never candidates (real corpus leaked 'Every','Because'…)
    noisy = author_from_text(
        "I said. You did. It's fine. Every Because After Someone Just Should Same.",
        source="s")
    surfaces_noisy = [c.surface for c in noisy]
    for w in ("I", "You", "It's", "Every", "Because", "After", "Someone", "Just", "Should", "Same"):
        assert w not in surfaces_noisy, w
    # but real domain words that merely look common are NOT excluded
    kept = [c.surface for c in author_from_text("We use Cloud, API and ROI daily.", source="s")]
    assert kept == ["Cloud", "API", "ROI"]


# -- constraint: extractors_explicit_never_autodetected --------------------------

def test_extractor_strings_rejected_callables_accepted() -> None:
    for bad in ("llm", "gliner", "discriminative"):
        with pytest.raises(ValueError):
            author_from_text("text", source="s", extractor=bad)

    def my_llm_wrapper(text: str) -> list[str]:  # the caller owns the boundary
        return ["Custom Concept"]

    cands = author_from_text("whatever", source="s", extractor=my_llm_wrapper)
    assert [c.surface for c in cands] == ["Custom Concept"]
    assert cands[0].extractor == "my_llm_wrapper"
    # and the module itself imports no third-party packages
    import pathlib

    import cairn_engine.entity.ontology as mod

    text = pathlib.Path(mod.__file__).read_text()
    for banned in ("rapidfuzz", "gliner", "openai", "anthropic", "requests", "httpx", "numpy"):
        assert f"import {banned}" not in text and f"from {banned}" not in text


# -- constraint: dedup_tier1_exact_normalized ------------------------------------

def test_dedup_tier1_exact_normalized() -> None:
    cands = [
        Candidate("Entity Resolution", "concept", "s", "heuristic"),
        Candidate("entity-resolution", "concept", "s", "heuristic"),   # same normalized
        Candidate("World Models", "concept", "s", "heuristic"),
    ]
    report = dedup_candidates(cands)
    assert [c.surface for c in report.unique] == ["Entity Resolution", "World Models"]
    assert len(report.duplicates) == 1
    kept, dropped = report.duplicates[0]
    assert kept.surface == "Entity Resolution" and dropped.surface == "entity-resolution"
    # against an existing table's normals
    report2 = dedup_candidates(
        [Candidate("World Models", "concept", "s", "heuristic")],
        existing_normals=["world models"],
    )
    assert report2.unique == ()
    # F11: the `kept` side is a sentinel pointing at the existing normal
    kept2, dropped2 = report2.duplicates[0]
    assert kept2.extractor == "existing_table" and kept2.surface == "world models"
    assert dropped2.surface == "World Models"


# -- constraint: dedup_tier2_minhash_tokensort_gated -------------------------------

def test_dedup_tier2_minhash_tokensort() -> None:
    # typo pair -> token-sort >= 0.85 -> duplicate, first kept
    report = dedup_candidates([
        Candidate("payment retry policy", "concept", "s", "heuristic"),
        Candidate("payment retry polcy", "concept", "s", "heuristic"),
    ])
    assert [c.surface for c in report.unique] == ["payment retry policy"]
    assert report.review_pairs == ()
    # low-entropy pair: fuzzy skipped entirely -> both kept
    report2 = dedup_candidates([
        Candidate("aa", "concept", "s", "heuristic"),
        Candidate("ab", "concept", "s", "heuristic"),
    ])
    assert len(report2.unique) == 2
    # deterministic across runs
    cands = [
        Candidate("The Decision Layer", "concept", "s", "heuristic"),
        Candidate("the decision layers", "concept", "s", "heuristic"),
        Candidate("World Models", "concept", "s", "heuristic"),
    ]
    assert repr(dedup_candidates(cands)) == repr(dedup_candidates(cands))


# -- constraint: mirror_edges_deterministic -----------------------------------------

def test_mirror_edges_deterministic() -> None:
    post = Entity(canonical_id="post::a", label="A", entity_type="document",
                  relations=(Relation("mentions", "concept::x",
                                      valid_from="2026-01-01", valid_until="2026-06-01"),))
    concept = Entity(canonical_id="concept::x", label="x", entity_type="concept")
    out = with_mirror_edges([post, concept])
    by_id = {e.canonical_id: e for e in out}
    mirrors = by_id["concept::x"].relations
    assert mirrors == (Relation("mentioned_in", "post::a",
                                valid_from="2026-01-01", valid_until="2026-06-01"),)
    # validity window preserved; original entity untouched (new records returned)
    assert concept.relations == ()
    # idempotent: applying twice adds nothing
    out2 = with_mirror_edges(list(out))
    assert repr(sorted(out2, key=lambda e: e.canonical_id)) == repr(
        sorted(out, key=lambda e: e.canonical_id))
    # edges to targets OUTSIDE the entity set are not mirrored (closed world)
    lone = Entity(canonical_id="p::l", label="l", entity_type="document",
                  relations=(Relation("mentions", "concept::ghost"),))
    assert with_mirror_edges([lone]) == (lone,)


# -- constraint: serialization_roundtrip_deterministic --------------------------------

def test_serialization_roundtrip_deterministic() -> None:
    entities = [
        Entity(canonical_id="concept::x", label="x", entity_type="concept",
               aliases=("ex", "the x"), refs=(Ref(doc_id="post::a", locator="p1"),),
               relations=(Relation("mentioned_in", "post::a"),), metadata={"k": "v"}),
        Entity(canonical_id="post::a", label="A", entity_type="document",
               valid_from="2026-01-01", source="wp"),
    ]
    blob = dump_entities(entities)
    loaded = load_entities(blob)
    assert loaded == tuple(sorted(entities, key=lambda e: e.canonical_id))
    # byte-stable: dump(load(dump(x))) == dump(x), and input order irrelevant
    assert dump_entities(list(loaded)) == blob
    assert dump_entities(list(reversed(entities))) == blob
    with pytest.raises(ValueError):
        load_entities('{"schema_version": 99, "entities": []}')


# -- constraint: staging_never_hotpath_never_network ------------------------------------

def test_staging_and_offline() -> None:
    real_socket = socket.socket

    def _no_network(*a: object, **k: object) -> object:
        raise AssertionError("network call attempted during authoring")

    socket.socket = _no_network  # type: ignore[misc, assignment]
    try:
        cands = author_from_text(_TEXT, source="post::demo")
        report = dedup_candidates(cands)
    finally:
        socket.socket = real_socket  # type: ignore[misc]
    # everything staged — nothing auto-enters any table
    assert all(c.status == "pending_review" for c in report.unique)
    # the human gate: approval is an explicit act
    table = InMemoryAliasTable()
    approved = report.unique[0].to_entity("concept::decision_layer")
    table.add(approved)
    table.freeze()
    assert table.has_id("concept::decision_layer")


# -- joint satisfaction: ALL constraints on ONE pipeline run ------------------------------

def test_joint_authoring_pipeline() -> None:
    """extract -> dedup -> approve -> mirror -> serialize -> load -> freeze -> resolve."""
    def pipeline() -> str:
        cands = author_from_text(_TEXT, source="post::demo")                 # C1 deterministic
        report = dedup_candidates(cands + [
            Candidate("the decision layer", "concept", "s2", "heuristic"),   # tier-1 dup
        ])
        assert all(c.status == "pending_review" for c in report.unique)      # C7 staging
        approved = [
            c.to_entity(f"concept::{'_'.join(c.surface.lower().split())}")
            for c in report.unique
        ]
        post = Entity(canonical_id="post::demo", label="Demo", entity_type="document",
                      relations=tuple(Relation("mentions", e.canonical_id) for e in approved))
        entities = with_mirror_edges([post, *approved])                      # C5 mirrors
        blob = dump_entities(list(entities))                                 # C6 serialization
        loaded = load_entities(blob)
        table = InMemoryAliasTable()
        for e in loaded:
            table.add(e)
        table.freeze()                                                       # the human gate closed
        resolved, _ = resolve("tell me about the Decision Layer", table=table)
        assert any(r.canonical_id == "concept::decision_layer" for r in resolved)
        return blob

    assert pipeline() == pipeline()                                          # byte-stable end to end
    with pytest.raises(ValueError):
        author_from_text("x", source="s", extractor="llm")                   # C2 explicit callables

def test_long_runs_chunk_without_dropping_tokens() -> None:
    """F9: recall-oriented means NEVER dropping data — a 7-token capitalized
    run emits two chunks (5 + 2), not one truncated candidate."""
    cands = author_from_text("Alpha Beta Gamma Delta Epsilon Zeta Eta ended.", source="s")
    surfaces = [c.surface for c in cands]
    assert "Alpha Beta Gamma Delta Epsilon" in surfaces
    assert "Zeta Eta" in surfaces


def test_alias_conflict_gate() -> None:
    """F19: the OP-35 conflict-audit gate — surfaces mapping to 2+ ids."""
    from cairn_engine.entity.ontology import find_alias_conflicts

    conflicts = find_alias_conflicts([
        Entity(canonical_id="auth::user", label="auth user", entity_type="concept",
               aliases=("user",)),
        Entity(canonical_id="payment::user", label="payment user", entity_type="concept",
               aliases=("user",)),
        Entity(canonical_id="c::solo", label="solo", entity_type="concept"),
    ])
    assert conflicts == (("user", ("auth::user", "payment::user")),)


def test_metadata_json_fidelity_and_validation() -> None:
    """F6/F12: metadata contents survive round-trip; non-JSON-native values
    fail loudly at dump; frozen records can't be mutated through metadata."""
    import pytest as _pytest

    from cairn_engine.adapters.jsonfile import dump_entities, load_entities

    e = Entity(canonical_id="c::m", label="m", entity_type="concept",
               metadata={"k": "v", "n": 3, "nested": {"a": [1, 2]}})
    (loaded,) = load_entities(dump_entities([e]))
    assert dict(loaded.metadata) == {"k": "v", "n": 3, "nested": {"a": [1, 2]}}  # contents, not just ==
    # non-JSON-native (tuple) -> loud TypeError at dump, never silent corruption
    bad = Entity(canonical_id="c::b", label="b", entity_type="concept",
                 metadata={"tup": (1, 2)})
    with _pytest.raises(TypeError):
        dump_entities([bad])
    # F12: metadata is read-only on the frozen record
    with _pytest.raises(TypeError):
        e.metadata["k"] = "mutated"  # type: ignore[index]


def test_relation_weight_roundtrips_and_mirrors() -> None:
    """Edge weight (term frequency) survives serialization and is carried onto
    the mirror edge (TF-IDF foundation)."""
    from cairn_engine.adapters.jsonfile import dump_entities, load_entities

    e = Entity(canonical_id="post::a", label="A", entity_type="document",
               relations=(Relation("mentions", "concept::x", weight=3.0),))
    (loaded,) = load_entities(dump_entities([e]))
    assert loaded.relations[0].weight == 3.0                       # round-trips
    # default weight is 1.0 and also round-trips
    d = Entity(canonical_id="post::b", label="B", entity_type="document",
               relations=(Relation("mentions", "concept::x"),))
    assert load_entities(dump_entities([d]))[0].relations[0].weight == 1.0
    # mirror carries the same weight
    concept = Entity(canonical_id="concept::x", label="x", entity_type="concept")
    out = {ent.canonical_id: ent for ent in with_mirror_edges([e, concept])}
    assert out["concept::x"].relations[0].weight == 3.0
