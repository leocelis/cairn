#!/usr/bin/env python3
"""M1.6 deliverable — internal-link recommendations for a real blog.

BRING YOUR OWN CORPUS: reads `corpus/blog/posts.json` (gitignored — user content
never ships with the library); fetch yours with examples/wordpress_corpus_prep.py.
The APPROVED list below is a worked example of the OP-35 human gate — replace it
with the concept set you approve for your own corpus.

Uses a HUMAN-APPROVED concept ontology (the OP-35 gate) over real posts. Full
pipeline, dogfooding the whole engine:

  approved ontology -> scan each post body (TF per concept + post-title citations)
  -> freeze to a SQLite .db (M2.2) -> TF-IDF cosine link ranking (M3.0)
  -> emit, per post:
       (a) mid-content anchors  : a concept mention links to the AUTHORITY post
                                   for that concept (the one that covers it most)
       (b) next reads           : TF-IDF-ranked sibling posts + direct citations

Run:  .venv/bin/python examples/wordpress_m16_links.py
"""

from __future__ import annotations

import json
import pathlib
import tempfile

from cairn_engine import (
    Entity,
    InMemoryAliasTable,
    InMemoryGraph,
    Ref,
    Relation,
    SqliteAliasTable,
    resolve,
    with_mirror_edges,
)
from cairn_engine.entity.normalize import normalize, tokenize
from cairn_retrieval import rank_links

CORPUS = pathlib.Path(__file__).parent.parent / "corpus" / "blog" / "posts.json"

# The human-approved ontology (canonical_id, label, aliases). Merges are encoded
# as one entity with several aliases; ubiquitous/noise candidates were excluded.
APPROVED = [
    ("concept::llm", "LLM", ("LLMs", "large language model", "large language models")),
    ("tool::github_copilot", "GitHub Copilot", ("Copilot",)),
    ("concept::ai_agents", "AI agents", ("agents",)),
    ("concept::ivd", "IVD", ("IVD Intent-Verified Development", "Intent-Verified Development")),
    ("concept::chatbot", "chatbot", ("chatbots",)),
    ("concept::vc", "VC", ("VCs",)),
    ("concept::gpt4", "GPT-4", ("GPT-4.5",)),
    ("concept::cursor", "Cursor", ()),
    ("concept::chatgpt", "ChatGPT", ()),
    ("concept::openai", "OpenAI", ()),
    ("concept::anthropic", "Anthropic", ()),
    ("concept::google", "Google", ()),
    ("concept::meta", "Meta", ()),
    ("concept::microsoft", "Microsoft", ()),
    ("concept::deep_research", "Deep Research", ()),
    ("concept::roi", "ROI", ()),
    ("concept::crm", "CRM", ()),
    ("concept::api", "API", ()),
    ("concept::qa", "QA", ()),
    ("concept::cloud", "Cloud", ()),
    ("concept::scripts", "Scripts", ()),
    ("concept::bottleneck", "Bottleneck", ()),
    ("concept::founders", "Founders", ()),
    ("concept::pm", "PM", ()),
    ("concept::automation", "Automation", ()),
    ("concept::workflows", "Workflows", ()),
    ("concept::visual_studio", "Visual Studio", ()),
    ("concept::junior_engineer", "Junior Engineer", ()),
    ("concept::senior_engineer", "Senior Engineer", ()),
]


def _count(tokens: tuple[str, ...], surfaces: list[str]) -> int:
    total = 0
    for surface in surfaces:
        atoks = surface.split(" ") if surface else []
        if atoks:
            total += sum(
                1 for i in range(len(tokens) - len(atoks) + 1)
                if list(tokens[i:i + len(atoks)]) == atoks
            )
    return total


