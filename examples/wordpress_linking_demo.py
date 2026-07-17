#!/usr/bin/env python3
"""WordPress internal-linking on a real blog corpus — how content drives links.

BRING YOUR OWN CORPUS: this example reads `corpus/blog/posts.json` (gitignored —
user content never ships with the library). Fetch your own WordPress export with
`examples/wordpress_corpus_prep.py`, or run the self-contained
`blog_graph_demo.py` instead.

Content is used TWICE:
  BUILD TIME  — scan each post's body to learn WHICH concepts it discusses
                (post -> concept edges come from the actual text, not tags/dates)
  LINK TIME   — (a) concept mentions found IN a post body -> mid-content anchors
                (b) traverse concept edges -> sibling posts that SHARE a concept

The concept set below is a small HAND-CURATED ontology (this is the human gate
of OP-35 — in production you approve these; here they are picked to demo the
mechanics). Matching is deterministic alias resolution: a concept is "in" a post
iff one of its aliases literally appears in the post's normalized text. It does
NOT paraphrase — a post about "large language models" that never writes "LLM"
would need that alias, the LLM extractor, or the opt-in semantic tier.

Run:  .venv/bin/python examples/wordpress_linking_demo.py
"""

from __future__ import annotations

import json
import pathlib

from cairn_engine import Entity, InMemoryAliasTable, InMemoryGraph, Ref, Relation, resolve, traverse, with_mirror_edges
from cairn_engine.entity.normalize import normalize, tokenize

CORPUS = pathlib.Path(__file__).parent.parent / "corpus" / "blog" / "posts.json"

# Human-approved concept ontology (curated for the demo). label + aliases are
# the surface forms the scanner looks for in post bodies.
CONCEPTS = [
    ("concept::llm", "LLM", ("LLMs", "large language model", "large language models")),
    ("concept::rag", "RAG", ("Retrieval Augmented Generation",)),
    ("concept::github_copilot", "GitHub Copilot", ("Copilot",)),
    ("concept::cursor", "Cursor", ()),
    ("concept::chatgpt", "ChatGPT", ()),
    ("concept::openai", "OpenAI", ()),
    ("concept::ai_agents", "AI agents", ("agents",)),
    ("concept::automation_engineer", "AI Automation Engineer", ()),
]


def _count_mentions(tokens: tuple[str, ...], surfaces: list[str]) -> int:
    """Total occurrences of any normalized alias (as a token subsequence)."""
    total = 0
    for surface in surfaces:
        atoks = surface.split(" ") if surface else []
        if not atoks:
            continue
        for i in range(len(tokens) - len(atoks) + 1):
            if list(tokens[i:i + len(atoks)]) == atoks:
                total += 1
    return total


def build() -> tuple[list[dict], InMemoryAliasTable, InMemoryGraph]:
    if not CORPUS.exists():
        raise SystemExit(
            f"corpus not found: {CORPUS}\n"
            "Bring your own: fetch a WordPress export with examples/wordpress_corpus_prep.py\n"
            "(corpus/ is gitignored — user content never ships with the library), or run\n"
            "the self-contained examples/blog_graph_demo.py instead."
        )
    posts = json.loads(CORPUS.read_text())

    # concept table (for scanning post bodies)
    concept_table = InMemoryAliasTable.from_entities([
        Entity(canonical_id=cid, label=label, entity_type="concept", aliases=aliases,
               refs=(Ref(doc_id=cid),))
        for cid, label, aliases in CONCEPTS
    ])

    # BUILD TIME: scan each post's CONTENT -> which concepts it mentions -> edges
    entities: list[Entity] = [
        Entity(canonical_id=cid, label=label, entity_type="concept", aliases=aliases,
               refs=(Ref(doc_id=cid),))
        for cid, label, aliases in CONCEPTS
    ]
    # normalized surfaces per concept, for true occurrence counting (the scan
    # dedupes, so we count in the text to get real term frequency)
    concept_surfaces = {
        cid: [normalize(label), *(normalize(a) for a in aliases)]
        for cid, label, aliases in CONCEPTS
    }
    for post in posts:
        found = resolve(post["title"] + ". " + post["text"], table=concept_table)[0]
        toks = tokenize(post["title"] + ". " + post["text"])
        mentioned = sorted({r.canonical_id for r in found})
        # term frequency = how many times the concept's aliases occur in the body,
        # carried on the edge as its weight (structural build-time fact -> TF-IDF)
        tf = {c: _count_mentions(toks, concept_surfaces[c]) or 1 for c in mentioned}
        post["_concepts"] = mentioned
        post["_tf"] = tf
        entities.append(Entity(
            canonical_id=f"post::{post['slug']}", label=post["title"], entity_type="document",
            refs=(Ref(doc_id=f"post::{post['slug']}"),),
            relations=tuple(
                Relation("mentions", c, weight=float(tf[c])) for c in mentioned
            ),
        ))

    entities = list(with_mirror_edges(entities))  # concept -mentioned_in-> post
    table = InMemoryAliasTable.from_entities(entities)
    graph = InMemoryGraph.from_entities(table.canonical_entities())
    return posts, table, graph


def main() -> None:
    posts, table, graph = build()
    by_slug = {f"post::{p['slug']}": p for p in posts}

    print("=" * 68)
    print("CONTENT -> CONCEPTS  (built by scanning each post's body)")
    print("=" * 68)
    for p in sorted(posts, key=lambda p: p["slug"]):
        labels = [c.split("::")[1] for c in p["_concepts"]]
        print(f"  {p['title'][:42]:42}  {labels}")

    # Pick two well-connected posts and show their link surfaces
    print("\n" + "=" * 68)
    print("LINK SURFACES for two posts (a=mid-content anchors, b=next reads)")
    print("=" * 68)
    focus = [p for p in posts if len(p["_concepts"]) >= 2][:2]
    for p in focus:
        pid = f"post::{p['slug']}"
        print(f"\n### {p['title']}")

        # (a) mid-content anchors: concept mentions inside THIS post's body
        found = resolve(p["title"] + ". " + p["text"], table=table)[0]
        anchors = sorted({r.surface_form: r.canonical_id for r in found
                          if r.canonical_id.startswith("concept::")}.items())
        print("  (a) mid-content anchors (concept -> its owning post):")
        for surface, cid in anchors[:6]:
            print(f"        \"{surface}\" -> {cid}")

        # (b) next reads: traverse post -> concept -> sibling posts (2 hops)
        hits = traverse(pid, graph=graph, depth=2).hits
        siblings: dict[str, float] = {}
        for h in hits:
            if h.ref.doc_id.startswith("post::") and h.ref.doc_id != pid:
                siblings[h.ref.doc_id] = max(siblings.get(h.ref.doc_id, 0), h.score)
        ranked = sorted(siblings.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        print("  (b) next reads (sibling posts sharing a concept, max 3):")
        for doc_id, score in ranked:
            shared = sorted(set(p["_concepts"]) & set(by_slug[doc_id]["_concepts"]))
            shared_labels = [c.split("::")[1] for c in shared]
            print(f"        {by_slug[doc_id]['title'][:44]:44} (via {shared_labels})")


if __name__ == "__main__":
    main()
