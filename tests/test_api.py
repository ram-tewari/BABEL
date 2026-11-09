import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from babel.api.app import create_app
from babel.config import Settings
from babel.pipeline.jobs import run_job
from babel.scenario.cascade import Cascade
from tests.conftest import FIXTURES, SAMPLE_ORACLE, FakeLLM, make_local
from tests.test_ingest import make_epub


def png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (300, 300), (40, 90, 160)).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def client(tmp_path, store):
    fake = FakeLLM(oracle=SAMPLE_ORACLE, people={"Mira Vell": "f", "Tobin": "m"}, aliases={"Mira": "Mira Vell"})
    cascade = Cascade(local=make_local(fake))
    app = create_app(Settings(data_dir=tmp_path), store=store, cascade=cascade, start_worker=False)
    with TestClient(app) as c:
        c.store, c.cascade, c.fake = store, cascade, fake
        yield c


def _import(client, name="lanterns.txt", path=FIXTURES / "sample_chapter.txt") -> int:
    with open(path, "rb") as f:
        r = client.post("/api/novels/import", files={"file": (name, f, "application/octet-stream")})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _run(client):
    for j in client.store.q("SELECT id FROM jobs WHERE status='queued'"):
        run_job(client.store, client.cascade, j["id"])


def _first_chapter(client, nid) -> int:
    return client.get(f"/api/novels/{nid}/chapters").json()[0]["id"]


def test_status_reports_tiers(client):
    s = client.get("/api/status").json()
    assert s["tiers"]["local"] == "ollama:fake-local" and s["tiers"]["cloud"] == []


def test_preview_then_transform_then_read(client):
    nid = _import(client)
    cid = _first_chapter(client, nid)
    pre = client.get(f"/api/chapters/{cid}").json()
    assert pre["method"] == "preview" and any(b["type"] == "dialogue" for b in pre["blocks"])
    assert client.post(f"/api/novels/{nid}/jobs", json={"tiers": "auto"}).status_code == 201
    _run(client)
    view = client.get(f"/api/chapters/{cid}").json()
    assert view["method"] == "cascade" and view["summary"]
    names = {c["name"]: c for c in view["characters"]}
    assert {"Mira Vell", "Tobin"} <= set(names)
    assert names["Mira Vell"]["is_pov"] and names["Mira Vell"]["side"] == "right"
    late = next(b for b in view["blocks"] if b["text"] == "You're late,")
    assert late["speaker"] == "Tobin" and late["tier"] in ("rule", "memory", "local") and late["why"]
    novel = client.get(f"/api/novels/{nid}").json()
    assert novel["done_count"] == 1 and novel["tier_counts"] and novel["usage"][0]["tier"] == "local"


def test_corrections_accept_review_and_export(client):
    nid = _import(client)
    client.post(f"/api/novels/{nid}/jobs", json={"tiers": "rules"})
    _run(client)
    cid = _first_chapter(client, nid)
    blocks = client.get(f"/api/chapters/{cid}").json()["blocks"]
    target = next(b for b in blocks if b["text"] == "Then we wait.")
    r = client.post(f"/api/chapters/{cid}/edit", json={"segs": target["seg"], "type": "dialogue",
                                                       "speaker": "Old Harrow", "tone": "whisper"})
    edited = next(b for b in r.json()["blocks"] if b["seg"] == target["seg"])
    assert edited["edited"] and edited["speaker"] == "Old Harrow" and edited["tier"] == "user" and edited["tone"] == "whisper"
    # a re-transform keeps the correction
    client.post(f"/api/chapters/{cid}/transform", json={"tiers": "rules"})
    _run(client)
    again = next(b for b in client.get(f"/api/chapters/{cid}").json()["blocks"] if b["seg"] == target["seg"])
    assert again["speaker"] == "Old Harrow"
    # accept a line as-is
    other = next(b for b in blocks if b["text"] == "See what?")
    client.post(f"/api/chapters/{cid}/accept", json={"segs": other["seg"]})
    corr = client.get(f"/api/novels/{nid}/corrections").json()
    assert {c["after"]["speaker"] for c in corr} == {"Old Harrow", "Tobin"}
    assert any(c["confirmed"] for c in corr) and any(not c["confirmed"] for c in corr)
    lines = client.get(f"/api/novels/{nid}/export/corrections").text.strip().splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["text"]
    assert isinstance(client.get(f"/api/novels/{nid}/review").json(), list)
    client.post(f"/api/chapters/{cid}/edit/clear", json={})
    assert not any(b["edited"] for b in client.get(f"/api/chapters/{cid}").json()["blocks"])
    assert client.post(f"/api/chapters/{cid}/edit", json={"segs": [9999], "type": "dialogue"}).status_code == 422


