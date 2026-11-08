"""The art scheduler: drafts profiles and draws characters in reading order, sharing the machine.

One computer runs both the text model (Ollama) and the image models, and they
don't fit in memory comfortably at the same time. So:

- text jobs always win: while a transform job is queued or running, the image
  worker is stopped (all of its memory freed) and the scheduler waits;
- before drawing, the scheduler asks Ollama to unload its models;
- profiles (text-model work) are drafted in a batch before switching to images;
- after a few idle minutes the image worker is stopped again.

Work order follows the reader: expressions of already-chosen characters first
(they unblock chapters), then candidates for the next characters by first appearance.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import httpx

from babel.art import designs, plan
from babel.art.profile import (
    FIELDS,
    draft_messages,
    gather_evidence,
    parse_profile,
    profile_schema,
    setting_messages,
)
from babel.memory.akashic import Akashic
from babel.store.db import Store

log = logging.getLogger("babel.art")

WORKER_SCRIPT = Path(__file__).with_name("worker_proc.py")
LOOKAHEAD = 4  # designs waiting for your pick before the scheduler stops drafting new candidates
IDLE_STOP_SECS = 180


class ArtError(RuntimeError):
    pass


class Backend(Protocol):
    def call(self, req: dict) -> dict: ...
    def close(self) -> None: ...
    @property
    def running(self) -> bool: ...


class SubprocessBackend:
    """Talks to ``worker_proc.py`` running under the art environment's Python."""

    def __init__(self, python: Path, log_path: Path):
        self.python, self.log_path = python, log_path
        self.proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._n = 0

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def _ensure(self) -> subprocess.Popen:
        if not self.running:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            logf = self.log_path.open("a")
            self.proc = subprocess.Popen([str(self.python), "-u", str(WORKER_SCRIPT)], stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=logf, text=True, bufsize=1)
        assert self.proc is not None
        return self.proc

    def call(self, req: dict) -> dict:
        with self._lock:
            proc = self._ensure()
            self._n += 1
            req = {**req, "id": self._n}
            assert proc.stdin and proc.stdout
            try:
                proc.stdin.write(json.dumps(req) + "\n")
                proc.stdin.flush()
                line = proc.stdout.readline()
            except (BrokenPipeError, OSError) as e:
                raise ArtError(f"image worker died: {e}") from e
            if not line:
                raise ArtError(f"image worker exited (see {self.log_path})")
            rep = json.loads(line)
            if not rep.get("ok"):
                raise ArtError(rep.get("error") or "image worker failed")
            return rep

    def close(self) -> None:
        with self._lock:
            if self.proc is not None:
                try:
                    if self.proc.stdin:
                        self.proc.stdin.close()
                    self.proc.wait(timeout=10)
                except Exception:
                    self.proc.kill()
                self.proc = None


def unload_ollama(base_url: str) -> None:
    """Ask Ollama to drop its loaded models so the image models have the memory."""
    try:
        loaded = httpx.get(f"{base_url}/api/ps", timeout=3).json().get("models", [])
        for m in loaded:
            httpx.post(f"{base_url}/api/generate", json={"model": m["name"], "keep_alive": 0}, timeout=30)
    except Exception:  # Ollama not running: nothing to unload
        pass


def make_thumb(path: Path, width: int = 360) -> Path:
    from PIL import Image

    out = path.with_suffix(".thumb.jpg")
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((width, width * 2))
        im.save(out, "JPEG", quality=86)
    return out


def make_portrait(store: Store, eid: int, base: Path, portraits_dir: Path) -> None:
    """Use the approved design's face as the character's chat avatar (unless you uploaded one)."""
    from PIL import Image

    e = store.one("SELECT portrait_path FROM entities WHERE id=?", (eid,))
    if e and e.get("portrait_path") and not Path(e["portrait_path"]).name.endswith("_auto.jpg"):
        return
    portraits_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(base) as im:
        w, h = im.size
        side = int(w * 0.78)  # head and shoulders: half-body framing puts the chin at ~35-45% height
        left, top = (w - side) // 2, int(h * 0.01)
        face = im.convert("RGB").crop((left, top, left + side, top + side)).resize((256, 256))
        out = portraits_dir / f"char_{eid}_auto.jpg"
        face.save(out, "JPEG", quality=88)
    store.x("UPDATE entities SET portrait_path=? WHERE id=?", (str(out), eid))


