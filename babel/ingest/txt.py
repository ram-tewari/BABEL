"""Plain-text ingestion: detect chapter headings, else split by size."""

from __future__ import annotations

from pathlib import Path

from babel.ingest import Book, IngestError, RawChapter
from babel.ingest.clean import clean_text, is_heading

_ENCODINGS = ("utf-8-sig", "utf-16", "gb18030", "cp1252", "latin-1")
TARGET_WORDS = 3000


def _decode(data: bytes) -> str:
    for enc in _ENCODINGS:
        try:
            text = data.decode(enc)
            if enc == "utf-16" and "\x00" in text:
                continue
            return text
        except (UnicodeDecodeError, UnicodeError):
            continue
    return data.decode("utf-8", errors="replace")


def split_chapters(text: str, pattern: str | None = None) -> list[RawChapter]:
    """Split on chapter headings (built-in patterns, or a custom regex for odd formats)."""
    import re

    lines = text.split("\n")
    if pattern:
        rx = re.compile(pattern, re.IGNORECASE)
        heads = [i for i, line in enumerate(lines) if line.strip() and rx.search(line.strip())]
    else:
        heads = [i for i, line in enumerate(lines) if is_heading(line)]
    # a single heading on the first line titles a one-chapter file
    if len(heads) == 1 and heads[0] == next(i for i, line in enumerate(lines) if line.strip()):
        body = "\n".join(lines[heads[0] + 1 :]).strip()
        return [RawChapter(lines[heads[0]].strip(), body)] if body else []
    # otherwise need at least two headings to trust them
    if len(heads) >= 2:
        chapters: list[RawChapter] = []
        preface = "\n".join(lines[: heads[0]]).strip()
        if len(preface.split()) > 150:
            chapters.append(RawChapter("Prologue", preface))
        for n, start in enumerate(heads):
            end = heads[n + 1] if n + 1 < len(heads) else len(lines)
            body = "\n".join(lines[start + 1 : end]).strip()
            title = lines[start].strip()
            if not body:
                continue
            chapters.append(RawChapter(title, body))
        if chapters:
            return chapters
    # fallback: paragraph-aligned parts of ~TARGET_WORDS words
    paras = [p for p in text.split("\n\n") if p.strip()]
    parts: list[RawChapter] = []
    buf: list[str] = []
    words = 0
    for p in paras:
        buf.append(p)
        words += len(p.split())
        if words >= TARGET_WORDS:
            parts.append(RawChapter(f"Part {len(parts) + 1}", "\n\n".join(buf)))
            buf, words = [], 0
    if buf:
        parts.append(RawChapter(f"Part {len(parts) + 1}", "\n\n".join(buf)))
    return parts


def read_txt(path: Path, name: str, chapter_pattern: str | None = None) -> Book:
    text = clean_text(_decode(Path(path).read_bytes()))
    if not text:
        raise IngestError("the file is empty")
    chapters = split_chapters(text, chapter_pattern)
    title = Path(name).stem.replace("_", " ").strip() or "Untitled"
    return Book(title=title, chapters=chapters)
