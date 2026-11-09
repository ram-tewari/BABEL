"""Who needs a design, in what order, and which chapters are ready to read as a visual novel.

- **Importance** comes from how much a character talks and in how many chapters
  (the user can override it): main and supporting characters get their own design;
  minor characters and extras will come from the shared extras library and never
  block reading.
- **Order** is first appearance, so the start of the book is ready first and the
  reader never waits for characters from chapter 900.
- **A chapter is ready** once every main/supporting character who speaks or thinks
  in it has an approved design.
"""

from __future__ import annotations

from babel.memory.akashic import Akashic
from babel.store.db import Store

TIERS = ("main", "supporting", "minor", "extra")
REQUIRED = ("main", "supporting")


_PARTICLES = {"of", "de", "van", "von", "la", "le", "du", "da", "di", "bin", "al"}


def is_descriptive(name: str) -> bool:
    """'Circus fortune-teller', 'mobile hawkers', 'Gray-eyed police inspector' — a description, not a name."""
    words = name.split()
    return not words or not words[0][:1].isupper() or any(
        w[:1].islower() and w.lower() not in _PARTICLES for w in words[1:])


def tier_of(lines: int, chapters: int, override: str | None = None, name: str = "") -> str:
    if override in TIERS:
        return override
    if lines >= 40 or chapters >= 12:
        tier = "main"
    elif (lines >= 6 and chapters >= 2) or lines >= 15 or chapters >= 3:
        tier = "supporting"
    elif lines >= 1:
        tier = "minor"
    else:
        tier = "extra"
    # unnamed people come from the shared extras library until the book gives them a name
    if name and is_descriptive(name) and tier in ("main", "supporting"):
        tier = "minor"
    return tier


def cast_stats(store: Store, novel_id: int) -> dict[int, dict]:
    """entity → {lines, chapters, first_idx} from the per-chapter cast table."""
    rows = store.q("SELECT cc.entity_id eid, SUM(cc.lines) lines, COUNT(*) chapters, MIN(c.idx) first_idx"
                   " FROM chapter_cast cc JOIN chapters c ON c.id=cc.chapter_id WHERE c.novel_id=?"
                   " GROUP BY cc.entity_id", (novel_id,))
    return {r["eid"]: r for r in rows}


def characters(store: Store, ak: Akashic) -> list[dict]:
    """Every character with importance, first appearance and design status, in first-appearance order."""
    stats = cast_stats(store, ak.novel_id)
    designs = {d["entity_id"]: d for d in store.q(
        "SELECT d.* FROM designs d JOIN entities e ON e.id=d.entity_id WHERE e.novel_id=?", (ak.novel_id,))}
    out = []
    for e in ak.characters:
        st = stats.get(e["id"], {})
        first = st.get("first_idx")
        if first is None:
            first = e.get("first_idx")
        d = designs.get(e["id"])
        out.append({
            "id": e["id"], "name": e["name"], "gender": e.get("gender"),
            "lines": st.get("lines") or 0, "chapters": st.get("chapters") or 0, "first_idx": first,
            "tier": tier_of(st.get("lines") or 0, st.get("chapters") or 0, e.get("art_tier"), e["name"]),
            "tier_locked": e.get("art_tier") in TIERS,
            "design_id": d["id"] if d else None, "status": d["status"] if d else "new",
            "message": d.get("message") if d else None,
        })
    out.sort(key=lambda c: (c["first_idx"] if c["first_idx"] is not None else 1 << 30, -c["lines"], c["id"]))
    return out


def queue(store: Store, ak: Akashic) -> list[dict]:
    """Characters that need their own design and don't have an approved one yet, in reading order."""
    return [c for c in characters(store, ak) if c["tier"] in REQUIRED and c["status"] != "approved"]


def readiness(store: Store, ak: Akashic, limit: int = 5) -> dict:
    """Which transformed chapters can be read as a visual novel right now."""
    chars = {c["id"]: c for c in characters(store, ak)}
    rows = store.q("SELECT c.id, c.idx, c.status, cc.entity_id FROM chapters c LEFT JOIN chapter_cast cc"
                   " ON cc.chapter_id=c.id WHERE c.novel_id=? ORDER BY c.idx", (ak.novel_id,))
    chapters: dict[int, dict] = {}
    for r in rows:
        ch = chapters.setdefault(r["id"], {"id": r["id"], "idx": r["idx"], "done": r["status"] == "done", "missing": []})
        c = chars.get(r["entity_id"]) if r["entity_id"] is not None else None
        if c and c["tier"] in REQUIRED and c["status"] != "approved" and c["name"] not in ch["missing"]:
            ch["missing"].append(c["name"])
    ordered = sorted(chapters.values(), key=lambda c: c["idx"])
    ready_ids = [c["id"] for c in ordered if c["done"] and not c["missing"]]
    through = None
    for c in ordered:  # contiguous from the start: "read straight through to chapter N"
        if not c["done"] or c["missing"]:
            break
        through = c["idx"]
    blocked = [{"chapter_id": c["id"], "idx": c["idx"], "missing": c["missing"]}
               for c in ordered if c["done"] and c["missing"]][:limit]
    return {"ready": len(ready_ids), "transformed": sum(c["done"] for c in ordered), "total": len(ordered),
            "ready_through": through, "ready_ids": ready_ids, "blocked": blocked}
