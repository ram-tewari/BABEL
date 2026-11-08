"""Character art: profiles, planning/readiness, the design lifecycle and the scheduler (fake image backend)."""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from babel.api.app import create_app
from babel.art import designs, plan
from babel.art.profile import EMOTIONS, base_prompt, gather_evidence, parse_profile
from babel.art.runner import ArtScheduler, draft_profile
from babel.config import Settings
from babel.memory.akashic import Akashic
from babel.scenario.cascade import Cascade

CHAPTERS = [
    ("Chapter 1", "Klein woke up. In the mirror he saw black hair, brown eyes and a thin build.\n\n"
                  '"Where am I?" Klein asked.'),
    ("Chapter 2", 'Melissa entered. She had reddish black hair, bright brown eyes and a delicate face.\n\n'
                  '"You overslept," Melissa said.'),
    ("Chapter 3", '"Hold on," Dunn said. Dunn wore a black trench coat; his hairline was high and his eyes gray.'),
    ("Chapter 4", '"Fine," Klein said.'),
]


class FakeBackend:
    """Writes a small solid-colour PNG instead of running a diffusion model."""

    def __init__(self):
        self.calls: list[dict] = []
        self.running = False

    def call(self, req: dict) -> dict:
        self.running = True
        self.calls.append(req)
        Image.new("RGB", (req["width"] // 8, req["height"] // 8), (req["seed"] % 255, 90, 120)).save(req["out"])
        return {"ok": True, "secs": 0.01}

    def close(self) -> None:
        self.running = False


class StubLLM:
    def __init__(self):
        self.calls = 0

    def chat(self, messages, *, schema=None, max_tokens=1024):
        self.calls += 1
        if "setting" in json.dumps(schema):
            content = json.dumps({"setting": "Victorian-era city, frock coats and long dresses", "era": "1880s Victorian"})
        else:
            content = json.dumps({
                "age": {"value": "about 20", "guessed": True}, "hair": {"value": "short black hair", "chapter": 1,
                                                                        "quote": "black hair", "guessed": False},
                "eyes": {"value": "brown eyes", "chapter": 1, "quote": "brown eyes", "guessed": False},
                "build": {"value": "thin", "guessed": False}, "face": {"value": "average features", "guessed": True},
                "skin": {"value": "fair", "guessed": True}, "outfit": {"value": "black frock coat", "guessed": True},
                "accessories": {"value": "", "guessed": True}, "marks": {"value": "none", "guessed": True},
                "tags": ["black hair", "brown eyes", "frock coat"]})
        return SimpleNamespace(content=content, provider="ollama", model="stub", prompt_tokens=10, completion_tokens=5)


@pytest.fixture
def novel(store):
    nid = store.create_novel("t", [(t, x, f"h{i}") for i, (t, x) in enumerate(CHAPTERS)])
    ak = Akashic(store, nid)
    ids = {n: ak.create(n, chapter_idx=i, gender=g) for n, i, g in (("Klein", 0, "m"), ("Melissa", 1, "f"),
                                                                     ("Dunn", 2, "m"))}
    chapters = store.q("SELECT id, idx FROM chapters WHERE novel_id=? ORDER BY idx", (nid,))
    cast = {0: {"Klein": 50}, 1: {"Melissa": 16, "Klein": 3}, 2: {"Dunn": 1}, 3: {"Klein": 2}}
    for ch in chapters:
        store.x("UPDATE chapters SET status='done' WHERE id=?", (ch["id"],))
        for name, n in cast[ch["idx"]].items():
            store.x("INSERT INTO chapter_cast (chapter_id, entity_id, lines) VALUES (?,?,?)", (ch["id"], ids[name], n))
    ak.reload()
    return SimpleNamespace(id=nid, ak=ak, ids=ids, store=store)


@pytest.fixture
def scheduler(tmp_path, store):
    backend = FakeBackend()
    sch = ArtScheduler(store, art_dir=tmp_path / "art", portraits_dir=tmp_path / "portraits",
                       backend_factory=lambda: backend, llm_factory=StubLLM)
    sch.fake = backend
    return sch


def drain(sch, limit=50):
    for _ in range(limit):
        if not sch.step():
            return


def test_tiers_order_and_readiness(novel):
    assert plan.tier_of(50, 1) == "main" and plan.tier_of(8, 2) == "supporting" and plan.tier_of(8, 1) == "minor"
    assert plan.tier_of(30, 5, name="Circus fortune-teller") == "minor" and plan.tier_of(30, 5, name="mobile hawkers") == "minor"
    assert plan.tier_of(45, 5, name="Klein Moretti") == "main" and plan.tier_of(30, 1, name="Ince of Zangwill") == "supporting"
    assert plan.tier_of(1, 1) == "minor" and plan.tier_of(0, 0) == "extra" and plan.tier_of(0, 0, "main") == "main"
    chars = plan.characters(novel.store, novel.ak)
    assert [c["name"] for c in chars] == ["Klein", "Melissa", "Dunn"]  # first appearance
    assert [c["name"] for c in plan.queue(novel.store, novel.ak)] == ["Klein", "Melissa"]  # Dunn is minor
    r = plan.readiness(novel.store, novel.ak)
    assert r["ready"] == 1 and r["ready_through"] is None  # only ch3 (minor Dunn) is ready
    assert r["blocked"][0]["missing"] == ["Klein"]


def test_gather_evidence_and_prompt(novel):
    ev = gather_evidence(novel.store, novel.ak, novel.ids["Melissa"])
    assert ev and "reddish black hair" in ev[0]["text"] and ev[0]["chapter"] == 2
    profile = parse_profile(StubLLM().chat([]).content)
    assert profile["hair"]["value"] == "short black hair" and profile["hair"]["chapter"] == 1
    assert profile["accessories"]["value"] == "" and profile["tags"][:1] == ["black hair"]
    prompt, negative = base_prompt(profile, "m", {"style": "manhwa", "setting": "Victorian city with gas lamps"})
    assert "1boy" in prompt and "short black hair" in prompt and "manhwa" in prompt
    assert "mouth clearly visible" in prompt and "watermark" in negative
    assert "Victorian" not in prompt and "gas lamp" not in prompt  # the setting is never drawn
    prompt, _ = base_prompt(profile, "m", {"setting": "Victorian city with gas lamps", "era": "1880s Victorian"})
    assert "Clothing in 1880s Victorian style" in prompt and "gas lamp" not in prompt  # …but shapes the clothes


def test_portrait_prompt_keeps_only_the_character():
    from babel.art.profile import portrait_tags
    p = parse_profile(json.dumps({
        "accessories": {"value": "felt hat, silver pocket watch", "guessed": False},
        "outfit": {"value": "1880s fashion tailored suit, felt hat", "guessed": False},
        "tags": ["black hair", "felt hat", "gas lamp city", "occult symbolism", "1880s fashion", "pocket watch"]}))
    assert portrait_tags(p) == ["black hair", "pocket watch"]
    prompt, negative = base_prompt(p, "m", {})
    person = prompt.split("Half-body illustration of")[1].split("Korean")[0]
    assert "hat" not in person and "pocket watch" in prompt and "headwear" in negative
    assert "1880s" not in prompt.split(".")[0]  # era words aren't tags (but may describe the clothes)
    p["marks"] = {"value": "always wears a battered top hat", "guessed": False, "chapter": None, "quote": ""}
    prompt, negative = base_prompt(p, "m", {})
    assert "top hat" in prompt and "headwear" not in negative  # a signature hat stays


def test_user_edits_lock_profile_fields(novel):
    eid = novel.ids["Klein"]
    designs.save_profile(novel.store, eid, {"hair": {"value": "messy black hair", "guessed": False}}, user=True)
    draft_profile(novel.store, novel.ak, eid, StubLLM())
    v = designs.design_view(novel.store, novel.ak, eid)
    assert v["profile"]["hair"]["value"] == "messy black hair"  # the model didn't overwrite your edit
    assert v["profile"]["eyes"]["value"] == "brown eyes" and v["profile_locked"] == ["hair"]
    assert designs.art_settings(novel.store, novel.id)["setting"].startswith("Victorian")
    assert designs.art_settings(novel.store, novel.id)["era"] == "1880s Victorian"


def test_design_lifecycle_with_scheduler(novel, scheduler, tmp_path):
    eid = novel.ids["Klein"]
    draft_profile(novel.store, novel.ak, eid, StubLLM())
    designs.queue_candidates(novel.store, novel.ak, eid)
    drain(scheduler)
    v = designs.design_view(novel.store, novel.ak, eid)
    assert v["status"] == "choose" and len(v["candidates"]) == 6 and all(c["url"] for c in v["candidates"])
    assert all(c["op"] == "generate" and c["model"] == "anima-turbo" for c in scheduler.fake.calls)

    designs.approve_candidate(novel.store, v["candidates"][2]["id"])
    drain(scheduler)
    v = designs.design_view(novel.store, novel.ak, eid)
    assert v["status"] == "approved" and all(v["sheet"][e] for e in EMOTIONS)
    edits = [c for c in scheduler.fake.calls if c["op"] == "edit"]
    assert len(edits) == len(EMOTIONS) - 1 and all(c["model"] == "flux2-klein-4b" for c in edits)
    assert novel.store.one("SELECT portrait_path FROM entities WHERE id=?", (eid,))["portrait_path"].endswith("_auto.jpg")

    # reroll one expression: the design goes back to "sheet" and returns to approved
    designs.reroll(novel.store, v["sheet"]["angry"]["id"])
    assert designs.design_view(novel.store, novel.ak, eid)["status"] == "sheet"
    drain(scheduler)
    v2 = designs.design_view(novel.store, novel.ak, eid)
    assert v2["status"] == "approved" and v2["sheet"]["angry"]["id"] != v["sheet"]["angry"]["id"]

    # Klein approved → chapters 1 and 4 have no blockers left (2 still needs Melissa)
    r = plan.readiness(novel.store, novel.ak)
    assert r["ready_through"] == 0 and r["ready"] == 3 and r["blocked"][0]["missing"] == ["Melissa"]


def test_text_jobs_take_priority(novel, scheduler):
    eid = novel.ids["Klein"]
    draft_profile(novel.store, novel.ak, eid, StubLLM())
    designs.queue_candidates(novel.store, novel.ak, eid)
    novel.store.x("INSERT INTO jobs (novel_id, status, created_at) VALUES (?, 'running', 'now')", (novel.id,))
    assert scheduler.step() is False and scheduler.state["status"] == "waiting" and not scheduler.fake.calls
    novel.store.x("UPDATE jobs SET status='done'")
    assert scheduler.step() is True and len(scheduler.fake.calls) == 1


def test_auto_mode_profiles_then_draws_in_reading_order(novel, scheduler):
    designs.set_art_settings(novel.store, novel.id, auto=True)
    drain(scheduler)
    view = {n: designs.design_view(novel.store, novel.ak, novel.ids[n]) for n in ("Klein", "Melissa", "Dunn")}
    assert view["Klein"]["status"] == "choose" and view["Melissa"]["status"] == "choose"
    assert view["Dunn"]["status"] == "new"  # minor: will come from the extras library
    first = scheduler.fake.calls[0]["out"]
    assert f"/{novel.ids['Klein']}/" in first  # Klein (chapter 1) was drawn before Melissa (chapter 2)


def test_no_image_models_is_reported_not_fatal(novel, store, tmp_path):
    sch = ArtScheduler(store, art_dir=tmp_path / "art", portraits_dir=tmp_path / "p", backend_factory=None,
                       llm_factory=lambda: None)
    eid = novel.ids["Klein"]
    designs.save_profile(store, eid, {"hair": {"value": "black hair", "guessed": False}}, user=True)
    designs.queue_candidates(store, novel.ak, eid)
    assert sch.step() is False and sch.state["status"] == "unavailable" and "babel art setup" in sch.state["detail"]


def test_art_api(novel, scheduler, tmp_path):
    cascade = Cascade()
    app = create_app(Settings(data_dir=tmp_path), store=novel.store, cascade=cascade, start_worker=False, art=scheduler)
    with TestClient(app) as c:
        eid = novel.ids["Melissa"]
        r = c.get(f"/api/novels/{novel.id}/art").json()
        assert r["needed"] == 2 and [q["name"] for q in r["queue"]] == ["Klein", "Melissa"]
        assert c.post(f"/api/entities/{eid}/design/draft").status_code == 503  # no text model in this cascade
        assert c.post(f"/api/entities/{eid}/design/candidates").status_code == 400  # no profile yet
        prof = {"hair": {"value": "reddish black hair"}, "eyes": {"value": "bright brown eyes"}, "tags": ["red hair"]}
        v = c.put(f"/api/entities/{eid}/design/profile", json={"profile": prof}).json()
        assert v["profile"]["hair"]["value"] == "reddish black hair" and "hair" in v["profile_locked"]
        assert c.post(f"/api/entities/{eid}/design/candidates").json()["status"] == "candidates"
        drain(scheduler)
        v = c.get(f"/api/entities/{eid}/design").json()
        assert v["status"] == "choose"
        img = c.get(v["candidates"][0]["thumb"])
        assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
        v = c.post(f"/api/art/images/{v['candidates'][0]['id']}/approve").json()
        assert v["status"] == "sheet" and v["sheet"]["neutral"]
        drain(scheduler)
        assert c.get(f"/api/entities/{eid}/design").json()["status"] == "approved"
        assert c.put(f"/api/entities/{novel.ids['Dunn']}/design/tier", json={"tier": "main"}).json()["tier"] == "main"
        assert c.put(f"/api/novels/{novel.id}/art", json={"auto": True}).json()["auto"] is True
        assert c.get("/api/art/status").json()["emotions"][0] == "neutral"