def build() -> tuple[list[dict], list[Entity], SqliteAliasTable, InMemoryGraph]:
    if not CORPUS.exists():
        raise SystemExit(
            f"corpus not found: {CORPUS}\n"
            "Fetch your own WordPress export with examples/wordpress_corpus_prep.py "
            "(corpus/ is gitignored — user content never ships with the library)."
        )
    posts = json.loads(CORPUS.read_text())
    pid = {p["slug"]: f"post::{p['slug']}" for p in posts}

    # scan table = concepts + post TITLES (so a post naming another links directly)
    scan_entities = [
        Entity(canonical_id=cid, label=label, entity_type="concept", aliases=aliases)
        for cid, label, aliases in APPROVED
    ] + [
        Entity(canonical_id=pid[p["slug"]], label=p["title"], entity_type="document")
        for p in posts
    ]
    scan_table = InMemoryAliasTable.from_entities(scan_entities)
    surfaces_of = {cid: [normalize(label), *(normalize(a) for a in aliases)]
                   for cid, label, aliases in APPROVED}

    entities = [
        Entity(canonical_id=cid, label=label, entity_type="concept", aliases=aliases,
               refs=(Ref(doc_id=cid),))
        for cid, label, aliases in APPROVED
    ]
    for p in posts:
        body = p["title"] + ". " + p["text"]
        toks = tokenize(body)
        found = {r.canonical_id for r in resolve(body, table=scan_table)[0]}
        concepts = sorted(c for c in found if c.startswith(("concept::", "tool::")))
        cited = sorted(c for c in found if c.startswith("post::") and c != pid[p["slug"]])
        p["_concepts"] = concepts
        p["_tf"] = {c: _count(toks, surfaces_of[c]) or 1 for c in concepts}
        entities.append(Entity(
            canonical_id=pid[p["slug"]], label=p["title"], entity_type="document",
            refs=(Ref(doc_id=pid[p["slug"]]),),
            relations=(
                *(Relation("mentions", c, weight=float(p["_tf"][c])) for c in concepts),
                *(Relation("cites", c) for c in cited),
            ),
        ))

    entities = list(with_mirror_edges(entities, mirrors={"mentions": "mentioned_in",
                                                         "cites": "cited_by"}))
    db = str(pathlib.Path(tempfile.mkdtemp()) / "blog.db")
    table = SqliteAliasTable.from_entities(entities, path=db)      # dogfood M2.2
    graph = InMemoryGraph.from_entities(table.canonical_entities())
    return posts, list(table.canonical_entities()), table, graph


def main() -> None:
    posts, entities, table, graph = build()
    title = {e.canonical_id: e.label for e in entities}

    # authority post per concept = the post with the highest TF for it
    authority: dict[str, tuple[str, int]] = {}
    for p in posts:
        for c, tf in p["_tf"].items():
            if c not in authority or tf > authority[c][1]:
                authority[c] = (f"post::{p['slug']}", tf)

    links = {link.source_id: link for link in rank_links(entities, top_k=1)}
    cites = {e.canonical_id: [r.target_id for r in e.relations if r.predicate == "cites"]
             for e in entities if e.entity_type == "document"}

    print("=" * 72)
    print("M1.6 — INTERNAL-LINK RECOMMENDATIONS  (approved ontology, TF-IDF ranked)")
    print("=" * 72)
    for p in sorted(posts, key=lambda p: p["title"]):
        src = f"post::{p['slug']}"
        print(f'\n### "{p["title"]}"')

        # (a) mid-content anchors: concept -> its authority post (not self)
        anchors = [(title[c], authority[c][0]) for c in p["_concepts"]
                   if authority[c][0] != src][:4]
        if anchors:
            print("  mid-content anchors (link the concept mention to its authority post):")
            for concept_label, target in anchors:
                print(f'      "{concept_label}" -> "{title[target][:40]}"')

        # (b) next reads: direct citation (strongest) then TF-IDF sibling
        nexts = []
        for cited in cites.get(src, []):
            nexts.append(f'"{title[cited][:40]}"  (cites it by name)')
        link = links.get(src)
        if link:
            shared = ", ".join(c.split("::")[1].replace("_", " ") for c in link.shared[:4])
            nexts.append(f'"{title[link.target_id][:40]}"  (cosine {link.score}, via {shared})')
        print("  next reads:")
        for n in nexts or ["(no specific link)"]:
            print(f"      {n}")

    print(f"\n(ontology frozen to SQLite: {table.path})")


if __name__ == "__main__":
    main()
