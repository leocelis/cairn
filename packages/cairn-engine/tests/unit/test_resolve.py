"""Constraint tests for intents/entity_resolution_intent.yaml.

Each test name maps 1:1 to a constraint in the module intent. Golden fixtures
are hand-computed (execution_derived oracles). Runs on stdlib only — this
environment has zero third-party packages, which is itself the proof of the
no_autodetected_accelerators constraint's premise.
"""

from __future__ import annotations

import socket

from cairn_engine.adapters.memory import InMemoryAliasTable
from cairn_engine.entity.model import Entity
from cairn_engine.entity.normalize import normalize, shannon_entropy_bits, tokenize
from cairn_engine.entity.resolve import ResolverConfig, resolve, token_sort_ratio


def _table() -> InMemoryAliasTable:
    t = InMemoryAliasTable()
    t.add(Entity(canonical_id="doc::payment_retry_policy", label="Payment Retry Policy",
                 entity_type="document", aliases=("retry policy",)))
    t.add(Entity(canonical_id="account::schwab_main", label="Schwab",
                 entity_type="config", aliases=("my Schwab account", "schwab-main")))
    t.add(Entity(canonical_id="concept::payment", label="payment", entity_type="concept"))
    t.add(Entity(canonical_id="auth::user", label="auth user", entity_type="concept",
                 aliases=("user",)))
    t.add(Entity(canonical_id="payment::user", label="payment user", entity_type="concept",
                 aliases=("user",)))
    return t.freeze()


# -- constraint: normalization_is_nfkc_casefold_collapse ---------------------

def test_normalization_nfkc_casefold_collapse() -> None:
    # golden fixtures (hand-computed)
    assert normalize("Payment-Retry  POLICY!") == "payment retry policy"
    assert normalize("Ｓｃｈｗａｂ") == "schwab"          # NFKC fullwidth -> ascii
    assert normalize("  --  ") == ""                      # separators only
    assert normalize("AI-OS") == "ai os"
    assert tokenize("Payment-Retry POLICY") == ("payment", "retry", "policy")
    assert tokenize("") == ()
    # pure function: same input -> same output
    assert normalize("Ünïted—Stätes") == normalize("Ünïted—Stätes")


# -- constraint: gazetteer_scan_longest_match_deterministic ------------------

def test_scan_longest_match_wins_and_ordering() -> None:
    table = _table()
    resolved, unresolved = resolve(
        "does the Payment Retry Policy affect my Schwab account today?", table=table
    )
    assert unresolved == []
    ids = [r.canonical_id for r in resolved]
    # longest match won: 'payment retry policy' (3 tokens) beat nested 'payment'
    assert "doc::payment_retry_policy" in ids
    assert "concept::payment" not in ids
    # 'my schwab account' (3-token alias) matched
    assert "account::schwab_main" in ids
    # output order = query position
    assert ids.index("doc::payment_retry_policy") < ids.index("account::schwab_main")
    # duplicate occurrences dedupe to one (surface, canonical) pair
    resolved2, _ = resolve("payment payment payment", table=table)
    assert [r.canonical_id for r in resolved2] == ["concept::payment"]
    # empty query
    assert resolve("", table=table) == ([], [])


# -- constraint: fuzzy_tier_thresholded_and_entropy_gated --------------------

def test_fuzzy_threshold_and_entropy_gate() -> None:
    table = _table()
    # typo above threshold resolves via fuzzy
    resolved, unresolved = resolve("", table=table, mentions=["Payment Retry Polcy"])
    assert unresolved == []
    assert [r.canonical_id for r in resolved] == ["doc::payment_retry_policy"]
    assert resolved[0].tier == "fuzzy"
    assert resolved[0].confidence >= 0.85
    # nonsense below threshold -> unresolved
    _, missed = resolve("", table=table, mentions=["zzz qqq vvv"])
    assert missed == ["zzz qqq vvv"]
    # entropy gate: 'aa' has entropy 0.0 < 1.5 -> fuzzy skipped -> unresolved
    assert shannon_entropy_bits("aa") < 1.5
    _, missed2 = resolve("", table=table, mentions=["aa"])
    assert missed2 == ["aa"]
    # gate only affects FUZZY: low-entropy exact alias still resolves via Tier 1
    resolved3, un3 = resolve("", table=table, mentions=["user"])
    assert un3 == [] and len(resolved3) == 2
    # fuzzy can be disabled by config
    _, missed4 = resolve("", table=table, mentions=["Payment Retry Polcy"],
                         config=ResolverConfig(enable_fuzzy=False))
    assert missed4 == ["Payment Retry Polcy"]


