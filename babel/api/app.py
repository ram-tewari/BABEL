"""HTTP API + static web UI."""

from __future__ import annotations

import json
import shutil
import tempfile
from collections import Counter
from contextlib import asynccontextmanager
from itertools import combinations
from pathlib import Path

from fastapi import APIRouter, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from babel import __version__
from babel.config import Settings
from babel.ingest import IngestError, load_book
from babel.library import (
    blocks_for_segments,
    chapter_view,
    character_public,
    import_book,
    save_cover,
)
from babel.llm.providers import Router, build_router
from babel.memory.codex import Codex
from babel.models import BlockType
from babel.pipeline.jobs import Worker, create_job
from babel.store.db import Store
from babel.transform.engine import Engine
from babel.transform.segment import segment_text

WEB_DIST_CANDIDATES = [
    Path(__file__).resolve().parent.parent / "web_dist",  # installed / built into the package
    Path(__file__).resolve().parents[2] / "web" / "dist",  # repo checkout
]


# ── request bodies ─────────────────────────────────────────────────────────
class NovelPatch(BaseModel):
    title: str | None = None
    author: str | None = None
    description: str | None = None
    pov_character_id: int | None = None


class EditBody(BaseModel):
    segs: list[int] = Field(min_length=1)
    type: str
    speaker: str | None = None


class ClearEditBody(BaseModel):
    segs: list[int] | None = None


class CharacterPatch(BaseModel):
    name: str | None = None
    note: str | None = None
    color: str | None = None
    side: str | None = None  # left | right | auto


class MergeBody(BaseModel):
    into: int


class AliasBody(BaseModel):
    alias: str = Field(min_length=1, max_length=60)


class JobBody(BaseModel):
    first: int | None = None
    last: int | None = None
    force: bool = False
    mode: str = "auto"


class ProgressBody(BaseModel):
    chapter_id: int
    position: float = 0.0


