"""Bi-temporal state — point-in-time queries and append-only supersession (M2.1, TH-3).

A fact carries TWO independent time axes (TH-3):

  * valid-time        [valid_from,  valid_until)   — when the fact was TRUE in the world
  * transaction-time  [known_from,  known_until)   — when the SYSTEM knew the fact

One timestamp conflates two different questions ("what was true" vs "what did I
know"). Both axes let an agent answer audit ("what did I know on Tuesday") AND
correctness ("what was actually true then"), and let corrections be recorded
WITHOUT destroying history.

Design decisions (pinned in intents/entity_bitemporal_intent.yaml):
  * Open-end sentinel (OQ-4): None == +infinity. Every interval is half-open
    [start, end): it INCLUDES start and EXCLUDES end. `_within` is the ONE place
    this rule is implemented — traverse imports it too.
  * Transaction-time is a caller-supplied EXPLICIT instant. This module never
    reads the wall clock (no now()/today()/time()) — a hidden clock read would
    break byte-stability and the determinism invariant.

These are pure functions over immutable value records (TH-5): they never mutate a
frozen Entity/Relation; a "change" produces new versions and keeps the old ones.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable, Protocol, TypeVar, cast, runtime_checkable

__all__ = ["as_at", "supersede"]


@runtime_checkable
class Temporal(Protocol):
    """Anything carrying the four bi-temporal columns — Entity and Relation both do."""

    valid_from: str | None
    valid_until: str | None
    known_from: str | None
    known_until: str | None


T = TypeVar("T", bound=Temporal)


def _within(start: str | None, end: str | None, at: str | None) -> bool:
    """Half-open membership on ONE axis, `at` in [start, end).

    OQ-4 sentinel: None bound == open (unbounded) on that side. A None query
    instant (`at is None`) means 'do not filter this axis' -> always in.
    ISO 8601 strings order correctly under lexicographic comparison.
    """
    if at is None:
        return True
    return (start is None or start <= at) and (end is None or at < end)


def as_at(
    facts: Iterable[T],
    *,
    valid_as_of: str | None = None,
    known_as_of: str | None = None,
) -> tuple[T, ...]:
    """Point-in-time slice over BOTH axes (input order preserved).

    Keeps each fact whose valid-time interval contains `valid_as_of` AND whose
    transaction-time interval contains `known_as_of`. None on an axis disables
    filtering on that axis only, so:

        as_at(facts)                              -> everything (both axes open)
        as_at(facts, valid_as_of="2026-03-10")    -> what was TRUE on Mar 10
        as_at(facts, known_as_of="2026-03-10")    -> what was KNOWN on Mar 10
        as_at(facts, valid_as_of=v, known_as_of=k)-> true at v as best known at k
    """
    return tuple(
        f
        for f in facts
        if _within(f.valid_from, f.valid_until, valid_as_of)
        and _within(f.known_from, f.known_until, known_as_of)
    )


def supersede(history: Iterable[T], new_fact: T, *, at: str) -> tuple[T, ...]:
    """Record a correction append-only: close the current version(s), append the new one.

    `history` is the caller-scoped set of versions of ONE fact. Every version
    that is still current knowledge (known_until is None) is CLOSED at `at` (a
    new copy with known_until=at — the originals are never mutated); `new_fact`
    is stamped known_from=at and appended as the now-current version. Nothing is
    dropped, so the full audit chain is reconstructable with `as_at`.

    `at` is an explicit ISO 8601 transaction-time instant — never derived from
    the wall clock (determinism invariant).
    """
    # replace() returns the same concrete type at runtime; the cast is only to
    # satisfy the checker, which can't see that a Temporal T is a dataclass.
    def _close(f: T) -> T:
        return cast(T, replace(cast(Any, f), known_until=at)) if f.known_until is None else f

    closed = tuple(_close(f) for f in history)
    return (*closed, cast(T, replace(cast(Any, new_fact), known_from=at)))
