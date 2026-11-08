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
    def image_file(image_id: int, thumb: bool = False):
        img, _ = image_or_404(image_id)
        if not img["path"]:
            raise HTTPException(404, "not drawn yet")
        p = Path(img["path"])
        if thumb and p.with_suffix(".thumb.jpg").exists():
            return FileResponse(p.with_suffix(".thumb.jpg"), media_type="image/jpeg",
                                headers={"Cache-Control": "max-age=86400"})
        if not p.exists():
            raise HTTPException(404, "file missing")
        return FileResponse(p, media_type="image/png", headers={"Cache-Control": "max-age=86400"})

    return r