# ── profiles (text-model work) ─────────────────────────────────────────────
def draft_setting(store: Store, novel_id: int, llm) -> dict:
    """The novel's visual setting (for profiles) and clothing era (for prompts)."""
    rows = store.q("SELECT summary, source_text FROM chapters WHERE novel_id=? ORDER BY idx LIMIT 3", (novel_id,))
    sample = "\n\n".join((r["summary"] or "") + "\n" + r["source_text"][:2500] for r in rows)
    schema = {"type": "object", "properties": {"setting": {"type": "string"}, "era": {"type": "string"}},
              "required": ["setting", "era"]}
    reply = llm.chat(setting_messages(sample), schema=schema, max_tokens=240)
    from babel.scenario.ask import extract_json

    data = extract_json(reply.content)
    store.log_usage(novel_id, None, "local" if "ollama" in reply.provider else "cloud", "art-setting",
                    reply.provider, reply.model, reply.prompt_tokens, reply.completion_tokens, 0)
    return {"setting": str(data.get("setting", "")).strip()[:300], "era": str(data.get("era", "")).strip()[:60]}


def draft_profile(store: Store, ak: Akashic, eid: int, llm) -> dict:
    """Fill the appearance profile from the book (keeps any field you edited)."""
    art = designs.art_settings(store, ak.novel_id)
    if llm is None:
        return designs.save_profile(store, eid, {f: {"value": "", "guessed": True, "chapter": None, "quote": ""}
                                                 for f in FIELDS}, user=False)
    if not art.get("setting") or not art.get("era"):
        try:
            drafted = draft_setting(store, ak.novel_id, llm)
            art = designs.set_art_settings(store, ak.novel_id, setting=art.get("setting") or drafted["setting"],
                                           era=art.get("era") or drafted["era"])
        except Exception as e:
            log.warning("setting draft failed: %s", e)
    e = ak.ents[eid]
    evidence = gather_evidence(store, ak, eid)
    msgs = draft_messages(e["name"], [a for a in ak.alias_text.get(eid, []) if a.lower() != e["name"].lower()],
                          e.get("gender"), e.get("note"), art.get("setting", ""), evidence)
    reply = llm.chat(msgs, schema=profile_schema(), max_tokens=1400)
    store.log_usage(ak.novel_id, None, "local" if "ollama" in reply.provider else "cloud", "art-profile",
                    reply.provider, reply.model, reply.prompt_tokens, reply.completion_tokens, 0)
    return designs.save_profile(store, eid, parse_profile(reply.content), user=False)