def test_entities_glossary_portrait_graph(client):
    nid = _import(client)
    client.post(f"/api/novels/{nid}/jobs", json={})
    _run(client)
    chars = {c["name"]: c for c in client.get(f"/api/novels/{nid}/entities", params={"kind": "character"}).json()}
    tobin, mira = chars["Tobin"], chars["Mira Vell"]
    r = client.patch(f"/api/entities/{tobin['id']}", json={"name": "Tobin Ash", "color": "#ff0000", "side": "right", "gender": "m"})
    assert r.json()["name"] == "Tobin Ash" and "name" in r.json()["locked"]
    assert client.patch(f"/api/entities/{tobin['id']}", json={"side": "up"}).status_code == 422
    assert client.post(f"/api/entities/{mira['id']}/portrait", files={"file": ("p.png", png(), "image/png")}).status_code == 200
    assert client.get(f"/api/entities/{mira['id']}/portrait").headers["content-type"] == "image/jpeg"
    loc = client.post(f"/api/novels/{nid}/entities", json={"name": "Lantern Market", "kind": "location", "note": "night bazaar"})
    assert loc.status_code == 201
    assert client.post(f"/api/novels/{nid}/entities", json={"name": "Lantern Market", "kind": "location"}).status_code == 409
    cid = _first_chapter(client, nid)
    assert any(g["name"] == "Lantern Market" for g in client.get(f"/api/chapters/{cid}").json()["glossary"])
    yaml_text = client.get(f"/api/novels/{nid}/glossary.yaml").text
    assert "Tobin Ash:" in yaml_text and "Lantern Market" in yaml_text
    r = client.post(f"/api/novels/{nid}/glossary", content="characters:\n  Old Harrow: {gender: m, description: ferryman}\n",
                    headers={"content-type": "text/plain"})
    assert r.json()["created"] == 1
    assert client.post(f"/api/novels/{nid}/glossary", content="nonsense: [", headers={"content-type": "text/plain"}).status_code == 422
    graph = client.get(f"/api/novels/{nid}/graph", params={"min_weight": 1}).json()
    assert {n["name"] for n in graph["nodes"]} >= {"Tobin Ash", "Mira Vell"} and graph["edges"][0]["weight"] >= 1
    assert client.post(f"/api/entities/{tobin['id']}/merge", json={"into": mira["id"]}).status_code == 200
    names = {c["name"] for c in client.get(f"/api/chapters/{cid}").json()["characters"]}
    assert "Tobin Ash" not in names
    assert client.delete(f"/api/entities/{mira['id']}/aliases/Mira Vell").status_code == 400


def test_epub_library_flow_exports_and_reading(client, tmp_path):
    p = tmp_path / "t.epub"
    make_epub(p)
    nid = _import(client, "t.epub", p)
    assert client.get(f"/api/novels/{nid}/cover").status_code == 200
    est = client.get(f"/api/novels/{nid}/estimate").json()
    assert est["chapters"] == 3 and "local" in est["per_tier"]
    job = client.post(f"/api/novels/{nid}/jobs", json={"first": 0, "last": 1, "tiers": "rules"}).json()
    assert client.post(f"/api/jobs/{job['id']}/pause").json()["status"] == "paused"
    assert client.post(f"/api/jobs/{job['id']}/pause").status_code == 409
    assert client.post(f"/api/jobs/{job['id']}/resume").json()["status"] == "queued"
    _run(client)
    rows = client.get(f"/api/novels/{nid}/chapters").json()
    assert [c["status"] for c in rows] == ["done", "done", "pending"]
    client.put(f"/api/novels/{nid}/progress", json={"chapter_id": rows[1]["id"], "position": 0.95})
    rows = client.get(f"/api/novels/{nid}/chapters").json()
    assert rows[1]["is_read"] and not rows[0]["is_read"]
    assert client.get("/api/novels").json()[0]["last_chapter_id"] == rows[1]["id"]
    assert client.get(f"/api/novels/{nid}/search", params={"q": "Third"}).json()[0]["idx"] == 2
    assert client.get(f"/api/novels/{nid}/export/epub").content[:2] == b"PK"
    assert 'class="line' in client.get(f"/api/novels/{nid}/export/html", params={"last": 0}).text
    js = client.get(f"/api/novels/{nid}/export/json").json()
    assert js["format"] == "babel-visual-scenario" and js["chapters"][0]["blocks"][0]["type"]
    assert client.post(f"/api/novels/{nid}/cover", files={"file": ("c.png", png(), "image/png")}).status_code == 200
    assert client.patch(f"/api/novels/{nid}", json={"tags": ["mystery"], "status": "ongoing"}).json()["tags"] == ["mystery"]
    assert client.delete(f"/api/novels/{nid}").status_code == 204
    assert client.get(f"/api/novels/{nid}").status_code == 404


def test_append_and_custom_chapter_pattern(client, tmp_path):
    txt = tmp_path / "odd.txt"
    txt.write_text("=== Part One ===\n\nFirst body here.\n\n=== Part Two ===\n\nSecond body.")
    with open(txt, "rb") as f:
        r = client.post("/api/novels/import", files={"file": ("odd.txt", f, "text/plain")},
                        data={"chapter_pattern": r"^=== .* ===$"})
    nid = r.json()["id"]
    assert [c["title"] for c in client.get(f"/api/novels/{nid}/chapters").json()] == ["=== Part One ===", "=== Part Two ==="]
    more = tmp_path / "more.txt"
    more.write_text("Chapter 1: A\n\nAlpha.\n\nChapter 2: B\n\nBeta.")
    with open(more, "rb") as f:
        assert client.post(f"/api/novels/{nid}/append", files={"file": ("more.txt", f, "text/plain")}).json()["added"] == 2


def test_errors(client):
    assert client.post("/api/novels/import", files={"file": ("x.pdf", b"%PDF", "application/pdf")}).status_code == 400
    assert client.get("/api/chapters/999").status_code == 404
    assert client.patch("/api/entities/999", json={}).status_code == 404
    nid = _import(client)
    assert client.post(f"/api/novels/{nid}/jobs", json={"tiers": "magic"}).status_code == 422
