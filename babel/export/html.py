"""Single self-contained HTML file export."""

from __future__ import annotations

import html

from babel.export.render import CSS, chapters_in_range, render_blocks
from babel.library import chapter_view
from babel.memory.akashic import Akashic
from babel.store.db import Store

PAGE_CSS = """
:root { color-scheme: light dark; }
body { background: #fbfaf7; color: #1f1d1a; }
@media (prefers-color-scheme: dark) { body { background: #16161a; color: #e6e3dc; } }
nav.toc { margin: 2em 0; } nav.toc a { color: inherit; }
section.chapter { border-top: 1px solid rgba(127,127,127,.3); margin-top: 3em; }
"""


def build_html(store: Store, novel_id: int, first: int | None = None, last: int | None = None) -> str:
    novel = store.get_novel(novel_id)
    ak = Akashic(store, novel_id)
    sections, toc = [], []
    for row in chapters_in_range(store, novel_id, first, last):
        view = chapter_view(store, row["id"], ak)
        toc.append(f'<li><a href="#c{row["idx"]}">{html.escape(view["title"])}</a></li>')
        sections.append(f'<section class="chapter" id="c{row["idx"]}">{render_blocks(view)}</section>')
    title = html.escape(novel["title"])
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{title}</title><style>{CSS}{PAGE_CSS}</style></head><body>"
        f"<h1 style='text-align:center;margin-top:1.5em'>{title}</h1>"
        f"<nav class='toc'><ol>{''.join(toc)}</ol></nav>{''.join(sections)}</body></html>"
    )
