"""The Akashic Record: a novel's global memory.

Holds every entity BABEL knows about — characters (with aliases, gender, notes,
faction, display color/side/portrait), locations, factions and terms — and the
alias table that maps any name a text uses to the right entity. It answers:

* "who is 'Klein'?"            → resolve / lookup (aliases, titles, partial names)
* "who could 'she' be?"        → gender
* "what does the model need?"  → brief() lines for the candidates in a question
* "which terms deserve a tooltip in this chapter?" → glossary_hits

User edits are sticky: a renamed character or a hand-written note is never
overwritten by what a model reports later.
"""

from __future__ import annotations

import json
import re
from collections import Counter

from babel.models import EntityHint
from babel.store.db import Store, norm_name, now

KINDS = ("character", "location", "faction", "term")

_TITLES = {
    "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "miss", "sir", "lady", "lord", "master", "young",
    "old", "the", "dr", "dr.", "elder", "senior", "brother", "sister", "uncle", "aunt", "madam",
    "captain", "professor", "teacher", "father", "mother", "little", "big",
}
PRONOUNS = {"he", "she", "they", "i", "we", "you", "him", "her", "it", "me", "someone", "somebody", "us", "them"}
UNKNOWN = {"?", "unknown", "narrator", "none", "null", "n/a", "unknown speaker", "nobody", "someone", "someone else",
           "somebody", "someone else (give the name)", "speaker", "the speaker", "a voice", "voice", "anonymous"}


def tokens(name: str) -> list[str]:
    return [t for t in re.split(r"[\s·•\-]+", norm_name(name)) if t]


def core(name: str) -> str:
    toks = tokens(name)
    while len(toks) > 1 and toks[0] in _TITLES:
        toks.pop(0)
    return " ".join(toks)


def valid_label(label: str | None) -> bool:
    if not label:
        return False
    n = norm_name(label)
    return n not in PRONOUNS and n not in UNKNOWN and len(label) <= 60 and any(c.isalpha() for c in label)