# -- constraint: ambiguity_returns_all_candidates -----------------------------

def test_ambiguous_surface_returns_all_candidates() -> None:
    table = _table()
    resolved, unresolved = resolve("", table=table, mentions=["user"])
    assert unresolved == []
    # ALL candidates, deterministic order: confidence desc, then canonical_id asc
    assert [r.canonical_id for r in resolved] == ["auth::user", "payment::user"]


# -- constraint: no_autodetected_accelerators --------------------------------

def test_no_third_party_imports_on_default_path() -> None:
    import pathlib

    import cairn_engine.entity.resolve as resolve_mod

    src_dir = pathlib.Path(resolve_mod.__file__).parent
    banned = ("rapidfuzz", "numpy", "requests", "sentence_transformers", "gliner", "httpx")
    for py in (*src_dir.glob("*.py"), *(src_dir.parent / "adapters").glob("*.py")):
        text = py.read_text()
        for name in banned:
            assert f"import {name}" not in text and f"from {name}" not in text, (
                f"{py.name} imports third-party '{name}' on the default path"
            )
        # dynamic-import evasion is banned too (F10)
        assert "importlib" not in text and "__import__" not in text, py.name


# -- constraint: closed_world_never_synthesizes -------------------------------

def test_miss_goes_to_unresolved_never_synthesized() -> None:
    table = _table()
    resolved, unresolved = resolve(
        "totally unknown thing", table=table, mentions=["totally unknown thing"]
    )
    assert resolved == []
    assert unresolved == ["totally unknown thing"]
    # property oracle: every id ever returned is a member of the table
    r_all, _ = resolve("payment retry policy and my schwab account and user stuff", table=table)
    assert all(table.has_id(r.canonical_id) for r in r_all)


# -- constraint: byte_stable_zero_llm_zero_network ----------------------------

def test_byte_stable_and_offline() -> None:
    q = "does the Payment Retry Policy affect my Schwab account?"
    m = ["Payment Retry Polcy", "user", "nope nope"]

    def run() -> str:
        table = _table()  # rebuilt from scratch each run
        a = resolve(q, table=table)
        b = resolve(q, table=table, mentions=m)
        return repr((a, b))

    # identical across repeated runs and independently rebuilt tables
    assert run() == run() == run()

    # offline: sockets disabled -> still works
    real_socket = socket.socket

    def _no_network(*a: object, **k: object) -> object:
        raise AssertionError("network call attempted on the hot path")

    socket.socket = _no_network  # type: ignore[misc, assignment]
    try:
        out = run()
    finally:
        socket.socket = real_socket  # type: ignore[misc]
    assert out == run()


# -- joint satisfaction: ALL constraints on ONE output ------------------------

def test_joint_all_constraints_on_one_resolve() -> None:
    table = _table()
    q = "does the Payment-Retry POLICY affect my Schwab account? user asks."
    run1 = resolve(q, table=table, mentions=None)
    resolved, unresolved = run1

    # normalization: hyphen/case did not break the 3-token alias match
    ids = [r.canonical_id for r in resolved]
    assert "doc::payment_retry_policy" in ids                      # C1 normalization
    assert "concept::payment" not in ids                           # C2 longest-match
    assert ids.index("doc::payment_retry_policy") == 0             # C2 ordering
    both_users = [i for i in ids if i.endswith("::user")]
    assert both_users == ["auth::user", "payment::user"]           # C4 ambiguity: all, ordered
    assert all(table.has_id(i) for i in ids) and unresolved == []  # C6 closed world
    assert repr(run1) == repr(resolve(q, table=table))             # C7 byte-stable
    # C3 (fuzzy) exercised on the same table within the same contract:
    fz, _ = resolve("", table=table, mentions=["Payment Retry Polcy"])
    assert fz and fz[0].tier == "fuzzy" and fz[0].confidence >= 0.85
    # C5 stdlib-only is proven by this environment having no third-party packages.


# -- supporting: token_sort_ratio sanity ---------------------------------------

def test_token_sort_ratio_deterministic_bounds() -> None:
    assert token_sort_ratio("payment retry policy", "payment retry policy") == 1.0
    assert token_sort_ratio("retry policy payment", "payment retry policy") == 1.0  # order-free
    assert token_sort_ratio("", "anything") == 0.0
    s = token_sort_ratio("payment retry polcy", "payment retry policy")
    assert 0.85 <= s < 1.0
    assert s == token_sort_ratio("payment retry polcy", "payment retry policy")
    # NO subset freebie (the v0.1.1 finding): 'payment' alone must NOT score 1.0
    assert token_sort_ratio("payment retry polcy", "payment") < 0.85


