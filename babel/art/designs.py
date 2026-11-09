"""Design operations shared by the API, the CLI and the art scheduler.

Lifecycle of a character's design:

    new ──draft profile──▶ profiled ──queue candidates──▶ candidates ──(images done)──▶ choose
        ──you pick one──▶ sheet ──(expressions done)──▶ approved

Every generated image is a row in ``art_images``; rows with status ``queued`` are the
work queue the scheduler drains in reading order.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from babel.art import plan
from babel.art.profile import EMOTIONS, FIELDS, base_prompt, expression_prompt
from babel.memory.akashic import Akashic
from babel.store.db import Store, now

BASE_W, BASE_H = 832, 1216
CANDIDATES = 6
DEFAULT_ART = {"style": "manhwa", "setting": "", "era": "", "auto": False}
BASE_MODEL = "anima-turbo"
EDIT_MODEL = "flux2-klein-4b"


# ── novel-level settings ──────────────────────────────────────────────────
def art_settings(store: Store, novel_id: int) -> dict:
    row = store.one("SELECT art FROM novels WHERE id=?", (novel_id,)) or {}
    return {**DEFAULT_ART, **(json.loads(row["art"]) if row.get("art") else {})}


def set_art_settings(store: Store, novel_id: int, **changes) -> dict:
    cur = art_settings(store, novel_id)
    cur.update({k: v for k, v in changes.items() if k in DEFAULT_ART and v is not None})
    store.x("UPDATE novels SET art=? WHERE id=?", (json.dumps(cur), novel_id))
    return cur


# ── designs ───────────────────────────────────────────────────────────────
def get_design(store: Store, eid: int) -> dict | None:
    return store.one("SELECT * FROM designs WHERE entity_id=?", (eid,))


def ensure_design(store: Store, eid: int) -> dict:
    d = get_design(store, eid)
    if d is None:
        store.x("INSERT INTO designs (entity_id, status, updated_at) VALUES (?, 'new', ?)", (eid, now()))
        d = get_design(store, eid)
    assert d is not None
    return d


def _update(store: Store, design_id: int, **fields) -> None:
    fields["updated_at"] = now()
    cols = ", ".join(f"{k}=?" for k in fields)
    store.x(f"UPDATE designs SET {cols} WHERE id=?", (*fields.values(), design_id))


def save_profile(store: Store, eid: int, profile: dict, *, user: bool, status: str | None = None) -> dict:
    """Store a profile. User edits lock their fields; a model draft never overwrites a locked field."""
    d = ensure_design(store, eid)
    old = json.loads(d["profile"]) if d.get("profile") else {}
    locked = set(json.loads(d["profile_locked"])) if d.get("profile_locked") else set()
    merged = dict(old)
    for f in (*FIELDS, "tags"):
        if f not in profile:
            continue
        if user:
            if profile[f] != old.get(f):
                locked.add(f)
            merged[f] = profile[f]
        elif f not in locked:
            merged[f] = profile[f]
    for f in FIELDS:
        merged.setdefault(f, {"value": "", "guessed": True, "chapter": None, "quote": ""})
    merged.setdefault("tags", [])
    new_status = status or (d["status"] if d["status"] != "new" else "profiled")
    _update(store, d["id"], profile=json.dumps(merged), profile_locked=json.dumps(sorted(locked)), status=new_status)
    return merged


def image_dir(art_dir: Path, novel_id: int, eid: int) -> Path:
    p = art_dir / str(novel_id) / str(eid)
    p.mkdir(parents=True, exist_ok=True)
    return p


def queue_candidates(store: Store, ak: Akashic, eid: int, n: int = CANDIDATES, *, manual: bool = True,
                     attempt: int = 1) -> list[int]:
    """Queue ``n`` base options. ``manual`` (you asked) runs right away; automatic work waits until you're idle."""
    d = ensure_design(store, eid)
    if not d.get("profile"):
        raise ValueError("draft or write the appearance profile first")
    profile = json.loads(d["profile"])
    prompt, negative = base_prompt(profile, ak.gender(eid), art_settings(store, ak.novel_id))
    ids = []
    for _ in range(n):
        ids.append(store.x(
            "INSERT INTO art_images (design_id, kind, status, seed, model, prompt, manual, attempt, created_at)"
            " VALUES (?, 'candidate', 'queued', ?, ?, ?, ?, ?, ?)",
            (d["id"], random.randint(1, 2**31 - 1), BASE_MODEL, json.dumps({"prompt": prompt, "negative": negative}),
             int(manual), attempt, now())))
    _update(store, d["id"], status="candidates", message=None)
    return ids


