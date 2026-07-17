#!/usr/bin/env python3
"""TF-IDF-weighted link ranking on the real blog corpus.

Two weights make a link strong:
  IDF  — the shared concept is rare (specific), not ubiquitous. A concept in
         every post has IDF 0 and cannot link anything.
  TF   — each post actually centres on the concept (mention count, carried on
         the doc->concept edge weight), not just name-drops it once.

score(A, B) = cosine( tfidf_vector(A), tfidf_vector(B) )  in [0, 1] — the
textbook "related documents" measure, computed purely on the entity graph.

Run:  .venv/bin/python examples/wordpress_ranked_links.py
"""

from __future__ import annotations

from cairn_retrieval import concept_idf, rank_links
from wordpress_linking_demo import build


def main() -> None:
    posts, table, graph = build()
    entities = table.canonical_entities()
    title = {e.canonical_id: e.label for e in entities}

    idf = concept_idf(entities)
    print("=" * 72)
    print("CONCEPT WEIGHTS  (IDF = log(N / documents-mentioning); higher = rarer)")
    print("=" * 72)
    for cid, w in sorted(idf.items(), key=lambda kv: kv[1]):
        df = sum(1 for p in posts if cid in p["_concepts"])
        note = "   <- ubiquitous, cannot link" if w == 0 else ""
        print(f"  {cid.split('::')[1].replace('_',' '):22} in {df:2d} posts   IDF={w:.3f}{note}")

    # show TF in action on one post: how many times it mentions each concept
    sample = max(posts, key=lambda p: len(p["_concepts"]))
    print(f'\n  TF example — "{sample["title"][:40]}" mention counts:')
    for cid, n in sorted(sample["_tf"].items(), key=lambda kv: -kv[1]):
        print(f"      {cid.split('::')[1].replace('_',' '):22} x{n}")

    print("\n" + "=" * 72)
    print("LINKS RANKED BY TF-IDF COSINE  (strongest link per post, score in [0,1])")
    print("=" * 72)
    links = rank_links(entities, top_k=1)
    by_source = {link.source_id: link for link in links}
    for e in sorted((e for e in entities if e.entity_type == "document"), key=lambda e: e.label):
        link = by_source.get(e.canonical_id)
        if not link:
            print(f'\n  "{e.label[:46]}"\n     -> (only ubiquitous concepts shared — no specific link)')
            continue
        labels = ", ".join(c.split("::")[1].replace("_", " ") for c in link.shared)
        print(f'\n  "{e.label[:46]}"\n     -> "{title[link.target_id][:46]}"'
              f"\n     cosine={link.score}  via: {labels}")


if __name__ == "__main__":
    main()
