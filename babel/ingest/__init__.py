"""Ingest EPUB / TXT files into clean chapters."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RawChapter:
    title: str
    text: str

    @property
    def sha(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


@dataclass
class Book:
    title: str
    chapters: list[RawChapter]
    author: str | None = None
    description: str | None = None
    language: str | None = None
    cover: bytes | None = None
    cover_ext: str = "jpg"
    warnings: list[str] = field(default_factory=list)


class IngestError(ValueError):
    pass


def load_book(path: Path | str, filename: str | None = None, chapter_pattern: str | None = None) -> Book:
    path = Path(path)
    name = filename or path.name
    suffix = Path(name).suffix.lower()
    if suffix == ".epub":
        from babel.ingest.epub import read_epub

        return read_epub(path, name)
    if suffix in (".txt", ".md", ".text"):
        from babel.ingest.txt import read_txt

        return read_txt(path, name, chapter_pattern)
    raise IngestError(f"unsupported file type {suffix!r} (use .epub or .txt)")
