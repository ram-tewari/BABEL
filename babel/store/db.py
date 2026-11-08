"""SQLite storage for the whole library (one file).

A chapter stores its source text and a *decision document* — one Decision per
segment (type, speaker, tone, confidence, tier, candidates) — never rendered
output. User corrections live in a separate override layer so they survive
re-transforms; speakers are resolved through the alias table at read time so a
rename or merge applies to every chapter instantly.
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

SCHEMA_VERSION = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS novels (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  author TEXT,
  description TEXT,
  language TEXT,
  status TEXT,                                 -- ongoing | completed | hiatus (from metadata)
  tags TEXT,                                   -- JSON list
  source_name TEXT,
  source_url TEXT,                             -- where metadata came from
  cover_path TEXT,
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
  doc_json TEXT,                               -- {"decisions": {seg: compact}, "stats": {...}}
  summary TEXT,
  review_count INTEGER NOT NULL DEFAULT 0,     -- decisions still below the review threshold
  tiers TEXT,                                  -- JSON {tier: count}
  error TEXT,
  transformed_at TEXT,
  UNIQUE (novel_id, idx)
);
CREATE INDEX IF NOT EXISTS idx_chapters_novel ON chapters(novel_id, idx);
CREATE TABLE IF NOT EXISTS entities (
  id INTEGER PRIMARY KEY,
  novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  kind TEXT NOT NULL DEFAULT 'character',      -- character | location | faction | term
  name TEXT NOT NULL,
  gender TEXT,                                 -- m | f | n
  note TEXT,
  faction_id INTEGER,
  color TEXT,
  side TEXT,
  portrait_path TEXT,
  first_idx INTEGER,
  lines INTEGER NOT NULL DEFAULT 0,
  mentions INTEGER NOT NULL DEFAULT 0,
  auto_slot INTEGER,
  locked TEXT,                                 -- JSON list of user-edited fields
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entities_novel ON entities(novel_id, kind);
CREATE TABLE IF NOT EXISTS aliases (
  novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  norm TEXT NOT NULL,
  alias TEXT NOT NULL,
  entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  PRIMARY KEY (novel_id, norm)
);
CREATE INDEX IF NOT EXISTS idx_aliases_entity ON aliases(entity_id);
CREATE TABLE IF NOT EXISTS overrides (
  chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
  seg INTEGER NOT NULL,
  decision TEXT NOT NULL,                      -- compact Decision (tier=user)
  original TEXT,                               -- what the pipeline had decided
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
  tiers TEXT NOT NULL DEFAULT 'auto',          -- auto | rules | local | cloud
  total INTEGER NOT NULL DEFAULT 0,
  done INTEGER NOT NULL DEFAULT 0,
  failed INTEGER NOT NULL DEFAULT 0,
  message TEXT,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT
);
CREATE TABLE IF NOT EXISTS usage (
  id INTEGER PRIMARY KEY,
  novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  chapter_id INTEGER,
  tier TEXT NOT NULL,                          -- local | cloud
  purpose TEXT NOT NULL,                       -- decide | entities | summary
  provider TEXT NOT NULL,
  model TEXT,
  prompt_tokens INTEGER NOT NULL DEFAULT 0,
  completion_tokens INTEGER NOT NULL DEFAULT 0,
  questions INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_novel ON usage(novel_id, tier);
CREATE TABLE IF NOT EXISTS progress (
  novel_id INTEGER PRIMARY KEY REFERENCES novels(id) ON DELETE CASCADE,
  chapter_id INTEGER,
  position REAL NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reads (
  novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
  read_at TEXT NOT NULL,
  PRIMARY KEY (novel_id, chapter_id)
);
"""

CHAPTER_LIST_COLS = "id, novel_id, idx, title, word_count, status, review_count, tiers, error, transformed_at"


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def norm_name(name: str) -> str:
    return " ".join(name.lower().replace("’", "'").split())


