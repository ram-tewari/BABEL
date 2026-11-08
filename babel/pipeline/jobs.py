"""Background transform jobs: resumable, pausable, several novels at once.

Jobs are database rows. The worker runs up to ``parallel_novels`` jobs at the
same time (one per novel — a novel's memory grows front to back, so a novel
never has two jobs). Within a job, chapters are dispatched in reading order to a
small pool. Interrupted jobs resume where they stopped: finished chapters are
skipped unless the job forces a re-run.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

from babel.memory.akashic import Akashic
from babel.scenario.cascade import Cascade, TransformFailed
from babel.store.db import Store, now

log = logging.getLogger(__name__)

TIER_MODES = ("auto", "rules", "local", "cloud")


def create_job(store: Store, novel_id: int, first: int | None = None, last: int | None = None,
               force: bool = False, tiers: str = "auto") -> int:
    if tiers not in TIER_MODES:
        raise ValueError(f"tiers must be one of {', '.join(TIER_MODES)}")
    live = store.one("SELECT id FROM jobs WHERE novel_id=? AND status IN ('queued','running','paused')", (novel_id,))
    if live:  # one live job per novel: retarget it instead of stacking another
        store.x("UPDATE jobs SET first_idx=?, last_idx=?, force=?, tiers=?, status='queued' WHERE id=?",
                (first, last, int(force), tiers, live["id"]))
        return live["id"]
    return store.x("INSERT INTO jobs (novel_id, status, first_idx, last_idx, force, tiers, created_at)"
                   " VALUES (?,?,?,?,?,?,?)", (novel_id, "queued", first, last, int(force), tiers, now()))


def job_targets(store: Store, job: dict, *, all_in_range: bool = False) -> list[dict]:
    sql = "SELECT id, idx, title, status FROM chapters WHERE novel_id=?"
    args: list = [job["novel_id"]]
    if job.get("first_idx") is not None:
        sql += " AND idx>=?"
        args.append(job["first_idx"])
    if job.get("last_idx") is not None:
        sql += " AND idx<=?"
        args.append(job["last_idx"])
    if not job.get("force") and not all_in_range:
        sql += " AND status!='done'"
    return store.q(sql + " ORDER BY idx", args)


def run_job(store: Store, cascade: Cascade, job_id: int, concurrency: int = 2,
            on_chapter: Callable[[dict, str], None] | None = None) -> dict:
    """Run a job to completion (or until paused/cancelled). Returns the final job row."""
    job = store.one("SELECT * FROM jobs WHERE id=?", (job_id,))
    if job is None:
        raise ValueError(f"no job {job_id}")
    targets = job_targets(store, job)
    if job["force"]:
        total, already = len(targets), 0
    else:
        total = len(job_targets(store, job, all_in_range=True))
        already = total - len(targets)
    label = "rules + memory" if job["tiers"] == "rules" else cascade.label
    store.x("UPDATE jobs SET status='running', started_at=COALESCE(started_at, ?), total=?, done=?, failed=0,"
            " message=? WHERE id=?", (now(), total, already, f"using {label}", job_id))
    ak = Akashic(store, job["novel_id"])
    done, failed = already, 0
    stop: str | None = None

    def work(ch: dict) -> tuple[dict, str | None]:
        full = store.get_chapter(ch["id"])
        try:
            out = cascade.transform(store, ak, full, mode=job["tiers"])
        except TransformFailed as e:
            store.mark_failed(ch["id"], str(e))
            return ch, str(e)
        except Exception as e:  # one bad chapter never kills the job
            log.exception("chapter %s failed", ch["id"])
            store.mark_failed(ch["id"], f"{type(e).__name__}: {e}")
            return ch, str(e)
        store.save_doc(ch["id"], out.decisions, summary=out.summary, review_count=out.review_count,
                       tiers=out.tiers, stats=out.stats)
        return ch, None

    pending = list(targets)
    running: set[Future] = set()
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        while pending or running:
            status = (store.one("SELECT status FROM jobs WHERE id=?", (job_id,)) or {}).get("status")
            if status in ("paused", "cancelled") and stop is None:
                stop = status
                if pending and job["force"]:
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
                if done % 25 == 0:
                    with cascade.memory_lock:
                        ak.recount()

    with cascade.memory_lock:
        ak.recount()
    final = stop or ("failed" if failed and done == already else "done")
    store.x("UPDATE jobs SET status=?, finished_at=? WHERE id=?",
            (final, now() if final != "paused" else None, job_id))
    return store.one("SELECT * FROM jobs WHERE id=?", (job_id,))


class Worker:
    """Runs queued jobs on background threads — up to ``parallel_novels`` novels at once."""

    def __init__(self, store: Store, cascade_factory: Callable[[], Cascade], concurrency: int = 2,
                 parallel_novels: int = 2):
        self.store = store
        self.cascade_factory = cascade_factory
        self.concurrency = concurrency
        self.parallel_novels = max(1, parallel_novels)
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._active: dict[int, threading.Thread] = {}
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.store.x("UPDATE jobs SET status='queued' WHERE status='running'")  # resume after restart
        self._thread = threading.Thread(target=self._loop, name="babel-worker", daemon=True)
        self._thread.start()

    def poke(self) -> None:
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def _run(self, job_id: int) -> None:
        try:
            run_job(self.store, self.cascade_factory(), job_id, self.concurrency)
        except Exception as e:
            log.exception("job %s crashed", job_id)
            self.store.x("UPDATE jobs SET status='failed', message=?, finished_at=? WHERE id=?",
                         (f"crashed: {e}", now(), job_id))
        finally:
            self._active.pop(job_id, None)
            self._wake.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            free = self.parallel_novels - len(self._active)
            busy = {j for j in self._active}
            if free > 0:
                for job in self.store.q("SELECT id FROM jobs WHERE status='queued' ORDER BY id"):
                    if free <= 0:
                        break
                    if job["id"] in busy:
                        continue
                    t = threading.Thread(target=self._run, args=(job["id"],), name=f"babel-job-{job['id']}", daemon=True)
                    self._active[job["id"]] = t
                    t.start()
                    free -= 1
            self._wake.wait(timeout=3)
            self._wake.clear()
