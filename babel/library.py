"""Library operations shared by the API, CLI and exporters."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

from babel.ingest import Book, load_book
from babel.memory.codex import Codex
from babel.models import Block, BlockType
from babel.store.db import Store
from babel.transform.assemble import assemble
from babel.transform.heuristic import label_segments
from babel.transform.segment import segment_text

PALETTE_SIZE = 12


def import_book(store: Store, covers_dir: Path, path: Path, filename: str | None = None) -> tuple[int, Book]:
    book = load_book(path, filename)
    nid = store.create_novel(
        book.title,
        [(c.title, c.text, c.sha) for c in book.chapters],
        author=book.author,
        description=book.description,
        language=book.language,
        source_name=filename or Path(path).name,
    )
    if book.cover:
        save_cover(store, covers_dir, nid, book.cover)
    return nid, book


def save_cover(store: Store, covers_dir: Path, novel_id: int, data: bytes) -> Path:
    """Normalize any image to a ≤600px-tall JPEG cover."""
    from PIL import Image

    covers_dir.mkdir(parents=True, exist_ok=True)
    out = covers_dir / f"{novel_id}.jpg"
    img = Image.open(io.BytesIO(data))
    img = img.convert("RGB")
    img.thumbnail((400, 600))
    img.save(out, "JPEG", quality=88)
    store.update_novel(novel_id, cover_path=str(out))
    return out


def chapter_labels(store: Store, chapter: dict) -> tuple[dict[int, tuple[str, str | None]], dict[int, tuple[str, str | None]]]:
    """(effective labels, overrides) for a chapter; untransformed chapters get a heuristic preview."""
    if chapter.get("labels"):
        labels = {int(k): (v[0], v[1]) for k, v in chapter["labels"].items()}
    else:
        segs = segment_text(chapter["source_text"])
        labels = {i: (t.value, s) for i, (t, s) in label_segments(segs).items()}
    overrides = store.get_overrides(chapter["id"])
    return {**labels, **overrides}, overrides


def chapter_view(store: Store, chapter_id: int, codex: Codex | None = None) -> dict | None:
    ch = store.get_chapter(chapter_id)
    if ch is None:
        return None
    codex = codex or Codex(store, ch["novel_id"])
    segments = segment_text(ch["source_text"])
    labels, overrides = chapter_labels(store, ch)
    typed = {i: (BlockType.parse(t) or BlockType.NARRATION, s) for i, (t, s) in labels.items()}
    blocks = assemble(segments, typed)
    pov = store.one("SELECT pov_character_id FROM novels WHERE id=?", (ch["novel_id"],))
    pov_id = (pov or {}).get("pov_character_id")

    char_ids: set[int] = set()
    out_blocks = []
    for b in blocks:
        cid = codex.lookup(b.speaker) if b.speaker else None
        if cid is None and b.type == BlockType.THOUGHT and not b.speaker:
            cid = pov_id
        if cid is not None:
            char_ids.add(cid)
        out_blocks.append({
            "type": b.type.value,
            "text": b.text,
            "speaker": b.speaker,
            "character_id": cid,
            "para": b.para,
            "seg": b.seg,
            "edited": any(s in overrides for s in b.seg),
        })
    prev_id, next_id = store.neighbors(ch["novel_id"], ch["idx"])
    characters = [character_public(codex.chars[c], pov_id) for c in sorted(char_ids) if c in codex.chars]
    return {
        "id": ch["id"],
        "novel_id": ch["novel_id"],
        "idx": ch["idx"],
        "title": ch["title"],
        "status": ch["status"],
        "method": ch["method"] or "preview",
        "model": ch["model"],
        "summary": ch["summary"],
        "error": ch["error"],
        "word_count": ch["word_count"],
        "prev_id": prev_id,
        "next_id": next_id,
        "blocks": out_blocks,
        "characters": characters,
    }


def character_public(c: dict, pov_id: int | None) -> dict:
    return {
        "id": c["id"],
        "name": c["name"],
        "note": c.get("note"),
        "color": c.get("color") or auto_color(c["name"]),
        "side": c.get("side") or ("right" if c["id"] == pov_id else "left"),
        "lines": c.get("lines") or 0,
        "is_pov": c["id"] == pov_id,
        "first_idx": c.get("first_idx"),
    }


def auto_color(name: str) -> str:
    """Stable palette slot from the name (the UI maps slots to theme-aware colors)."""
    h = int(hashlib.sha1(name.lower().encode()).hexdigest()[:8], 16)
    return f"slot:{h % PALETTE_SIZE}"


def blocks_for_segments(store: Store, chapter_id: int, segs: list[int]) -> dict[int, tuple[str, str | None]]:
    ch = store.get_chapter(chapter_id)
    labels, _ = chapter_labels(store, ch)
    return {s: labels.get(s, ("narration", None)) for s in segs}


__all__ = ["Block", "import_book", "chapter_view", "save_cover", "character_public"]