# ── the scheduler ─────────────────────────────────────────────────────────
class ArtScheduler:
    def __init__(self, store: Store, *, art_dir: Path, portraits_dir: Path,
                 backend_factory: Callable[[], Backend] | None, llm_factory: Callable[[], object | None],
                 ollama_url: str = "http://localhost:11434", idle_stop_secs: float = IDLE_STOP_SECS):
        self.store, self.art_dir, self.portraits_dir = store, art_dir, portraits_dir
        self.backend_factory, self.llm_factory = backend_factory, llm_factory
        self.ollama_url, self.idle_stop_secs = ollama_url, idle_stop_secs
        self.backend: Backend | None = None
        self.state: dict = {"status": "idle" if backend_factory else "unavailable", "detail": None, "error": None}
        self._wake, self._stop = threading.Event(), threading.Event()
        self._thread: threading.Thread | None = None
        self._last_work = time.time()
        self._drawing = False

    # lifecycle
    def start(self) -> None:
        self.store.x("UPDATE art_images SET status='queued' WHERE status='running'")  # resume after restart
        self._thread = threading.Thread(target=self._loop, name="babel-art", daemon=True)
        self._thread.start()

    def poke(self) -> None:
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        self._release()

    def _release(self) -> None:
        if self.backend is not None and self.backend.running:
            self.backend.close()
        self._drawing = False

    def _set(self, status: str, detail: str | None = None) -> None:
        self.state.update(status=status, detail=detail)

    def _text_busy(self) -> bool:
        return self.store.one("SELECT 1 FROM jobs WHERE status IN ('queued','running') LIMIT 1") is not None

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                worked = self.step()
            except Exception as e:  # never let the art thread die
                log.exception("art step failed")
                self.state["error"] = str(e)[:300]
                worked = False
            if worked:
                self._last_work = time.time()
                continue
            if self.backend is not None and self.backend.running and time.time() - self._last_work > self.idle_stop_secs:
                self._release()
            self._wake.wait(timeout=5)
            self._wake.clear()

    # one unit of work; returns True if something was done
    def step(self) -> bool:
        if self._text_busy():
            self._release()
            self._set("waiting", "a transform job is running; drawing resumes when it finishes")
            return False
        if self._auto_profiles() or self._auto_candidates():
            return True
        img = self._next_image()
        if img is None:
            self._set("idle" if self.backend_factory else "unavailable",
                      None if self.backend_factory else "image models not installed — run `babel art setup`")
            return False
        if self.backend_factory is None:
            self._set("unavailable", "image models not installed — run `babel art setup`")
            return False
        self._draw(img)
        return True

    def _auto_novels(self) -> list[int]:
        return [r["id"] for r in self.store.q("SELECT id, art FROM novels")
                if r["art"] and json.loads(r["art"]).get("auto")]

    def _auto_profiles(self) -> bool:
        for nid in self._auto_novels():
            ak = Akashic(self.store, nid)
            todo = [c for c in plan.queue(self.store, ak)[:LOOKAHEAD * 2] if c["status"] == "new"]
            if not todo:
                continue
            c = todo[0]
            self._release()  # profiles need the text model, not the image models
            self._set("profiling", c["name"])
            try:
                draft_profile(self.store, ak, c["id"], self.llm_factory())
            except Exception as e:
                d = designs.ensure_design(self.store, c["id"])
                self.store.x("UPDATE designs SET status='profiled', message=? WHERE id=?",
                             (f"profile draft failed ({str(e)[:120]}) — fill it in by hand", d["id"]))
            return True
        return False

    def _auto_candidates(self) -> bool:
        for nid in self._auto_novels():
            ak = Akashic(self.store, nid)
            q = plan.queue(self.store, ak)
            waiting = sum(1 for c in q if c["status"] in ("candidates", "choose"))
            if waiting >= LOOKAHEAD:
                continue
            c = next((c for c in q if c["status"] == "profiled"), None)
            if c:
                designs.queue_candidates(self.store, ak, c["id"])
                return True
        return False

    def _next_image(self) -> dict | None:
        # expressions first (they finish a character and unblock chapters), then by first appearance
        rows = self.store.q(
            "SELECT i.*, d.entity_id, e.novel_id, COALESCE(e.first_idx, 1<<30) AS first FROM art_images i"
            " JOIN designs d ON d.id=i.design_id JOIN entities e ON e.id=d.entity_id"
            " WHERE i.status='queued' ORDER BY (i.kind='expression') DESC, first, i.id LIMIT 1")
        return rows[0] if rows else None

    def _draw(self, img: dict) -> None:
        assert self.backend_factory is not None
        if not self._drawing:
            unload_ollama(self.ollama_url)
            self._drawing = True
        if self.backend is None:
            self.backend = self.backend_factory()
        name = (self.store.one("SELECT name FROM entities WHERE id=?", (img["entity_id"],)) or {}).get("name")
        self._set("drawing", f"{name}: {img['emotion'] or 'candidate'}")
        self.store.x("UPDATE art_images SET status='running' WHERE id=?", (img["id"],))
        out = designs.image_dir(self.art_dir, img["novel_id"], img["entity_id"]) / f"{img['id']}.png"
        p = json.loads(img["prompt"])
        try:
            if img["kind"] == "candidate":
                req = {"op": "generate", "model": img["model"], "prompt": p["prompt"], "negative": p.get("negative"),
                       "seed": img["seed"], "width": designs.BASE_W, "height": designs.BASE_H, "out": str(out)}
            else:
                d = self.store.one("SELECT base_image_id FROM designs WHERE id=?", (img["design_id"],))
                base = self.store.one("SELECT path FROM art_images WHERE id=?", (d["base_image_id"],))
                req = {"op": "edit", "model": img["model"], "prompt": p["prompt"], "image": base["path"],
                       "seed": img["seed"], "width": designs.BASE_W, "height": designs.BASE_H, "out": str(out)}
            rep = self.backend.call(req)
            make_thumb(out)
            self.store.x("UPDATE art_images SET status='done', path=?, secs=?, error=NULL WHERE id=?",
                         (str(out), rep.get("secs"), img["id"]))
            self.state["error"] = None
        except Exception as e:
            self.store.x("UPDATE art_images SET status='failed', error=? WHERE id=?", (str(e)[:500], img["id"]))
            self.state["error"] = str(e)[:300]
            if not (self.backend and self.backend.running):
                self.backend = None
        designs.after_image(self.store, img["design_id"])
        d = self.store.one("SELECT * FROM designs WHERE id=?", (img["design_id"],))
        if d and d["status"] == "approved" and d["base_image_id"]:
            base = self.store.one("SELECT path FROM art_images WHERE id=?", (d["base_image_id"],))
            if base and base["path"]:
                make_portrait(self.store, d["entity_id"], Path(base["path"]), self.portraits_dir)

    def status(self) -> dict:
        counts = {r["status"]: r["n"] for r in self.store.q(
            "SELECT status, COUNT(*) n FROM art_images WHERE status IN ('queued','running','failed') GROUP BY status")}
        return {**self.state, "worker_running": bool(self.backend and self.backend.running),
                "queued": counts.get("queued", 0) + counts.get("running", 0), "failed": counts.get("failed", 0)}
