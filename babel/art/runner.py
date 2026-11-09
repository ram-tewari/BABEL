"""The art scheduler: drafts profiles, draws and checks characters in reading order — politely.

One computer runs the text model (Ollama), the image models and the vision checker,
and it's also *your* computer. So:

- text jobs win: while a transform job is queued or running, the image worker is
  stopped (all of its memory freed) and the scheduler waits;
- nothing loads unless it fits: before each model is loaded the governor checks free
  memory and pressure; the worker drops the image model it doesn't need when memory
  is tight; on critical pressure everything art-related is released at once;
- what you ask for (draw options, use this look, redraw) runs right away; *automatic*
  work (profiles and options for upcoming characters, checker redraws of those) only
  runs while you're away from the keyboard and not on battery (configurable);
- the image worker runs at low CPU priority and exits after a couple of idle minutes;
  BABEL only ever unloads the Ollama models it uses itself, never yours.

Every image is checked by the quality approver (``approve.py``) when a vision model is
installed: failing options are hidden and replaced, failing expressions are redrawn
(a few attempts), and options are ranked best-first.

Work order follows the reader: your requests first, then expressions of chosen
characters (they unblock chapters), then options for the next characters by first appearance.
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

from babel.art import designs, plan
from babel.art.approve import Approver
from babel.art.profile import (
    FIELDS,
    draft_messages,
    gather_evidence,
    parse_profile,
    profile_schema,
    setting_messages,
    verify_citations,
)
from babel.memory.akashic import Akashic
from babel.store.db import Store
from babel.system import Governor, ollama_unload

log = logging.getLogger("babel.art")

WORKER_SCRIPT = Path(__file__).with_name("worker_proc.py")
LOOKAHEAD = 4  # designs waiting for your pick before the scheduler stops drafting new options
IDLE_STOP_SECS = 120
# measured on an M5 Max (MLX cache capped at 2 GB, Anima with tiled decoding): the peak while drawing one image,
# and what the worker keeps holding between images
MODEL_PEAK_GB = {"anima-turbo": 12.0, "flux2-klein-4b": 12.0}
MODEL_HELD_GB = {"anima-turbo": 6.0, "flux2-klein-4b": 4.5}
DRAW_MARGIN_GB = 3.0  # on top of the governor's headroom: free memory stays clear of macOS compressing
MAX_CANDIDATE_DRAWS = 12  # per design: the checker may redraw failing options until this many were drawn
MAX_EXPRESSION_ATTEMPTS = 3
MAX_LIBRARY_DRAWS = 6  # extras/backgrounds: give up (and use the closest) after this many options
PRESSURE_COOLDOWN_S = 300  # after a memory-pressure pause, automatic work waits this long
STAGE_AHEAD = 8  # chapters after your reading position that are prepared automatically


class ArtError(RuntimeError):
    pass


class Backend(Protocol):
    loaded: set[str]

    def call(self, req: dict) -> dict: ...
    def close(self) -> None: ...
    @property
    def running(self) -> bool: ...


class SubprocessBackend:
    """Talks to ``worker_proc.py`` running under the art environment's Python, at low CPU priority."""

    def __init__(self, python: Path, log_path: Path):
        self.python, self.log_path = python, log_path
        self.proc: subprocess.Popen | None = None
        self.loaded: set[str] = set()
        self._lock = threading.Lock()
        self._n = 0

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def _ensure(self) -> subprocess.Popen:
        if not self.running:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            logf = self.log_path.open("a")
            self.loaded = set()
            # nice: your apps get the CPU first
            self.proc = subprocess.Popen(["nice", "-n", "10", str(self.python), "-u", str(WORKER_SCRIPT)],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=logf, text=True,
                                         bufsize=1)
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
                self.loaded = set()
                raise ArtError(f"image worker exited (see {self.log_path})")
            rep = json.loads(line)
            self.loaded = set(rep.get("loaded") or [])
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
            self.loaded = set()


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
    profile = verify_citations(parse_profile(reply.content), evidence)
    return designs.save_profile(store, eid, profile, user=False)


