import pytest

from babel.library import chapter_view
from babel.memory.codex import Codex
from babel.models import CharacterHint
from babel.pipeline.jobs import create_job, run_job
from babel.transform.engine import Engine, TransformFailed
from tests.conftest import SAMPLE_SPEAKERS, FakeLLM, make_router


def _novel(store, sample_text, n=1):
    body = sample_text.split("\n", 1)[1]
    return store.create_novel("Lanterns", [(f"Chapter {i + 1}", body, f"h{i}") for i in range(n)])


def test_llm_labels_and_codex_learning(store, sample_text):
    nid = _novel(store, sample_text)
    fake = FakeLLM(SAMPLE_SPEAKERS)
    engine = Engine(make_router(fake))
    codex = Codex(store, nid)
    ch = store.get_chapter(store.chapter_at(nid, 0)["id"])
    out = engine.transform(store, codex, ch)
    assert out.method == "llm" and out.model == "fake:fake-model"
    assert out.summary.startswith("Mira waits")
    # "Mira" and "Mira Vell" are the same character thanks to the reported alias
    assert codex.lookup("Mira") == codex.lookup("Mira Vell")
    assert codex.chars[codex.lookup("Mira")]["name"] == "Mira Vell"
    store.save_labels(ch["id"], out.labels, method=out.method, model=out.model, summary=out.summary)
    view = chapter_view(store, ch["id"])
    names = {c["name"] for c in view["characters"]}
    assert names == {"Mira Vell", "Tobin"}
    assert any(b["type"] == "sfx" for b in view["blocks"])


def test_second_chapter_prompt_carries_memory(store, sample_text):
    nid = _novel(store, sample_text, n=2)
    fake = FakeLLM(SAMPLE_SPEAKERS)
    job = create_job(store, nid)
    run_job(store, Engine(make_router(fake)), job, concurrency=1)
    second = fake.calls[-1]["body"]["messages"][-1]["content"]
    assert "Mira Vell — aka Mira" in second
    assert "STORY SO FAR" in second and "Mira waits" in second


def test_llm_failure_falls_back_to_heuristic(store, sample_text):
    nid = _novel(store, sample_text)
    engine = Engine(make_router(FakeLLM(script=["not json", "still not json"])))
    ch = store.get_chapter(store.chapter_at(nid, 0)["id"])
    out = engine.transform(store, Codex(store, nid), ch)
    assert out.method == "heuristic" and out.warnings
    assert any(sp == "Tobin" for _, sp in out.labels.values())


def test_strict_mode_raises(store, sample_text):
    nid = _novel(store, sample_text)
    engine = Engine(make_router(FakeLLM(script=[500] * 10)))
    ch = store.get_chapter(store.chapter_at(nid, 0)["id"])
    with pytest.raises(TransformFailed):
        engine.transform(store, Codex(store, nid), ch, mode="llm")


def test_codex_resolution_rename_merge(store):
    nid = store.create_novel("N", [("c", "text", "h")])
    cx = Codex(store, nid)
    k = cx.resolve("Klein")
    assert cx.resolve("Klein Moretti") == k  # token-subset match
    assert cx.resolve("he") is None and cx.resolve("?") is None
    assert cx.lookup("Mr. Klein") == k  # title stripped
    cx.learn(CharacterHint(name="Klein Moretti", aliases=["The Fool"], note="lead"))
    assert cx.chars[k]["name"] == "Klein Moretti" and cx.lookup("the fool") == k
    cx.rename(k, "Klein")
    cx.learn(CharacterHint(name="Klein Moretti Jr"))
    assert cx.chars[k]["name"] == "Klein"  # renamed names are locked
    z = cx.resolve("Zhou Mingrui")
    cx.merge(z, k)
    assert cx.lookup("Zhou Mingrui") == k and z not in cx.chars


def test_jobs_skip_done_and_pause_resume(store, sample_text):
    nid = _novel(store, sample_text, n=4)
    engine = Engine(None)  # heuristic
    j = create_job(store, nid, last=1)
    final = run_job(store, engine, j)
    assert final["status"] == "done" and final["done"] == 2
    j2 = create_job(store, nid)
    final = run_job(store, engine, j2)
    assert final["total"] == 4 and final["done"] == 4  # 2 already done + 2 new
    assert store.one("SELECT pov_character_id FROM novels WHERE id=?", (nid,))["pov_character_id"]

    j3 = create_job(store, nid, force=True)
    store.x("UPDATE jobs SET status='paused' WHERE id=?", (j3,))
    # a paused job stops before dispatching anything
    store.x("UPDATE jobs SET status='queued' WHERE id=?", (j3,))
    seen = []

    def pause_after_first(ch, result):
        seen.append(ch["idx"])
        store.x("UPDATE jobs SET status='paused' WHERE id=?", (j3,))

    final = run_job(store, engine, j3, concurrency=1, on_chapter=pause_after_first)
    assert final["status"] == "paused" and seen == [0]
    assert store.one("SELECT first_idx FROM jobs WHERE id=?", (j3,))["first_idx"] == 1


def test_old_database_is_migrated(tmp_path):
    import sqlite3

    from babel.store.db import Store

    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE characters (id INTEGER PRIMARY KEY, novel_id INTEGER, name TEXT, note TEXT,"
                " color TEXT, side TEXT, first_idx INTEGER, lines INTEGER DEFAULT 0, created_at TEXT)")
    con.commit()
    con.close()
    s = Store(db)
    cols = {r["name"] for r in s.q("PRAGMA table_info(characters)")}
    assert {"name_locked", "auto_slot"} <= cols


def test_top_characters_get_distinct_colors(store, sample_text):
    nid = _novel(store, sample_text)
    run_job(store, Engine(None), create_job(store, nid))
    slots = [r["auto_slot"] for r in store.q("SELECT auto_slot FROM characters WHERE novel_id=? AND lines>0", (nid,))]
    assert len(slots) >= 2 and len(set(slots)) == len(slots)
