"""EPUB export of the visual scenario, for e-readers."""

from __future__ import annotations

import tempfile
from pathlib import Path

from ebooklib import epub

from babel.export.render import CSS, chapters_in_range, render_blocks
from babel.library import chapter_view
from babel.memory.akashic import Akashic
from babel.store.db import Store


def build_epub(store: Store, novel_id: int, first: int | None = None, last: int | None = None) -> bytes:
    novel = store.get_novel(novel_id)
    book = epub.EpubBook()
    book.set_identifier(f"babel-{novel_id}-{first}-{last}")
    book.set_title(novel["title"])
    book.set_language((novel.get("language") or "en")[:5])
    if novel.get("author"):
        book.add_author(novel["author"])
    if novel.get("cover_path") and Path(novel["cover_path"]).exists():
        book.set_cover("cover.jpg", Path(novel["cover_path"]).read_bytes())

    style = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=CSS)
    book.add_item(style)

    ak = Akashic(store, novel_id)
    items = []
    for row in chapters_in_range(store, novel_id, first, last):
        view = chapter_view(store, row["id"], ak)
        item = epub.EpubHtml(title=view["title"], file_name=f"c{row['idx']:05d}.xhtml", lang=book.language)
        item.content = render_blocks(view)
        item.add_item(style)
        book.add_item(item)
        items.append(item)

    book.toc = items
    book.spine = ["nav", *items]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
        path = tmp.name
    try:
        epub.write_epub(path, book)
        return Path(path).read_bytes()
    finally:
        Path(path).unlink(missing_ok=True)

