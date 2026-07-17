"""Concept-weighted link ranking (cairn-retrieval M3.0).

Rank document<->document links by TF-IDF cosine similarity over the concepts
they share — the textbook content-based "related documents" measure:

  * IDF (concept specificity)  — a concept in every document has IDF 0 and
    contributes nothing, so a ubiquitous concept no longer links everything to
    everything. IDF(c) = log(N / df(c)).
  * TF (per-document centrality) — how strongly a document is about a concept,
    taken from the doc->concept edge WEIGHT (mention count). A post that
    mentions a concept many times weighs it more than one that mentions it once.
  * score(A, B) = cosine( tfidf_vector(A), tfidf_vector(B) ) in [0, 1].

Pure graph structure (edges carry the weights) — no post bodies, no model, no
network, deterministic. Ranking is the retrieval layer's job; it is kept OUT of
the entity engine's traverse(), which does only structural bounded closure
(OP-34). See intents/link_ranking_intent.yaml.

    from cairn_engine import InMemoryAliasTable
    from cairn_retrieval import rank_links
    links = rank_links(table.canonical_entities())
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from cairn_engine import Entity

__all__ = ["LinkRecommendation", "concept_idf", "tfidf_vectors", "rank_links"]


@dataclass(frozen=True, slots=True)
class LinkRecommendation:
    """One recommended internal link, scored by TF-IDF cosine similarity."""

    source_id: str
    target_id: str
    score: float             # cosine similarity in [0, 1]
    shared: tuple[str, ...]  # the concept ids that connect the two documents


def _doc_concept_tf(
    entities: Sequence[Entity], doc_type: str, concept_type: str
) -> tuple[list[Entity], dict[str, dict[str, float]]]:
    """(documents, {doc_id -> {concept_id -> term-frequency}}). TF is the summed
    edge weight of the document's edges to that concept-type entity."""
    by_id = {e.canonical_id: e for e in entities}
    docs = [e for e in entities if e.entity_type == doc_type]
    tf: dict[str, dict[str, float]] = {}
    for d in docs:
        counts: dict[str, float] = {}
        for r in d.relations:
            target = by_id.get(r.target_id)
            if target is not None and target.entity_type == concept_type:
                counts[r.target_id] = counts.get(r.target_id, 0.0) + r.weight
        tf[d.canonical_id] = counts
    return docs, tf


def concept_idf(
    entities: Sequence[Entity], *, doc_type: str = "document", concept_type: str = "concept"
) -> dict[str, float]:
    """IDF(c) = log(N / df(c)) — N documents, df(c) documents mentioning c.

    A concept in all N documents has IDF exactly 0.0. Empty document set -> {}.
    """
    docs, tf = _doc_concept_tf(entities, doc_type, concept_type)
    n = len(docs)
    if n == 0:
        return {}
    df: dict[str, int] = {}
    for counts in tf.values():
        for c in counts:
            df[c] = df.get(c, 0) + 1
    return {c: math.log(n / df_c) for c, df_c in sorted(df.items())}


def tfidf_vectors(
    entities: Sequence[Entity], *, doc_type: str = "document", concept_type: str = "concept"
) -> dict[str, dict[str, float]]:
    """{doc_id -> {concept_id -> tf*idf}}. Concepts with IDF 0 drop out."""
    docs, tf = _doc_concept_tf(entities, doc_type, concept_type)
    idf = concept_idf(entities, doc_type=doc_type, concept_type=concept_type)
    return {
        d.canonical_id: {
            c: w * idf[c] for c, w in tf[d.canonical_id].items() if idf.get(c, 0.0) > 0.0
        }
        for d in docs
    }


def _cosine(a: dict[str, float], b: dict[str, float]) -> tuple[float, tuple[str, ...]]:
    """Cosine similarity of two sparse vectors + the shared (nonzero) keys."""
    shared = sorted(a.keys() & b.keys())
    if not shared:
        return 0.0, ()
    dot = sum(a[c] * b[c] for c in shared)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0, ()
    return dot / (na * nb), tuple(shared)


def rank_links(
    entities: Sequence[Entity],
    *,
    top_k: int = 3,
    doc_type: str = "document",
    concept_type: str = "concept",
) -> list[LinkRecommendation]:
    """Per document, its top_k sibling documents ranked by TF-IDF cosine
    similarity. Links whose only shared concepts are ubiquitous (IDF 0) score 0
    and are dropped. Deterministic: score desc, then target_id asc."""
    vectors = tfidf_vectors(entities, doc_type=doc_type, concept_type=concept_type)

    out: list[LinkRecommendation] = []
    for source_id in sorted(vectors):
        scored: list[LinkRecommendation] = []
        for target_id, vec_b in vectors.items():
            if target_id == source_id:
                continue
            score, shared = _cosine(vectors[source_id], vec_b)
            if score > 0.0:
                scored.append(LinkRecommendation(
                    source_id=source_id, target_id=target_id,
                    score=round(score, 6), shared=shared,
                ))
        scored.sort(key=lambda link: (-link.score, link.target_id))
        out.extend(scored[:top_k])
    return out
