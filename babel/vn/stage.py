"""Stage a chapter as a visual novel: who's on screen, with which expression, in front of which background.

Computed from the chapter's decisions (instant, rules), stored per chapter, and
refined by the text model for the uncertain lines and scenes (one batched call
each). Recomputed automatically whenever the chapter's lines change.
"""

from __future__ import annotations

import hashlib
import json

from babel.art import designs, plan
from babel.art.profile import EMOTIONS
from babel.library import chapter_view
from babel.memory.akashic import Akashic
from babel.store.db import Store, now
from babel.vn import emotion as emo
from babel.vn import library as lib
from babel.vn import scenes as sc

REFINE_BELOW = 0.7


RULES_VERSION = 3  # bump when the staging rules change: every chapter is re-staged


def _basis(view: dict) -> str:
    sig = [RULES_VERSION] + [(b["type"], b.get("speaker"), b.get("tone"), b["text"][:40]) for b in view["blocks"]]
    return hashlib.sha1(json.dumps(sig).encode()).hexdigest()[:16]


def get(store: Store, ak: Akashic, chapter_id: int) -> tuple[dict, dict, bool]:
    """(chapter view, stage data, refined) — recomputed from rules if the chapter changed."""
    view = chapter_view(store, chapter_id, ak)
    if view is None:
        raise KeyError(chapter_id)
    basis = _basis(view)
    row = store.one("SELECT * FROM stage WHERE chapter_id=?", (chapter_id,))
    if row and row["basis"] == basis:
        return view, json.loads(row["data"]), bool(row["refined"])
    data = {"emotions": emo.rule_emotions(view["blocks"]), "scenes": sc.locate(view["blocks"], ak)}
    data = json.loads(json.dumps(data, default=str))  # one key type (str) from here on
    _save(store, chapter_id, basis, data, False)
    return view, data, False


def _save(store: Store, chapter_id: int, basis: str, data: dict, refined: bool) -> None:
    store.x("INSERT OR REPLACE INTO stage (chapter_id, basis, data, refined, updated_at) VALUES (?,?,?,?,?)",
            (chapter_id, basis, json.dumps(data, default=str), int(refined), now()))


def refine(store: Store, ak: Akashic, chapter_id: int, llm, batch: int = 24) -> dict:
    """Ask the text model about the uncertain lines' expressions and the scenes' places."""
    view, data, _ = get(store, ak, chapter_id)
    blocks = view["blocks"]
    targets = [i for i, b in enumerate(blocks) if b["type"] in ("dialogue", "thought")
               and str(b["seg"][0]) in data["emotions"]
               and _emotion_row(data, b)[1] < REFINE_BELOW]
    for k in range(0, len(targets), batch):
        part = targets[k:k + batch]
        msgs, schema, part = emo.refine_messages(blocks, part)
        reply = llm.chat(msgs, schema=schema, max_tokens=40 + 6 * len(part))
        _log(store, view, reply, "stage-emotion", len(part))
        for i, e in emo.parse_refine(reply.content, part).items():
            data["emotions"][str(blocks[i]["seg"][0])] = [e, 0.85, "local"]
    if data["scenes"] and any(s["conf"] < REFINE_BELOW for s in data["scenes"]):
        msgs, schema = sc.refine_messages(blocks, data["scenes"], ak)
        reply = llm.chat(msgs, schema=schema, max_tokens=60 + 30 * len(data["scenes"]))
        _log(store, view, reply, "stage-scenes", len(data["scenes"]))
        data["scenes"] = sc.apply_refine(reply.content, data["scenes"], ak)
    _save(store, chapter_id, _basis(view), data, True)
    return data


def _log(store: Store, view: dict, reply, purpose: str, n: int) -> None:
    tier = "local" if getattr(reply, "provider", "") == "ollama" else "cloud"
    store.log_usage(view["novel_id"], view["id"], tier, purpose, reply.provider, reply.model,
                    reply.prompt_tokens, reply.completion_tokens, n)


def _emotion_row(data: dict, block: dict) -> list:
    return data["emotions"].get(str(block["seg"][0])) or ["neutral", 0.5, "rule"]


# ── who plays whom ─────────────────────────────────────────────────────────
def _era(store: Store, novel_id: int) -> str:
    return designs.art_settings(store, novel_id).get("era") or "timeless"


def actors(store: Store, ak: Akashic, view: dict, data: dict) -> dict[int, dict]:
    """entity → the design that plays them on stage: their own, or a library face (minor characters)."""
    chars = {c["id"]: c for c in plan.characters(store, ak)}
    era = _era(store, ak.novel_id)
    out: dict[int, dict] = {}
    for b in view["blocks"]:
        eid = b.get("character_id")
        if eid is None or eid in out or eid not in ak.ents:
            continue
        c = chars.get(eid)
        if c and c["tier"] in plan.REQUIRED:
            out[eid] = {"design_entity": eid, "kind": "design"}
        else:
            out[eid] = {"design_entity": lib.assign_extra(store, ak, eid, era), "kind": "extra"}
    return out


