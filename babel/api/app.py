"""HTTP API + the built web UI."""

from __future__ import annotations

import json
import shutil
import tempfile
from collections import Counter
from contextlib import asynccontextmanager
from itertools import combinations
from pathlib import Path

from fastapi import APIRouter, Body, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from babel import __version__
from babel.api.art_routes import art_router
from babel.art.runner import ArtScheduler, SubprocessBackend
from babel.config import Settings
from babel.ingest import IngestError, load_book
from babel.library import chapter_view, effective_decisions, entity_public, import_book, save_image
from babel.memory.akashic import KINDS, Akashic
from babel.memory.glossary import GlossaryError, export_yaml, import_yaml, parse_yaml
from babel.models import TONES, BlockType, Decision, Tier
from babel.pipeline.jobs import TIER_MODES, Worker, create_job
from babel.scenario.cascade import Cascade
from babel.scenario.segment import segment_text
from babel.store.db import Store

WEB_DIST = [Path(__file__).resolve().parent.parent / "web_dist", Path(__file__).resolve().parents[2] / "web" / "dist"]


class NovelPatch(BaseModel):
    title: str | None = None
    author: str | None = None
    description: str | None = None
    status: str | None = None
    tags: list[str] | None = None
    pov_character_id: int | None = None


class EditBody(BaseModel):
    segs: list[int] = Field(min_length=1)
    type: str
    speaker: str | None = None
    tone: str | None = None


class SegsBody(BaseModel):
    segs: list[int] | None = None


class EntityBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: str = "character"
    note: str | None = None
    gender: str | None = None


class EntityPatch(BaseModel):
    name: str | None = None
    kind: str | None = None
    note: str | None = None
    gender: str | None = None
    color: str | None = None
    side: str | None = None
    faction_id: int | None = None


class MergeBody(BaseModel):
    into: int


class AliasBody(BaseModel):
    alias: str = Field(min_length=1, max_length=60)


class JobBody(BaseModel):
    first: int | None = None
    last: int | None = None
    force: bool = False
    tiers: str = "auto"


class ProgressBody(BaseModel):
    chapter_id: int
    position: float = 0.0


class MetadataBody(BaseModel):
    sources: list[str] | None = None
    apply: bool = False


class CoverUrlBody(BaseModel):
    url: str


def build_art_scheduler(settings: Settings, store: Store, cascade: Cascade) -> ArtScheduler:
    python = settings.art_python_path()
    backend = (lambda: SubprocessBackend(python, settings.art_dir / "worker.log")) if python else None
    return ArtScheduler(store, art_dir=settings.art_dir, portraits_dir=settings.portraits_dir,
                        backend_factory=backend, llm_factory=lambda: cascade.local or cascade.cloud)


