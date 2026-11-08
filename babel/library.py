"""Library operations shared by the API, CLI, exporters and evals."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

from babel.ingest import Book, load_book
from babel.memory.akashic import Akashic
from babel.models import BlockType, Decision, Tier
from babel.scenario.assemble import assemble
from babel.scenario.convert import convert
from babel.scenario.resolve import Resolver, is_first_person
from babel.scenario.segment import segment_text
from babel.store.db import Store

PALETTE_SIZE = 12


def import_book(store: Store, covers_dir: Path, path: Path, filename: str | None = None,
                chapter_pattern: str | None = None) -> tuple[int, Book]:
    book = load_book(path, filename, chapter_pattern=chapter_pattern)
    nid = store.create_novel(
        book.title, [(c.title, c.text, c.sha) for c in book.chapters],
        author=book.author, description=book.description, language=book.language,
        source_name=filename or Path(path).name,
    )
    if book.cover:
        try:
            save_image(store, covers_dir, nid, book.cover)
        except Exception:  # a broken cover never fails an import
            pass
    return nid, book


def save_image(store: Store, folder: Path, owner_id: int, data: bytes, *, kind: str = "cover") -> Path:
    """Normalize an image to JPEG. Covers: fit 400×600. Portraits: square 256."""
    from PIL import Image, ImageOps

    folder.mkdir(parents=True, exist_ok=True)
    img = Image.open(io.BytesIO(data)).convert("RGB")
    if kind == "cover":
        img = ImageOps.fit(img, (400, 600)) if img.width / max(1, img.height) > 0.5 else img
        img.thumbnail((400, 600))
        out = folder / f"{owner_id}.jpg"
        img.save(out, "JPEG", quality=88)
        store.update_novel(owner_id, cover_path=str(out))
    else:
        img = ImageOps.fit(img, (256, 256))
        out = folder / f"char_{owner_id}.jpg"
        img.save(out, "JPEG", quality=88)
        store.x("UPDATE entities SET portrait_path=? WHERE id=?", (str(out), owner_id))
    return out


def preview_decisions(store: Store, ch: dict, ak: Akashic) -> dict[int, Decision]:
    """Instant rules+memory labeling for a chapter that hasn't been transformed yet."""
    segments = segment_text(ch["source_text"])
    decisions, paras = convert(segments, set(ak.character_names()))
    Resolver(ak, first_person=is_first_person(segments)).run(segments, decisions, paras)
    return decisions


def effective_decisions(store: Store, ch: dict, ak: Akashic) -> tuple[dict[int, Decision], set[int]]:
    """Pipeline decisions with user corrections layered on top. Returns (decisions, corrected segs)."""
    if ch.get("doc"):
        decisions = {int(k): Decision.from_compact(v) for k, v in ch["doc"]["decisions"].items()}
    else:
        decisions = preview_decisions(store, ch, ak)
    overrides = store.get_overrides(ch["id"])
    for seg, row in overrides.items():
        decisions[seg] = Decision.from_compact(row)
    return decisions, set(overrides)


def chapter_view(store: Store, chapter_id: int, ak: Akashic | None = None, review: float = 0.6) -> dict | None:
    ch = store.get_chapter(chapter_id)
    if ch is None:
        return None
    ak = ak or Akashic(store, ch["novel_id"])
    segments = segment_text(ch["source_text"])
    decisions, corrected = effective_decisions(store, ch, ak)
    blocks = assemble(segments, decisions)

    char_ids: set[int] = set()
    out = []
    for b in blocks:
        eid = ak.lookup(b.speaker) if b.speaker else None
        if eid is None and b.type == BlockType.THOUGHT and not b.speaker:
            eid = ak.pov_id
        if eid is not None:
            char_ids.add(eid)
        d = decisions.get(b.seg[0])
        out.append({
            "type": b.type.value, "text": b.text, "speaker": b.speaker, "character_id": eid, "tone": b.tone,
            "conf": round(b.conf, 2), "tier": b.tier.value, "para": b.para, "seg": b.seg,
            "edited": any(s in corrected for s in b.seg), "review": b.conf < review and b.tier != Tier.USER,
            "candidates": (d.candidates if d else [])[:4], "why": d.why if d else None,
        })
    prev_id, next_id = store.neighbors(ch["novel_id"], ch["idx"])
    full_text = " ".join(b["text"] for b in out)
    return {
        "id": ch["id"], "novel_id": ch["novel_id"], "idx": ch["idx"], "title": ch["title"],
        "status": ch["status"], "method": "preview" if not ch.get("doc") else "cascade",
        "tiers": ch["tiers"], "summary": ch["summary"], "error": ch["error"], "word_count": ch["word_count"],
        "review_count": sum(1 for b in out if b["review"]),
        "prev_id": prev_id, "next_id": next_id, "blocks": out,
        "characters": [entity_public(ak, ak.ents[c]) for c in sorted(char_ids) if c in ak.ents],
        "glossary": ak.glossary_hits(full_text),
    }


def entity_public(ak: Akashic, e: dict) -> dict:
    eid = e["id"]
    if e.get("color"):
        color = e["color"]
    elif e.get("auto_slot") is not None:
        color = f"slot:{e['auto_slot']}"
    elif e["kind"] == "character" and e.get("faction_id") in ak.ents and ak.ents[e["faction_id"]].get("color"):
        color = ak.ents[e["faction_id"]]["color"]
    else:
        color = auto_color(e["name"])
    return {
        "id": eid, "kind": e["kind"], "name": e["name"], "note": e.get("note"), "gender": e.get("gender"),
        "color": color, "side": e.get("side") or ("right" if eid == ak.pov_id else "left"),
        "lines": e.get("lines") or 0, "is_pov": eid == ak.pov_id, "first_idx": e.get("first_idx"),
        "faction_id": e.get("faction_id"), "has_portrait": bool(e.get("portrait_path")),
        "aliases": [a for a in ak.alias_text.get(eid, []) if a.lower() != e["name"].lower()],
        "locked": sorted(e.get("locked") or []),
    }


def auto_color(name: str) -> str:
    h = int(hashlib.sha1(name.lower().encode()).hexdigest()[:8], 16)
    return f"slot:{h % PALETTE_SIZE}"