def create_app(settings: Settings | None = None, store: Store | None = None,
               router: Router | None = None, start_worker: bool = True) -> FastAPI:
    settings = settings or Settings.from_env()
    store = store or Store(settings.db_path)
    llm = router if router is not None else build_router(settings.providers, settings.models)

    def engine_factory() -> Engine:
        return Engine(llm, settings.chunk_tokens, settings.summary_window)

    worker = Worker(store, engine_factory, settings.concurrency)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if start_worker:
            worker.start()
        yield
        worker.stop()

    app = FastAPI(title="BABEL", version=__version__, lifespan=lifespan)
    app.state.store = store
    app.state.worker = worker
    api = APIRouter(prefix="/api")

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

    def character_or_404(cid: int) -> dict:
        c = store.one("SELECT * FROM characters WHERE id=?", (cid,))
        if c is None:
            raise HTTPException(404, "character not found")
        return c

    def novel_public(n: dict) -> dict:
        n = dict(n)
        n["has_cover"] = bool(n.pop("cover_path", None))
        job = store.one("SELECT * FROM jobs WHERE novel_id=? ORDER BY id DESC LIMIT 1", (n["id"],))
        n["job"] = job
        return n

    # ── status ────────────────────────────────────────────────────────────
    @api.get("/status")
    def status() -> dict:
        return {
            "version": __version__,
            "llm": llm.label if llm.providers else None,
            "providers": [{"name": p.name, "model": p.model} for p in llm.providers],
            "concurrency": settings.concurrency,
        }

    # ── novels ────────────────────────────────────────────────────────────
    @api.get("/novels")
    def list_novels() -> list[dict]:
        return [novel_public(n) for n in store.list_novels()]

    @api.post("/novels/import", status_code=201)
    def import_novel(file: UploadFile = File(...)) -> dict:
        suffix = Path(file.filename or "upload").suffix.lower()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = Path(tmp.name)
        try:
            nid, book = import_book(store, settings.covers_dir, tmp_path, file.filename)
        except IngestError as e:
            raise HTTPException(400, str(e)) from e
        finally:
            tmp_path.unlink(missing_ok=True)
        return {"id": nid, "title": book.title, "chapters": len(book.chapters), "warnings": book.warnings}

    @api.post("/novels/{nid}/append")
    def append_chapters(nid: int, file: UploadFile = File(...)) -> dict:
        """Add newly released chapters (chapters already present are skipped by content hash)."""
        novel_or_404(nid)
        suffix = Path(file.filename or "upload").suffix.lower()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = Path(tmp.name)
        try:
            book = load_book(tmp_path, file.filename)
        except IngestError as e:
            raise HTTPException(400, str(e)) from e
        finally:
            tmp_path.unlink(missing_ok=True)
        added = store.append_chapters(nid, [(c.title, c.text, c.sha) for c in book.chapters])
        return {"added": added}

    @api.get("/novels/{nid}")
    def get_novel(nid: int) -> dict:
        n = novel_public(novel_or_404(nid))
        n["progress"] = store.get_progress(nid)
        stats = store.q("SELECT method, COUNT(*) n FROM chapters WHERE novel_id=? AND status='done' GROUP BY method", (nid,))
        n["methods"] = {r["method"]: r["n"] for r in stats}
        n["failed_count"] = (store.one("SELECT COUNT(*) n FROM chapters WHERE novel_id=? AND status='failed'", (nid,)) or {})["n"]
        n["word_count"] = (store.one("SELECT SUM(word_count) n FROM chapters WHERE novel_id=?", (nid,)) or {})["n"] or 0
        return n

    @api.patch("/novels/{nid}")
    def patch_novel(nid: int, body: NovelPatch) -> dict:
        novel_or_404(nid)
        store.update_novel(nid, **body.model_dump(exclude_unset=True))
        return get_novel(nid)

    @api.delete("/novels/{nid}", status_code=204)
    def delete_novel(nid: int) -> Response:
        n = novel_or_404(nid)
        store.delete_novel(nid)
        cover = settings.covers_dir / f"{n['id']}.jpg"
        cover.unlink(missing_ok=True)
        return Response(status_code=204)

    @api.get("/novels/{nid}/cover")
    def get_cover(nid: int):
        n = store.one("SELECT cover_path FROM novels WHERE id=?", (nid,))
        if not n or not n["cover_path"] or not Path(n["cover_path"]).exists():
            raise HTTPException(404, "no cover")
        return FileResponse(n["cover_path"], media_type="image/jpeg", headers={"Cache-Control": "no-cache"})

    @api.post("/novels/{nid}/cover")
    def upload_cover(nid: int, file: UploadFile = File(...)) -> dict:
        novel_or_404(nid)
        try:
            save_cover(store, settings.covers_dir, nid, file.file.read())
        except Exception as e:
            raise HTTPException(400, f"not a usable image: {e}") from e
        return {"ok": True}

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

    # ── chapters ──────────────────────────────────────────────────────────
    @api.get("/chapters/{cid}")
    def get_chapter(cid: int) -> dict:
        view = chapter_view(store, cid)
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
        if btype not in (BlockType.DIALOGUE, BlockType.THOUGHT):
            speaker = None
        originals = {int(k): tuple(v) for k, v in (ch.get("labels") or {}).items()}
        if not originals:
            originals = blocks_for_segments(store, cid, body.segs)
        store.set_overrides(cid, body.segs, btype.value, speaker, originals)
        if speaker:
            codex = Codex(store, ch["novel_id"])
            codex.resolve(speaker, ch["idx"])
        return get_chapter(cid)

    @api.post("/chapters/{cid}/edit/clear")
    def clear_edits(cid: int, body: ClearEditBody) -> dict:
        chapter_or_404(cid)
        store.clear_overrides(cid, body.segs)
        return get_chapter(cid)

    @api.post("/chapters/{cid}/transform")
    def retransform(cid: int, body: JobBody | None = None) -> dict:
        ch = chapter_or_404(cid)
        mode = body.mode if body else "auto"
        jid = create_job(store, ch["novel_id"], ch["idx"], ch["idx"], force=True, mode=mode)
        worker.poke()
        return store.one("SELECT * FROM jobs WHERE id=?", (jid,))

    # ── characters ────────────────────────────────────────────────────────
    @api.get("/novels/{nid}/characters")
    def list_characters(nid: int) -> list[dict]:
        n = novel_or_404(nid)
        rows = store.q("SELECT * FROM characters WHERE novel_id=? ORDER BY lines DESC, name", (nid,))
        aliases: dict[int, list[str]] = {}
        for a in store.q("SELECT alias, character_id FROM aliases WHERE novel_id=? ORDER BY length(alias)", (nid,)):
            aliases.setdefault(a["character_id"], []).append(a["alias"])
        out = []
        for r in rows:
            c = character_public(r, n["pov_character_id"])
            c["aliases"] = [a for a in aliases.get(r["id"], []) if a.lower() != r["name"].lower()]
            c["custom_color"] = r["color"] is not None
            c["custom_side"] = r["side"] is not None
            out.append(c)
        return out

    @api.patch("/characters/{cid}")
    def patch_character(cid: int, body: CharacterPatch) -> dict:
        c = character_or_404(cid)
        data = body.model_dump(exclude_unset=True)
        codex = Codex(store, c["novel_id"])
        if data.get("name"):
            codex.rename(cid, data["name"])
        if "note" in data:
            store.x("UPDATE characters SET note=? WHERE id=?", (data["note"], cid))
        if "color" in data:
            store.x("UPDATE characters SET color=? WHERE id=?", (data["color"] or None, cid))
        if "side" in data:
            side = data["side"] if data["side"] in ("left", "right") else None
            store.x("UPDATE characters SET side=? WHERE id=?", (side, cid))
        return {"ok": True}

    @api.post("/characters/{cid}/merge")
    def merge_character(cid: int, body: MergeBody) -> dict:
        src = character_or_404(cid)
        dst = character_or_404(body.into)
        if src["novel_id"] != dst["novel_id"]:
            raise HTTPException(400, "characters belong to different novels")
        Codex(store, src["novel_id"]).merge(cid, body.into)
        return {"ok": True}

    @api.post("/characters/{cid}/aliases")
    def add_alias(cid: int, body: AliasBody) -> dict:
        c = character_or_404(cid)
        Codex(store, c["novel_id"]).set_alias(cid, body.alias)
        return {"ok": True}

    @api.delete("/characters/{cid}/aliases/{alias}")
    def remove_alias(cid: int, alias: str) -> dict:
        c = character_or_404(cid)
        if alias.strip().lower() == c["name"].strip().lower():
            raise HTTPException(400, "can't remove a character's own name; rename it instead")
        Codex(store, c["novel_id"]).remove_alias(alias)
        return {"ok": True}

    @api.get("/novels/{nid}/graph")
    def character_graph(nid: int, min_weight: int = 2) -> dict:
        """Who talks in the same chapters, weighted by shared chapters."""
        novel_or_404(nid)
        codex = Codex(store, nid)
        pair: Counter[tuple[int, int]] = Counter()
        rows = store.q("SELECT id, labels_json FROM chapters WHERE novel_id=? AND labels_json IS NOT NULL", (nid,))
        for r in rows:
            speakers = set()
            for t, sp in json.loads(r["labels_json"]).values():
                if sp and t in ("dialogue", "thought"):
                    cid = codex.lookup(sp)
                    if cid is not None:
                        speakers.add(cid)
            for a, b in combinations(sorted(speakers), 2):
                pair[(a, b)] += 1
        edges = [{"source": a, "target": b, "weight": w} for (a, b), w in pair.items() if w >= min_weight]
        ids = {e["source"] for e in edges} | {e["target"] for e in edges}
        n = store.get_novel(nid)
        nodes = [character_public(codex.chars[i], n["pov_character_id"]) for i in ids if i in codex.chars]
        return {"nodes": nodes, "edges": edges}

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
            jid = create_job(store, nid, body.first, body.last, body.force, body.mode)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        worker.poke()
        return store.one("SELECT * FROM jobs WHERE id=?", (jid,))

    @api.post("/jobs/{jid}/{action}")
    def job_action(jid: int, action: str) -> dict:
        job = store.one("SELECT * FROM jobs WHERE id=?", (jid,))
        if job is None:
            raise HTTPException(404, "job not found")
        transitions = {"pause": ("paused", ("queued", "running")),
                       "resume": ("queued", ("paused", "failed")),
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
    @api.get("/novels/{nid}/export/epub")
    def export_epub(nid: int, first: int | None = None, last: int | None = None):
        from babel.export.epub import build_epub

        n = novel_or_404(nid)
        data = build_epub(store, nid, first, last)
        return Response(data, media_type="application/epub+zip",
                        headers={"Content-Disposition": f'attachment; filename="{_safe(n["title"])}.babel.epub"'})

    @api.get("/novels/{nid}/export/html")
    def export_html(nid: int, first: int | None = None, last: int | None = None):
        from babel.export.html import build_html

        n = novel_or_404(nid)
        return Response(build_html(store, nid, first, last), media_type="text/html",
                        headers={"Content-Disposition": f'attachment; filename="{_safe(n["title"])}.babel.html"'})

    @api.get("/novels/{nid}/export/corrections")
    def export_corrections(nid: int):
        """User corrections as JSONL — training/eval data for labeling quality."""
        novel_or_404(nid)
        lines = []
        for o in store.all_overrides(nid):
            ch = store.get_chapter(o["chapter_id"])
            segs = {s.id: s for s in segment_text(ch["source_text"])}
            seg = segs.get(o["seg"])
            lines.append(json.dumps({
                "chapter_idx": o["chapter_idx"], "chapter": o["chapter_title"], "seg": o["seg"],
                "text": seg.text if seg else None,
                "before": {"type": o["original_type"], "speaker": o["original_speaker"]},
                "after": {"type": o["type"], "speaker": o["speaker"]},
            }, ensure_ascii=False))
        return Response("\n".join(lines) + ("\n" if lines else ""), media_type="application/x-ndjson",
                        headers={"Content-Disposition": 'attachment; filename="corrections.jsonl"'})

    app.include_router(api)

    @app.exception_handler(ValueError)
    async def value_error(_req, exc: ValueError):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    _mount_web(app)
    return app


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in " -_" else "_" for c in name).strip()[:80] or "novel"


def _mount_web(app: FastAPI) -> None:
    dist = next((d for d in WEB_DIST_CANDIDATES if (d / "index.html").exists()), None)
    if dist is None:
        @app.get("/", include_in_schema=False)
        def no_ui() -> Response:
            return Response(
                "<h1>BABEL API is running</h1><p>The web UI is not built. Run <code>npm --prefix web run build</code>,"
                " or use the dev server (<code>npm --prefix web run dev</code>).</p><p><a href='/docs'>API docs</a></p>",
                media_type="text/html",
            )
        return

    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
    index = dist / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)
