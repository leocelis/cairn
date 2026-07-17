"""Ontology authoring — building the canonical alias table (OP-35, TH-1). BUILD-TIME ONLY.

Implements the module intent `intents/ontology_authoring_intent.yaml`:

    author_from_text()   extract candidate entities -> staged for human review
    dedup_candidates()   exact/normalized -> MinHash/LSH + token-sort -> review band
    with_mirror_edges()  reverse edges so traversal is symmetric (M1.4 finding)

Boundaries (the ones that keep the thesis intact):
  * cairn never imports third-party extractors and NEVER makes a network call —
    GLiNER/LLM extraction enters as a caller-supplied callable (explicit opt-in)
  * nothing here touches a frozen table: output is Candidate records with
    status 'pending_review'; the human gate adds approved entities explicitly
  * everything is deterministic: fixed MinHash salts, sorted iteration,
    first-occurrence ordering — same input, byte-identical output
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from cairn_engine.entity.model import Entity, Relation
from cairn_engine.entity.normalize import normalize, shannon_entropy_bits
from cairn_engine.entity.resolve import token_sort_ratio

__all__ = [
    "Candidate",
    "DedupReport",
    "author_from_text",
    "dedup_candidates",
    "find_alias_conflicts",
    "suggest_canonical_id",
    "with_mirror_edges",
]


def find_alias_conflicts(entities: Sequence[Entity]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """The OP-35 conflict-audit gate: every normalized surface that maps to 2+
    canonical ids, with those ids (sorted). Run it in CI / before freezing —
    a non-empty result means the resolver will return multi-candidate
    ambiguity for those surfaces (never a silent pick), which a human should
    either accept or disambiguate with scoped aliases."""
    surface_ids: dict[str, set[str]] = {}
    for ent in entities:
        for surface in (ent.label, *ent.aliases):
            norm = normalize(surface)
            if norm:
                surface_ids.setdefault(norm, set()).add(ent.canonical_id)
    return tuple(
        (surface, tuple(sorted(ids)))
        for surface, ids in sorted(surface_ids.items())
        if len(ids) >= 2
    )


def suggest_canonical_id(surface: str, entity_type: str) -> str:
    """Deterministic `type::slug` suggestion for the human gate ('Decision Layer',
    'concept' -> 'concept::decision_layer'). A SUGGESTION — the human owns the id."""
    slug = "_".join(normalize(surface).split(" "))
    if not slug:
        raise ValueError(f"surface normalizes to nothing: {surface!r}")
    return f"{entity_type}::{slug}"

# -- staging ------------------------------------------------------------------

_STATUS_PENDING = "pending_review"


@dataclass(frozen=True, slots=True)
class Candidate:
    """A staged candidate entity — NOT in any table until a human approves it."""

    surface: str
    entity_type: str
    source: str
    extractor: str          # provenance: which extractor produced it
    status: str = _STATUS_PENDING

    def to_entity(self, canonical_id: str) -> Entity:
        """Human-gate helper: approve this candidate under an explicit canonical_id."""
        return Entity(
            canonical_id=canonical_id,
            label=self.surface,
            entity_type=self.entity_type,
            source=self.source,
        )


# -- extraction ----------------------------------------------------------------

ExtractorFn = Callable[[str], Sequence[str]]

_QUOTED = re.compile(r'"([^"]{2,80})"|“([^”]{2,80})”')
_TOKEN = re.compile(r"[^\s]+")
_MAX_RUN = 5
_CLAUSE_BREAK = frozenset(",.;:!?)”\"'")  # clause boundaries end a capitalized run

# FIXED stopword list (Rule-5 finding): on real prose, sentence-start function
# words dominate capitalized runs and bury the real concepts. A standard English
# function-word set — deliberately EXCLUDES nothing domain-specific (no "cloud",
# "api", "check", "pick", "back", "right"…), so real concepts survive. Fixed and
# documented -> still fully deterministic.
_STOPWORDS = frozenset(
    "a about above after again against all also am an and another any anyone anything are around as "
    "ask at back be because been before being below between both but by can cannot could did do does "
    "doing done down during each either else enough ever every everyone everything few for from "
    "further get gets got had has have having he her here hers herself him himself his how however i "
    "if in into is it its itself just let like many may maybe me might more most much must my myself "
    "neither never no nobody nor not nothing now of off on once one only onto or other others our "
    "ours ourselves out over own perhaps rather same shall she should since so some somebody someone "
    "something still such than that the their theirs them themselves then there therefore these they "
    "thing things this those though through thus to together too toward und until up upon us very was "
    "we well were what whatever when whenever where whether which while who whoever whom whose why "
    "will with within without would yet you your yours yourself yourselves".split()
)


def _clean_token(word: str) -> str:
    word = word.strip(".,;:!?()[]{}«»\"'").rstrip("”").lstrip("“")
    for suffix in ("’s", "'s", "’", "'"):
        if word.endswith(suffix):
            word = word[: -len(suffix)]
    return word


def _is_stopword(word: str) -> bool:
    base = word.casefold().replace("’", "'")
    return base in _STOPWORDS or "'" in base  # contractions (I've, it's) are never concepts


def _trim_run(run: list[str]) -> list[str]:
    """Strip leading/trailing stopwords from a capitalized run ('Ask World Models'
    -> 'World Models'); a run that is all stopwords vanishes."""
    start, end = 0, len(run)
    while start < end and _is_stopword(run[start]):
        start += 1
    while end > start and _is_stopword(run[end - 1]):
        end -= 1
    return run[start:end]


def _heuristic_surfaces(text: str) -> list[str]:
    """Stdlib candidate generator: maximal runs (1..5 tokens) of Capitalized/UPPER
    tokens in the ORIGINAL text (stopword-trimmed), plus quoted phrases.
    Recall-oriented — precision comes from dedup + the human gate."""
    surfaces: list[str] = []
    run: list[str] = []

    def flush() -> None:
        # Long runs emit consecutive <=5-token chunks — recall-oriented means
        # NEVER dropping tokens (a 7-token run yields two candidates, not one
        # truncated one). Each chunk is stopword-trimmed independently.
        for i in range(0, len(run), _MAX_RUN):
            trimmed = _trim_run(run[i : i + _MAX_RUN])
            if trimmed:
                surfaces.append(" ".join(trimmed))
        run.clear()

    for match in _TOKEN.finditer(text):
        raw = match.group()
        word = _clean_token(raw)
        if word and (word[0].isupper() or word.isupper()) and any(c.isalpha() for c in word):
            run.append(word)
            if raw[-1] in _CLAUSE_BREAK:  # a comma/period ends the run: "Cloud, API" = two
                flush()
        else:
            flush()
    flush()
    for m in _QUOTED.finditer(text):
        phrase = m.group(1) or m.group(2)
        if phrase:
            surfaces.append(phrase.strip())
    # dedupe by normalized form, first occurrence wins (deterministic)
    seen: set[str] = set()
    out: list[str] = []
    for s in surfaces:
        key = normalize(s)
        if key and key not in seen:
            seen.add(key)
            out.append(s)
    return out


def author_from_text(
    text: str,
    *,
    source: str,
    extractor: str | ExtractorFn = "heuristic",
    entity_type: str = "concept",
) -> list[Candidate]:
    """BUILD-TIME: extract candidate entities from text and stage them for review.

    extractor:
      "heuristic" (default) — the stdlib deterministic candidate generator.
      a callable(text) -> surfaces — YOUR GLiNER / LLM wrapper. Cairn will not
          import third-party packages or call an API for you: passing "llm" or
          "gliner" as a string raises. The callable keeps that boundary — and
          any network use — explicitly in the caller's hands.

    Output is staged (`pending_review`); approve via Candidate.to_entity() and
    add to a table yourself — the human gate is not optional (OP-35).
    """
    name = extractor if isinstance(extractor, str) else getattr(extractor, "__name__", "callable")
    if isinstance(extractor, str):
        if extractor != "heuristic":
            raise ValueError(
                f"unknown extractor string {extractor!r}: cairn never auto-imports third-party "
                "extractors or calls APIs. Pass a callable(text) -> surfaces for GLiNER/LLM "
                "extraction (explicit opt-in; see intents/ontology_authoring_intent.yaml)."
            )
        surfaces: Iterable[str] = _heuristic_surfaces(text)
    else:
        surfaces = extractor(text)
    return [
        Candidate(surface=s, entity_type=entity_type, source=source, extractor=name)
        for s in surfaces
    ]


# -- dedup (three-tier, build-time; TH-1: class construction) -------------------

_FUZZY_DUP = 0.85       # >= : duplicate (inclusive)
_REVIEW_BAND = 0.70     # [0.70, 0.85) : flagged for human/tier-3 — never auto-merged
_ENTROPY_MIN = 1.5
_MINHASH_PERMS = 32
_BAND_SIZE = 4          # 32 / 4 = 8 bands


@dataclass(frozen=True, slots=True)
class DedupReport:
    unique: tuple[Candidate, ...]
    duplicates: tuple[tuple[Candidate, Candidate], ...]      # (kept, dropped)
    review_pairs: tuple[tuple[Candidate, Candidate], ...]    # ambiguous band -> humans


def _shingles(norm: str) -> set[bytes]:
    padded = f"  {norm} ".encode()
    return {padded[i : i + 3] for i in range(len(padded) - 2)} or {padded}


def _minhash(norm: str) -> tuple[int, ...]:
    """32-permutation MinHash with FIXED salts (blake2b) — byte-stable by construction."""
    sh = _shingles(norm)
    sig: list[int] = []
    for perm in range(_MINHASH_PERMS):
        salt = perm.to_bytes(2, "big")
        sig.append(
            min(
                int.from_bytes(hashlib.blake2b(s, digest_size=8, salt=salt).digest(), "big")
                for s in sh
            )
        )
    return tuple(sig)


def dedup_candidates(
    candidates: Sequence[Candidate],
    *,
    existing_normals: Iterable[str] = (),
) -> DedupReport:
    """Three-tier build-time dedup.

    Tier 1: identical normalized surfaces (batch + against `existing_normals`)
            -> first occurrence kept, rest recorded as duplicates.
    Tier 2: MinHash/LSH pairs confirmed by token-sort ratio — >= 0.85 duplicate;
            [0.70, 0.85) flagged in review_pairs (tier 3 is HUMAN territory,
            never auto-merged); entropy < 1.5 bits skips fuzzy entirely.
    """
    existing = set(existing_normals)
    # Tier 1 — exact/normalized
    kept: list[Candidate] = []
    by_norm: dict[str, Candidate] = {}
    duplicates: list[tuple[Candidate, Candidate]] = []
    for cand in candidates:
        norm = normalize(cand.surface)
        if norm in by_norm:
            duplicates.append((by_norm[norm], cand))
        elif norm in existing:
            # duplicate of an already-authored entity: `kept` is a sentinel
            # pointing at the existing normal (extractor="existing_table")
            sentinel = Candidate(surface=norm, entity_type=cand.entity_type,
                                 source="alias_table", extractor="existing_table")
            duplicates.append((sentinel, cand))
        else:
            by_norm[norm] = cand
            kept.append(cand)

    # Tier 2 — MinHash/LSH banding, then token-sort confirmation
    eligible = [c for c in kept if shannon_entropy_bits(normalize(c.surface)) >= _ENTROPY_MIN]
    bands: dict[tuple[int, bytes], list[int]] = {}
    for idx, cand in enumerate(eligible):
        sig = _minhash(normalize(cand.surface))
        for b in range(_MINHASH_PERMS // _BAND_SIZE):
            chunk = sig[b * _BAND_SIZE : (b + 1) * _BAND_SIZE]
            key = (b, hashlib.blake2b(repr(chunk).encode(), digest_size=8).digest())
            bands.setdefault(key, []).append(idx)
    pairs = sorted({(i, j) for idxs in bands.values() for i in idxs for j in idxs if i < j})

    dropped: set[int] = set()
    review: list[tuple[Candidate, Candidate]] = []
    for i, j in pairs:
        if i in dropped or j in dropped:
            continue
        cand_a, cand_b = eligible[i], eligible[j]
        score = token_sort_ratio(normalize(cand_a.surface), normalize(cand_b.surface))
        if score >= _FUZZY_DUP:
            duplicates.append((cand_a, cand_b))
            dropped.add(j)  # keep the earlier occurrence (deterministic)
        elif score >= _REVIEW_BAND:
            review.append((cand_a, cand_b))  # humans decide — never auto-merged

    dropped_ids = {id(eligible[j]) for j in dropped}
    unique = tuple(c for c in kept if id(c) not in dropped_ids)
    return DedupReport(unique=unique, duplicates=tuple(duplicates), review_pairs=tuple(review))


# -- mirror edges (M1.4 finding; OP-28 reversal mitigation) ----------------------

_DEFAULT_MIRRORS = {"mentions": "mentioned_in", "links_to": "linked_from"}


def with_mirror_edges(
    entities: Sequence[Entity],
    *,
    mirrors: dict[str, str] | None = None,
) -> tuple[Entity, ...]:
    """For each edge (a -[p]-> b) with p in the mirror map, add (b -[mirror(p)]-> a)
    onto the TARGET entity, preserving the bitemporal validity window.

    Without mirrors, post->concept edges make traversal asymmetric (a sibling
    post can't be reached back through the shared concept) — the M1.4 demo
    exposed exactly this. Returns NEW frozen records; input is never mutated.
    """
    mirror_map = _DEFAULT_MIRRORS if mirrors is None else mirrors
    extra: dict[str, list[Relation]] = {}
    ids = {e.canonical_id for e in entities}
    for ent in entities:
        for rel in ent.relations:
            reverse_pred = mirror_map.get(rel.predicate)
            if reverse_pred and rel.target_id in ids:
                extra.setdefault(rel.target_id, []).append(
                    Relation(
                        predicate=reverse_pred,
                        target_id=ent.canonical_id,
                        valid_from=rel.valid_from,
                        valid_until=rel.valid_until,
                        weight=rel.weight,   # the mirror carries the same edge weight
                    )
                )
    import dataclasses

    out: list[Entity] = []
    for ent in entities:
        additions = extra.get(ent.canonical_id)
        if not additions:
            out.append(ent)
            continue
        merged = list(ent.relations)
        for rel in sorted(additions, key=lambda r: (r.predicate, r.target_id)):
            if rel not in merged:  # dedupe pre-existing mirrors
                merged.append(rel)
        out.append(dataclasses.replace(ent, relations=tuple(merged)))
    return tuple(out)
