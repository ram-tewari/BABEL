import json

import pytest
from fastapi.testclient import TestClient

from babel.api.app import create_app
from babel.config import Settings
from babel.llm.providers import Router
from babel.pipeline.jobs import run_job
from babel.transform.engine import Engine
from tests.conftest import FIXTURES, SAMPLE_SPEAKERS, FakeLLM, make_router
from tests.test_ingest import make_epub


@pytest.fixture
def client(tmp_path, store):
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings, store=store, router=Router([]), start_worker=False)
    with TestClient(app) as c:
        c.store = store
        yield c


def _import_sample(client) -> int:
    with open(FIXTURES / "sample_chapter.txt", "rb") as f:
        r = client.post("/api/novels/import", files={"file": ("lanterns.txt", f, "text/plain")})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _run_jobs(client, router=None):
    engine = Engine(router)
    for j in client.store.q("SELECT id FROM jobs WHERE status='queued'"):
        run_job(client.store, engine, j["id"])


def test_import_list_and_preview(client):
    nid = _import_sample(client)
    novels = client.get("/api/novels").json()
    assert novels[0]["title"] == "lanterns" and novels[0]["chapter_count"] == 1
    chapters = client.get(f"/api/novels/{nid}/chapters").json()
    view = client.get(f"/api/chapters/{chapters[0]['id']}").json()
    assert view["method"] == "preview" and view["status"] == "pending"  # heuristic preview before transform
    assert any(b["type"] == "dialogue" for b in view["blocks"])


def test_transform_job_then_read(client):
    nid = _import_sample(client)
    r = client.post(f"/api/novels/{nid}/jobs", json={"mode": "auto"})
    assert r.status_code == 201
    _run_jobs(client, make_router(FakeLLM(SAMPLE_SPEAKERS)))
    novel = client.get(f"/api/novels/{nid}").json()
    assert novel["done_count"] == 1 and novel["job"]["status"] == "done"
    cid = client.get(f"/api/novels/{nid}/chapters").json()[0]["id"]
    view = client.get(f"/api/chapters/{cid}").json()
    assert view["method"] == "llm"
    names = {c["name"]: c for c in view["characters"]}
    assert set(names) == {"Mira Vell", "Tobin"}
    assert names["Mira Vell"]["side"] == "right" and names["Mira Vell"]["is_pov"]  # auto POV = top speaker
    cast = client.get(f"/api/novels/{nid}/characters").json()
    assert cast[0]["name"] == "Mira Vell" and "Mira" in cast[0]["aliases"]


def test_edit_override_survives_and_exports(client):
    nid = _import_sample(client)
    client.post(f"/api/novels/{nid}/jobs", json={})
    _run_jobs(client)
    cid = client.get(f"/api/novels/{nid}/chapters").json()[0]["id"]
    view = client.get(f"/api/chapters/{cid}").json()
    target = next(b for b in view["blocks"] if b["text"] == "Then we wait.")
    r = client.post(f"/api/chapters/{cid}/edit", json={"segs": target["seg"], "type": "dialogue", "speaker": "Old Harrow"})
    edited = next(b for b in r.json()["blocks"] if b["seg"] == target["seg"])
    assert edited["edited"] and edited["speaker"] == "Old Harrow" and edited["character_id"]
    # re-transform keeps the correction
    client.post(f"/api/chapters/{cid}/transform", json={"mode": "heuristic"})
    _run_jobs(client)
    again = next(b for b in client.get(f"/api/chapters/{cid}").json()["blocks"] if b["seg"] == target["seg"])
    assert again["speaker"] == "Old Harrow"
    lines = client.get(f"/api/novels/{nid}/export/corrections").text.strip().splitlines()
    rec = json.loads(lines[0])
    assert rec["after"]["speaker"] == "Old Harrow" and rec["text"] == '"Then we wait."'
    client.post(f"/api/chapters/{cid}/edit/clear", json={})
    assert not any(b["edited"] for b in client.get(f"/api/chapters/{cid}").json()["blocks"])