# -- Tier 4: the opt-in LLM arbiter (OP-28: 2+ candidates in [0.70, 0.85) ONLY) --

def _band_table() -> InMemoryAliasTable:
    """Two aliases engineered so one mention scores in-band vs BOTH:
    token_sort('aaaa bbbb czzz', 'aaaa bbbb cccc'/'aaaa bbbb ccdd')
    = 2*11/28 ~= 0.7857 in [0.70, 0.85), for each alias."""
    return InMemoryAliasTable.from_entities([
        Entity(canonical_id="x::one", label="aaaa bbbb cccc", entity_type="concept"),
        Entity(canonical_id="x::two", label="aaaa bbbb ccdd", entity_type="concept"),
    ])


def test_arbiter_fires_only_in_band_and_cannot_mint() -> None:
    table = _table()
    calls: list[tuple[str, tuple]] = []

    def arbiter(surface: str, candidates: tuple) -> str | None:
        calls.append((surface, candidates))
        return candidates[0].canonical_id  # deterministic stub: pick first

    cfg = ResolverConfig(arbiter=arbiter)

    # exact/normalized hits are NEVER arbitrated (confidence 1.0 is outside the
    # band — OP-28's gate is band-only). Ambiguity returns ALL candidates.
    resolve("", table=table, mentions=["Schwab"], config=cfg)
    resolved, _ = resolve("", table=table, mentions=["user"], config=cfg)
    assert calls == []
    assert [r.canonical_id for r in resolved] == ["auth::user", "payment::user"]

    # fuzzy >= 0.85: resolves via Tier 2, arbiter NOT consulted
    resolved2, _ = resolve("", table=table, mentions=["Payment Retry Polcy"], config=cfg)
    assert calls == [] and resolved2[0].tier == "fuzzy"

    # POSITIVE band case (F10): 2+ distinct candidates in [0.70, 0.85) -> fires
    band_table = _band_table()
    resolved3, _ = resolve("", table=band_table, mentions=["aaaa bbbb czzz"], config=cfg)
    assert len(calls) == 1
    assert [c.canonical_id for c in calls[0][1]] == ["x::one", "x::two"]  # FULL pool
    assert [r.canonical_id for r in resolved3] == ["x::one"]
    assert resolved3[0].tier == "llm" and 0.70 <= resolved3[0].confidence < 0.85

    # single in-band candidate: not genuine ambiguity -> no arbiter, unresolved
    calls.clear()
    single = InMemoryAliasTable.from_entities(
        [Entity(canonical_id="x::one", label="aaaa bbbb cccc", entity_type="concept")])
    _, missed_single = resolve("", table=single, mentions=["aaaa bbbb czzz"], config=cfg)
    assert calls == [] and missed_single == ["aaaa bbbb czzz"]

    # arbiter answer outside the candidate set is IGNORED (pick, never mint)
    _, missed_mint = resolve("", table=band_table, mentions=["aaaa bbbb czzz"],
                             config=ResolverConfig(arbiter=lambda s, c: "concept::minted"))
    assert missed_mint == ["aaaa bbbb czzz"]

    # abstain (None) -> unresolved, never synthesized
    _, missed = resolve("", table=band_table, mentions=["aaaa bbbb czzz"],
                        config=ResolverConfig(arbiter=lambda s, c: None))
    assert missed == ["aaaa bbbb czzz"]

    # DEFAULT path (no arbiter): band -> unresolved; byte-stable
    a = resolve("", table=band_table, mentions=["aaaa bbbb czzz"])
    b = resolve("", table=band_table, mentions=["aaaa bbbb czzz"])
    assert a[1] == ["aaaa bbbb czzz"] and repr(a) == repr(b)


def test_scan_partial_overlap_policy_pinned() -> None:
    """F14: aliases 'a b' + 'b c' over query 'a b c' — longest/leftmost wins,
    the overlapped alias is not matched. Pinned so covered[] regressions show."""
    table = InMemoryAliasTable.from_entities([
        Entity(canonical_id="e::ab", label="alpha beta", entity_type="concept"),
        Entity(canonical_id="e::bc", label="beta gamma", entity_type="concept"),
    ])
    resolved, _ = resolve("alpha beta gamma", table=table)
    assert [r.canonical_id for r in resolved] == ["e::ab"]
