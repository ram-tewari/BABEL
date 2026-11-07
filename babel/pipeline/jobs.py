"""Background transform jobs: resumable, pausable, one novel at a time.

Jobs are rows in the database. A single worker thread runs them in order;
within a job, chapters are dispatched in reading order to a small thread pool
(``concurrency``) so the codex mostly grows front-to-back. Interrupted jobs
resume where they stopped because finished chapters are skipped.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

from babel.memory.codex import Codex
from babel.store.db import Store, now
from babel.transform.engine import Engine, TransformFailed

log = logging.getLogger(__name__)

ACTIVE = ("queued", "running")


def create_job(store: Store, novel_id: int, first: int | None = None, last: int | None = None,
               force: bool = False, mode: str = "auto") -> int:
    if mode not in ("auto", "llm", "heuristic"):
        raise ValueError("mode must be auto, llm or heuristic")
    existing = store.one(
        "SELECT id FROM jobs WHERE novel_id=? AND status IN ('queued','running','paused')", (novel_id,))
    if existing:
        # one live job per novel: update its range instead of stacking another
        store.x("UPDATE jobs SET first_idx=?, last_idx=?, force=?, mode=?, status='queued' WHERE id=?",
                (first, last, int(force), mode, existing["id"]))
        return existing["id"]
    return store.x(
        "INSERT INTO jobs (novel_id, status, first_idx, last_idx, force, mode, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (novel_id, "queued", first, last, int(force), mode, now()),
    )


def job_targets(store: Store, job: dict) -> list[dict]:
    sql = "SELECT id, idx, title, status FROM chapters WHERE novel_id=?"
    args: list = [job["novel_id"]]
    if job.get("first_idx") is not None:
        sql += " AND idx>=?"
        args.append(job["first_idx"])
    if job.get("last_idx") is not None:
        sql += " AND idx<=?"
        args.append(job["last_idx"])
    if not job.get("force"):
        sql += " AND status!='done'"
    return store.q(sql + " ORDER BY idx", args)


def run_job(store: Store, engine: Engine, job_id: int, concurrency: int = 2,
            on_chapter: Callable[[dict, str], None] | None = None) -> dict:
    """Run a job to completion (or until paused/cancelled). Returns the final job row."""
    job = store.one("SELECT * FROM jobs WHERE id=?", (job_id,))
    if job is None:
        raise ValueError(f"no job {job_id}")
    targets = job_targets(store, job)
    if job["force"]:
        total, already = len(targets), 0
    else:
        in_range = job_targets(store, {**job, "force": 1})
        total, already = len(in_range), len(in_range) - len(targets)
    engine_label = engine.router.label if engine.router else "heuristic (no LLM configured)"
    if job["mode"] == "heuristic":
        engine_label = "heuristic"
    store.x("UPDATE jobs SET status='running', started_at=COALESCE(started_at, ?), total=?, done=?, failed=0,"
            " message=? WHERE id=?", (now(), total, already, f"using {engine_label}", job_id))
    codex = Codex(store, job["novel_id"])
    done = already
    failed = 0
    stop_reason: str | None = None

    def work(ch: dict) -> tuple[dict, str | None]:
        full = store.get_chapter(ch["id"])
        try:
            out = engine.transform(store, codex, full, mode=job["mode"])
        except TransformFailed as e:
            store.mark_failed(ch["id"], str(e))
            return ch, str(e)
        except Exception as e:  # never let one chapter kill the job
            log.exception("chapter %s failed", ch["id"])
            store.mark_failed(ch["id"], f"{type(e).__name__}: {e}")
            return ch, str(e)
        store.save_labels(ch["id"], out.labels, method=out.method, model=out.model, summary=out.summary)
        return ch, None

    pending = list(targets)
    running: set[Future] = set()
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        while pending or running:
            status = (store.one("SELECT status FROM jobs WHERE id=?", (job_id,)) or {}).get("status")
            if status in ("paused", "cancelled") and stop_reason is None:
                stop_reason = status
                if pending and job["force"]:
                    # a resumed forced job continues from here, not from the start
                    store.x("UPDATE jobs SET first_idx=? WHERE id=?", (pending[0]["idx"], job_id))
                pending.clear()
            while pending and len(running) < concurrency:
                running.add(pool.submit(work, pending.pop(0)))
            if not running:
                break
            finished, running = wait(running, return_when=FIRST_COMPLETED)
            for f in finished:
                ch, err = f.result()
                if err:
                    failed += 1
                else:
                    done += 1
                msg = f"{'✗' if err else '✓'} {ch['title']}" + (f": {err[:200]}" if err else "")
                store.x("UPDATE jobs SET done=?, failed=?, message=? WHERE id=?", (done, failed, msg, job_id))
                if on_chapter:
                    on_chapter(ch, err or "ok")

    codex.recount()
    if stop_reason:
        final = stop_reason
    else:
        final = "failed" if failed and not done else "done"
    store.x("UPDATE jobs SET status=?, finished_at=? WHERE id=?",
            (final, now() if final in ("done", "failed", "cancelled") else None, job_id))
    _auto_pov(store, job["novel_id"])
    return store.one("SELECT * FROM jobs WHERE id=?", (job_id,))


def _auto_pov(store: Store, novel_id: int) -> None:
    """Default the point-of-view character to the most active speaker."""
    n = store.one("SELECT pov_character_id FROM novels WHERE id=?", (novel_id,))
    if n and n["pov_character_id"] is None:
        top = store.one("SELECT id FROM characters WHERE novel_id=? AND lines>0 ORDER BY lines DESC LIMIT 1",
                        (novel_id,))
        if top:
            store.x("UPDATE novels SET pov_character_id=? WHERE id=?", (top["id"], novel_id))


class Worker:
    """Runs queued jobs on a background thread (used by the web server)."""

    def __init__(self, store: Store, engine_factory: Callable[[], Engine], concurrency: int = 2):
        self.store = store
        self.engine_factory = engine_factory
        self.concurrency = concurrency
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        # jobs interrupted by a restart resume from where they were
        self.store.x("UPDATE jobs SET status='queued' WHERE status='running'")
        self._thread = threading.Thread(target=self._loop, name="babel-worker", daemon=True)
        self._thread.start()

    def poke(self) -> None:
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            job = self.store.one("SELECT id FROM jobs WHERE status='queued' ORDER BY id LIMIT 1")
            if job is None:
                self._wake.wait(timeout=5)
                self._wake.clear()
                continue
            try:
                run_job(self.store, self.engine_factory(), job["id"], self.concurrency)
            except Exception as e:
                log.exception("job %s crashed", job["id"])
                self.store.x("UPDATE jobs SET status='failed', message=?, finished_at=? WHERE id=?",
                             (f"crashed: {e}", now(), job["id"]))
