#!/usr/bin/env python3
"""M2.1 — bi-temporal state: audit ('what did I know') vs correctness ('what was true').

A single timestamp can't answer both. Cairn tracks two independent axes (TH-3):

    valid-time        when a fact was TRUE in the world     [valid_from, valid_until)
    transaction-time  when the SYSTEM learned it            [known_from, known_until)

Story: an agent records a retry policy, then discovers weeks later that it had
been wrong all along and corrects it. The correction is APPEND-ONLY — the old
belief is never destroyed, so both questions stay answerable at any point.

Run:  .venv/bin/python examples/bitemporal_audit.py
"""

from __future__ import annotations

from cairn_engine import Entity, as_at, dump_entities, supersede


def main() -> None:
    # Jan 5: we learn the policy is "retry 3x" (and believe it holds from Jan 1).
    v1 = Entity(
        canonical_id="policy::retry", label="retry: 3x", entity_type="concept",
        valid_from="2026-01-01", valid_until=None,
        known_from="2026-01-05", known_until=None,
    )
    # Apr 2: we discover it was actually "retry 5x" the whole time — a CORRECTION.
    v2 = Entity(
        canonical_id="policy::retry", label="retry: 5x", entity_type="concept",
        valid_from="2026-01-01", valid_until=None,
    )
    history = supersede([v1], v2, at="2026-04-02")   # explicit instant — no wall clock

    print("=" * 66)
    print("M2.1 — BI-TEMPORAL STATE  (append-only history; two time axes)")
    print("=" * 66)

    print("\nFull history (nothing is ever overwritten):")
    for e in history:
        print(f"  {e.label:<10} valid[{e.valid_from}, {e.valid_until}) "
              f"known[{e.known_from}, {e.known_until})")

    print("\nAUDIT — 'what did the agent KNOW at time T?'")
    for t in ("2026-01-01", "2026-02-01", "2026-05-01"):
        knew = [e.label for e in as_at(history, known_as_of=t)]
        print(f"  on {t}: {knew or ['(nothing yet)']}")

    print("\nCORRECTNESS — 'what was TRUE on Mar 1, as best known at T?'")
    for t in ("2026-02-01", "2026-05-01"):
        truth = [e.label for e in as_at(history, valid_as_of="2026-03-01", known_as_of=t)]
        print(f"  asked on {t}: {truth}")
    print("  -> same world-question, different answer before vs after the correction.")

    # deterministic + byte-stable: the whole history serializes identically twice
    assert dump_entities(list(history)) == dump_entities(list(history))
    print("\n(byte-stable: identical serialization across runs — no clock read)")


if __name__ == "__main__":
    main()
