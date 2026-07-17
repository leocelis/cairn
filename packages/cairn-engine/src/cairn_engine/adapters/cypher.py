"""openCypher graph-backend adapter (M2.3, OQ-3 for openCypher).

`design_principle_no_query_language`: the agent never writes Cypher. Cairn owns
the bounded-traversal INTENT and compiles it — once, deterministically — into an
openCypher query; an external graph DB (Neo4j / FalkorDB / Neptune openCypher)
runs it. Cairn decides WHAT to traverse; the backend executes HOW.

`storage_agnostic_core` (SACRED): cairn imports NO database driver. The driver
enters as a caller-supplied callable `run(query, params) -> rows` — the same
callable boundary as EmbedderFn / ArbiterFn. This module only EMITS the query
and MAPS the rows; connecting is the caller's job.

Fixed graph schema this compiler targets:
    (:Entity {id})-[edge {valid_from, valid_until, known_from, known_until,
                          predicate, weight}]->(:Entity)
    (:Entity)-[:HAS_REF]->(:Ref {doc_id, locator})

The result of `traverse_cypher` is identical (same hits, order, scores) to the
in-memory `traverse` on the same graph — the closure semantics are the same,
only the executor changed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping

from cairn_engine.entity.model import Ref
from cairn_engine.entity.traverse import TraversalHit, TraversalResult

__all__ = ["CypherQuery", "CypherRunFn", "compile_traversal", "traverse_cypher"]

_MAX_DEPTH = 3

# The caller's DB driver boundary: run(query_text, params) -> iterable of rows,
# each row a mapping with keys entity_id, hop, doc_id, locator.
CypherRunFn = Callable[[str, Mapping[str, str]], Iterable[Mapping[str, object]]]


@dataclass(frozen=True, slots=True)
class CypherQuery:
    """A compiled, parametrized openCypher query — pure data, byte-stable."""

    text: str
    params: Mapping[str, str] = field(default_factory=dict)


def compile_traversal(
    canonical_id: str,
    *,
    depth: int = 2,
    as_of: str | None = None,
    known_as_of: str | None = None,
) -> CypherQuery:
    """Compile a bounded relation closure into one deterministic openCypher query.

    Bounded variable-length path from the seed (hop 0) out to `depth`; both-axis
    bitemporal edge filter (half-open, None = open) emitted ONLY for the axes
    supplied; shortest hop per node; refs joined via OPTIONAL MATCH. `depth` is
    inlined as a literal (openCypher forbids parametrized `*0..$d`); every user
    string is a $param (injection-safe). Same args -> byte-identical output.
    """
    if not 0 <= depth <= _MAX_DEPTH:
        raise ValueError(
            f"depth must be in 0..{_MAX_DEPTH} (bounded closure — see TH-4 / OP-34): got {depth}"
        )
    params: dict[str, str] = {"seed": canonical_id}
    edge_predicates: list[str] = []
    if as_of is not None:
        params["as_of"] = as_of
        edge_predicates.append(
            "(r.valid_from IS NULL OR r.valid_from <= $as_of) "
            "AND (r.valid_until IS NULL OR $as_of < r.valid_until)"
        )
    if known_as_of is not None:
        params["known_as_of"] = known_as_of
        edge_predicates.append(
            "(r.known_from IS NULL OR r.known_from <= $known_as_of) "
            "AND (r.known_until IS NULL OR $known_as_of < r.known_until)"
        )

    lines = [f"MATCH p = (seed:Entity {{id: $seed}})-[rels*0..{depth}]->(n:Entity)"]
    if edge_predicates:
        lines.append(f"WHERE all(r IN rels WHERE {' AND '.join(edge_predicates)})")
    lines += [
        "WITH n, min(length(p)) AS hop",
        "OPTIONAL MATCH (n)-[:HAS_REF]->(ref:Ref)",
        "RETURN n.id AS entity_id, hop, ref.doc_id AS doc_id, ref.locator AS locator",
        "ORDER BY hop, entity_id, doc_id",
    ]
    return CypherQuery(text="\n".join(lines), params=params)


def traverse_cypher(
    canonical_id: str,
    *,
    run: CypherRunFn,
    depth: int = 2,
    as_of: str | None = None,
    known_as_of: str | None = None,
) -> TraversalResult:
    """Compile, execute via the caller's `run`, and map rows to a TraversalResult.

    Output is sorted (hop, entity_id, doc_id) and scored 1/(1+hop) — identical to
    the in-memory `traverse`, regardless of the order the backend returned rows.
    Ref-less rows (null doc_id) contribute no hit (closed world: no ref, no hit).
    """
    query = compile_traversal(
        canonical_id, depth=depth, as_of=as_of, known_as_of=known_as_of
    )
    hits: list[TraversalHit] = []
    for row in run(query.text, query.params):
        doc_id = row.get("doc_id")
        if doc_id is None:
            continue
        hop = int(row["hop"])  # type: ignore[call-overload]
        locator = row.get("locator")
        hits.append(
            TraversalHit(
                ref=Ref(doc_id=str(doc_id), locator=None if locator is None else str(locator)),
                entity_id=str(row["entity_id"]),
                hop=hop,
                score=1.0 / (1 + hop),
            )
        )
    hits.sort(key=lambda h: (h.hop, h.entity_id, h.ref.doc_id))
    return TraversalResult(tuple(hits), "graph")
