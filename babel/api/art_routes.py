"""HTTP routes for character art: profiles, candidates, expression sheets, readiness."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from babel.art import designs, plan
from babel.art.profile import EMOTIONS, FIELD_LABELS, FIELDS
from babel.art.runner import ArtScheduler, draft_profile
from babel.memory.akashic import Akashic
from babel.store.db import Store


class ArtSettingsBody(BaseModel):
    style: str | None = None
    setting: str | None = None
    era: str | None = None
    auto: bool | None = None


class ProfileBody(BaseModel):
    profile: dict


class TierBody(BaseModel):
    tier: str | None  # main | supporting | minor | extra | None (automatic)


def art_router(store: Store, scheduler: ArtScheduler, llm_factory: Callable[[], object | None],
               novel_or_404: Callable[[int], dict], entity_or_404: Callable[[int], tuple[dict, Akashic]]) -> APIRouter:
    r = APIRouter()

    def character_or_404(eid: int) -> tuple[dict, Akashic]:
        e, ak = entity_or_404(eid)
        if e["kind"] != "character":
            raise HTTPException(400, "only characters get designs")
        return e, ak

    @r.get("/art/status")
    def art_status() -> dict:
        return {**scheduler.status(), "emotions": list(EMOTIONS), "fields": [
            {"key": f, "label": FIELD_LABELS[f]} for f in FIELDS]}

    @r.get("/novels/{nid}/art")
    def novel_art(nid: int) -> dict:
        novel_or_404(nid)
        ak = Akashic(store, nid)
        chars = plan.characters(store, ak)
        tiers = {t: sum(1 for c in chars if c["tier"] == t) for t in plan.TIERS}
        designed = sum(1 for c in chars if c["tier"] in plan.REQUIRED and c["status"] == "approved")
        return {"settings": designs.art_settings(store, nid), "scheduler": scheduler.status(),
                "tiers": tiers, "designed": designed, "needed": tiers["main"] + tiers["supporting"],
                "queue": plan.queue(store, ak), "readiness": plan.readiness(store, ak),
                "characters": [c for c in chars if c["tier"] in plan.REQUIRED or c["status"] != "new"]}

    @r.put("/novels/{nid}/art")
    def update_novel_art(nid: int, body: ArtSettingsBody) -> dict:
        novel_or_404(nid)
        if body.style is not None and body.style not in ("manhwa",):
            raise HTTPException(422, "style must be: manhwa")
        out = designs.set_art_settings(store, nid, **body.model_dump(exclude_unset=True))
        scheduler.poke()
        return out

    @r.get("/entities/{eid}/design")
    def get_design(eid: int) -> dict:
        _, ak = character_or_404(eid)
        return designs.design_view(store, ak, eid)

    @r.put("/entities/{eid}/design/profile")
    def put_profile(eid: int, body: ProfileBody) -> dict:
        _, ak = character_or_404(eid)
        clean: dict = {}
        for f in FIELDS:
            v = body.profile.get(f)
            if isinstance(v, dict) and isinstance(v.get("value"), str):
                clean[f] = {"value": v["value"].strip()[:200], "guessed": False,
                            "chapter": v.get("chapter") if isinstance(v.get("chapter"), int) else None,
                            "quote": str(v.get("quote") or "")[:240]}
        if isinstance(body.profile.get("tags"), list):
            clean["tags"] = [str(t).strip().lower()[:40] for t in body.profile["tags"] if str(t).strip()][:20]
        designs.save_profile(store, eid, clean, user=True)
        return designs.design_view(store, ak, eid)

    @r.post("/entities/{eid}/design/draft")
    def draft(eid: int) -> dict:
        _, ak = character_or_404(eid)
        llm = llm_factory()
        if llm is None:
            raise HTTPException(503, "no text model available to read the book — fill in the profile by hand")
        try:
            draft_profile(store, ak, eid, llm)
        except Exception as e:
            raise HTTPException(502, f"profile draft failed: {e}") from e
        return designs.design_view(store, ak, eid)

    @r.post("/entities/{eid}/design/candidates")
    def candidates(eid: int) -> dict:
        _, ak = character_or_404(eid)
        try:
            designs.queue_candidates(store, ak, eid)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        scheduler.poke()
        return designs.design_view(store, ak, eid)

    @r.post("/entities/{eid}/design/reset")
    def reset(eid: int) -> dict:
        _, ak = character_or_404(eid)
        designs.reset(store, eid)
        return designs.design_view(store, ak, eid)

    @r.put("/entities/{eid}/design/tier")
    def set_tier(eid: int, body: TierBody) -> dict:
        _, ak = character_or_404(eid)
        if body.tier is not None and body.tier not in plan.TIERS:
            raise HTTPException(422, f"tier must be one of {', '.join(plan.TIERS)}")
        store.x("UPDATE entities SET art_tier=? WHERE id=?", (body.tier, eid))
        ak.reload()
        scheduler.poke()
        return designs.design_view(store, ak, eid)

    def image_or_404(image_id: int) -> tuple[dict, Akashic]:
        img = store.one("SELECT i.*, d.entity_id FROM art_images i JOIN designs d ON d.id=i.design_id WHERE i.id=?",
                        (image_id,))
        if img is None:
            raise HTTPException(404, "image not found")
        _, ak = entity_or_404(img["entity_id"])
        return img, ak

    @r.post("/art/images/{image_id}/approve")
    def approve(image_id: int) -> dict:
        img, ak = image_or_404(image_id)
        try:
            designs.approve_candidate(store, image_id)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        scheduler.poke()
        return designs.design_view(store, ak, img["entity_id"])

    @r.post("/art/images/{image_id}/reroll")
    def reroll(image_id: int) -> dict:
        img, ak = image_or_404(image_id)
        try:
            designs.reroll(store, image_id)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        scheduler.poke()
        return designs.design_view(store, ak, img["entity_id"])

    @r.get("/art/images/{image_id}")
    def image_file(image_id: int, thumb: bool = False, sprite: bool = False):
        img, _ = image_or_404(image_id)
        if not img["path"]:
            raise HTTPException(404, "not drawn yet")
        p = Path(img["path"])
        if sprite and p.exists():
            from babel.art.sprite import make_sprite

            return FileResponse(make_sprite(p), media_type="image/png", headers={"Cache-Control": "max-age=86400"})
        if thumb and p.with_suffix(".thumb.jpg").exists():
            return FileResponse(p.with_suffix(".thumb.jpg"), media_type="image/jpeg",
                                headers={"Cache-Control": "max-age=86400"})
        if not p.exists():
            raise HTTPException(404, "file missing")
        return FileResponse(p, media_type="image/png", headers={"Cache-Control": "max-age=86400"})

    @r.get("/novels/{nid}/library")
    def novel_library(nid: int) -> dict:
        """The shared faces and backgrounds this novel uses (and the novel's own named places)."""
        import json as _json

        from babel.vn.library import library_novel_id

        novel_or_404(nid)
        lib_id = library_novel_id(store)
        used = {r["extra_id"] for r in store.q("SELECT extra_id FROM entities WHERE novel_id=? AND extra_id IS NOT NULL",
                                               (nid,))}
        rows = store.q("SELECT d.*, e.name, e.novel_id FROM designs d JOIN entities e ON e.id=d.entity_id"
                       " WHERE d.kind IN ('extra','background') AND (e.novel_id=? OR e.novel_id=?)"
                       " ORDER BY d.kind, d.id", (lib_id, nid))
        era = designs.art_settings(store, nid).get("era") or "timeless"
        from babel.vn.library import era_key

        out = []
        for d in rows:
            spec = _json.loads(d["spec"]) if d.get("spec") else {}
            if d["novel_id"] == lib_id and d["kind"] == "extra" and d["entity_id"] not in used:
                continue
            if d["novel_id"] == lib_id and d["kind"] == "background" and era_key(spec.get("era")) != era_key(era):
                continue
            label = spec.get("name") or spec.get("label") or d["name"]
            if d["kind"] == "extra":
                label = f"{spec.get('label', 'extra')} #{spec.get('variant', 0) + 1}"
            out.append({"entity_id": d["entity_id"], "kind": d["kind"], "label": label, "status": d["status"],
                        "thumb": f"/api/art/images/{d['base_image_id']}?thumb=1" if d.get("base_image_id") else None,
                        "users": [x["name"] for x in store.q("SELECT name FROM entities WHERE novel_id=? AND extra_id=?",
                                                              (nid, d["entity_id"]))][:6]})
        first_ready = plan.readiness(store, Akashic(store, nid), limit=0)["ready_ids"][:1]
        return {"items": out, "first_ready_chapter": first_ready[0] if first_ready else None}

    @r.post("/novels/{nid}/library/defaults")
    def paint_defaults(nid: int) -> dict:
        """Paint the common sets for this novel's era up front (street, room, pub, …), so scenes rarely wait."""
        from babel.vn.library import DEFAULT_SETS, ensure_generic_background, library_novel_id

        novel_or_404(nid)
        era = designs.art_settings(store, nid).get("era") or "timeless"
        lib_ak = Akashic(store, library_novel_id(store))
        queued = 0
        for key in DEFAULT_SETS:
            eid = ensure_generic_background(store, era, key)
            d = designs.get_design(store, eid)
            if d and d["status"] == "profiled":
                lib_ak.reload()
                designs.queue_candidates(store, lib_ak, eid, manual=True)
                queued += 1
        scheduler.poke()
        return {"queued": queued, "era": era}

    @r.post("/library/{eid}/redraw")
    def redraw_library(eid: int) -> dict:
        """Draw a shared face or background again (you didn't like it)."""
        d = designs.get_design(store, eid)
        if d is None or d.get("kind") not in ("extra", "background"):
            raise HTTPException(404, "not a library item")
        row = store.one("SELECT novel_id FROM entities WHERE id=?", (eid,))
        designs.reset(store, eid)
        designs.queue_candidates(store, Akashic(store, row["novel_id"]), eid, manual=True)
        scheduler.poke()
        return {"ok": True}

    @r.get("/novels/{nid}/play")
    def play(nid: int) -> dict:
        """Where the visual novel starts and where you left off."""
        n = novel_or_404(nid)
        first = store.one("SELECT id, idx, title FROM chapters WHERE novel_id=? AND status='done' ORDER BY idx LIMIT 1",
                          (nid,))
        prog = store.one("SELECT c.id, c.idx, c.title FROM progress p JOIN chapters c ON c.id=p.chapter_id"
                         " WHERE p.novel_id=?", (nid,))
        r_ = plan.readiness(store, Akashic(store, nid), limit=0)
        return {"title": n["title"], "author": n.get("author"), "has_cover": bool(n.get("cover_path")),
                "first": first, "continue": prog if prog and prog["id"] != (first or {}).get("id") else None,
                "ready": r_["ready"], "transformed": r_["transformed"], "total": r_["total"]}

    # ── visual novel ──────────────────────────────────────────────────────
    def chapter_ak(cid: int) -> Akashic:
        row = store.one("SELECT novel_id FROM chapters WHERE id=?", (cid,))
        if row is None:
            raise HTTPException(404, "chapter not found")
        return Akashic(store, row["novel_id"])

    @r.get("/chapters/{cid}/stage")
    def chapter_stage(cid: int) -> dict:
        """The chapter staged as a visual novel (instant; uses rules until the text model has refined it)."""
        from babel.vn import stage

        return stage.stage_view(store, chapter_ak(cid), cid)

    @r.post("/chapters/{cid}/stage/prepare")
    def prepare_stage(cid: int) -> dict:
        """You're reading this chapter now: refine it and draw what it (and the next one) needs, right away."""
        from babel.vn import stage

        ak = chapter_ak(cid)
        llm = llm_factory()
        _, _, refined = stage.get(store, ak, cid)
        # the text model only if it (or a smaller one) fits right now — otherwise the rules' staging is used
        from babel.system import fitting_model

        llm = fitting_model(llm, scheduler.governor)
        if llm is not None and not refined:
            try:
                stage.refine(store, ak, cid, llm)
            except Exception as e:  # rules are a fine fallback
                raise HTTPException(502, f"couldn't refine the staging: {e}") from e
        needed = stage.prepare(store, ak, cid, manual=True, llm=llm)
        nxt = store.one("SELECT c2.id FROM chapters c1 JOIN chapters c2 ON c2.novel_id=c1.novel_id"
                        " AND c2.idx=c1.idx+1 WHERE c1.id=? AND c2.status='done'", (cid,))
        if nxt:
            stage.prepare(store, ak, nxt["id"], manual=False)
        scheduler.poke()
        return {**stage.stage_view(store, ak, cid), "queued": len(needed)}

    return r