def test_character_rename_merge_alias(client):
    nid = _import_sample(client)
    client.post(f"/api/novels/{nid}/jobs", json={})
    _run_jobs(client)
    cast = {c["name"]: c for c in client.get(f"/api/novels/{nid}/characters").json()}
    tobin, mira = cast["Tobin"], cast["Mira"]
    assert client.patch(f"/api/characters/{tobin['id']}", json={"name": "Tobin Ash", "color": "#ff0000", "side": "right"}).is_success
    cid = client.get(f"/api/novels/{nid}/chapters").json()[0]["id"]
    chars = {c["name"]: c for c in client.get(f"/api/chapters/{cid}").json()["characters"]}
    assert chars["Tobin Ash"]["color"] == "#ff0000" and chars["Tobin Ash"]["side"] == "right"
    assert client.post(f"/api/characters/{mira['id']}/aliases", json={"alias": "The Lamplighter"}).is_success
    assert client.post(f"/api/characters/{tobin['id']}/merge", json={"into": mira["id"]}).is_success
    names = {c["name"] for c in client.get(f"/api/chapters/{cid}").json()["characters"]}
    assert names == {"Mira"}
    assert client.delete(f"/api/characters/{mira['id']}/aliases/Mira").status_code == 400


def test_jobs_actions_progress_search_and_exports(client, tmp_path):
    epub_path = tmp_path / "t.epub"
    make_epub(epub_path)
    with open(epub_path, "rb") as f:
        r = client.post("/api/novels/import", files={"file": ("t.epub", f, "application/epub+zip")})
    nid = r.json()["id"]
    assert client.get(f"/api/novels/{nid}/cover").status_code == 200
    job = client.post(f"/api/novels/{nid}/jobs", json={"first": 0, "last": 1}).json()
    assert client.post(f"/api/jobs/{job['id']}/pause").json()["status"] == "paused"
    assert client.post(f"/api/jobs/{job['id']}/pause").status_code == 409
    assert client.post(f"/api/jobs/{job['id']}/resume").json()["status"] == "queued"
    _run_jobs(client)
    chapters = client.get(f"/api/novels/{nid}/chapters").json()
    assert [c["status"] for c in chapters] == ["done", "done", "pending"]
    assert client.put(f"/api/novels/{nid}/progress", json={"chapter_id": chapters[1]["id"], "position": 0.5}).is_success
    assert client.get("/api/novels").json()[0]["last_chapter_id"] == chapters[1]["id"]
    hits = client.get(f"/api/novels/{nid}/search", params={"q": "Third"}).json()
    assert hits and hits[0]["idx"] == 2 and "Third" in hits[0]["snippet"]
    ep = client.get(f"/api/novels/{nid}/export/epub")
    assert ep.status_code == 200 and ep.content[:2] == b"PK"
    html = client.get(f"/api/novels/{nid}/export/html", params={"last": 0}).text
    assert "Where am I?" in html and 'class="line' in html
    assert client.delete(f"/api/novels/{nid}").status_code == 204
    assert client.get(f"/api/novels/{nid}").status_code == 404


def test_append_new_chapters(client, tmp_path):
    nid = _import_sample(client)
    extra = tmp_path / "more.txt"
    extra.write_text((FIXTURES / "sample_chapter.txt").read_text() + "\n\nChapter 2: Dawn\n\nThe sun rose.")
    with open(extra, "rb") as f:
        r = client.post(f"/api/novels/{nid}/append", files={"file": ("more.txt", f, "text/plain")})
    assert r.json()["added"] >= 1
    titles = [c["title"] for c in client.get(f"/api/novels/{nid}/chapters").json()]
    assert titles[-1] == "Chapter 2: Dawn"


def test_bad_upload_and_404s(client, tmp_path):
    r = client.post("/api/novels/import", files={"file": ("x.pdf", b"%PDF", "application/pdf")})
    assert r.status_code == 400
    assert client.get("/api/chapters/999").status_code == 404
    assert client.get("/api/status").json()["llm"] is None
