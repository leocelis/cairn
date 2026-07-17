"""Connection suggestion — cold-start link prediction (cairn-retrieval OP-36).

Given a CANDIDATE node that is not yet in the graph (a table/module about to be
created), rank the existing entities it should connect to. A brand-new node has
no edges, so every structural index (Common Neighbors / Adamic-Adar / Resource
Allocation) is 0 — the COLD-START regime, where content/attribute similarity is
the primary signal (Lü & Zhou survey; Rahm & Bernstein linguistic matcher; the
cold-start link-prediction literature).

  * content_score(y)  — cosine of the candidate's TF-IDF concept vector against
    y's, using IDF from the EXISTING corpus. This is the candidate-vs-corpus
    generalisation of link_ranking's node<->node rank_links (OP-33). A concept the
    candidate has that the corpus lacks matches nothing and contributes 0.
  * structural_score(y) — OPTIONAL, seeds only. If the caller supplies seed
    entities the candidate provisionally relates to, add a Resource-Allocation
    term over seeds ∩ Γ(y): sum 1/deg(s). Without seeds this term is exactly 0 —
    the API never manufactures structural evidence a cold node cannot have.
  * total = content + graph_weight · structural_norm  (content-dominant default).

Deterministic, stdlib-only (math), no model, no network. Ranking lives in
cairn-retrieval, NOT the entity engine (OP-34 boundary). Cairn SUGGESTS; the
caller decides whether to create the edge. See
intents/connection_suggestion_intent.yaml and OP-36.

    from cairn_engine import InMemoryAliasTable
    from cairn_retrieval import suggest_connections
    picks = suggest_connections(candidate, table.canonical_entities())
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from cairn_engine import Entity
from cairn_retrieval.link_ranking import _cosine, concept_idf, tfidf_vectors

__all__ = ["ConnectionSuggestion", "suggest_connections"]


@dataclass(frozen=True, slots=True)
class ConnectionSuggestion:
    """One recommended connection for a candidate node, with its evidence."""

    target_id: str
    score: float             # fused total, content + graph_weight·structural_norm
    content_score: float     # TF-IDF cosine in [0, 1]
    structural_score: float  # normalised RA over seeds ∩ Γ(target); 0 without seeds
    shared: tuple[str, ...]  # concept ids that earned the content score
    via: tuple[str, ...]     # seed ids that contributed the structural score


def _entity_adjacency(
    existing: Sequence[Entity], by_id: dict[str, Entity], doc_type: str
) -> tuple[dict[str, set[str]], dict[str, int]]:
    """Undirected adjacency + degree over the entity-entity graph (doc_type nodes
    only). Concept edges are content, not structure, so they are excluded here."""
    adj: dict[str, set[str]] = {}
    for e in existing:
        if e.entity_type != doc_type:
            continue
        for r in e.relations:
            t = by_id.get(r.target_id)
            if t is not None and t.entity_type == doc_type and r.target_id != e.canonical_id:
                adj.setdefault(e.canonical_id, set()).add(r.target_id)
                adj.setdefault(r.target_id, set()).add(e.canonical_id)
    deg = {n: len(nbrs) for n, nbrs in adj.items()}
    return adj, deg


def suggest_connections(
    candidate: Entity,
    existing: Sequence[Entity],
    *,
    top_k: int = 5,
    doc_type: str = "document",
    concept_type: str = "concept",
    seeds: Sequence[str] = (),
    graph_weight: float = 0.25,
) -> list[ConnectionSuggestion]:
    """Rank the existing entities the candidate should connect to.

    Content-first (TF-IDF cosine over shared concepts, corpus IDF); an optional
    Resource-Allocation structural term fires only when `seeds` are given.
    Deterministic: total desc then target_id asc. Closed world: score-0
    suggestions and a no-overlap candidate return nothing (never fabricated).
    """
    existing = list(existing)
    by_id = {e.canonical_id: e for e in existing}

    # Corpus IDF + existing document vectors (reused from link_ranking).
    idf = concept_idf(existing, doc_type=doc_type, concept_type=concept_type)
    doc_vectors = tfidf_vectors(existing, doc_type=doc_type, concept_type=concept_type)

    # Candidate TF from its edges to concept-type entities that exist in the corpus.
    cand_tf: dict[str, float] = {}
    for r in candidate.relations:
        t = by_id.get(r.target_id)
        if t is not None and t.entity_type == concept_type:
            cand_tf[r.target_id] = cand_tf.get(r.target_id, 0.0) + r.weight
    # Corpus IDF weighting; a concept with IDF 0 (ubiquitous) or absent drops out.
    cand_vec = {c: w * idf[c] for c, w in cand_tf.items() if idf.get(c, 0.0) > 0.0}

    # Structural graph (only used when seeds are supplied).
    seed_set = {s for s in seeds if s in by_id}
    adj, deg = _entity_adjacency(existing, by_id, doc_type) if seed_set else ({}, {})

    out: list[ConnectionSuggestion] = []
    for y in existing:
        yid = y.canonical_id
        if yid == candidate.canonical_id or y.entity_type != doc_type or yid in seed_set:
            continue  # never the candidate itself; seeds are inputs, not results

        content, shared = _cosine(cand_vec, doc_vectors.get(yid, {}))

        struct = 0.0
        via: list[str] = []
        for s in sorted(seed_set):
            if s in adj.get(yid, set()):  # seed s is a neighbour of y -> common neighbour
                d = deg.get(s, 0)
                if d > 0:
                    struct += 1.0 / d  # Resource Allocation index
                    via.append(s)
        struct_norm = struct / len(seed_set) if seed_set else 0.0

        total = content + graph_weight * struct_norm
        if total <= 0.0:
            continue  # closed world: no overlap, no fabricated connection

        out.append(ConnectionSuggestion(
            target_id=yid,
            score=round(total, 6),
            content_score=round(content, 6),
            structural_score=round(struct_norm, 6),
            shared=shared,
            via=tuple(via),
        ))

    out.sort(key=lambda c: (-c.score, c.target_id))
    return out[:top_k]
