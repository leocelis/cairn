#!/usr/bin/env python3
"""M3.1 — the adaptive gate decides whether/what to retrieve, before spending a token.

Always-on retrieval hurts (SRACG: -2.6 to -3.6pp); selective retrieval helps. This
gate (OP-33) returns a strategy in {none, grep, semantic, graph, composite} with
ZERO generative-LLM calls — `none` (skip retrieval) is a first-class answer.

Run:  .venv/bin/python examples/adaptive_gate_demo.py
"""

from __future__ import annotations

from cairn_retrieval import gate

# a couple of caller-supplied static label sets (built at ontology-authoring time)
PRIVATE = frozenset({"proj::internal"})
TAIL = frozenset({"person::obscure_researcher"})

CASES = [
    ("capital of France", ["geo::france"], "popular fact — model already knows"),
    ("what is the latest model pricing", [], "temporal marker -> must retrieve fresh"),
    ("how do org::acme and org::beta relate", ["org::acme", "org::beta"], "two entities"),
    ("summarize my internal project", ["proj::internal"], "private entity"),
    ("who is this obscure researcher", ["person::obscure_researcher"], "long-tail entity"),
    ("compare why these two approaches connect", ["x::a"], "relational, complex"),
]


def main() -> None:
    print("=" * 78)
    print("M3.1 — ADAPTIVE GATE  (LLM-free; strategy=none is a real answer)")
    print("=" * 78)
    print(f"\n{'query':<44}{'strategy':<11}{'stage':<7}why")
    print("-" * 78)
    for query, entities, _note in CASES:
        d = gate(query, entities=entities, private_ids=PRIVATE, tail_ids=TAIL)
        q = (query[:41] + "…") if len(query) > 42 else query
        print(f"{q:<44}{d.strategy:<11}{d.stage:<7}{d.reason}")

    print("\nStage-2 utility breakdown for 'capital of France' (popular vs long-tail):")
    for label, tail in (("popular", frozenset()), ("long-tail", TAIL | {"geo::france"})):
        d = gate("capital of France", entities=["geo::france"], tail_ids=tail)
        row = "  ".join(f"{t}={u:.3f}" for t, u in d.scores)
        print(f"  {label:<10} -> {d.strategy:<6} | {row}")
    print("\n-> popular entity: none wins (retrieval would add noise). tail entity: grep wins.")


if __name__ == "__main__":
    main()
