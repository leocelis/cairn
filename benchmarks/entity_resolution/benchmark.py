#!/usr/bin/env python3
"""Entity-resolution grounding benchmark for cairn-engine.

Question measured
-----------------
When a downstream consumer (an agent, a pipeline, a tool call) must act on an
entity referenced by name, does feeding it Cairn's deterministic resolution
raise the rate at which it produces the CORRECT stored canonical id — versus the
common baseline of *deriving* the id from the name (slugify)?

Two resolvers, same tasks, exact-match scoring against a known ground truth:

    BASELINE  slugify(name)              — derive the id (what code/agents do today)
    CAIRN     resolve(name) -> id        — look the id up in a frozen alias table

An optional --llm mode replaces the slugify baseline with a real model (the
consumer "guesses" the id), and feeds Cairn's candidates to the same model in the
treatment arm — to confirm the deterministic result holds with a model in the loop.

Dataset
-------
Fully synthetic and public — classic fictional companies (Contoso, Fabrikam,
Hooli, Initech, …) and generic names. No real, private, or personal data. It is
built to mirror a condition every real datastore accumulates: stored ids that are
NOT a clean slugify of the current display name (legacy imports, renames,
abbreviations, manual edits). That is exactly the case a lookup handles and a
derivation cannot.

Reproduce
---------
    pip install cairn-engine
    python benchmark.py            # deterministic, no API key, byte-stable
    python benchmark.py --llm      # optional: real model in the loop (needs OPENAI_API_KEY)
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from dataclasses import dataclass, field

from cairn_engine import Entity, InMemoryAliasTable, resolve


# --------------------------------------------------------------------------- #
# Synthetic, public dataset                                                   #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Item:
    kind: str                       # company | person | stock
    canonical_id: str               # the STORED id (ground truth)
    name: str                       # the reference a user/agent would use
    category: str                   # for the results breakdown
    aliases: tuple[str, ...] = field(default_factory=tuple)


DATASET: list[Item] = [
    # -- companies whose stored id IS a clean slugify of the name (control) ----
    Item("company", "northwind-traders", "Northwind Traders", "company: clean id"),
    Item("company", "fabrikam", "Fabrikam", "company: clean id"),
    Item("company", "adventure-works", "Adventure Works", "company: clean id"),
    Item("company", "tailspin-toys", "Tailspin Toys", "company: clean id"),
    Item("company", "proseware", "Proseware", "company: clean id"),
    # -- companies whose stored id is NOT re-derivable (legacy / abbreviated) --
    Item("company", "globex-inc", "Globex AI Inc", "company: irregular id"),
    Item("company", "initech", "Initech.io", "company: irregular id"),
    Item("company", "hooli-net", "Hooli Networks", "company: irregular id"),
    Item("company", "umbrella-corp", "Umbrella Corporation", "company: irregular id"),
    Item("company", "stark", "Stark Industries LLC", "company: irregular id"),
    Item("company", "wayne-ent", "Wayne Enterprises", "company: irregular id"),
    Item("company", "cyberdyne-sys", "Cyberdyne Systems", "company: irregular id"),
    # -- people whose slug is a clean first-last (control) ---------------------
    Item("person", "sam-carter", "Sam Carter", "person: clean id"),
    Item("person", "alex-rivera", "Alex Rivera", "person: clean id"),
    Item("person", "jordan-lee", "Jordan Lee", "person: clean id"),
    Item("person", "riya-patel", "Riya Patel", "person: clean id"),
    # -- people whose name has punctuation/accents (LLM baseline stumbles) -----
    Item("person", "sam-o-brien", "Sam O'Brien", "person: punctuation/accents"),
    Item("person", "renee-dubois", "Renée Dubois", "person: punctuation/accents"),
    Item("person", "jose-garcia", "José García", "person: punctuation/accents"),
    # -- stocks referenced by ticker (control) --------------------------------
    Item("stock", "HOOL", "HOOL", "stock: ticker", aliases=("Hooli Networks",)),
    Item("stock", "NRTH", "NRTH", "stock: ticker", aliases=("Northwind Traders",)),
    Item("stock", "GLBX", "GLBX", "stock: ticker", aliases=("Globex",)),
]


def build_table() -> InMemoryAliasTable:
    """The human-approved ontology: canonical id + the surface forms that mean it."""
    entities = [
        Entity(canonical_id=f"{it.kind}::{it.canonical_id}", label=it.name,
               entity_type=it.kind, aliases=(it.name, *it.aliases))
        for it in DATASET
    ]
    return InMemoryAliasTable.from_entities(entities)


def slugify(name: str) -> str:
    """The baseline: derive an id from a name (the standard non-resolver approach)."""
    s = "".join(c if c.isalnum() else "-" for c in name.lower())
    return re.sub(r"-+", "-", s).strip("-")


# --------------------------------------------------------------------------- #
# Resolvers under test                                                        #
# --------------------------------------------------------------------------- #
def baseline_derive(item: Item) -> str:
    return item.name if item.kind == "stock" else slugify(item.name)


def cairn_resolve(item: Item, table: InMemoryAliasTable) -> str:
    hits = resolve(item.name, table=table)[0]
    return hits[0].canonical_id.split("::", 1)[1] if hits else ""


def _llm_client():
    from openai import OpenAI
    return OpenAI()


_SYS = ("You resolve an entity reference to its stored canonical id. Companies use a "
        "slug (e.g. 'northwind-traders'), people a 'first-last' slug (e.g. 'jane-doe'), "
        "stocks a ticker (e.g. 'HOOL'). Output ONLY the id — no words, no punctuation.")


def _ask(client, prompt: str, model: str) -> str:
    r = client.chat.completions.create(
        model=model, temperature=0, max_tokens=20,
        messages=[{"role": "system", "content": _SYS}, {"role": "user", "content": prompt}])
    return (r.choices[0].message.content or "").strip().strip(".`'\"")


# --------------------------------------------------------------------------- #
# Run                                                                         #
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", metavar="MODEL", nargs="?", const="gpt-4o-mini", default=None,
                    help="run the model-in-the-loop variant (needs OPENAI_API_KEY)")
    args = ap.parse_args()

    table = build_table()
    client = _llm_client() if args.llm else None

    agg: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])  # cat -> [n, base_ok, cairn_ok]
    diffs: list[str] = []
    for it in DATASET:
        truth = it.canonical_id.lower()
        if client:
            base = _ask(client, f'Reference: "{it.name}"', args.llm).lower()
            cand = [c.canonical_id.split("::", 1)[1] for c in resolve(it.name, table=table)[0]]
            cair = _ask(client, f'Reference: "{it.name}"\nResolved candidates: {cand or "none"}.\n'
                        f"Pick the one id.", args.llm).lower()
        else:
            base = baseline_derive(it).lower()
            cair = cairn_resolve(it, table).lower()
        b_ok, c_ok = base == truth, cair == truth
        agg[it.category][0] += 1
        agg[it.category][1] += b_ok
        agg[it.category][2] += c_ok
        if b_ok != c_ok:
            diffs.append(f'  "{it.name}"  truth={truth}   base={base!r} '
                         f'{"OK" if b_ok else "X"}   cairn={cair!r} {"OK" if c_ok else "X"}')

    n = len(DATASET)
    b = sum(v[1] for v in agg.values())
    c = sum(v[2] for v in agg.values())
    mode = f"LLM in the loop ({args.llm})" if client else "deterministic (slugify baseline)"

    print("=" * 74)
    print(f"cairn-engine — entity-resolution grounding benchmark  [{mode}]")
    print("=" * 74)
    print(f"{'category':30}{'n':>3}  {'baseline':>10}  {'+ Cairn':>10}")
    print("-" * 74)
    for cat in sorted(agg):
        nn, bo, co = agg[cat]
        print(f"{cat:30}{nn:>3}  {bo}/{nn} ={100*bo//nn:>4}%  {co}/{nn} ={100*co//nn:>4}%")
    print("-" * 74)
    print(f"{'OVERALL':30}{n:>3}  {b}/{n} ={100*b//n:>4}%  {c}/{n} ={100*c//n:>4}%")
    print(f"\ncorrect-id accuracy: {100*b//n}% -> {100*c//n}%   "
          f"errors: {n-b} -> {n-c}  ({100*(n-b-(n-c))//max(n-b,1)}% of errors eliminated)")
    if diffs:
        print("\ntasks where the two resolvers disagree:")
        print("\n".join(diffs))


if __name__ == "__main__":
    main()
