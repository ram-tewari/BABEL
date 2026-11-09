"""Measure labeling quality and cost on gold chapters.

Each gold chapter is ``<name>.txt`` plus ``<name>.gold.json``:

    {"title": "...", "pov": "Sam", "aliases": {"Mira": "Mira Vell"},
     "lines": [["You're late,", "dialogue", "Tobin"], ["CRASH!", "sfx", null], ...]}

A gold line matches the first not-yet-used block whose text contains the snippet.
Speakers are compared after alias normalization (gold aliases + BABEL's own memory),
so "Mira" and "Mira Vell" count as the same person.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from babel.library import chapter_view
from babel.memory.akashic import Akashic
from babel.scenario.cascade import Cascade
from babel.store.db import Store, norm_name

GOLD_DIR = Path(__file__).parent / "gold"


@dataclass
class FileResult:
    name: str
    total: int = 0
    type_ok: int = 0
    speaker_total: int = 0
    speaker_ok: int = 0
    missing: int = 0
    errors: list[str] = field(default_factory=list)
    usage: dict[str, dict[str, int]] = field(default_factory=dict)
    tiers: dict[str, int] = field(default_factory=dict)


def load_gold(directory: Path = GOLD_DIR) -> list[tuple[str, str, dict]]:
    out = []
    for gold in sorted(directory.glob("*.gold.json")):
        name = gold.name.removesuffix(".gold.json")
        out.append((name, (directory / f"{name}.txt").read_text(), json.loads(gold.read_text())))
    return out


def evaluate_one(name: str, text: str, gold: dict, cascade: Cascade, mode: str = "auto") -> FileResult:
    from babel.ingest.txt import split_chapters

    res = FileResult(name)
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "eval.db")
        chapters = split_chapters(text)
        nid = store.create_novel(gold.get("title", name), [(c.title, c.text, c.sha) for c in chapters])
        ak = Akashic(store, nid)
        if gold.get("pov"):
            eid = ak.create(gold["pov"])
            ak.set_alias(eid, "I")
            ak.set_pov(eid)
        for row in store.q("SELECT id FROM chapters WHERE novel_id=? ORDER BY idx", (nid,)):
            ch = store.get_chapter(row["id"])
            out = cascade.transform(store, ak, ch, mode=mode)
            store.save_doc(ch["id"], out.decisions, summary=out.summary, review_count=out.review_count,
                           tiers=out.tiers, stats=out.stats)
            for k, v in out.tiers.items():
                res.tiers[k] = res.tiers.get(k, 0) + v
        ak.reload()
        blocks = []
        for row in store.q("SELECT id FROM chapters WHERE novel_id=? ORDER BY idx", (nid,)):
            blocks += chapter_view(store, row["id"], ak)["blocks"]
        for u in store.usage_summary(nid):
            t = res.usage.setdefault(u["tier"], {"prompt": 0, "completion": 0, "questions": 0, "calls": 0})
            t["prompt"] += u["prompt_tokens"] or 0
            t["completion"] += u["completion_tokens"] or 0
            t["questions"] += u["questions"] or 0
            t["calls"] += u["calls"] or 0

        aliases = {norm_name(k): v for k, v in gold.get("aliases", {}).items()}

        def canon(n: str | None) -> str | None:
            if not n:
                return None
            n = aliases.get(norm_name(n), n)
            eid = ak.lookup(n)
            n2 = ak.name(eid) if eid is not None else n
            return norm_name(aliases.get(norm_name(n2), n2))

        cursor = 0
        for snippet, gtype, gspeaker in gold["lines"]:
            res.total += 1
            idx = next((i for i in range(cursor, len(blocks)) if snippet in blocks[i]["text"]), None)
            if idx is None:
                idx = next((i for i in range(len(blocks)) if snippet in blocks[i]["text"]), None)
            if idx is None:
                res.missing += 1
                res.errors.append(f"missing block for {snippet!r}")
                continue
            cursor = idx
            b = blocks[idx]
            if b["type"] == gtype:
                res.type_ok += 1
            else:
                res.errors.append(f"type  {snippet[:40]!r}: got {b['type']}, want {gtype}")
            if gspeaker is not None:
                res.speaker_total += 1
                got = b["speaker"]
                if got is None and b["character_id"] is not None:
                    got = ak.name(b["character_id"])
                if canon(got) == canon(gspeaker):
                    res.speaker_ok += 1
                else:
                    res.errors.append(f"who   {snippet[:40]!r}: got {got}, want {gspeaker}"
                                      f"  [{b['tier']} {b['conf']}: {b.get('why')}]")
        store.close()
    return res


def evaluate(cascade: Cascade, mode: str = "auto", directory: Path = GOLD_DIR) -> list[FileResult]:
    return [evaluate_one(n, t, g, cascade, mode) for n, t, g in load_gold(directory)]