def queue_expression(store: Store, design_id: int, emotion: str, *, manual: bool = True, attempt: int = 1) -> int:
    return store.x("INSERT INTO art_images (design_id, kind, emotion, status, seed, model, prompt, manual, attempt,"
                   " created_at) VALUES (?, 'expression', ?, 'queued', ?, ?, ?, ?, ?, ?)",
                   (design_id, emotion, random.randint(1, 2**31 - 1), EDIT_MODEL,
                    json.dumps({"prompt": expression_prompt(emotion)}), int(manual), attempt, now()))


def approve_candidate(store: Store, image_id: int) -> dict:
    """You picked a base portrait: it becomes the neutral expression and the rest of the sheet is queued."""
    img = store.one("SELECT * FROM art_images WHERE id=?", (image_id,))
    if img is None or img["kind"] != "candidate" or img["status"] not in ("done", "rejected") or not img["path"]:
        raise ValueError("only a finished option can be chosen")
    if img["status"] == "rejected":  # you overrule the quality checker
        store.x("UPDATE art_images SET status='done' WHERE id=?", (image_id,))
    d = store.one("SELECT * FROM designs WHERE id=?", (img["design_id"],))
    with store.tx() as c:
        c.execute("UPDATE art_images SET status='rejected' WHERE design_id=? AND kind='expression'", (d["id"],))
        c.execute("INSERT INTO art_images (design_id, kind, emotion, status, path, seed, model, prompt, manual,"
                  " qc_status, qc_score, qc, created_at) VALUES (?, 'expression', 'neutral', 'done', ?, ?, ?, ?, 1,"
                  " ?, ?, ?, ?)", (d["id"], img["path"], img["seed"], img["model"], img["prompt"], img.get("qc_status"),
                                   img.get("qc_score"), img.get("qc"), now()))
    for emotion in EMOTIONS:
        if emotion != "neutral":
            queue_expression(store, d["id"], emotion, manual=True)  # you're waiting for this sheet
    _update(store, d["id"], base_image_id=image_id, status="sheet", message=None)
    return store.one("SELECT * FROM designs WHERE id=?", (d["id"],))


def reroll(store: Store, image_id: int) -> int:
    """Redo one expression (new seed); the old one is kept as rejected."""
    img = store.one("SELECT * FROM art_images WHERE id=?", (image_id,))
    if img is None or img["kind"] != "expression" or img["emotion"] == "neutral":
        raise ValueError("only a generated expression can be rerolled")
    store.x("UPDATE art_images SET status='rejected' WHERE id=?", (image_id,))
    new = queue_expression(store, img["design_id"], img["emotion"], manual=True)
    _update(store, img["design_id"], status="sheet")
    return new


def reset(store: Store, eid: int, *, keep_profile: bool = True) -> None:
    d = get_design(store, eid)
    if d is None:
        return
    store.x("UPDATE art_images SET status='rejected' WHERE design_id=? AND status IN ('queued','done','failed')",
            (d["id"],))
    _update(store, d["id"], status="profiled" if keep_profile and d.get("profile") else "new",
            base_image_id=None, message=None)