class Store:
    # Columns added after a table first shipped: (table, column, definition).
    _ADDED_COLUMNS: list[tuple[str, str, str]] = []

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
            has = lambda t: self._conn.execute(  # noqa: E731
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (t,)).fetchone()
            if has("chapters") and not has("meta"):
                raise RuntimeError(
                    f"{path} was created by an older BABEL version. Move it aside and re-import your books.")
            self._conn.executescript(SCHEMA)
            for table, column, ddl in self._ADDED_COLUMNS:
                cols = {r[1] for r in self._conn.execute(f"PRAGMA table_info({table})")}
                if column not in cols:
                    self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
            self._conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('schema', ?)", (str(SCHEMA_VERSION),))

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
        """Create a novel with chapters given as (title, text, sha256) tuples — atomically."""
        ts = now()
        with self.tx() as c:
            nid = c.execute(
                "INSERT INTO novels (title, author, description, language, source_name, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (title, meta.get("author"), meta.get("description"), meta.get("language"),
                 meta.get("source_name"), ts, ts),
            ).lastrowid
            c.executemany(
                "INSERT INTO chapters (novel_id, idx, title, source_text, source_hash, word_count) VALUES (?,?,?,?,?,?)",
                [(nid, i, t, txt, h, len(txt.split())) for i, (t, txt, h) in enumerate(chapters)],
            )
        return nid

    def append_chapters(self, novel_id: int, chapters: list[tuple[str, str, str]]) -> int:
        existing = {r["source_hash"] for r in self.q("SELECT source_hash FROM chapters WHERE novel_id=?", (novel_id,))}
        top = (self.one("SELECT MAX(idx) m FROM chapters WHERE novel_id=?", (novel_id,)) or {}).get("m")
        start = -1 if top is None else top
        new = [c for c in chapters if c[2] not in existing]
        with self.tx() as c:
            c.executemany(
                "INSERT INTO chapters (novel_id, idx, title, source_text, source_hash, word_count) VALUES (?,?,?,?,?,?)",
                [(novel_id, start + 1 + i, t, txt, h, len(txt.split())) for i, (t, txt, h) in enumerate(new)],
            )
            c.execute("UPDATE novels SET updated_at=? WHERE id=?", (now(), novel_id))
        return len(new)

    def list_novels(self, novel_id: int | None = None) -> list[dict]:
        where = "WHERE n.id=?" if novel_id is not None else ""
        rows = self.q(
            f"""SELECT n.*,
                 (SELECT COUNT(*) FROM chapters c WHERE c.novel_id=n.id) AS chapter_count,
                 (SELECT COUNT(*) FROM chapters c WHERE c.novel_id=n.id AND c.status='done') AS done_count,
                 (SELECT COUNT(*) FROM reads r WHERE r.novel_id=n.id) AS read_count,
                 p.chapter_id AS last_chapter_id
               FROM novels n LEFT JOIN progress p ON p.novel_id=n.id {where}
               ORDER BY COALESCE(p.updated_at, n.updated_at) DESC""",
            () if novel_id is None else (novel_id,),
        )
        for r in rows:
            r["tags"] = json.loads(r["tags"]) if r.get("tags") else []
        return rows

    def get_novel(self, novel_id: int) -> dict | None:
        rows = self.list_novels(novel_id)
        return rows[0] if rows else None

    def update_novel(self, novel_id: int, **fields: Any) -> None:
        allowed = {"title", "author", "description", "language", "cover_path", "pov_character_id", "status",
                   "tags", "source_url"}
        sets = {k: (json.dumps(v) if k == "tags" and v is not None else v) for k, v in fields.items() if k in allowed}
        if sets:
            cols = ", ".join(f"{k}=?" for k in sets)
            self.x(f"UPDATE novels SET {cols}, updated_at=? WHERE id=?", (*sets.values(), now(), novel_id))

    def delete_novel(self, novel_id: int) -> bool:
        return self.x("DELETE FROM novels WHERE id=?", (novel_id,)) > 0

    # ── chapters ──────────────────────────────────────────────────────────
    def list_chapters(self, novel_id: int) -> list[dict]:
        rows = self.q(
            f"SELECT {CHAPTER_LIST_COLS}, EXISTS(SELECT 1 FROM reads r WHERE r.chapter_id=chapters.id) AS is_read"
            " FROM chapters WHERE novel_id=? ORDER BY idx", (novel_id,))
        for r in rows:
            r["tiers"] = json.loads(r["tiers"]) if r.get("tiers") else {}
            r["is_read"] = bool(r["is_read"])
        return rows

    def get_chapter(self, chapter_id: int) -> dict | None:
        row = self.one("SELECT * FROM chapters WHERE id=?", (chapter_id,))
        if row:
            row["doc"] = json.loads(row["doc_json"]) if row.get("doc_json") else None
            row["tiers"] = json.loads(row["tiers"]) if row.get("tiers") else {}
        return row

    def chapter_at(self, novel_id: int, idx: int) -> dict | None:
        return self.one("SELECT id FROM chapters WHERE novel_id=? AND idx=?", (novel_id, idx))

    def neighbors(self, novel_id: int, idx: int) -> tuple[int | None, int | None]:
        prev = self.one("SELECT id FROM chapters WHERE novel_id=? AND idx<? ORDER BY idx DESC LIMIT 1", (novel_id, idx))
        nxt = self.one("SELECT id FROM chapters WHERE novel_id=? AND idx>? ORDER BY idx LIMIT 1", (novel_id, idx))
        return (prev or {}).get("id"), (nxt or {}).get("id")

    def save_doc(self, chapter_id: int, decisions: dict[int, list], *, summary: str | None,
                 review_count: int, tiers: dict[str, int], stats: dict | None = None) -> None:
        doc = {"decisions": {str(k): v for k, v in decisions.items()}, "stats": stats or {}}
        self.x(
            "UPDATE chapters SET status='done', doc_json=?, summary=?, review_count=?, tiers=?, error=NULL,"
            " transformed_at=? WHERE id=?",
            (json.dumps(doc, ensure_ascii=False), summary, review_count, json.dumps(tiers), now(), chapter_id),
        )

    def mark_failed(self, chapter_id: int, error: str) -> None:
        self.x("UPDATE chapters SET status='failed', error=? WHERE id=?", (error[:1000], chapter_id))

    def recent_summaries(self, novel_id: int, before_idx: int, n: int) -> list[str]:
        rows = self.q("SELECT title, summary FROM chapters WHERE novel_id=? AND idx<? AND summary IS NOT NULL"
                      " ORDER BY idx DESC LIMIT ?", (novel_id, before_idx, n))
        return [f"{r['title']}: {r['summary']}" for r in reversed(rows)]

    def search(self, novel_id: int, query: str, limit: int = 50) -> list[dict]:
        rows = self.q("SELECT id, idx, title, source_text FROM chapters WHERE novel_id=? AND"
                      " (title LIKE ? OR source_text LIKE ?) ORDER BY idx LIMIT ?",
                      (novel_id, f"%{query}%", f"%{query}%", limit))
        ql = query.lower()
        for r in rows:
            text = r.pop("source_text")
            pos = text.lower().find(ql)
            r["snippet"] = text[max(0, pos - 80): pos + 120].replace("\n", " ") if pos >= 0 else ""
        return rows

    # ── overrides (user corrections) ──────────────────────────────────────
    def get_overrides(self, chapter_id: int) -> dict[int, list]:
        return {r["seg"]: json.loads(r["decision"]) for r in
                self.q("SELECT seg, decision FROM overrides WHERE chapter_id=?", (chapter_id,))}

    def set_overrides(self, chapter_id: int, rows: dict[int, tuple[list, list | None]]) -> None:
        """rows: seg -> (new compact decision, original compact decision)."""
        ts = now()
        with self.tx() as c:
            for seg, (dec, orig) in rows.items():
                c.execute(
                    "INSERT INTO overrides (chapter_id, seg, decision, original, created_at) VALUES (?,?,?,?,?)"
                    " ON CONFLICT(chapter_id, seg) DO UPDATE SET decision=excluded.decision, created_at=excluded.created_at",
                    (chapter_id, seg, json.dumps(dec), json.dumps(orig) if orig else None, ts),
                )

    def clear_overrides(self, chapter_id: int, segs: list[int] | None = None) -> None:
        if segs is None:
            self.x("DELETE FROM overrides WHERE chapter_id=?", (chapter_id,))
        else:
            with self.tx() as c:
                c.executemany("DELETE FROM overrides WHERE chapter_id=? AND seg=?", [(chapter_id, s) for s in segs])

    def all_overrides(self, novel_id: int) -> list[dict]:
        rows = self.q("SELECT o.*, c.idx AS chapter_idx, c.title AS chapter_title FROM overrides o"
                      " JOIN chapters c ON c.id=o.chapter_id WHERE c.novel_id=? ORDER BY c.idx, o.seg", (novel_id,))
        for r in rows:
            r["decision"] = json.loads(r["decision"])
            r["original"] = json.loads(r["original"]) if r.get("original") else None
        return rows

    # ── usage / cost ──────────────────────────────────────────────────────
    def log_usage(self, novel_id: int, chapter_id: int | None, tier: str, purpose: str, provider: str,
                  model: str | None, prompt_tokens: int, completion_tokens: int, questions: int) -> None:
        self.x("INSERT INTO usage (novel_id, chapter_id, tier, purpose, provider, model, prompt_tokens,"
               " completion_tokens, questions, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
               (novel_id, chapter_id, tier, purpose, provider, model, prompt_tokens, completion_tokens, questions, now()))

    def usage_summary(self, novel_id: int) -> list[dict]:
        return self.q("SELECT tier, provider, model, SUM(prompt_tokens) prompt_tokens, SUM(completion_tokens)"
                      " completion_tokens, SUM(questions) questions, COUNT(*) calls FROM usage WHERE novel_id=?"
                      " GROUP BY tier, provider, model ORDER BY tier", (novel_id,))

    # ── reading ───────────────────────────────────────────────────────────
    def set_progress(self, novel_id: int, chapter_id: int, position: float) -> None:
        self.x("INSERT INTO progress (novel_id, chapter_id, position, updated_at) VALUES (?,?,?,?)"
               " ON CONFLICT(novel_id) DO UPDATE SET chapter_id=excluded.chapter_id,"
               " position=excluded.position, updated_at=excluded.updated_at",
               (novel_id, chapter_id, position, now()))
        if position >= 0.9:
            self.x("INSERT OR IGNORE INTO reads (novel_id, chapter_id, read_at) VALUES (?,?,?)",
                   (novel_id, chapter_id, now()))

    def get_progress(self, novel_id: int) -> dict | None:
        return self.one("SELECT * FROM progress WHERE novel_id=?", (novel_id,))
