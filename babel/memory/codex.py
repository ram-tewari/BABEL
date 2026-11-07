"""The Akashic Record: per-novel story memory.

The codex holds every character (canonical name, aliases, notes, line counts)
and resolves raw speaker labels from the transformer to characters. It feeds
the LLM a cast list of characters relevant to each chunk, which is what keeps
attribution consistent across thousands of chapters.
"""

from __future__ import annotations

import json
import re
from collections import Counter

from babel.models import CharacterHint
from babel.store.db import Store, norm_name, now

_TITLES = {
    "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "miss", "sir", "lady", "lord", "master", "young",
    "old", "the", "dr", "dr.", "elder", "senior", "brother", "sister", "uncle", "aunt", "madam",
}
_UNKNOWN = {"unknown", "narrator", "none", "null", "n/a", "unknown speaker"}
_PRONOUNS = {"he", "she", "they", "i", "we", "you", "him", "her", "it", "me", "someone", "somebody"}


def _tokens(name: str) -> list[str]:
    return [t for t in re.split(r"[\s·•\-]+", norm_name(name)) if t]


def _core(name: str) -> str:
    toks = _tokens(name)
    while len(toks) > 1 and toks[0] in _TITLES:
        toks.pop(0)
    return " ".join(toks)


class Codex:
    def __init__(self, store: Store, novel_id: int):
        self.store = store
        self.novel_id = novel_id
        self.reload()

    def reload(self) -> None:
        self.chars: dict[int, dict] = {
            r["id"]: r for r in self.store.q("SELECT * FROM characters WHERE novel_id=?", (self.novel_id,))
        }
        self.alias: dict[str, int] = {
            r["norm"]: r["character_id"]
            for r in self.store.q("SELECT norm, character_id FROM aliases WHERE novel_id=?", (self.novel_id,))
        }

    # ── resolution ────────────────────────────────────────────────────────
    def lookup(self, label: str | None) -> int | None:
        """Resolve a label to a character id without creating anything."""
        if not label:
            return None
        n = norm_name(label)
        if n in self.alias:
            return self.alias[n]
        core = _core(label)
        if core in self.alias:
            return self.alias[core]
        toks = core.split()
        if not toks or n in _PRONOUNS:
            return None
        # "Klein" ↔ "Klein Moretti": a unique token-subset match in either direction
        cands = set()
        for alias_norm, cid in self.alias.items():
            at = alias_norm.split()
            if len(toks) == 1 and toks[0] in at:
                cands.add(cid)
            elif len(at) == 1 and at[0] in toks and len(toks) <= 3:
                cands.add(cid)
        if len(cands) == 1:
            return cands.pop()
        return None

    def resolve(self, label: str | None, chapter_idx: int | None = None, create: bool = True) -> int | None:
        if (not label or norm_name(label) in _PRONOUNS or norm_name(label) in _UNKNOWN
                or len(label) > 60 or not any(c.isalpha() for c in label)):
            return None
        cid = self.lookup(label)
        if cid is not None:
            self._add_alias(cid, label)
            return cid
        if not create:
            return None
        return self._create(label.strip(), chapter_idx)

    def _create(self, name: str, chapter_idx: int | None, note: str | None = None) -> int:
        cid = self.store.x(
            "INSERT INTO characters (novel_id, name, note, first_idx, created_at) VALUES (?,?,?,?,?)",
            (self.novel_id, name, note, chapter_idx, now()),
        )
        self.chars[cid] = {"id": cid, "novel_id": self.novel_id, "name": name, "note": note,
                           "color": None, "side": None, "first_idx": chapter_idx, "lines": 0}
        self._add_alias(cid, name)
        return cid

    def _add_alias(self, cid: int, alias: str) -> None:
        n = norm_name(alias)
        if not n or n in self.alias or n in _PRONOUNS:
            return
        self.store.x(
            "INSERT OR IGNORE INTO aliases (novel_id, norm, alias, character_id) VALUES (?,?,?,?)",
            (self.novel_id, n, alias.strip(), cid),
        )
        self.alias[n] = cid

    def learn(self, hint: CharacterHint, chapter_idx: int | None = None) -> int | None:
        """Merge an LLM-reported character (name + aliases + note) into the codex."""
        cid = self.lookup(hint.name)
        if cid is None:
            for a in hint.aliases:
                cid = self.lookup(a)
                if cid is not None:
                    break
        if cid is None:
            cid = self._create(hint.name, chapter_idx, hint.note)
        else:
            ch = self.chars[cid]
            # Upgrade "Klein" to "Klein Moretti" when the fuller name is reported.
            if (not ch.get("name_locked") and len(hint.name) > len(ch["name"])
                    and set(_tokens(ch["name"])) <= set(_tokens(hint.name))):
                self.store.x("UPDATE characters SET name=? WHERE id=?", (hint.name, cid))
                ch["name"] = hint.name
            if hint.note and not ch.get("note"):
                self.store.x("UPDATE characters SET note=? WHERE id=?", (hint.note[:300], cid))
                ch["note"] = hint.note[:300]
        self._add_alias(cid, hint.name)
        for a in hint.aliases:
            self._add_alias(cid, a)
        return cid

    # ── context for the LLM ───────────────────────────────────────────────
    def aliases_of(self, cid: int) -> list[str]:
        return [r["alias"] for r in self.store.q(
            "SELECT alias FROM aliases WHERE character_id=? ORDER BY length(alias)", (cid,))]

    def cast_context(self, text: str, limit: int = 40) -> list[str]:
        """Characters whose names/aliases occur in ``text``, plus the most active ones."""
        lowered = norm_name(text)
        mentioned: Counter[int] = Counter()
        for alias_norm, cid in self.alias.items():
            if len(alias_norm) < 2:
                continue
            hits = len(re.findall(rf"(?<!\w){re.escape(alias_norm)}(?!\w)", lowered))
            if hits:
                mentioned[cid] += hits
        ranked = [cid for cid, _ in mentioned.most_common()]
        for c in sorted(self.chars.values(), key=lambda c: -(c.get("lines") or 0)):
            if len(ranked) >= limit:
                break
            if c["id"] not in ranked and (c.get("lines") or 0) > 0:
                ranked.append(c["id"])
        lines = []
        for cid in ranked[:limit]:
            c = self.chars.get(cid)
            if not c:
                continue
            others = [a for a in self.aliases_of(cid) if norm_name(a) != norm_name(c["name"])][:6]
            line = c["name"]
            if others:
                line += " — aka " + ", ".join(others)
            if c.get("note"):
                line += f" — {c['note']}"
            lines.append(line)
        return lines

    def pov_name(self) -> str | None:
        n = self.store.one("SELECT pov_character_id FROM novels WHERE id=?", (self.novel_id,))
        cid = (n or {}).get("pov_character_id")
        return self.chars[cid]["name"] if cid in self.chars else None

    # ── editing ───────────────────────────────────────────────────────────
    def rename(self, cid: int, name: str) -> None:
        self.store.x("UPDATE characters SET name=?, name_locked=1 WHERE id=?", (name.strip(), cid))
        self._add_alias(cid, name)
        self.reload()

    def merge(self, src: int, dst: int) -> None:
        """Fold character ``src`` into ``dst`` (all aliases and lines move over)."""
        if src == dst:
            return
        with self.store.tx() as c:
            c.execute("UPDATE aliases SET character_id=? WHERE character_id=?", (dst, src))
            c.execute("UPDATE characters SET lines = lines + (SELECT lines FROM characters WHERE id=?)"
                      " WHERE id=?", (src, dst))
            c.execute("UPDATE novels SET pov_character_id=? WHERE pov_character_id=?", (dst, src))
            c.execute("DELETE FROM characters WHERE id=?", (src,))
        self.reload()

    def set_alias(self, cid: int, alias: str) -> None:
        """Point an alias at ``cid`` (moving it from another character if needed)."""
        n = norm_name(alias)
        self.store.x(
            "INSERT INTO aliases (novel_id, norm, alias, character_id) VALUES (?,?,?,?)"
            " ON CONFLICT(novel_id, norm) DO UPDATE SET character_id=excluded.character_id",
            (self.novel_id, n, alias.strip(), cid),
        )
        self.alias[n] = cid

    def remove_alias(self, alias: str) -> None:
        self.store.x("DELETE FROM aliases WHERE novel_id=? AND norm=?", (self.novel_id, norm_name(alias)))
        self.alias.pop(norm_name(alias), None)

    def recount(self) -> None:
        """Recompute per-character line counts from every chapter's labels and overrides."""
        counts: Counter[int] = Counter()
        rows = self.store.q(
            "SELECT id, labels_json FROM chapters WHERE novel_id=? AND labels_json IS NOT NULL", (self.novel_id,))
        overrides: dict[int, dict[int, tuple[str, str | None]]] = {}
        for o in self.store.all_overrides(self.novel_id):
            overrides.setdefault(o["chapter_id"], {})[o["seg"]] = (o["type"], o["speaker"])
        for r in rows:
            labels = {int(k): tuple(v) for k, v in json.loads(r["labels_json"]).items()}
            labels.update(overrides.get(r["id"], {}))
            for t, sp in labels.values():
                if sp and t in ("dialogue", "thought"):
                    cid = self.lookup(sp)
                    if cid is not None:
                        counts[cid] += 1
        with self.store.tx() as c:
            c.execute("UPDATE characters SET lines=0 WHERE novel_id=?", (self.novel_id,))
            c.executemany("UPDATE characters SET lines=? WHERE id=?", [(n, cid) for cid, n in counts.items()])
        self.reload()
        self.assign_slots()

    def assign_slots(self, palette: int = 12) -> None:
        """Give the most active characters distinct palette slots (stable once assigned)."""
        ranked = sorted(self.chars.values(), key=lambda c: (-(c.get("lines") or 0), c["id"]))
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
                tx.executemany("UPDATE characters SET auto_slot=? WHERE id=?", updates)