class Akashic:
    def __init__(self, store: Store, novel_id: int):
        self.store = store
        self.novel_id = novel_id
        self.reload()

    def reload(self) -> None:
        self.ents: dict[int, dict] = {}
        for r in self.store.q("SELECT * FROM entities WHERE novel_id=?", (self.novel_id,)):
            r["locked"] = set(json.loads(r.get("locked") or "[]"))
            self.ents[r["id"]] = r
        self.alias: dict[str, int] = {}
        self.alias_text: dict[int, list[str]] = {}
        for r in self.store.q("SELECT norm, alias, entity_id FROM aliases WHERE novel_id=? ORDER BY length(alias)",
                              (self.novel_id,)):
            self.alias[r["norm"]] = r["entity_id"]
            self.alias_text.setdefault(r["entity_id"], []).append(r["alias"])
        novel = self.store.one("SELECT pov_character_id FROM novels WHERE id=?", (self.novel_id,))
        self.pov_id: int | None = (novel or {}).get("pov_character_id")

    # ── queries ───────────────────────────────────────────────────────────
    @property
    def characters(self) -> list[dict]:
        return [e for e in self.ents.values() if e["kind"] == "character"]

    def name(self, eid: int | None) -> str | None:
        return self.ents[eid]["name"] if eid in self.ents else None

    def gender(self, eid: int | None) -> str | None:
        return self.ents[eid].get("gender") if eid in self.ents else None

    def pov_name(self) -> str | None:
        return self.name(self.pov_id)

    def character_names(self) -> list[str]:
        """Every alias that refers to a character (longest first, for scanning text)."""
        out = [a for eid, names in self.alias_text.items()
               if self.ents.get(eid, {}).get("kind") == "character" for a in names]
        return sorted(out, key=len, reverse=True)

    def lookup(self, label: str | None, kind: str | None = "character") -> int | None:
        """Resolve a name to an entity id without creating anything."""
        if not valid_label(label):
            return None
        n = norm_name(label)
        for key in (n, core(label)):
            eid = self.alias.get(key)
            if eid is not None and (kind is None or self.ents.get(eid, {}).get("kind") == kind):
                return eid
        toks = core(label).split()
        if not toks:
            return None
        # "Klein" ↔ "Klein Moretti": a unique token-subset match in either direction
        cands = set()
        for alias_norm, eid in self.alias.items():
            if kind is not None and self.ents.get(eid, {}).get("kind") != kind:
                continue
            at = [t for t in alias_norm.split() if t not in _TITLES]
            if not at:
                continue
            if len(toks) == 1 and toks[0] in at:
                cands.add(eid)
            elif len(at) == 1 and at[0] in toks and len(toks) <= 3:
                cands.add(eid)
        return cands.pop() if len(cands) == 1 else None

    def brief(self, eid: int) -> str:
        """One line for prompts: name (gender, aka …) — note."""
        e = self.ents[eid]
        bits = []
        if e.get("gender") in ("m", "f"):
            bits.append({"m": "male", "f": "female"}[e["gender"]])
        others = [a for a in self.alias_text.get(eid, []) if norm_name(a) != norm_name(e["name"])][:4]
        if others:
            bits.append("aka " + ", ".join(others))
        if eid == self.pov_id:
            bits.append("point-of-view character")
        line = e["name"] + (f" ({'; '.join(bits)})" if bits else "")
        if e.get("note"):
            line += f" — {e['note'][:120]}"
        return line

    def mentioned_in(self, text: str, kind: str | None = "character") -> Counter[int]:
        lowered = norm_name(text)
        hits: Counter[int] = Counter()
        for alias_norm, eid in self.alias.items():
            if len(alias_norm) < 2 or (kind and self.ents.get(eid, {}).get("kind") != kind):
                continue
            n = len(re.findall(rf"(?<!\w){re.escape(alias_norm)}(?!\w)", lowered))
            if n:
                hits[eid] += n
        return hits

    def glossary_hits(self, text: str) -> list[dict]:
        """Entities with something worth showing in a tooltip that appear in ``text``."""
        out = []
        for eid in self.mentioned_in(text, kind=None):
            e = self.ents[eid]
            # characters have avatars to click; only notes *you* wrote earn them an inline tooltip
            if not e.get("note") or (e["kind"] == "character" and "note" not in e["locked"]):
                continue
            terms = [a for a in self.alias_text.get(eid, []) if len(a) >= 3 and re.search(
                rf"(?<!\w){re.escape(a)}(?!\w)", text, re.I)]
            if terms:
                out.append({"entity_id": eid, "kind": e["kind"], "name": e["name"], "note": e.get("note"),
                            "terms": sorted(set(terms), key=len, reverse=True)})
        return out

    # ── writes ────────────────────────────────────────────────────────────
    def resolve(self, label: str | None, chapter_idx: int | None = None, create: bool = True,
                kind: str = "character") -> int | None:
        if not valid_label(label):
            return None
        eid = self.lookup(label, kind)
        if eid is not None:
            self._upgrade_name(eid, label)
            self._add_alias(eid, label)
            return eid
        return self.create(label.strip(), kind, chapter_idx) if create else None

    def _upgrade_name(self, eid: int, label: str) -> None:
        """'Mira' → 'Mira Vell' when a fuller form of the same name shows up (unless the user named it)."""
        e = self.ents[eid]
        old, new = set(tokens(core(e["name"]))), set(tokens(core(label)))
        if len(label.strip()) > len(e["name"]) and old < new and len(new) <= 4:
            self._set(eid, "name", label.strip())

    def create(self, name: str, kind: str = "character", chapter_idx: int | None = None, *,
               gender: str | None = None, note: str | None = None) -> int:
        if gender is None and kind == "character":
            from babel.scenario.resolve import title_gender

            gender = title_gender(name)
        eid = self.store.x(
            "INSERT INTO entities (novel_id, kind, name, gender, note, first_idx, created_at) VALUES (?,?,?,?,?,?,?)",
            (self.novel_id, kind, name, gender, note, chapter_idx, now()),
        )
        self.ents[eid] = {"id": eid, "novel_id": self.novel_id, "kind": kind, "name": name, "gender": gender,
                          "note": note, "first_idx": chapter_idx, "lines": 0, "mentions": 0, "locked": set(),
                          "color": None, "side": None, "auto_slot": None, "faction_id": None, "portrait_path": None}
        self._add_alias(eid, name)
        return eid

    def _add_alias(self, eid: int, alias: str) -> None:
        n = norm_name(alias)
        if not n or n in self.alias or n in PRONOUNS or n in UNKNOWN:
            return
        self.store.x("INSERT OR IGNORE INTO aliases (novel_id, norm, alias, entity_id) VALUES (?,?,?,?)",
                     (self.novel_id, n, alias.strip(), eid))
        self.alias[n] = eid
        self.alias_text.setdefault(eid, []).append(alias.strip())

    def _set(self, eid: int, field: str, value, *, user: bool = False) -> None:
        e = self.ents[eid]
        if not user and field in e["locked"]:
            return
        self.store.x(f"UPDATE entities SET {field}=? WHERE id=?", (value, eid))
        e[field] = value
        if user and field not in e["locked"]:
            e["locked"].add(field)
            self.store.x("UPDATE entities SET locked=? WHERE id=?", (json.dumps(sorted(e["locked"])), eid))

    def learn(self, hint: EntityHint, chapter_idx: int | None = None) -> int | None:
        """Merge a reported entity (name, kind, aliases, gender, note) into memory."""
        kind = hint.kind if hint.kind in KINDS else "character"
        eid = self.lookup(hint.name, kind)
        if eid is None:
            for a in hint.aliases:
                eid = self.lookup(a, kind)
                if eid is not None:
                    break
        if eid is None:
            if not valid_label(hint.name):
                return None
            eid = self.create(hint.name, kind, chapter_idx, gender=hint.gender, note=hint.note)
        else:
            e = self.ents[eid]
            self._upgrade_name(eid, hint.name)  # "Klein" → "Klein Moretti" unless user-locked
            if hint.note and not e.get("note"):
                self._set(eid, "note", hint.note[:300])
            if hint.gender in ("m", "f") and not e.get("gender"):
                self._set(eid, "gender", hint.gender)
        self._add_alias(eid, hint.name)
        for a in hint.aliases:
            self._add_alias(eid, a)
        return eid

    def edit(self, eid: int, **fields) -> None:
        """A user edit: applied and locked against model updates."""
        for k, v in fields.items():
            if k == "name" and v:
                self._set(eid, "name", v.strip(), user=True)
                self._add_alias(eid, v)
            elif k in ("note", "gender", "color", "side", "faction_id", "portrait_path", "kind"):
                self._set(eid, k, v, user=True)

    def merge(self, src: int, dst: int) -> None:
        """Fold entity ``src`` into ``dst``: aliases, lines and POV move over."""
        if src == dst:
            return
        with self.store.tx() as c:
            c.execute("UPDATE aliases SET entity_id=? WHERE entity_id=?", (dst, src))
            c.execute("UPDATE entities SET lines = lines + (SELECT lines FROM entities WHERE id=?),"
                      " mentions = mentions + (SELECT mentions FROM entities WHERE id=?) WHERE id=?", (src, src, dst))
            c.execute("UPDATE novels SET pov_character_id=? WHERE pov_character_id=?", (dst, src))
            c.execute("INSERT INTO chapter_cast (chapter_id, entity_id, lines) SELECT chapter_id, ?, lines"
                      " FROM chapter_cast WHERE entity_id=? ON CONFLICT (chapter_id, entity_id)"
                      " DO UPDATE SET lines = lines + excluded.lines", (dst, src))
            # keep a design if only the merged-away entity had one
            c.execute("UPDATE designs SET entity_id=? WHERE entity_id=?"
                      " AND NOT EXISTS (SELECT 1 FROM designs WHERE entity_id=?)", (dst, src, dst))
            c.execute("DELETE FROM entities WHERE id=?", (src,))
        self.reload()

    def set_alias(self, eid: int, alias: str) -> None:
        n = norm_name(alias)
        self.store.x("INSERT INTO aliases (novel_id, norm, alias, entity_id) VALUES (?,?,?,?)"
                     " ON CONFLICT(novel_id, norm) DO UPDATE SET entity_id=excluded.entity_id",
                     (self.novel_id, n, alias.strip(), eid))
        self.reload()

    def remove_alias(self, alias: str) -> None:
        self.store.x("DELETE FROM aliases WHERE novel_id=? AND norm=?", (self.novel_id, norm_name(alias)))
        self.reload()

    def set_pov(self, eid: int | None) -> None:
        self.store.x("UPDATE novels SET pov_character_id=? WHERE id=?", (eid, self.novel_id))
        self.pov_id = eid

    def observe_gender(self, text: str) -> None:
        """Cheap gender inference: pronouns right after a character's name ("Mira ... she")."""
        votes: dict[int, Counter[str]] = {}
        for eid in self.mentioned_in(text):
            if self.ents[eid].get("gender") or "gender" in self.ents[eid]["locked"]:
                continue
            c: Counter[str] = Counter()
            for a in self.alias_text.get(eid, []):
                for m in re.finditer(rf"\b{re.escape(a)}\b[^.!?\"“”]{{0,60}}?\b(he|his|him|she|her|hers)\b", text):
                    c["m" if m.group(1) in ("he", "his", "him") else "f"] += 1
            if c:
                votes[eid] = c
        for eid, c in votes.items():
            (g, n), = c.most_common(1)
            if n >= 2 and n >= 3 * (sum(c.values()) - n):
                self._set(eid, "gender", g)

    def recount(self) -> None:
        """Recompute line counts from every chapter's decisions (incl. user corrections)."""
        counts: Counter[int] = Counter()
        cast: list[tuple[int, int, int]] = []
        overrides: dict[int, dict[str, list]] = {}
        for o in self.store.q("SELECT o.chapter_id, o.seg, o.decision FROM overrides o JOIN chapters c ON"
                              " c.id=o.chapter_id WHERE c.novel_id=?", (self.novel_id,)):
            overrides.setdefault(o["chapter_id"], {})[str(o["seg"])] = json.loads(o["decision"])
        for r in self.store.q("SELECT id, doc_json FROM chapters WHERE novel_id=? AND doc_json IS NOT NULL",
                              (self.novel_id,)):
            decisions = json.loads(r["doc_json"])["decisions"]
            decisions.update(overrides.get(r["id"], {}))
            here: Counter[int] = Counter()
            for row in decisions.values():
                if row[1] and row[0] in ("dialogue", "thought"):
                    eid = self.lookup(row[1])
                    if eid is not None:
                        here[eid] += 1
            counts.update(here)
            cast += [(r["id"], eid, n) for eid, n in here.items()]
        with self.store.tx() as c:
            c.execute("DELETE FROM chapter_cast WHERE chapter_id IN (SELECT id FROM chapters WHERE novel_id=?)",
                      (self.novel_id,))
            c.executemany("INSERT INTO chapter_cast (chapter_id, entity_id, lines) VALUES (?,?,?)", cast)
            c.execute("UPDATE entities SET lines=0 WHERE novel_id=?", (self.novel_id,))
            c.executemany("UPDATE entities SET lines=? WHERE id=?", [(n, eid) for eid, n in counts.items()])
        self.reload()
        self.assign_slots()
        if self.pov_id is None and counts:
            self.set_pov(counts.most_common(1)[0][0])

    def assign_slots(self, palette: int = 12) -> None:
        """Give the most active characters distinct palette slots (stable once assigned)."""
        ranked = sorted(self.characters, key=lambda c: (-(c.get("lines") or 0), c["id"]))
        top = [c for c in ranked if (c.get("lines") or 0) > 0][:palette]
        used = {c["auto_slot"] for c in top if c.get("auto_slot") is not None}
        free = [s for s in range(palette) if s not in used]
        updates = []
        for c in top:
            if c.get("auto_slot") is None and free:
                c["auto_slot"] = free.pop(0)
                updates.append((c["auto_slot"], c["id"]))
        if updates:
            with self.store.tx() as tx:
                tx.executemany("UPDATE entities SET auto_slot=? WHERE id=?", updates)
