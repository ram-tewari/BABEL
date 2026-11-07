"""SQLite storage for the whole library.

Everything lives in one file: novels, chapter source text, per-segment labels,
the character codex (names + aliases), user overrides, jobs and reading progress.

A chapter stores its *labels* (segment id → type/speaker), not rendered blocks.
Segments are recomputed deterministically from the source text, user corrections
are kept as a separate override layer (so they survive re-transforms), and
speaker labels are resolved to characters through the alias table at read time
(so a rename or merge applies to every chapter instantly).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS novels (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  author TEXT,
  description TEXT,
  language TEXT,
  cover_path TEXT,
  source_name TEXT,
  pov_character_id INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chapters (
  id INTEGER PRIMARY KEY,
  novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  idx INTEGER NOT NULL,
  title TEXT NOT NULL,
  source_text TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  word_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending',      -- pending | done | failed
  method TEXT,                                 -- llm | heuristic | mixed
  model TEXT,
  labels_json TEXT,
  summary TEXT,
  error TEXT,
  transformed_at TEXT,
  UNIQUE (novel_id, idx)
);
CREATE INDEX IF NOT EXISTS idx_chapters_novel ON chapters(novel_id, idx);
CREATE TABLE IF NOT EXISTS characters (
  id INTEGER PRIMARY KEY,
  novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  note TEXT,
  color TEXT,
  side TEXT,                                   -- left | right | NULL (auto)
  first_idx INTEGER,
  lines INTEGER NOT NULL DEFAULT 0,
  name_locked INTEGER NOT NULL DEFAULT 0,
  auto_slot INTEGER,                           -- palette slot assigned by activity rank
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_characters_novel ON characters(novel_id);
CREATE TABLE IF NOT EXISTS aliases (
  novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  norm TEXT NOT NULL,
  alias TEXT NOT NULL,
  character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  PRIMARY KEY (novel_id, norm)
);
CREATE INDEX IF NOT EXISTS idx_aliases_char ON aliases(character_id);
CREATE TABLE IF NOT EXISTS overrides (
  chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
  seg INTEGER NOT NULL,
  type TEXT NOT NULL,
  speaker TEXT,
  original_type TEXT,
  original_speaker TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (chapter_id, seg)
);
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY,
  novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  status TEXT NOT NULL,                        -- queued | running | paused | done | failed | cancelled
  first_idx INTEGER,
  last_idx INTEGER,
  force INTEGER NOT NULL DEFAULT 0,
  mode TEXT NOT NULL DEFAULT 'auto',           -- auto | llm | heuristic
  total INTEGER NOT NULL DEFAULT 0,
  done INTEGER NOT NULL DEFAULT 0,
  failed INTEGER NOT NULL DEFAULT 0,
  message TEXT,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT
);
CREATE TABLE IF NOT EXISTS progress (
  novel_id INTEGER PRIMARY KEY REFERENCES novels(id) ON DELETE CASCADE,
  chapter_id INTEGER,
  position REAL NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);
"""

