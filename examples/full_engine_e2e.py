#!/usr/bin/env python3
"""Cairn — FULL entity-engine walkthrough, end to end.

Exercises every stage of the engine on one tiny knowledge base:

  STAGE 1  build-time authoring   author_from_text -> dedup -> conflict gate
  STAGE 2  the human gate         approve candidates -> explicit canonical ids
  STAGE 3  serialization          deterministic JSON round-trip
  STAGE 4  merge (Union-Find)     LLMs folds into LLM — surfaces AND refs forward
  STAGE 5  resolution cascade     exact / normalized / fuzzy / embedding / llm / unresolved
  STAGE 6  bounded traversal      graph mode + bitemporal filter + hop-scored refs
  FINAL    determinism proof      the whole pipeline twice -> byte-identical

Zero network, zero third-party packages. The "LLM" arbiter and the "embedding"
model are deterministic stand-ins — exactly the callable boundary a real user
fills with their own model or API client.

Run:  .venv/bin/python examples/full_engine_e2e.py
"""

from __future__ import annotations

from cairn_engine import (
    Entity,
    InMemoryAliasTable,
    InMemoryGraph,
    Ref,
    Relation,
    ResolverConfig,
    author_from_text,
    dedup_candidates,
    dump_entities,
    find_alias_conflicts,
    load_entities,
    resolve,
    suggest_canonical_id,
    traverse,
    with_mirror_edges,
)

W = 62


def banner(title: str) -> None:
    print(f"\n{'=' * W}\n{title}\n{'=' * W}")


