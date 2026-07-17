"""Text normalization for deterministic resolution (constraint: normalization_is_nfkc_casefold_collapse).

Pure functions of their input — no state, no config, no environment dependence.
Pipeline: unicode NFKC -> casefold -> non-alphanumeric runs collapse to single
spaces -> strip. Tokenization = split on the collapsed spaces.

Stdlib only (unicodedata, math) — see constraint no_autodetected_accelerators.
"""

from __future__ import annotations

import math
import unicodedata

__all__ = ["normalize", "tokenize", "shannon_entropy_bits"]


def normalize(text: str) -> str:
    """NFKC -> casefold -> collapse non-alphanumeric runs to single spaces -> strip."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    out: list[str] = []
    prev_space = True  # collapse leading separators
    for ch in folded:
        if ch.isalnum():
            out.append(ch)
            prev_space = False
        elif not prev_space:
            out.append(" ")
            prev_space = True
    # strip a single trailing space left by a trailing separator run
    if out and out[-1] == " ":
        out.pop()
    return "".join(out)


def tokenize(text: str) -> tuple[str, ...]:
    """Tokens of the normalized form. tokenize(x) == tuple(normalize(x).split(' '))."""
    norm = normalize(text)
    return tuple(norm.split(" ")) if norm else ()


def shannon_entropy_bits(text: str) -> float:
    """Shannon entropy (bits/char) over the characters of the string.

    Used as the fuzzy-tier gate: low-entropy strings (short/repetitive) produce
    too many fuzzy false positives, so they skip Tier 2 (Graphiti entropy-gate
    pattern; OP-28).
    """
    if not text:
        return 0.0
    counts: dict[str, int] = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(text)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())