def create_app(settings: Settings | None = None, store: Store | None = None, cascade: Cascade | None = None,
               start_worker: bool = True, art: ArtScheduler | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = store or Store(settings.db_path)
    cascade = cascade or settings.build_cascade()
    worker = Worker(store, lambda: cascade, settings.concurrency, settings.parallel_novels)
    art = art or build_art_scheduler(settings, store, cascade)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if start_worker:
            worker.start()
            art.start()
        yield
        worker.stop()
        art.stop()

    app = FastAPI(title="BABEL", version=__version__, lifespan=lifespan)
    app.state.store, app.state.worker, app.state.cascade, app.state.art = store, worker, cascade, art
    api = APIRouter(prefix="/api")

    # ── helpers ───────────────────────────────────────────────────────────
    def novel_or_404(nid: int) -> dict:
        n = store.get_novel(nid)
        if n is None:
            raise HTTPException(404, "novel not found")
        return n

    def chapter_or_404(cid: int) -> dict:
        ch = store.get_chapter(cid)
        if ch is None:
            raise HTTPException(404, "chapter not found")
        return ch

    def entity_or_404(eid: int) -> tuple[dict, Akashic]:
        e = store.one("SELECT novel_id FROM entities WHERE id=?", (eid,))
        if e is None:
            raise HTTPException(404, "entity not found")
        ak = Akashic(store, e["novel_id"])
        return ak.ents[eid], ak

    def novel_public(n: dict) -> dict:
        n = dict(n)
        n["has_cover"] = bool(n.pop("cover_path", None))
        n["job"] = store.one("SELECT * FROM jobs WHERE novel_id=? ORDER BY id DESC LIMIT 1", (n["id"],))
        return n

    def save_upload(file: UploadFile) -> Path:
        suffix = Path(file.filename or "upload").suffix.lower()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            shutil.copyfileobj(file.file, tmp)
            return Path(tmp.name)

    # ── status ────────────────────────────────────────────────────────────
    @api.get("/status")
    def status() -> dict:
        return {
            "version": __version__,
            "tiers": {
                "local": cascade.local.label if cascade.local else None,
                "cloud": [{"name": p.name, "model": p.model} for p in (cascade.cloud.providers if cascade.cloud else [])],
            },
            "policy": {"accept": cascade.policy.accept, "escalate": cascade.policy.escalate,
                       "review": cascade.policy.review, "summaries": cascade.policy.summaries},
            "concurrency": settings.concurrency, "parallel_novels": settings.parallel_novels,
        }

    # ── novels ────────────────────────────────────────────────────────────
    @api.get("/novels")
    def list_novels() -> list[dict]:
        return [novel_public(n) for n in store.list_novels()]

    @api.post("/novels/import", status_code=201)
    def import_novel(file: UploadFile = File(...), chapter_pattern: str | None = Form(None)) -> dict:
        tmp = save_upload(file)
        try:
            nid, book = import_book(store, settings.covers_dir, tmp, file.filename, chapter_pattern or None)
        except IngestError as e:
            raise HTTPException(400, str(e)) from e
        finally:
            tmp.unlink(missing_ok=True)
        words = sum(len(c.text.split()) for c in book.chapters)
        return {"id": nid, "title": book.title, "chapters": len(book.chapters), "words": words,
                "warnings": book.warnings}

    @api.post("/novels/{nid}/append")
    def append_chapters(nid: int, file: UploadFile = File(...)) -> dict:
        novel_or_404(nid)
        tmp = save_upload(file)
        try:
            book = load_book(tmp, file.filename)
        except IngestError as e:
            raise HTTPException(400, str(e)) from e
        finally:
            tmp.unlink(missing_ok=True)
        return {"added": store.append_chapters(nid, [(c.title, c.text, c.sha) for c in book.chapters])}

    @api.get("/novels/{nid}")
    def get_novel(nid: int) -> dict:
        n = novel_public(novel_or_404(nid))
        n["progress"] = store.get_progress(nid)
        agg = store.one("SELECT SUM(word_count) words, SUM(review_count) review,"
                        " SUM(status='failed') failed FROM chapters WHERE novel_id=?", (nid,)) or {}
        n["word_count"], n["review_total"], n["failed_count"] = agg["words"] or 0, agg["review"] or 0, agg["failed"] or 0
        tiers: Counter[str] = Counter()
        for r in store.q("SELECT tiers FROM chapters WHERE novel_id=? AND tiers IS NOT NULL", (nid,)):
            tiers.update(json.loads(r["tiers"]))
        n["tier_counts"] = dict(tiers)
        n["usage"] = store.usage_summary(nid)
        n["corrections"] = (store.one("SELECT COUNT(*) n FROM overrides o JOIN chapters c ON c.id=o.chapter_id"
                                      " WHERE c.novel_id=?", (nid,)) or {})["n"]
        return n

    @api.patch("/novels/{nid}")
    def patch_novel(nid: int, body: NovelPatch) -> dict:
        novel_or_404(nid)
        store.update_novel(nid, **body.model_dump(exclude_unset=True))
        return get_novel(nid)

    @api.delete("/novels/{nid}", status_code=204)
    def delete_novel(nid: int) -> Response:
        novel_or_404(nid)
        portraits = [r["portrait_path"] for r in store.q(
            "SELECT portrait_path FROM entities WHERE novel_id=? AND portrait_path IS NOT NULL", (nid,))]
        store.delete_novel(nid)
        for p in [settings.covers_dir / f"{nid}.jpg", *map(Path, portraits)]:
            p.unlink(missing_ok=True)
        return Response(status_code=204)

    @api.get("/novels/{nid}/cover")
    def get_cover(nid: int):
        n = store.one("SELECT cover_path FROM novels WHERE id=?", (nid,))
        if not n or not n["cover_path"] or not Path(n["cover_path"]).exists():
            raise HTTPException(404, "no cover")
        return FileResponse(n["cover_path"], media_type="image/jpeg")

    @api.post("/novels/{nid}/cover")
    def upload_cover(nid: int, file: UploadFile = File(...)) -> dict:
        novel_or_404(nid)
        if not (file.content_type or "").startswith("image/") and Path(file.filename or "").suffix.lower() not in (
                ".jpg", ".jpeg", ".png", ".webp"):
            raise HTTPException(400, "upload a JPG, PNG or WebP image")
        try:
            save_image(store, settings.covers_dir, nid, file.file.read())
        except Exception as e:
            raise HTTPException(400, f"not a usable image: {e}") from e
        return {"ok": True}

    @api.post("/novels/{nid}/metadata")
    def fetch_metadata(nid: int, body: MetadataBody) -> dict:
        from babel.meta.sources import MetadataError, download, fetch

        n = novel_or_404(nid)
        meta, notes = fetch(n["title"], body.sources)
        if meta is None:
            raise HTTPException(404, "no metadata found: " + "; ".join(notes))
        result = {"metadata": meta.__dict__, "notes": notes, "applied": False}
        if body.apply:
            store.update_novel(nid, author=n["author"] or meta.author, description=meta.description or n["description"],
                               tags=meta.tags or n["tags"], status=meta.status or n["status"], source_url=meta.url)
            if meta.cover_url:
                try:
                    save_image(store, settings.covers_dir, nid, download(meta.cover_url))
                except (MetadataError, Exception) as e:  # keep the URL-less metadata even if the cover fails
                    result["notes"].append(f"cover: {e}")
            result["applied"] = True
        return result

    @api.get("/novels/{nid}/chapters")
    def list_chapters(nid: int) -> list[dict]:
        novel_or_404(nid)
        return store.list_chapters(nid)

    @api.get("/novels/{nid}/search")
    def search(nid: int, q: str = Query(min_length=2)) -> list[dict]:
        novel_or_404(nid)
        return store.search(nid, q)

    @api.put("/novels/{nid}/progress")
    def put_progress(nid: int, body: ProgressBody) -> dict:
        novel_or_404(nid)
        store.set_progress(nid, body.chapter_id, body.position)
        return {"ok": True}

    @api.get("/novels/{nid}/estimate")
    def estimate(nid: int, first: int | None = None, last: int | None = None) -> dict:
        """Rough cost/time for transforming a range, from this novel's own history when available."""
        novel_or_404(nid)
        sql, args = "SELECT COUNT(*) n, SUM(word_count) w FROM chapters WHERE novel_id=? AND status!='done'", [nid]
        if first is not None:
            sql += " AND idx>=?"
            args.append(first)
        if last is not None:
            sql += " AND idx<=?"
            args.append(last)
        todo = store.one(sql, args) or {}
        n, words = todo["n"] or 0, todo["w"] or 0
        done = (store.one("SELECT COUNT(*) n FROM chapters WHERE novel_id=? AND status='done'", (nid,)) or {})["n"]
        per: dict[str, dict[str, float]] = {}
        for u in store.usage_summary(nid):
            t = per.setdefault(u["tier"], {"prompt": 0, "completion": 0, "questions": 0})
            t["prompt"] += u["prompt_tokens"] or 0
            t["completion"] += u["completion_tokens"] or 0
            t["questions"] += u["questions"] or 0
        basis = "this novel's history" if done and per else "typical rates"
        if not (done and per):
            local = 1 if cascade.local else 0
            per = {"local": {"prompt": 1600, "completion": 220, "questions": 9}} if local else {}
            per["cloud"] = {"prompt": 500 if local else 1400, "completion": 60 if local else 180, "questions": 2 if local else 9}
            done = 1
        out = {tier: {k: round(v / done * n) for k, v in t.items()} for tier, t in per.items()}
        if not cascade.cloud:
            out.pop("cloud", None)
        return {"chapters": n, "words": words, "per_tier": out, "basis": basis,
                "local_minutes": round(n * (12 if cascade.local else 0) / 60 / max(1, settings.concurrency), 1)}

    # ── chapters ──────────────────────────────────────────────────────────
    @api.get("/chapters/{cid}")
    def get_chapter(cid: int) -> dict:
        view = chapter_view(store, cid, review=cascade.policy.review)
        if view is None:
            raise HTTPException(404, "chapter not found")
        return view

    @api.get("/chapters/{cid}/source")
    def get_source(cid: int) -> dict:
        ch = chapter_or_404(cid)
        return {"id": cid, "title": ch["title"], "text": ch["source_text"]}

    @api.post("/chapters/{cid}/edit")
    def edit_blocks(cid: int, body: EditBody) -> dict:
        ch = chapter_or_404(cid)
        btype = BlockType.parse(body.type)
        if btype is None:
            raise HTTPException(422, f"unknown block type {body.type!r}")
        speaker = (body.speaker or "").strip() or None
        if btype not in (BlockType.DIALOGUE, BlockType.THOUGHT, BlockType.ACTION):
            speaker = None
        if body.tone and body.tone not in TONES:
            raise HTTPException(422, f"tone must be one of {', '.join(TONES)}")
        ak = Akashic(store, ch["novel_id"])
        current, _ = effective_decisions(store, ch, ak)
        pipeline = {int(k): v for k, v in (ch["doc"] or {}).get("decisions", {}).items()}
        if speaker:
            eid = ak.resolve(speaker, ch["idx"])
            speaker = ak.name(eid) or speaker
        rows = {}
        for s in body.segs:
            if s not in current:
                raise HTTPException(422, f"segment {s} is not in this chapter")
            new = Decision(type=btype, speaker=speaker, tone=body.tone, conf=1.0, tier=Tier.USER, why="corrected by you")
            rows[s] = (new.compact(), pipeline.get(s) or current[s].compact())
        store.set_overrides(cid, rows)
        return get_chapter(cid)

    @api.post("/chapters/{cid}/accept")
    def accept_blocks(cid: int, body: SegsBody) -> dict:
        """Mark the pipeline's decision as correct (it leaves the review queue, and counts as gold)."""
        ch = chapter_or_404(cid)
        current, _ = effective_decisions(store, ch, Akashic(store, ch["novel_id"]))
        rows = {}
        for s in body.segs or []:
            if s in current:
                d = current[s].model_copy(update={"conf": 1.0, "tier": Tier.USER, "why": "confirmed by you"})
                rows[s] = (d.compact(), current[s].compact())
        store.set_overrides(cid, rows)
        return get_chapter(cid)

    @api.post("/chapters/{cid}/edit/clear")
    def clear_edits(cid: int, body: SegsBody) -> dict:
        chapter_or_404(cid)
        store.clear_overrides(cid, body.segs)
        return get_chapter(cid)

    @api.post("/chapters/{cid}/transform")
    def retransform(cid: int, body: JobBody | None = None) -> dict:
        ch = chapter_or_404(cid)
        tiers = body.tiers if body else "auto"
        if tiers not in TIER_MODES:
            raise HTTPException(422, f"tiers must be one of {', '.join(TIER_MODES)}")
        jid = create_job(store, ch["novel_id"], ch["idx"], ch["idx"], force=True, tiers=tiers)
        worker.poke()
        return store.one("SELECT * FROM jobs WHERE id=?", (jid,))

    # ── review queue & corrections ────────────────────────────────────────
    @api.get("/novels/{nid}/review")
    def review_queue(nid: int, limit: int = 60) -> list[dict]:
        """Lowest-confidence lines across the novel, with context, for a human to settle."""
        novel_or_404(nid)
        ak = Akashic(store, nid)
        items = []
        for row in store.q("SELECT id FROM chapters WHERE novel_id=? AND review_count>0 ORDER BY idx", (nid,)):
            view = chapter_view(store, row["id"], ak, review=cascade.policy.review)
            blocks = view["blocks"]
            for i, b in enumerate(blocks):
                if b["review"]:
                    items.append({"chapter_id": view["id"], "chapter_idx": view["idx"], "chapter_title": view["title"],
                                  "block": b, "before": [x["text"] for x in blocks[max(0, i - 2):i]],
                                  "after": [x["text"] for x in blocks[i + 1:i + 2]]})
            if len(items) >= limit:
                break
        return items[:limit]

    @api.get("/novels/{nid}/corrections")
    def corrections(nid: int) -> list[dict]:
        novel_or_404(nid)
        out = []
        texts: dict[int, dict[int, str]] = {}
        for o in store.all_overrides(nid):
            if o["chapter_id"] not in texts:
                texts[o["chapter_id"]] = {s.id: s.text for s in segment_text(store.get_chapter(o["chapter_id"])["source_text"])}
            dec, orig = Decision.from_compact(o["decision"]), Decision.from_compact(o["original"]) if o["original"] else None
            out.append({"chapter_id": o["chapter_id"], "chapter_idx": o["chapter_idx"], "chapter_title": o["chapter_title"],
                        "seg": o["seg"], "text": texts[o["chapter_id"]].get(o["seg"]), "created_at": o["created_at"],
                        "after": {"type": dec.type.value, "speaker": dec.speaker},
                        "before": {"type": orig.type.value, "speaker": orig.speaker, "tier": orig.tier.value,
                                   "conf": orig.conf} if orig else None,
                        "confirmed": orig is not None and orig.type == dec.type and orig.speaker == dec.speaker})
        return out

    @api.get("/novels/{nid}/export/corrections")
    def export_corrections(nid: int):
        lines = [json.dumps(c, ensure_ascii=False) for c in corrections(nid)]
        return Response("\n".join(lines) + ("\n" if lines else ""), media_type="application/x-ndjson",
                        headers={"Content-Disposition": 'attachment; filename="corrections.jsonl"'})

    # ── Akashic Record: entities & glossary ───────────────────────────────
    @api.get("/novels/{nid}/entities")
    def list_entities(nid: int, kind: str | None = None) -> list[dict]:
        novel_or_404(nid)
        ak = Akashic(store, nid)
        ents = [e for e in ak.ents.values() if kind is None or e["kind"] == kind]
        ents.sort(key=lambda e: (-(e.get("lines") or 0), e["name"].lower()))
        return [entity_public(ak, e) for e in ents]

    @api.post("/novels/{nid}/entities", status_code=201)
    def create_entity(nid: int, body: EntityBody) -> dict:
        novel_or_404(nid)
        if body.kind not in KINDS:
            raise HTTPException(422, f"kind must be one of {', '.join(KINDS)}")
        ak = Akashic(store, nid)
        if ak.lookup(body.name, body.kind) is not None:
            raise HTTPException(409, f"{body.name!r} already exists")
        eid = ak.create(body.name.strip(), body.kind)
        ak.edit(eid, note=body.note, gender=body.gender)
        ak.reload()
        return entity_public(ak, ak.ents[eid])

    @api.patch("/entities/{eid}")
    def patch_entity(eid: int, body: EntityPatch) -> dict:
        e, ak = entity_or_404(eid)
        data = body.model_dump(exclude_unset=True)
        if "kind" in data and data["kind"] not in KINDS:
            raise HTTPException(422, f"kind must be one of {', '.join(KINDS)}")
        if "side" in data and data["side"] not in ("left", "right", None):
            raise HTTPException(422, "side must be left or right")
        if "gender" in data and data["gender"] not in ("m", "f", "n", None):
            raise HTTPException(422, "gender must be m, f or n")
        ak.edit(eid, **data)
        ak.reload()
        return entity_public(ak, ak.ents[eid])

    @api.delete("/entities/{eid}", status_code=204)
    def delete_entity(eid: int) -> Response:
        e, ak = entity_or_404(eid)
        store.x("DELETE FROM entities WHERE id=?", (eid,))
        if e.get("portrait_path"):
            Path(e["portrait_path"]).unlink(missing_ok=True)
        return Response(status_code=204)

    @api.post("/entities/{eid}/merge")
    def merge_entity(eid: int, body: MergeBody) -> dict:
        e, ak = entity_or_404(eid)
        if body.into not in ak.ents:
            raise HTTPException(400, "target is not in the same novel")
        ak.merge(eid, body.into)
        return {"ok": True}

    @api.post("/entities/{eid}/aliases")
    def add_alias(eid: int, body: AliasBody) -> dict:
        _, ak = entity_or_404(eid)
        ak.set_alias(eid, body.alias)
        return {"ok": True}

    @api.delete("/entities/{eid}/aliases/{alias}")
    def remove_alias(eid: int, alias: str) -> dict:
        e, ak = entity_or_404(eid)
        if alias.strip().lower() == e["name"].strip().lower():
            raise HTTPException(400, "can't remove an entity's own name; rename it instead")
        ak.remove_alias(alias)
        return {"ok": True}

    @api.get("/entities/{eid}/portrait")
    def get_portrait(eid: int):
        e, _ = entity_or_404(eid)
        if not e.get("portrait_path") or not Path(e["portrait_path"]).exists():
            raise HTTPException(404, "no portrait")
        return FileResponse(e["portrait_path"], media_type="image/jpeg")

    @api.post("/entities/{eid}/portrait")
    def upload_portrait(eid: int, file: UploadFile = File(...)) -> dict:
        entity_or_404(eid)
        try:
            save_image(store, settings.portraits_dir, eid, file.file.read(), kind="portrait")
        except Exception as e:
            raise HTTPException(400, f"not a usable image: {e}") from e
        return {"ok": True}

    @api.get("/novels/{nid}/glossary.yaml")
    def glossary_yaml(nid: int, min_lines: int = 0):
        novel_or_404(nid)
        return PlainTextResponse(export_yaml(Akashic(store, nid), min_lines), media_type="application/yaml",
                                 headers={"Content-Disposition": 'attachment; filename="glossary.yaml"'})

    @api.post("/novels/{nid}/glossary")
    def glossary_import(nid: int, text: str = Body(..., media_type="text/plain"), dry_run: bool = False) -> dict:
        novel_or_404(nid)
        try:
            if dry_run:
                data = parse_yaml(text)
                return {"valid": True, "entries": {k: len(v or {}) for k, v in data.items()}}
            return import_yaml(Akashic(store, nid), text)
        except GlossaryError as e:
            raise HTTPException(422, str(e)) from e

    @api.get("/novels/{nid}/graph")
    def character_graph(nid: int, min_weight: int = 2) -> dict:
        """Characters who talk in the same scenes, weighted by how often."""
        novel_or_404(nid)
        ak = Akashic(store, nid)
        pair: Counter[tuple[int, int]] = Counter()
        for r in store.q("SELECT id, doc_json FROM chapters WHERE novel_id=? AND doc_json IS NOT NULL", (nid,)):
            decisions = json.loads(r["doc_json"])["decisions"]
            segs = segment_text(store.get_chapter(r["id"])["source_text"])
            scene: set[int] = set()
            scenes = []
            for s in segs:
                row = decisions.get(str(s.id))
                if row and row[0] == "break":
                    scenes.append(scene)
                    scene = set()
                elif row and row[1] and row[0] in ("dialogue", "thought"):
                    eid = ak.lookup(row[1])
                    if eid is not None:
                        scene.add(eid)
            scenes.append(scene)
            for sc in scenes:
                for a, b in combinations(sorted(sc), 2):
                    pair[(a, b)] += 1
        edges = [{"source": a, "target": b, "weight": w} for (a, b), w in pair.items() if w >= min_weight]
        ids = {e["source"] for e in edges} | {e["target"] for e in edges}
        return {"nodes": [entity_public(ak, ak.ents[i]) for i in ids if i in ak.ents], "edges": edges,
                "factions": [entity_public(ak, e) for e in ak.ents.values() if e["kind"] == "faction"]}

    # ── jobs ──────────────────────────────────────────────────────────────
    @api.get("/jobs")
    def list_jobs(active: bool = False) -> list[dict]:
        sql = "SELECT j.*, n.title AS novel_title FROM jobs j JOIN novels n ON n.id=j.novel_id"
        if active:
            sql += " WHERE j.status IN ('queued','running','paused')"
        return store.q(sql + " ORDER BY j.id DESC LIMIT 50")

    @api.post("/novels/{nid}/jobs", status_code=201)
    def start_job(nid: int, body: JobBody) -> dict:
        novel_or_404(nid)
        try:
            jid = create_job(store, nid, body.first, body.last, body.force, body.tiers)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        worker.poke()
        return store.one("SELECT * FROM jobs WHERE id=?", (jid,))

    @api.post("/jobs/{jid}/{action}")
    def job_action(jid: int, action: str) -> dict:
        job = store.one("SELECT * FROM jobs WHERE id=?", (jid,))
        if job is None:
            raise HTTPException(404, "job not found")
        transitions = {"pause": ("paused", ("queued", "running")), "resume": ("queued", ("paused", "failed")),
                       "cancel": ("cancelled", ("queued", "running", "paused"))}
        if action not in transitions:
            raise HTTPException(404, "unknown action")
        new, allowed = transitions[action]
        if job["status"] not in allowed:
            raise HTTPException(409, f"can't {action} a {job['status']} job")
        store.x("UPDATE jobs SET status=? WHERE id=?", (new, jid))
        worker.poke()
        return store.one("SELECT * FROM jobs WHERE id=?", (jid,))

    # ── exports ───────────────────────────────────────────────────────────
    def _safe(name: str) -> str:
        return "".join(c if c.isalnum() or c in " -_" else "_" for c in name).strip()[:80] or "novel"

    @api.get("/novels/{nid}/export/epub")
    def export_epub(nid: int, first: int | None = None, last: int | None = None):
        from babel.export.epub import build_epub

        n = novel_or_404(nid)
        return Response(build_epub(store, nid, first, last), media_type="application/epub+zip",
                        headers={"Content-Disposition": f'attachment; filename="{_safe(n["title"])}.babel.epub"'})

    @api.get("/novels/{nid}/export/html")
    def export_html(nid: int, first: int | None = None, last: int | None = None):
        from babel.export.html import build_html

        n = novel_or_404(nid)
        return Response(build_html(store, nid, first, last), media_type="text/html",
                        headers={"Content-Disposition": f'attachment; filename="{_safe(n["title"])}.babel.html"'})

    @api.get("/novels/{nid}/export/json")
    def export_json(nid: int, first: int | None = None, last: int | None = None):
        """The standardized Visual Scenario JSON — blocks with speaker, tone, confidence and tier."""
        from babel.export.render import chapters_in_range

        n = novel_or_404(nid)
        ak = Akashic(store, nid)
        chapters = [chapter_view(store, r["id"], ak) for r in chapters_in_range(store, nid, first, last)]
        payload = {"format": "babel-visual-scenario", "version": 3, "novel": {"title": n["title"], "author": n["author"]},
                   "characters": [entity_public(ak, e) for e in ak.characters if e.get("lines")],
                   "chapters": [{"index": c["idx"], "title": c["title"], "blocks": [
                       {k: b[k] for k in ("type", "text", "speaker", "tone", "conf", "tier")} for b in c["blocks"]]}
                       for c in chapters]}
        return JSONResponse(payload, headers={"Content-Disposition": f'attachment; filename="{_safe(n["title"])}.babel.json"'})

    api.include_router(art_router(store, art, lambda: cascade.local or cascade.cloud, novel_or_404, entity_or_404))
    app.include_router(api)
    _mount_web(app)
    return app


def _mount_web(app: FastAPI) -> None:
    dist = next((d for d in WEB_DIST if (d / "index.html").exists()), None)
    if dist is None:
        @app.get("/", include_in_schema=False)
        def no_ui() -> Response:
            return Response("<h1>BABEL API is running</h1><p>The web UI isn't built: run "
                            "<code>npm --prefix web ci && npm --prefix web run build</code>.</p>"
                            "<p><a href='/docs'>API docs</a></p>", media_type="text/html")
        return
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")
