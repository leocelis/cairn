#!/usr/bin/env python3
"""How an AI agent uses Cairn — the REAL integration pattern.

Division of labor:
    CAIRN  (deterministic)  ->  WHICH entities does this question refer to?
                                WHAT documents are connected to them?
    LLM    (generative)     ->  reason over that trusted context and answer.

The LLM never guesses entity identity and never hallucinates relationships —
it RECEIVES them. Cairn runs BEFORE the LLM call, costs zero tokens, and is
byte-stable; the single LLM call at the end gets a grounded prompt.

The `call_llm` below is a stand-in that PRINTS the exact prompt a real client
would send (swap the body for anthropic/openai — that is the whole change).
That one call is wrapped by ComplyEdge (examples/complyedge_guard.py): the
prompt is checked before it is sent and the answer before it is returned; a
blocked check stops the step and reports the rule IDs.

Run:  .venv/bin/python examples/agent_integration.py
"""

from __future__ import annotations

from collections.abc import Callable

from cairn_engine import Entity, InMemoryAliasTable, InMemoryGraph, Ref, Relation, resolve, traverse

# ---------------------------------------------------------------------------
# The user's EXISTING store (Cairn never holds this — it holds references)
# ---------------------------------------------------------------------------
DOC_STORE = {
    "doc::retry_decision": (
        "DECISION (2026-05-14): payment retries use exponential backoff with "
        "jitter, max 3 attempts. Circuit breaker opens BEFORE retry exhaustion."
    ),
    "doc::schwab_setup": (
        "The Schwab account (main brokerage) settles via ACH; payment failures "
        "here triggered the retry-policy review."
    ),
    "doc::cb_runbook": (
        "Circuit breaker: 5 failures -> open; while open return 503, no retry; "
        "reset after 30s."
    ),
}

# The frozen entity map (authored offline, human-approved — OP-35)
ENTITIES = [
    Entity(canonical_id="policy::payment_retry", label="Payment Retry Policy",
           entity_type="concept", aliases=("retry policy",),
           refs=(Ref(doc_id="doc::retry_decision"),),
           relations=(Relation("applies_to", "account::schwab_main"),
                      Relation("interacts_with", "concept::circuit_breaker"))),
    Entity(canonical_id="account::schwab_main", label="Schwab",
           entity_type="config", aliases=("my Schwab account",),
           refs=(Ref(doc_id="doc::schwab_setup"),)),
    Entity(canonical_id="concept::circuit_breaker", label="circuit breaker",
           entity_type="concept", refs=(Ref(doc_id="doc::cb_runbook"),)),
]

TABLE = InMemoryAliasTable.from_entities(ENTITIES)
GRAPH = InMemoryGraph.from_entities(TABLE.canonical_entities())


def call_llm(prompt: str) -> str:
    """Stand-in for the ONE generative call. Real version:

        client = anthropic.Anthropic()          # the AGENT's key, not cairn's
        return client.messages.create(model="claude-sonnet-5", max_tokens=500,
            messages=[{"role": "user", "content": prompt}]).content[0].text
    """
    print("┌─ EXACT PROMPT THE LLM RECEIVES " + "─" * 30)
    for line in prompt.splitlines():
        print("│ " + line)
    print("└" + "─" * 62)
    return "<LLM answer would be generated from the grounded prompt above>"


def agent_answer(question: str, llm: Callable[[str], str] = call_llm) -> str:
    """The agent loop: Cairn first (deterministic), LLM last (one call)."""
    print(f"\nUSER QUESTION: {question!r}")

    # 1) WHICH entities? — deterministic, zero tokens, byte-stable
    resolved, _ = resolve(question, table=TABLE)
    print("cairn.resolve  ->", [(r.surface_form, r.canonical_id, r.tier) for r in resolved])

    if not resolved:
        # closed world: no known entities -> nothing to ground; the agent may
        # answer from parametric knowledge (no context injected, no guessing)
        print("cairn: no known entities — answering without retrieval")
        return llm(f"Answer from general knowledge:\n\n{question}")

    # 2) WHAT is connected? — bounded traversal, hop-scored refs
    seen: dict[str, float] = {}
    for r in resolved:
        for hit in traverse(r.canonical_id, graph=GRAPH, depth=2).hits:
            seen[hit.ref.doc_id] = max(seen.get(hit.ref.doc_id, 0.0), hit.score)
    ranked = sorted(seen.items(), key=lambda kv: (-kv[1], kv[0]))
    print("cairn.traverse ->", ranked)

    # 3) fetch content from the USER'S store via the refs (cairn holds pointers)
    context = "\n".join(
        f"[{doc_id} | relevance {score:.2f}]\n{DOC_STORE[doc_id]}"
        for doc_id, score in ranked if doc_id in DOC_STORE
    )

    # 4) ONE grounded LLM call
    prompt = (
        "Answer using ONLY the context below. Cite doc ids.\n\n"
        f"## Context (resolved deterministically by cairn)\n{context}\n\n"
        f"## Question\n{question}"
    )
    return llm(prompt)


if __name__ == "__main__":
    from complyedge_guard import ComplianceBlocked, guard

    guarded_llm = guard(call_llm)
    for q in ("How does the retry policy affect my Schwab account?",
              "What is the capital of France?"):
        try:
            agent_answer(q, llm=guarded_llm)
        except ComplianceBlocked as blocked:
            print(f"BLOCKED ({blocked.direction}) by ComplyEdge rules: {blocked.rule_ids}")