# ── the scheduler ─────────────────────────────────────────────────────────
class ArtScheduler:
    def __init__(self, store: Store, *, art_dir: Path, portraits_dir: Path,
                 backend_factory: Callable[[], Backend] | None, llm_factory: Callable[[], object | None],
                 approver_factory: Callable[[], Approver | None] = lambda: None,
                 governor: Governor | None = None, ollama_url: str = "http://localhost:11434",
                 idle_stop_secs: float = IDLE_STOP_SECS):
        self.store, self.art_dir, self.portraits_dir = store, art_dir, portraits_dir
        self.backend_factory, self.llm_factory, self.approver_factory = backend_factory, llm_factory, approver_factory
        self.governor = governor or Governor(probes={  # no governor given (tests): never block
            "available_gb": lambda: None, "on_battery": lambda: None, "idle_seconds": lambda: None,
            "pressure_level": lambda: None, "ollama_loaded": lambda: {}, "ollama_size_gb": lambda m: None})
        self.ollama_url, self.idle_stop_secs = ollama_url, idle_stop_secs
        self.backend: Backend | None = None
        self.state: dict = {"status": "idle" if backend_factory else "unavailable", "detail": None, "error": None}
        self._wake, self._stop = threading.Event(), threading.Event()
        self._thread: threading.Thread | None = None
        self._last_work = time.time()
        self._approver: Approver | None = None
        self._approver_checked = False
        self._waiting: str | None = None
        self._pressure_until = 0.0

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
        self.release()

    @property
    def approver(self) -> Approver | None:
        if not self._approver_checked:
            self._approver_checked = True
            try:
                self._approver = self.approver_factory()
            except Exception as e:
                log.warning("no quality checker: %s", e)
        return self._approver

    def release(self, *, images: bool = True, vision: bool = True) -> None:
        """Give memory back: stop the image worker and/or unload the checker's vision model."""
        if images and self.backend is not None and self.backend.running:
            self.backend.close()
        if vision and self._approver is not None:
            ollama_unload(self.ollama_url, [self._approver.model])

    def _set(self, status: str, detail: str | None = None) -> None:
        self.state.update(status=status, detail=detail)
        if status == "waiting":
            self._waiting = detail

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
            if time.time() - self._last_work > self.idle_stop_secs:
                self.release()
            self._wake.wait(timeout=5)
            self._wake.clear()

    # one unit of work; returns True if something was done
    def step(self) -> bool:
        self._waiting: str | None = None
        if self._text_busy():
            self.release()
            self._set("waiting", "a transform job is running; art resumes when it finishes")
            return False
        if self.governor.critical():
            self.release()
            self._set("waiting", "memory pressure is critical — art paused and its memory freed")
            return False
        if self._check_pending(manual_only=True) or self._draw_next(manual=True):
            return True
        has_auto = self._auto_work_pending()
        if has_auto and (reason := self.governor.background() or self._pressure_reason()):
            self.release()  # don't sit on memory while you work (or while your apps need it)
            self._set("paused", reason)
            return False
        if self._check_pending(manual_only=False) or self._auto_profiles() or self._auto_candidates() \
                or self._auto_stage() or self._auto_library() or self._draw_next(manual=False):
            return True
        if self._waiting:  # keep showing why we're waiting (memory, …)
            self._set("waiting", self._waiting)
        else:
            idle = "idle" if self.backend_factory else "unavailable"
            self._set(idle, None if self.backend_factory else "image models not installed — run `babel art setup`")
        return False

    def _pressure_reason(self) -> str | None:
        """Automatic work also stops when the Mac is short of memory — even if it's what caused it —
        and stays off for a few minutes afterwards so it doesn't flap on and off."""
        if reason := self.governor.pressure():
            self._pressure_until = time.time() + PRESSURE_COOLDOWN_S
            return f"{reason} — automatic work paused and its memory freed so your apps have room"
        if time.time() < self._pressure_until:
            mins = max(1, round((self._pressure_until - time.time()) / 60))
            return f"memory was short recently — automatic work resumes in about {mins} min"
        return None

    def _text_model(self):
        """The text model for profile/staging work: frees our image memory first, falls back to a smaller model
        if the usual one doesn't fit, and returns False (after saying why) if nothing fits yet."""
        from babel.system import fitting_model

        llm = self.llm_factory()
        if llm is None:
            return None
        self.release(vision=False)  # text work doesn't need the image models
        fit = fitting_model(llm, self.governor)
        if fit is None:
            self._set("waiting", self.governor.ollama_model(getattr(llm, "model", None)))
            return False
        return fit

    def _auto_novels(self) -> list[int]:
        return [r["id"] for r in self.store.q("SELECT id, art FROM novels")
                if r["art"] and json.loads(r["art"]).get("auto")]

    def _auto_work_pending(self) -> bool:
        if self.store.one("SELECT 1 FROM art_images WHERE (status='queued' AND manual=0)"
                          " OR (status='done' AND qc_status='pending') LIMIT 1"):
            return True
        if self.store.one("SELECT 1 FROM designs WHERE kind IN ('extra','background') AND status='profiled' LIMIT 1"):
            return True
        for nid in self._auto_novels():
            q = plan.queue(self.store, Akashic(self.store, nid))
            if any(c["status"] in ("new", "profiled") for c in q[:LOOKAHEAD * 2]):
                return True
            pos = self._reading_idx(nid)
            if self.store.one("SELECT 1 FROM chapters c LEFT JOIN stage s ON s.chapter_id=c.id WHERE c.novel_id=?"
                              " AND c.status='done' AND c.idx>=? AND c.idx<? AND (s.refined IS NULL OR s.refined=0)"
                              " LIMIT 1", (nid, pos, pos + STAGE_AHEAD)):
                return True
        return False

    def _auto_profiles(self) -> bool:
        for nid in self._auto_novels():
            ak = Akashic(self.store, nid)
            todo = [c for c in plan.queue(self.store, ak)[:LOOKAHEAD * 2] if c["status"] == "new"]
            if not todo:
                continue
            llm = self._text_model()
            if llm is False:
                return False
            c = todo[0]
            self._set("profiling", c["name"])
            try:
                draft_profile(self.store, ak, c["id"], llm)
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
                designs.queue_candidates(self.store, ak, c["id"], manual=False)
                return True
        return False

    def _reading_idx(self, nid: int) -> int:
        row = self.store.one("SELECT c.idx FROM progress p JOIN chapters c ON c.id=p.chapter_id WHERE p.novel_id=?",
                             (nid,))
        return row["idx"] if row else 0

    def _auto_stage(self) -> bool:
        """Get the next chapters after your reading position ready: expressions, places, faces, backgrounds."""
        from babel.vn import stage

        for nid in self._auto_novels():
            pos = self._reading_idx(nid)
            rows = self.store.q("SELECT c.id FROM chapters c LEFT JOIN stage s ON s.chapter_id=c.id"
                                " WHERE c.novel_id=? AND c.status='done' AND c.idx>=? AND c.idx<?"
                                " AND (s.refined IS NULL OR s.refined=0) ORDER BY c.idx LIMIT 1",
                                (nid, pos, pos + STAGE_AHEAD))
            if not rows:
                continue
            ak = Akashic(self.store, nid)
            cid = rows[0]["id"]
            llm = self._text_model()
            if llm is False:
                return False
            if llm is not None:
                self._set("staging", f"chapter {self.store.one('SELECT idx FROM chapters WHERE id=?', (cid,))['idx'] + 1}")
                try:
                    stage.refine(self.store, ak, cid, llm)
                except Exception as e:
                    log.warning("staging failed: %s", e)
                    self.store.x("UPDATE stage SET refined=1 WHERE chapter_id=?", (cid,))  # rules are fine
            else:
                stage.get(self.store, ak, cid)
                self.store.x("UPDATE stage SET refined=1 WHERE chapter_id=?", (cid,))
            stage.prepare(self.store, ak, cid, manual=False)
            return True
        return False

    def _auto_library(self) -> bool:
        """Draw library faces/backgrounds that upcoming chapters need, a couple of designs at a time."""
        busy = self.store.one("SELECT COUNT(*) n FROM designs WHERE kind IN ('extra','background')"
                              " AND status IN ('candidates','sheet')")["n"]
        if busy >= 2:
            return False
        row = self.store.one("SELECT d.entity_id, e.novel_id FROM designs d JOIN entities e ON e.id=d.entity_id"
                             " WHERE d.kind IN ('extra','background') AND d.status='profiled' ORDER BY d.id LIMIT 1")
        if not row:
            return False
        designs.queue_candidates(self.store, Akashic(self.store, row["novel_id"]), row["entity_id"], manual=False)
        return True

    def _next_image(self, manual: bool) -> dict | None:
        # expressions first (they finish a character and unblock chapters), then by first appearance
        rows = self.store.q(
            "SELECT i.*, d.entity_id, e.novel_id, COALESCE(e.first_idx, 1<<30) AS first FROM art_images i"
            " JOIN designs d ON d.id=i.design_id JOIN entities e ON e.id=d.entity_id"
            " WHERE i.status='queued' AND i.manual=? ORDER BY (i.kind='expression') DESC, first, i.id LIMIT 1",
            (int(manual),))
        return rows[0] if rows else None

    def _make_room(self, model: str) -> str | None:
        """Make sure ``model`` can be loaded in the image worker; returns a reason if it can't yet."""
        assert self.backend is not None
        if model in self.backend.loaded:
            # already loaded, but every image has a short peak above what's held: check that too
            return self.governor.memory(MODEL_PEAK_GB.get(model, 14.0) - MODEL_HELD_GB.get(model, 5.0) + DRAW_MARGIN_GB)
        # one image model at a time: switching costs a few seconds and happens rarely (work is batched)
        for other in list(self.backend.loaded):
            self.backend.call({"op": "unload", "model": other})
        need = MODEL_PEAK_GB.get(model, 14.0) + DRAW_MARGIN_GB
        if self.governor.memory(need) is None:
            return None
        # still short: free the other models we use ourselves, then look again
        if self._approver is not None:
            ollama_unload(self.ollama_url, [self._approver.model])
        llm = self.llm_factory()
        if llm is not None and getattr(llm, "model", None):
            ollama_unload(self.ollama_url, [llm.model])
        return self.governor.memory(need)

    def _draw_next(self, manual: bool) -> bool:
        img = self._next_image(manual)
        if img is None:
            return False
        if self.backend_factory is None:
            self._set("unavailable", "image models not installed — run `babel art setup`")
            return False
        if self.backend is None:
            self.backend = self.backend_factory()
        if self.governor.pressure() and self._approver is not None:
            ollama_unload(self.ollama_url, [self._approver.model])  # short of memory: one model at a time
        if reason := self._make_room(img["model"]):
            self._set("waiting", reason)
            return False
        self._draw(img)
        return True

    def _draw(self, img: dict) -> None:
        assert self.backend is not None
        name = (self.store.one("SELECT name FROM entities WHERE id=?", (img["entity_id"],)) or {}).get("name")
        self._set("drawing", f"{name}: {img['emotion'] or 'option'}")
        self.store.x("UPDATE art_images SET status='running' WHERE id=?", (img["id"],))
        out = designs.image_dir(self.art_dir, img["novel_id"], img["entity_id"]) / f"{img['id']}.png"
        p = json.loads(img["prompt"])
        try:
            if img["kind"] == "candidate":
                req = {"op": "generate", "model": img["model"], "prompt": p["prompt"], "negative": p.get("negative"),
                       "seed": img["seed"], "width": p.get("width", designs.BASE_W),
                       "height": p.get("height", designs.BASE_H), "out": str(out)}
            else:
                d = self.store.one("SELECT base_image_id FROM designs WHERE id=?", (img["design_id"],))
                base = self.store.one("SELECT path FROM art_images WHERE id=?", (d["base_image_id"],))
                req = {"op": "edit", "model": img["model"], "prompt": p["prompt"], "image": base["path"],
                       "seed": img["seed"], "width": designs.BASE_W, "height": designs.BASE_H, "out": str(out)}
            rep = self.backend.call(req)
            make_thumb(out)
            self.store.x("UPDATE art_images SET status='done', path=?, secs=?, error=NULL, qc_status=? WHERE id=?",
                         (str(out), rep.get("secs"), "pending" if self.approver else "skipped", img["id"]))
            self.state["error"] = None
        except Exception as e:
            if (img.get("attempt") or 1) < 2:  # e.g. the worker was stopped mid-draw: try once more
                self.store.x("UPDATE art_images SET status='queued', attempt=attempt+1, error=? WHERE id=?",
                             (str(e)[:500], img["id"]))
            else:
                self.store.x("UPDATE art_images SET status='failed', error=? WHERE id=?", (str(e)[:500], img["id"]))
            self.state["error"] = str(e)[:300]
            return
        if not self.approver:
            self._finish(img["design_id"])
        # with a checker, the design advances once the check has run (``_check_pending``)

    # ── the quality checker ────────────────────────────────────────────────
    def _check_pending(self, manual_only: bool) -> bool:
        if not self.approver:
            return False
        rows = self.store.q(
            "SELECT i.*, d.entity_id, d.profile, d.base_image_id, d.kind AS design_kind, d.spec, e.gender"
            " FROM art_images i"
            " JOIN designs d ON d.id=i.design_id JOIN entities e ON e.id=d.entity_id"
            " WHERE i.status='done' AND i.qc_status='pending'" + (" AND i.manual=1" if manual_only else "") +
            " ORDER BY i.id LIMIT 1")
        if not rows:
            return False
        img = rows[0]
        if self.governor.pressure():
            # short of memory: finish drawing first, then check with the image model released
            if self.store.one("SELECT 1 FROM art_images WHERE status='queued' LIMIT 1"):
                return False
            self.release(vision=False)
        if reason := self.governor.ollama_model(self.approver.model):
            # make room by letting go of an idle image model rather than skipping the check
            if self.backend is not None and self.backend.loaded:
                for other in list(self.backend.loaded):
                    self.backend.call({"op": "unload", "model": other})
                reason = self.governor.ollama_model(self.approver.model)
            if reason:
                self._set("waiting", f"quality check {reason.removeprefix('waiting')}".replace("  ", " "))
                return False
        name = (self.store.one("SELECT name FROM entities WHERE id=?", (img["entity_id"],)) or {}).get("name")
        self._set("checking", f"{name}: {img['emotion'] or 'option'}")
        ref = None
        if img["kind"] == "expression" and img["emotion"] != "neutral" and img["base_image_id"]:
            ref = (self.store.one("SELECT path FROM art_images WHERE id=?", (img["base_image_id"],)) or {}).get("path")
        try:
            spec = json.loads(img["spec"]) if img.get("spec") else {}
            qc = self.approver.check(img["path"], profile=json.loads(img["profile"]) if img["profile"] else None,
                                     gender=img["gender"], kind=img["kind"], emotion=img["emotion"], reference=ref,
                                     background=spec.get("label") if img.get("design_kind") == "background" else None)
        except Exception as e:  # a checker failure never blocks a design
            log.warning("quality check failed: %s", e)
            self.store.x("UPDATE art_images SET qc_status='skipped', qc=? WHERE id=?",
                         (json.dumps({"error": str(e)[:200]}), img["id"]))
            self._finish(img["design_id"])
            return True
        verdict = "pass" if qc["pass"] else "fail"
        self.store.x("UPDATE art_images SET qc_status=?, qc_score=?, qc=? WHERE id=?",
                     (verdict, qc["score"], json.dumps(qc, ensure_ascii=False), img["id"]))
        if verdict == "fail":
            self._redraw(img)
        self._finish(img["design_id"])
        return True

    def _redraw(self, img: dict) -> None:
        """A failed check: hide a bad option and replace it; redraw a bad expression a few times."""
        if img["kind"] == "candidate":
            self.store.x("UPDATE art_images SET status='rejected' WHERE id=?", (img["id"],))
            drawn = self.store.one("SELECT COUNT(*) n FROM art_images WHERE design_id=? AND kind='candidate'",
                                   (img["design_id"],))["n"]
            d = self.store.one("SELECT auto_pick FROM designs WHERE id=?", (img["design_id"],))
            if d and d["auto_pick"]:
                # library items need one good option, not six: stop as soon as one passed, and give up sooner
                passed = self.store.one("SELECT 1 FROM art_images WHERE design_id=? AND kind='candidate'"
                                        " AND status IN ('done','queued','running') AND qc_status IS NOT 'fail'"
                                        " LIMIT 1", (img["design_id"],))
                if passed or drawn >= MAX_LIBRARY_DRAWS:
                    return
            if drawn < MAX_CANDIDATE_DRAWS:
                e = self.store.one("SELECT novel_id FROM entities WHERE id=?", (img["entity_id"],))
                designs.queue_candidates(self.store, Akashic(self.store, e["novel_id"]), img["entity_id"], 1,
                                         manual=bool(img["manual"]), attempt=(img["attempt"] or 1) + 1)
        elif img["emotion"] != "neutral" and (img["attempt"] or 1) < MAX_EXPRESSION_ATTEMPTS:
            self.store.x("UPDATE art_images SET status='rejected' WHERE id=?", (img["id"],))
            designs.queue_expression(self.store, img["design_id"], img["emotion"], manual=bool(img["manual"]),
                                     attempt=(img["attempt"] or 1) + 1)
        # else: out of attempts — keep the best we have; the sheet shows it as "needs a look"

    def _finish(self, design_id: int) -> None:
        designs.after_image(self.store, design_id)
        d = self.store.one("SELECT * FROM designs WHERE id=?", (design_id,))
        if d and d["status"] == "approved" and d["base_image_id"]:
            base = self.store.one("SELECT path FROM art_images WHERE id=?", (d["base_image_id"],))
            if base and base["path"]:
                make_portrait(self.store, d["entity_id"], Path(base["path"]), self.portraits_dir)

    def status(self) -> dict:
        counts = {r["status"]: r["n"] for r in self.store.q(
            "SELECT status, COUNT(*) n FROM art_images WHERE status IN ('queued','running','failed') GROUP BY status")}
        checked = self.store.one("SELECT COUNT(*) n, SUM(qc_status='fail') bad FROM art_images"
                                 " WHERE qc_status IN ('pass','fail')")
        return {**self.state, "worker_running": bool(self.backend and self.backend.running),
                "queued": counts.get("queued", 0) + counts.get("running", 0), "failed": counts.get("failed", 0),
                "checker": self.approver.model if self.approver else None,
                "checked": checked["n"] or 0, "caught": checked["bad"] or 0}