def run_pipeline(verbose: bool = True) -> str:
    trace: list[str] = []

    def log(*parts: object) -> None:
        line = " ".join(str(p) for p in parts)
        trace.append(line)
        if verbose:
            print(line)

    # ------------------------------------------------------------------
    if verbose:
        banner("STAGE 1 — build-time authoring (offline)")
    doc = (
        'Our stack uses Retrieval Augmented Generation. Teams pair "entity '
        "resolution\" with GitHub Copilot and LLMs every day. Retrieval "
        "Augmented Generation is everywhere now."
    )
    candidates = author_from_text(doc, source="doc::stack_notes")
    log("extracted:", [c.surface for c in candidates])

    report = dedup_candidates(candidates)
    log("after dedup:", [c.surface for c in report.unique],
        f"| dups={len(report.duplicates)} review_pairs={len(report.review_pairs)}")

    # ------------------------------------------------------------------
    if verbose:
        banner("STAGE 2 — the human gate (explicit approval)")
    approved = [
        c.to_entity(suggest_canonical_id(c.surface, "concept")) for c in report.unique
    ]
    # the human also authors richer records by hand (aliases, refs, relations):
    knowledge_base = [
        Entity(canonical_id="concept::rag", label="Retrieval Augmented Generation",
               entity_type="concept", aliases=("RAG",),
               refs=(Ref(doc_id="post::rag_explained"),)),
        Entity(canonical_id="concept::llm", label="LLM", entity_type="concept",
               refs=(Ref(doc_id="post::intro_llms"),)),
        Entity(canonical_id="concept::llms_plural", label="LLMs", entity_type="concept",
               refs=(Ref(doc_id="post::llms_deep_dive"),)),
        Entity(canonical_id="tool::github_copilot", label="GitHub Copilot",
               entity_type="tool", aliases=("Copilot",),
               refs=(Ref(doc_id="post::copilot_review"),)),
        Entity(canonical_id="post::rag_explained", label="RAG Explained",
               entity_type="document", refs=(Ref(doc_id="post::rag_explained"),),
               relations=(
                   Relation("mentions", "concept::rag"),
                   Relation("mentions", "concept::llm",
                            valid_from="2026-01-01", valid_until="2026-06-01"),
               )),
    ]
    conflicts = find_alias_conflicts(knowledge_base)
    log("approved from text:", [e.canonical_id for e in approved])
    log("alias conflicts (CI gate):", conflicts or "none")

    entities = with_mirror_edges(knowledge_base)  # symmetric traversal
    log("mirror edges added:",
        [f"{e.canonical_id}<-{r.predicate}" for e in entities for r in e.relations
         if r.predicate.endswith("_in") or r.predicate.startswith("mentioned")])

    # ------------------------------------------------------------------
    if verbose:
        banner("STAGE 3 — deterministic JSON round-trip")
    blob = dump_entities(list(entities))
    loaded = load_entities(blob)
    log(f"serialized {len(loaded)} entities -> {len(blob)} bytes;",
        "round-trip equal:", loaded == tuple(sorted(entities, key=lambda e: e.canonical_id)),
        "| re-dump identical:", dump_entities(list(loaded)) == blob)

    # ------------------------------------------------------------------
    if verbose:
        banner("STAGE 4 — merge: 'LLMs' is the same concept as 'LLM' (Union-Find)")
    table = InMemoryAliasTable()
    for e in loaded:
        table.add(e)
    table.merge("concept::llms_plural", "concept::llm")  # union: whole class moves
    table.freeze()
    rep = {e.canonical_id: e for e in table.canonical_entities()}["concept::llm"]
    log("representative concept::llm now carries refs:",
        sorted(r.doc_id for r in rep.refs))
    log("resolvable?  llm:", table.has_id("concept::llm"),
        "| llms_plural:", table.has_id("concept::llms_plural"),
        "(audit record kept:", str(table.has_record("concept::llms_plural")) + ")")

    graph = InMemoryGraph.from_entities(table.canonical_entities())

    # ------------------------------------------------------------------
    if verbose:
        banner("STAGE 5 — the full resolution cascade")

    def tiny_embedder(texts: list[str]) -> list[tuple[float, float]]:
        """Deterministic stand-in for a real embedding model (caller boundary)."""
        vocab = {
            "retrieval augmented generation": (1.0, 0.0),
            "grounded generation technique": (0.97, 0.243),  # cos vs RAG = 0.97
        }
        # unknown text -> zero vector -> cosine 0 (a real model gives every
        # text a distinct direction; a shared default would fake-collide)
        return [vocab.get(t, (0.0, 0.0)) for t in texts]

    def tiny_arbiter(surface: str, candidates: tuple) -> str | None:
        """Deterministic stand-in for an LLM arbiter — picks the first candidate."""
        return candidates[0].canonical_id

    index_entries = table.normalized_entries()
    from cairn_engine import EmbeddingIndex

    cfg = ResolverConfig(
        semantic_index=EmbeddingIndex.build(index_entries, tiny_embedder),
        embedder=tiny_embedder,
        arbiter=tiny_arbiter,
    )

    cases = [
        ("RAG", "exact alias"),
        ("github-copilot", "normalized (case+hyphen)"),
        ("Retrieval Augmentd Generation", "fuzzy (typo)"),
        ("grounded generation technique", "semantic (meaning, not strings)"),
        ("LLMs", "merged surface -> representative"),
        ("quantum blockchain synergy", "unknown -> closed world"),
    ]
    for mention, label in cases:
        resolved, unresolved = resolve("", table=table, mentions=[mention], config=cfg)
        if resolved:
            r = resolved[0]
            log(f"  [{label:34}] {mention!r} -> {r.canonical_id}  "
                f"(tier={r.tier}, conf={r.confidence})")
        else:
            log(f"  [{label:34}] {mention!r} -> UNRESOLVED (never invented)")

    scan_resolved, _ = resolve(
        "we compared RAG with GitHub Copilot in production", table=table)
    log("  free-text scan found:", [r.canonical_id for r in scan_resolved])

    # ------------------------------------------------------------------
    if verbose:
        banner("STAGE 6 — bounded traversal (graph + bitemporal)")
    for as_of, note in [("2026-03-01", "edge valid"), ("2026-07-01", "edge expired")]:
        result = traverse("post::rag_explained", graph=graph, depth=2, as_of=as_of)
        log(f"  as_of={as_of} ({note}): mode={result.traversal_mode},",
            f"{len(result.hits)} refs ->",
            [(h.ref.doc_id, h.hop, round(h.score, 3)) for h in result.hits[:4]], "...")

    return "\n".join(trace)


if __name__ == "__main__":
    first = run_pipeline(verbose=True)
    second = run_pipeline(verbose=False)
    banner("FINAL — determinism proof")
    print("entire pipeline run twice, outputs byte-identical:", first == second)
