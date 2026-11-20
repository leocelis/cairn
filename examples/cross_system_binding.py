#!/usr/bin/env python3
"""M2.4 — bind a canonical entity to the RIGHT system-specific id at tool-arg time.

The cold-silo failure: an agent resolves "Acme" correctly and picks the right
tool, but passes the CRM id where the Slack API wanted a channel id. Cairn's
cross-system index makes that binding a lookup, not a guess — and a miss is an
explicit None (closed world), never a fabricated id.

Run:  .venv/bin/python examples/cross_system_binding.py
"""

from __future__ import annotations

from cairn_engine import CrossSystemIndex, Entity


def main() -> None:
    # entities carry their known system ids under metadata["system_ids"]
    entities = [
        Entity(canonical_id="org::acme", label="Acme Inc", entity_type="org",
               metadata={"system_ids": {"crm": "cus_42", "slack": "C0299", "github": "acme-inc"}}),
        Entity(canonical_id="org::beta", label="Beta LLC", entity_type="org",
               metadata={"system_ids": {"crm": "cus_7"}}),  # not in Slack/GitHub
    ]
    idx = CrossSystemIndex.from_entities(entities)

    print("=" * 66)
    print("M2.4 — CROSS-SYSTEM ENTITY INDEX  (canonical -> right system id)")
    print("=" * 66)

    print("\nForward — 'the agent resolved org::acme; which id per tool?'")
    for system in ("crm", "slack", "github", "zendesk"):
        bound = idx.bind("org::acme", system=system)
        shown = repr(bound) if bound is not None else "None  (not in this system — no guess)"
        print(f"    {system:<8} -> {shown}")

    print("\nReverse — 'a Slack webhook fired for channel C0299; who is that?'")
    print(f"    slack/C0299 -> {idx.canonical_for(system='slack', external_id='C0299')}")
    print(f"    crm/cus_7   -> {idx.canonical_for(system='crm', external_id='cus_7')}")
    print(f"    crm/unknown -> {idx.canonical_for(system='crm', external_id='cus_999')}  (closed world)")

    print("\nCoverage — 'which systems is each entity actually known in?'")
    for cid in ("org::acme", "org::beta"):
        print(f"    {cid:<11} {list(idx.systems(cid))}")

    print("\n-> bind() returns None for a system the entity isn't in — the agent")
    print("   must NOT call that tool with a made-up id (the hallucinated-binding")
    print("   failure cairn exists to remove).")


if __name__ == "__main__":
    main()
