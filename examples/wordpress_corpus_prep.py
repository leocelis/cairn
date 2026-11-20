#!/usr/bin/env python3
"""Normalize a WordPress REST API dump into a Cairn-ready corpus (M1.6 step 0).

Input:  raw/*.json files — pages of GET /wp-json/wp/v2/posts with
        _fields=id,slug,link,title,content,excerpt,categories,tags,date
Output: posts.json — [{id, slug, title, link, date, text}], HTML stripped,
        entities unescaped, deterministic order (by slug).

Stdlib only. Usage:
    .venv/bin/python examples/wordpress_corpus_prep.py corpus/<site>/raw corpus/<site>/posts.json
"""

from __future__ import annotations

import html
import json
import pathlib
import sys
from html.parser import HTMLParser

_SKIP_TAGS = {"script", "style"}
_BLOCK_TAGS = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "tr"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._chunks.append(data)

    def text(self) -> str:
        raw = "".join(self._chunks)
        lines = [" ".join(line.split()) for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


def strip_html(rendered: str) -> str:
    parser = _TextExtractor()
    parser.feed(rendered)
    return parser.text()


def main(raw_dir: str, out_path: str) -> None:
    posts: list[dict[str, object]] = []
    for page_file in sorted(pathlib.Path(raw_dir).glob("posts_p*.json")):
        for post in json.loads(page_file.read_text()):
            posts.append(
                {
                    "id": post["id"],
                    "slug": post["slug"],
                    "title": html.unescape(post["title"]["rendered"]),
                    "link": post["link"],
                    "date": post["date"],
                    "text": strip_html(post["content"]["rendered"]),
                }
            )
    posts.sort(key=lambda p: str(p["slug"]))  # deterministic
    out = pathlib.Path(out_path)
    out.write_text(json.dumps(posts, sort_keys=True, indent=2) + "\n")
    total_chars = sum(len(str(p["text"])) for p in posts)
    print(f"{len(posts)} posts -> {out} ({total_chars:,} chars of clean text)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
