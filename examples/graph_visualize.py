#!/usr/bin/env python3
"""Draw Cairn's entity graph as ONE unified network — the real knowledge graph.

Both CONCEPTS and POSTS are nodes (that is what cairn actually stores — a
labeled property graph); edges are the `mentions` relations. Nodes are placed
with a deterministic force-directed layout (connected nodes attract, all nodes
repel) so clusters emerge — concepts sit among the posts that discuss them.

Nodes and edges are read straight from `table.canonical_entities()` — this is
literally Cairn's graph, not a reconstruction.

Pure stdlib (no networkx/graphviz — consistent with cairn's zero-dependency
core). Deterministic layout (fixed circular seed, no randomness). Opens the
image after writing it.

Run:  .venv/bin/python examples/graph_visualize.py
"""

from __future__ import annotations

import math
import pathlib
import subprocess
import sys

from wordpress_linking_demo import build

OUT = pathlib.Path(__file__).parent / "graph.svg"
W, H = 1100, 900
CONCEPT_FILL, CONCEPT_TEXT = "#7F77DD", "#26215C"   # purple
POST_FILL, POST_TEXT = "#1D9E75", "#04342C"          # teal
EDGE = "#C9C7BE"


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def layout(nodes: list[str], edges: list[tuple[str, str]]) -> dict[str, list[float]]:
    """Deterministic Fruchterman-Reingold force-directed layout (pure stdlib)."""
    n = len(nodes)
    area = W * H
    k = math.sqrt(area / n)                       # ideal edge length
    # deterministic seed: nodes on a circle (no randomness -> byte-stable image)
    pos = {
        v: [W / 2 + (W / 3) * math.cos(2 * math.pi * i / n),
            H / 2 + (H / 3) * math.sin(2 * math.pi * i / n)]
        for i, v in enumerate(nodes)
    }
    adj = set(map(frozenset, edges))
    temp = W / 8
    for _ in range(300):
        disp = {v: [0.0, 0.0] for v in nodes}
        for i, a in enumerate(nodes):            # repulsion (all pairs)
            for b in nodes[i + 1:]:
                dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
                d = math.hypot(dx, dy) or 0.01
                f = k * k / d
                ux, uy = dx / d, dy / d
                disp[a][0] += ux * f
                disp[a][1] += uy * f
                disp[b][0] -= ux * f
                disp[b][1] -= uy * f
        for a, b in edges:                        # attraction (along edges)
            dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
            d = math.hypot(dx, dy) or 0.01
            f = d * d / k
            ux, uy = dx / d, dy / d
            disp[a][0] -= ux * f
            disp[a][1] -= uy * f
            disp[b][0] += ux * f
            disp[b][1] += uy * f
        for v in nodes:                           # apply, capped by temperature
            dx, dy = disp[v]
            d = math.hypot(dx, dy) or 0.01
            pos[v][0] += dx / d * min(d, temp)
            pos[v][1] += dy / d * min(d, temp)
            pos[v][0] = min(W - 60, max(60, pos[v][0]))
            pos[v][1] = min(H - 40, max(70, pos[v][1]))
        temp *= 0.97                              # cool down
    _ = adj
    return pos


def build_svg() -> str:
    posts, table, graph = build()
    entities = {e.canonical_id: e for e in table.canonical_entities()}

    # undirected edge set (mentions / mentioned_in collapse to one line)
    edge_set: set[frozenset[str]] = set()
    for e in entities.values():
        for rel in e.relations:
            if rel.target_id in entities:
                edge_set.add(frozenset((e.canonical_id, rel.target_id)))
    # sort edges (and each pair) — iterating a set of strings is NOT
    # deterministic across runs (PYTHONHASHSEED), which would jitter the layout.
    edges = sorted(tuple(sorted(fs)) for fs in edge_set)
    node_ids = sorted(entities)
    degree = {v: sum(1 for fs in edge_set if v in fs) for v in node_ids}

    pos = layout(node_ids, edges)  # type: ignore[arg-type]

    svg = [
        f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        'xmlns="http://www.w3.org/2000/svg" font-family="system-ui, sans-serif">',
        f'<rect width="{W}" height="{H}" fill="white"/>',
        f'<text x="{W/2}" y="34" text-anchor="middle" font-size="20" font-weight="600" '
        'fill="#222">Cairn entity graph — concepts &amp; posts as one network</text>',
        f'<text x="{W/2}" y="54" text-anchor="middle" font-size="13" fill="#666">'
        'every node is an entity; lines are "mentions" edges — concepts cluster '
        'with the posts that discuss them</text>',
        f'<circle cx="40" cy="78" r="7" fill="{CONCEPT_FILL}"/>'
        f'<text x="54" y="82" font-size="12" fill="#444">concept</text>',
        f'<rect x="132" y="71" width="14" height="14" rx="2" fill="{POST_FILL}"/>'
        f'<text x="152" y="82" font-size="12" fill="#444">blog post</text>',
    ]

    for a, b in edges:                            # edges under nodes
        (x1, y1), (x2, y2) = pos[a], pos[b]
        svg.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                   f'stroke="{EDGE}" stroke-width="1.2" opacity="0.7"/>')

    for v in node_ids:
        x, y = pos[v]
        e = entities[v]
        label = e.label if len(e.label) <= 26 else e.label[:24] + "…"
        if e.entity_type == "concept":
            r = 6 + min(degree[v], 12)            # size by how many posts mention it
            svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{CONCEPT_FILL}"/>')
            svg.append(f'<text x="{x:.1f}" y="{y - r - 4:.1f}" text-anchor="middle" '
                       f'font-size="13" font-weight="600" fill="{CONCEPT_TEXT}">{_esc(label)}</text>')
        else:
            svg.append(f'<rect x="{x-5:.1f}" y="{y-5:.1f}" width="10" height="10" rx="2" fill="{POST_FILL}"/>')
            svg.append(f'<text x="{x:.1f}" y="{y + 16:.1f}" text-anchor="middle" '
                       f'font-size="10" fill="{POST_TEXT}">{_esc(label)}</text>')

    svg.append("</svg>")
    return "\n".join(svg)


def main() -> None:
    OUT.write_text(build_svg())
    print(f"wrote {OUT}  ({OUT.stat().st_size:,} bytes)")
    if sys.platform == "darwin":
        subprocess.run(["open", str(OUT)], check=False)
    else:
        print(f"open it manually: {OUT}")


if __name__ == "__main__":
    main()
