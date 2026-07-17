#!/usr/bin/env python3
"""M1.6 step 1 — author a blog's concept ontology from real posts.

BRING YOUR OWN CORPUS: reads `corpus/blog/posts.json` (gitignored — user content
never ships with the library); fetch yours with examples/wordpress_corpus_prep.py.

Runs the real authoring pipeline (author_from_text -> dedup_candidates) over the
posts and organizes the output into a CURATION WORKSHEET for the human gate
(OP-35): candidates that appear across many posts (the link-worthy ones), the
dedup review pairs, and the long tail. NOTHING is frozen here — a human approves
the canonical set, then a follow-up build freezes it.

Run:  .venv/bin/python examples/wordpress_authoring.py
"""

from __future__ import annotations

import json
import pathlib
from collections import Counter

from cairn_engine import author_from_text, dedup_candidates
from cairn_engine.entity.normalize import normalize

CORPUS = pathlib.Path(__file__).parent.parent / "corpus" / "blog" / "posts.json"


def main() -> None:
    if not CORPUS.exists():
        raise SystemExit(
            f"corpus not found: {CORPUS}\n"
            "Fetch your own WordPress export with examples/wordpress_corpus_prep.py "
            "(corpus/ is gitignored — user content never ships with the library)."
        )
    posts = json.loads(CORPUS.read_text())

    all_candidates = []
    doc_freq: Counter[str] = Counter()   # normalized surface -> #posts it appears in
    label_of: dict[str, str] = {}        # normalized surface -> a display label
    for post in posts:
        cands = author_from_text(post["title"] + ". " + post["text"],
                                 source=f"post::{post['slug']}")
        all_candidates.extend(cands)
        for surface in {normalize(c.surface): c.surface for c in cands}.items():
            norm, disp = surface
            doc_freq[norm] += 1
            label_of.setdefault(norm, disp)

    report = dedup_candidates(all_candidates)

    print("=" * 68)
    print(f"AUTHORING over {len(posts)} posts")
    print(f"  raw candidates: {len(all_candidates)}   after dedup: {len(report.unique)}"
          f"   dup pairs: {len(report.duplicates)}   review pairs: {len(report.review_pairs)}")
    print("=" * 68)

    print("\n### CROSS-POST CANDIDATES (in 2+ posts — these are what can LINK)")
    print("    [approve? / merge? / exclude?]  frequency  surface\n")
    for norm, n in sorted(doc_freq.items(), key=lambda kv: (-kv[1], kv[0])):
        if n >= 2:
            print(f"    {n:2d} posts   {label_of[norm]}")

    if report.review_pairs:
        print("\n### DEDUP REVIEW PAIRS (0.70-0.85 band — human decides merge/keep-both)")
        for a, b in report.review_pairs[:15]:
            print(f"    '{a.surface}'   ~   '{b.surface}'")

    print("\n" + "=" * 68)
    print("HUMAN GATE — decide, per cross-post candidate:")
    print("  KEEP    a real, specific concept (e.g. Cursor, ChatGPT, IVD)")
    print("  MERGE   variants of one concept  (e.g. LLM + LLMs -> concept::llm)")
    print("  EXCLUDE sentence-start noise / too-generic to link (e.g. 'Every', 'AI')")
    print("Then a follow-up build freezes the approved set + emits link recs.")
    print("=" * 68)


if __name__ == "__main__":
    main()