def backgrounds(store: Store, ak: Akashic, data: dict) -> list[int]:
    """The background design (entity) for each scene; named places get their own, others the library's."""
    era = _era(store, ak.novel_id)
    out = []
    for s in data["scenes"]:
        p = s["place"]
        if p["kind"] == "named" and p.get("id") in ak.ents:
            out.append(lib.ensure_named_background(store, ak, p["id"], era, p.get("generic")))
        else:
            out.append(lib.ensure_generic_background(store, era, p.get("key") or sc.GENERIC_DEFAULT))
    return out


def prepare(store: Store, ak: Akashic, chapter_id: int, *, manual: bool) -> list[int]:
    """Make sure every face and background this chapter needs is designed or queued. Returns design entity ids."""
    view, data, _ = get(store, ak, chapter_id)
    needed = [a["design_entity"] for a in actors(store, ak, view, data).values() if a["kind"] == "extra"]
    needed += backgrounds(store, ak, data)
    lib_ak = Akashic(store, lib.library_novel_id(store))
    for eid in dict.fromkeys(needed):
        d = designs.get_design(store, eid)
        if d and d["status"] == "profiled":
            owner = lib_ak if eid in lib_ak.ents else ak
            designs.queue_candidates(store, owner, eid, manual=manual)
    return needed


# ── what the reader gets ───────────────────────────────────────────────────
def _sheet(store: Store, design_entity: int) -> dict[str, int]:
    d = designs.get_design(store, design_entity)
    if not d or d["status"] not in ("approved", "sheet"):
        return {}
    rows = store.q("SELECT id, emotion FROM art_images WHERE design_id=? AND kind='expression' AND status='done'"
                   " ORDER BY id", (d["id"],))
    return {r["emotion"]: r["id"] for r in rows}


def _sprite_url(sheet: dict[str, int], emotion: str) -> str | None:
    e = emotion if emotion in sheet else lib.EXTRA_FALLBACK.get(emotion, "neutral")
    img = sheet.get(e) or sheet.get("neutral")
    return f"/api/art/images/{img}?sprite=1" if img else None


def _background_url(store: Store, design_entity: int) -> str | None:
    d = designs.get_design(store, design_entity)
    if d and d["status"] == "approved" and d.get("base_image_id"):
        return f"/api/art/images/{d['base_image_id']}"
    return None


def stage_view(store: Store, ak: Akashic, chapter_id: int) -> dict:
    view, data, refined = get(store, ak, chapter_id)
    cast = actors(store, ak, view, data)
    sheets = {eid: _sheet(store, a["design_entity"]) for eid, a in cast.items()}
    bg_entities = backgrounds(store, ak, data)
    scenes_out = []
    for s, bg in zip(data["scenes"], bg_entities, strict=True):
        scenes_out.append({"start": s["start"], "end": s["end"], "place": s["place"]["name"], "night": s["night"],
                           "background": _background_url(store, bg)})
    # extras who'd look identical in the same scene get another face of their archetype
    for s in data["scenes"]:
        seen: dict[int, int] = {}
        for b in view["blocks"][s["start"]:s["end"]]:
            eid = b.get("character_id")
            if eid is None or eid not in cast or cast[eid]["kind"] != "extra":
                continue
            face = cast[eid]["design_entity"]
            if face in seen and seen[face] != eid:
                alt = lib.other_variant(store, face, set(seen))
                cast[eid] = {**cast[eid], "design_entity": alt}
                sheets[eid] = _sheet(store, alt)
                face = alt
            seen.setdefault(face, eid)
    blocks = []
    scene_of = []
    for n, s in enumerate(data["scenes"]):
        scene_of += [n] * (s["end"] - s["start"])
    for i, b in enumerate(view["blocks"]):
        row = {k: b[k] for k in ("type", "text", "speaker", "character_id", "tone", "para")}
        row["scene"] = scene_of[i] if i < len(scene_of) else (len(data["scenes"]) - 1)
        if b["type"] in ("dialogue", "thought", "action"):
            e = _emotion_row(data, b)[0] if b["type"] != "action" else "neutral"
            row["emotion"] = e if e in EMOTIONS else "neutral"
            row["sprite"] = (_sprite_url(sheets.get(b["character_id"], {}), row["emotion"])
                             if b.get("character_id") in cast else None)
        blocks.append(row)
    readiness = plan.readiness(store, ak, limit=0)
    missing = next((x["missing"] for x in plan.readiness(store, ak, limit=10_000)["blocked"]
                    if x["chapter_id"] == chapter_id), [])
    characters = {c["id"]: c for c in view["characters"]}
    return {
        "chapter": {k: view[k] for k in ("id", "novel_id", "idx", "title", "prev_id", "next_id")},
        "ready": chapter_id in readiness["ready_ids"], "missing": missing, "refined": refined,
        "scenes": scenes_out, "blocks": blocks,
        "cast": {str(eid): {"name": (characters.get(eid) or {}).get("name") or ak.name(eid),
                            "color": (characters.get(eid) or {}).get("color"),
                            "side": (characters.get(eid) or {}).get("side", "left"),
                            "extra": a["kind"] == "extra", "has_art": bool(sheets.get(eid))}
                 for eid, a in cast.items()},
    }