CHAPTER_LIST_COLS = "id, novel_id, idx, title, word_count, status, method, model, error, transformed_at"


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def norm_name(name: str) -> str:
    return " ".join(name.lower().replace("’", "'").split())


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA synchronous = NORMAL")
            self._conn.executescript(SCHEMA)
            self._migrate()

    # Columns added after a table first shipped: (table, column, definition).
    _ADDED_COLUMNS = [
        ("characters", "name_locked", "INTEGER NOT NULL DEFAULT 0"),
        ("characters", "auto_slot", "INTEGER"),
    ]

    def _migrate(self) -> None:
        for table, column, ddl in self._ADDED_COLUMNS:
            cols = {r[1] for r in self._conn.execute(f"PRAGMA table_info({table})")}
            if column not in cols:
                self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    # ── plumbing ──────────────────────────────────────────────────────────
    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            else:
                self._conn.execute("COMMIT")

    def q(self, sql: str, args: Iterable[Any] = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, tuple(args)).fetchall()]

    def one(self, sql: str, args: Iterable[Any] = ()) -> dict | None:
        rows = self.q(sql, args)
        return rows[0] if rows else None

    def x(self, sql: str, args: Iterable[Any] = ()) -> int:
        with self._lock:
            cur = self._conn.execute(sql, tuple(args))
            return cur.lastrowid or cur.rowcount

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ── novels ────────────────────────────────────────────────────────────
    def create_novel(self, title: str, chapters: list[tuple[str, str, str]], **meta: Any) -> int:
        """Create a novel with chapters given as (title, text, sha256) tuples."""
        ts = now()
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO novels (title, author, description, language, source_name, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (title, meta.get("author"), meta.get("description"), meta.get("language"),
                 meta.get("source_name"), ts, ts),
            )
            nid = cur.lastrowid
            c.executemany(
                "INSERT INTO chapters (novel_id, idx, title, source_text, source_hash, word_count)"
                " VALUES (?,?,?,?,?,?)",
                [(nid, i, t, txt, h, len(txt.split())) for i, (t, txt, h) in enumerate(chapters)],
            )
        return nid

    def append_chapters(self, novel_id: int, chapters: list[tuple[str, str, str]]) -> int:
        """Append chapters whose source hash is not already in the novel. Returns count added."""
        existing = {r["source_hash"] for r in self.q("SELECT source_hash FROM chapters WHERE novel_id=?", (novel_id,))}
        start = (self.one("SELECT MAX(idx) m FROM chapters WHERE novel_id=?", (novel_id,)) or {}).get("m")
        start = -1 if start is None else start
        new = [c for c in chapters if c[2] not in existing]
        with self.tx() as c:
            c.executemany(
                "INSERT INTO chapters (novel_id, idx, title, source_text, source_hash, word_count)"
                " VALUES (?,?,?,?,?,?)",
                [(novel_id, start + 1 + i, t, txt, h, len(txt.split())) for i, (t, txt, h) in enumerate(new)],
            )
            c.execute("UPDATE novels SET updated_at=? WHERE id=?", (now(), novel_id))
        return len(new)

    def list_novels(self) -> list[dict]:
        return self.q(
            """SELECT n.*,
                 (SELECT COUNT(*) FROM chapters c WHERE c.novel_id=n.id) AS chapter_count,
                 (SELECT COUNT(*) FROM chapters c WHERE c.novel_id=n.id AND c.status='done') AS done_count,
                 p.chapter_id AS last_chapter_id
               FROM novels n LEFT JOIN progress p ON p.novel_id=n.id
               ORDER BY COALESCE(p.updated_at, n.updated_at) DESC"""
        )

    def get_novel(self, novel_id: int) -> dict | None:
        rows = [n for n in self.list_novels() if n["id"] == novel_id]
        return rows[0] if rows else None

    def update_novel(self, novel_id: int, **fields: Any) -> None:
        allowed = {"title", "author", "description", "language", "cover_path", "pov_character_id"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return
        cols = ", ".join(f"{k}=?" for k in sets)
        self.x(f"UPDATE novels SET {cols}, updated_at=? WHERE id=?", (*sets.values(), now(), novel_id))

    def delete_novel(self, novel_id: int) -> bool:
        return self.x("DELETE FROM novels WHERE id=?", (novel_id,)) > 0

    # ── chapters ──────────────────────────────────────────────────────────
    def list_chapters(self, novel_id: int) -> list[dict]:
        return self.q(f"SELECT {CHAPTER_LIST_COLS} FROM chapters WHERE novel_id=? ORDER BY idx", (novel_id,))

    def get_chapter(self, chapter_id: int) -> dict | None:
        row = self.one("SELECT * FROM chapters WHERE id=?", (chapter_id,))
        if row and row.get("labels_json"):
            row["labels"] = json.loads(row["labels_json"])
        return row

    def chapter_at(self, novel_id: int, idx: int) -> dict | None:
        return self.one("SELECT id FROM chapters WHERE novel_id=? AND idx=?", (novel_id, idx))

    def neighbors(self, novel_id: int, idx: int) -> tuple[int | None, int | None]:
        prev = self.one("SELECT id FROM chapters WHERE novel_id=? AND idx<? ORDER BY idx DESC LIMIT 1", (novel_id, idx))
        nxt = self.one("SELECT id FROM chapters WHERE novel_id=? AND idx>? ORDER BY idx LIMIT 1", (novel_id, idx))
        return (prev or {}).get("id"), (nxt or {}).get("id")

    def save_labels(self, chapter_id: int, labels: dict[int, tuple[str, str | None]], *, method: str,
                    model: str | None, summary: str | None) -> None:
        payload = json.dumps({str(k): [t, s] for k, (t, s) in labels.items()}, ensure_ascii=False)
        self.x(
            "UPDATE chapters SET status='done', labels_json=?, method=?, model=?, summary=?, error=NULL,"
            " transformed_at=? WHERE id=?",
            (payload, method, model, summary, now(), chapter_id),
        )

    def mark_failed(self, chapter_id: int, error: str) -> None:
        self.x("UPDATE chapters SET status='failed', error=? WHERE id=?", (error[:1000], chapter_id))

    def recent_summaries(self, novel_id: int, before_idx: int, n: int) -> list[str]:
        rows = self.q(
            "SELECT title, summary FROM chapters WHERE novel_id=? AND idx<? AND summary IS NOT NULL"
            " ORDER BY idx DESC LIMIT ?",
            (novel_id, before_idx, n),
        )
        return [f"{r['title']}: {r['summary']}" for r in reversed(rows)]

    def search(self, novel_id: int, query: str, limit: int = 50) -> list[dict]:
        rows = self.q(
            "SELECT id, idx, title, source_text FROM chapters WHERE novel_id=? AND"
            " (title LIKE ? OR source_text LIKE ?) ORDER BY idx LIMIT ?",
            (novel_id, f"%{query}%", f"%{query}%", limit),
        )
        out = []
        ql = query.lower()
        for r in rows:
            text = r.pop("source_text")
            pos = text.lower().find(ql)
            r["snippet"] = text[max(0, pos - 80) : pos + 120].replace("\n", " ") if pos >= 0 else ""
            out.append(r)
        return out

    # ── overrides ─────────────────────────────────────────────────────────
    def get_overrides(self, chapter_id: int) -> dict[int, tuple[str, str | None]]:
        rows = self.q("SELECT seg, type, speaker FROM overrides WHERE chapter_id=?", (chapter_id,))
        return {r["seg"]: (r["type"], r["speaker"]) for r in rows}

    def set_overrides(self, chapter_id: int, segs: list[int], type_: str, speaker: str | None,
                      originals: dict[int, tuple[str, str | None]]) -> None:
        ts = now()
        with self.tx() as c:
            for s in segs:
                ot, osp = originals.get(s, ("narration", None))
                c.execute(
                    "INSERT INTO overrides (chapter_id, seg, type, speaker, original_type, original_speaker, created_at)"
                    " VALUES (?,?,?,?,?,?,?) ON CONFLICT(chapter_id, seg) DO UPDATE SET"
                    " type=excluded.type, speaker=excluded.speaker, created_at=excluded.created_at",
                    (chapter_id, s, type_, speaker, ot, osp, ts),
                )

    def clear_overrides(self, chapter_id: int, segs: list[int] | None = None) -> None:
        if segs is None:
            self.x("DELETE FROM overrides WHERE chapter_id=?", (chapter_id,))
        else:
            with self.tx() as c:
                c.executemany("DELETE FROM overrides WHERE chapter_id=? AND seg=?", [(chapter_id, s) for s in segs])

    def all_overrides(self, novel_id: int) -> list[dict]:
        return self.q(
            "SELECT o.*, c.idx AS chapter_idx, c.title AS chapter_title FROM overrides o"
            " JOIN chapters c ON c.id=o.chapter_id WHERE c.novel_id=? ORDER BY c.idx, o.seg",
            (novel_id,),
        )

    # ── progress ──────────────────────────────────────────────────────────
    def set_progress(self, novel_id: int, chapter_id: int, position: float) -> None:
        self.x(
            "INSERT INTO progress (novel_id, chapter_id, position, updated_at) VALUES (?,?,?,?)"
            " ON CONFLICT(novel_id) DO UPDATE SET chapter_id=excluded.chapter_id,"
            " position=excluded.position, updated_at=excluded.updated_at",
            (novel_id, chapter_id, position, now()),
        )

    def get_progress(self, novel_id: int) -> dict | None:
        return self.one("SELECT * FROM progress WHERE novel_id=?", (novel_id,))