def after_image(store: Store, design_id: int) -> None:
    """Advance a design once its queued images are finished."""
    d = store.one("SELECT * FROM designs WHERE id=?", (design_id,))
    if d is None:
        return
    pending = store.one("SELECT COUNT(*) n FROM art_images WHERE design_id=? AND (status IN ('queued','running')"
                        " OR (status='done' AND qc_status='pending'))", (design_id,))["n"]
    if pending:
        return
    if d["status"] == "candidates":
        done = store.one("SELECT COUNT(*) n FROM art_images WHERE design_id=? AND kind='candidate' AND status='done'",
                         (design_id,))["n"]
        message = None
        if not done:  # the checker rejected everything: show the best few rather than nothing
            best = store.q("SELECT id FROM art_images WHERE design_id=? AND kind='candidate' AND status='rejected'"
                           " AND qc_status='fail' ORDER BY qc_score DESC LIMIT 3", (design_id,))
            for r in best:
                store.x("UPDATE art_images SET status='done' WHERE id=?", (r["id"],))
            done = len(best)
            message = ("The checker wasn't happy with any option; these are the closest. "
                       "Adjusting the profile usually helps.") if best else None
        _update(store, design_id, status="choose" if done else "failed",
                message=message if done else "every option failed — see the art log")
    elif d["status"] == "sheet":
        have = {r["emotion"] for r in store.q(
            "SELECT emotion FROM art_images WHERE design_id=? AND kind='expression' AND status='done'", (design_id,))}
        missing = [e for e in EMOTIONS if e not in have]
        _update(store, design_id, status="approved" if not missing else "failed",
                message=None if not missing else f"missing: {', '.join(missing)}")


# ── views ─────────────────────────────────────────────────────────────────
def image_public(img: dict) -> dict:
    qc = json.loads(img["qc"]) if img.get("qc") else None
    has_file = bool(img["path"]) and img["status"] in ("done", "rejected")
    return {"id": img["id"], "kind": img["kind"], "emotion": img["emotion"], "status": img["status"],
            "seed": img["seed"], "model": img["model"], "error": img["error"], "secs": img["secs"],
            "attempt": img.get("attempt") or 1, "qc_status": img.get("qc_status"), "qc_score": img.get("qc_score"),
            "qc_issues": (qc or {}).get("issues") or [],
            "url": f"/api/art/images/{img['id']}" if has_file else None,
            "thumb": f"/api/art/images/{img['id']}?thumb=1" if has_file else None}


def _rank(img: dict) -> tuple:
    """Best first: finished and passing the checker, by score; then the rest."""
    order = {"pass": 0, "skipped": 1, None: 1, "pending": 1, "fail": 2}
    return (img["status"] != "done", order.get(img.get("qc_status"), 1), -(img.get("qc_score") or 0), -img["id"])


def design_view(store: Store, ak: Akashic, eid: int) -> dict:
    d = get_design(store, eid)
    info = next((c for c in plan.characters(store, ak) if c["id"] == eid), None)
    images = store.q("SELECT * FROM art_images WHERE design_id=? AND status != 'rejected' ORDER BY id",
                     (d["id"],)) if d else []
    checker_rejected = store.q("SELECT * FROM art_images WHERE design_id=? AND status='rejected' AND qc_status='fail'"
                               " AND kind='candidate' ORDER BY id DESC", (d["id"],)) if d else []
    sheet = {e: None for e in EMOTIONS}
    for img in images:
        if img["kind"] == "expression":
            sheet[img["emotion"]] = image_public(img)
    return {
        "entity_id": eid, "name": ak.name(eid), "status": d["status"] if d else "new",
        "message": d.get("message") if d else None,
        "tier": info["tier"] if info else "extra", "tier_locked": bool(info and info["tier_locked"]),
        "first_idx": info["first_idx"] if info else None, "lines": info["lines"] if info else 0,
        "profile": json.loads(d["profile"]) if d and d.get("profile") else None,
        "profile_locked": json.loads(d["profile_locked"]) if d and d.get("profile_locked") else [],
        "base_image_id": d["base_image_id"] if d else None,
        "candidates": [image_public(i) for i in sorted((i for i in images if i["kind"] == "candidate"), key=_rank)],
        "rejected": [image_public(i) for i in checker_rejected],
        "sheet": sheet,
    }
