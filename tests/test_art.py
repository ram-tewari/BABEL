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
        self.loaded: set[str] = set()

    def call(self, req: dict) -> dict:
        self.running = True
        if req["op"] == "unload":
            self.loaded.discard(req.get("model"))
            return {"ok": True}
        self.calls.append(req)
        self.loaded.add(req["model"])
        Image.new("RGB", (req["width"] // 8, req["height"] // 8), (req["seed"] % 255, 90, 120)).save(req["out"])
        return {"ok": True, "secs": 0.01}

    def close(self) -> None:
        self.running = False
        self.loaded = set()


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


# ── step 3: the quality checker and politeness ───────────────────────────────

class FakeApprover:
    """Fails the images whose ids are in ``bad`` (or the first ``fail_first`` checks)."""

    model = "fake-vl"

    def __init__(self, fail_first=0, fail_emotions=()):
        self.fail_first, self.fail_emotions, self.n = fail_first, set(fail_emotions), 0

    def check(self, image, *, profile, gender, kind, emotion=None, reference=None, background=None, era=None):
        self.n += 1
        bad = self.n <= self.fail_first or emotion in self.fail_emotions
        return {"score": 0.2 if bad else 0.95, "pass": not bad, "issues": ["wearing a hat"] if bad else [],
                "answers": {}, "model": self.model}


def checked_scheduler(store, tmp_path, approver, governor=None):
    backend = FakeBackend()
    sch = ArtScheduler(store, art_dir=tmp_path / "art", portraits_dir=tmp_path / "portraits",
                       backend_factory=lambda: backend, llm_factory=StubLLM, approver_factory=lambda: approver,
                       governor=governor)
    sch.fake = backend
    return sch


def test_checker_scoring_rules():
    from babel.art.approve import questions, score
    prof = parse_profile(json.dumps({"hair": {"value": "black hair", "guessed": False},
                                     "outfit": {"value": "brown coat, felt hat", "guessed": False}}))
    qs, schema = questions(prof, "m", "candidate", None)
    assert "attr_hair" in schema["properties"] and "expression" not in schema["properties"]
    clothes = next(q for q in qs if q.startswith("attr_outfit"))
    assert "“brown coat”" in clothes and "hat" not in clothes  # checks what the prompt asked for
    ok = {"people": "one", "gender": "male", "attr_hair": "yes", "headwear": "no", "over_mouth": "no",
          "scenery": "no", "text": "no", "face_ok": "yes", "hands_ok": "unclear"}
    assert score(ok, profile=prof, gender="m", kind="candidate", emotion=None)["pass"]
    hat = score({**ok, "headwear": "yes"}, profile=prof, gender="m", kind="candidate", emotion=None)
    assert not hat["pass"] and "wearing a hat" in hat["issues"]
    prof["marks"] = {"value": "never without his felt hat", "guessed": False, "chapter": None, "quote": ""}
    assert score({**ok, "headwear": "yes"}, profile=prof, gender="m", kind="candidate", emotion=None)["pass"]
    assert not score({**ok, "over_mouth": "yes"}, profile=prof, gender="m", kind="candidate", emotion=None)["pass"]
    assert not score({**ok, "gender": "female"}, profile=prof, gender="m", kind="candidate", emotion=None)["pass"]
    _, schema = questions(prof, "m", "expression", "angry")
    assert "expression" in schema["properties"]
    assert not score({**ok, "expression": "no"}, profile=prof, gender="m", kind="expression", emotion="angry")["pass"]
    assert not score({**ok, "expression": "yes"}, profile=prof, gender="m", kind="expression", emotion="angry",
                     drift=0.2)["pass"]  # the edit changed the whole picture


def test_checker_hides_and_replaces_bad_options(novel, tmp_path):
    sch = checked_scheduler(novel.store, tmp_path, FakeApprover(fail_first=2))
    eid = novel.ids["Klein"]
    draft_profile(novel.store, novel.ak, eid, StubLLM())
    designs.queue_candidates(novel.store, novel.ak, eid)
    drain(sch)
    v = designs.design_view(novel.store, novel.ak, eid)
    assert v["status"] == "choose" and len(v["candidates"]) == 6  # two bad ones replaced
    assert len(v["rejected"]) == 2 and v["rejected"][0]["qc_issues"] == ["wearing a hat"]
    assert all(c["qc_status"] == "pass" for c in v["candidates"])
    assert len(sch.fake.calls) == 8


def test_checker_redraws_failing_expressions_then_keeps_the_best(novel, tmp_path):
    sch = checked_scheduler(novel.store, tmp_path, FakeApprover(fail_emotions={"afraid"}))
    eid = novel.ids["Klein"]
    draft_profile(novel.store, novel.ak, eid, StubLLM())
    designs.queue_candidates(novel.store, novel.ak, eid)
    drain(sch)
    designs.approve_candidate(novel.store, designs.design_view(novel.store, novel.ak, eid)["candidates"][0]["id"])
    drain(sch)
    v = designs.design_view(novel.store, novel.ak, eid)
    assert v["status"] == "approved"
    afraid = v["sheet"]["afraid"]
    assert afraid["attempt"] == 3 and afraid["qc_status"] == "fail"  # out of attempts: kept, flagged
    assert sum(1 for c in sch.fake.calls if c.get("op") == "edit") == len(EMOTIONS) - 1 + 2


def test_automatic_work_waits_while_you_work_but_your_clicks_dont(novel, tmp_path):
    from babel.system import Governor, Policy
    idle = {"s": 5.0}
    g = Governor(Policy(), probes={"available_gb": lambda: 30.0, "idle_seconds": lambda: idle["s"],
                                   "on_battery": lambda: False, "pressure_level": lambda: 1,
                                   "ollama_loaded": lambda: {}, "ollama_size_gb": lambda m: None})
    sch = checked_scheduler(novel.store, tmp_path, None, governor=g)
    designs.set_art_settings(novel.store, novel.id, auto=True)
    assert sch.step() is False and sch.state["status"] == "paused" and "using the computer" in sch.state["detail"]
    # you ask for Melissa's options yourself: that runs even while you're active
    designs.save_profile(novel.store, novel.ids["Melissa"], {"hair": {"value": "red hair", "guessed": False}}, user=True)
    designs.queue_candidates(novel.store, novel.ak, novel.ids["Melissa"], manual=True)
    assert sch.step() is True and len(sch.fake.calls) == 1
    idle["s"] = 999.0  # you walk away: the automatic work starts
    drain(sch)
    assert designs.design_view(novel.store, novel.ak, novel.ids["Klein"])["status"] == "choose"


def test_waits_for_memory_and_frees_what_it_holds(novel, tmp_path):
    from babel.system import Governor, Policy
    avail = {"gb": 4.0}
    g = Governor(Policy(), probes={"available_gb": lambda: avail["gb"], "idle_seconds": lambda: 999.0,
                                   "on_battery": lambda: False, "pressure_level": lambda: 1,
                                   "ollama_loaded": lambda: {}, "ollama_size_gb": lambda m: None})
    sch = checked_scheduler(novel.store, tmp_path, None, governor=g)
    eid = novel.ids["Klein"]
    designs.save_profile(novel.store, eid, {"hair": {"value": "black hair", "guessed": False}}, user=True)
    designs.queue_candidates(novel.store, novel.ak, eid)
    assert sch.step() is False and sch.state["status"] == "waiting" and "memory" in sch.state["detail"]
    avail["gb"] = 20.0
    assert sch.step() is True


def test_critical_pressure_releases_everything(novel, tmp_path):
    from babel.system import Governor, Policy
    level = {"v": 1}
    g = Governor(Policy(), probes={"available_gb": lambda: 30.0, "idle_seconds": lambda: 999.0,
                                   "on_battery": lambda: False, "pressure_level": lambda: level["v"],
                                   "ollama_loaded": lambda: {}, "ollama_size_gb": lambda m: None})
    sch = checked_scheduler(novel.store, tmp_path, None, governor=g)
    eid = novel.ids["Klein"]
    designs.save_profile(novel.store, eid, {"hair": {"value": "black hair", "guessed": False}}, user=True)
    designs.queue_candidates(novel.store, novel.ak, eid)
    assert sch.step() is True and sch.fake.running
    level["v"] = 4
    assert sch.step() is False and not sch.fake.running and "critical" in sch.state["detail"]


def test_citations_must_be_real_and_about_the_field():
    from babel.art.profile import verify_citations
    ev = [{"chapter": 16, "text": "It had reddish black hair, bright brown eyes, and a delicate, pretty face."},
          {"chapter": 4, "text": "making her face thin and slightly pale, her skin remained lustrous"}]
    prof = parse_profile(json.dumps({
        "hair": {"value": "light brown", "chapter": 4, "quote": "making her face thin and slightly pale", "guessed": False},
        "eyes": {"value": "bright brown", "chapter": 16, "quote": "bright brown eyes", "guessed": False},
        "face": {"value": "delicate", "chapter": 3, "quote": "a delicate, pretty face", "guessed": False},
        "build": {"value": "slim", "chapter": 2, "quote": "she was very tall and slim", "guessed": False}}))
    v = verify_citations(prof, ev)
    assert v["hair"]["guessed"] and v["hair"]["quote"] == ""  # quote isn't about hair: no fake citation
    assert not v["eyes"]["guessed"] and v["eyes"]["chapter"] == 16
    assert not v["face"]["guessed"] and v["face"]["chapter"] == 16  # chapter corrected to where the quote is
    assert v["build"]["guessed"]  # not in the passages at all
    prof2 = parse_profile(json.dumps({"hair": {"value": "blond", "chapter": 16, "quote": "reddish black hair"}}))
    assert verify_citations(prof2, ev)["hair"]["guessed"]  # colours disagree


def test_evidence_comes_from_any_chapter_that_mentions_them(store):
    nid = store.create_novel("t", [("c1", '"Hi," Mira said.', "a"), ("c2", "Tobin waved.", "b"),
                                   ("c3", "Mira came in. Mira had silver hair and green eyes.", "c")])
    ak = Akashic(store, nid)
    eid = ak.create("Mira", chapter_idx=0)
    ak.reload()
    ev = gather_evidence(store, ak, eid)
    assert ev and ev[0]["chapter"] == 3 and "silver hair" in ev[0]["text"]


def test_memory_pressure_pauses_automatic_work_but_not_yours(novel, tmp_path):
    from babel.system import Governor, Policy
    level = {"v": 1}
    g = Governor(Policy(), probes={"available_gb": lambda: 30.0, "idle_seconds": lambda: 999.0,
                                   "on_battery": lambda: False, "pressure_level": lambda: level["v"],
                                   "ollama_loaded": lambda: {}, "ollama_size_gb": lambda m: None})
    sch = checked_scheduler(novel.store, tmp_path, None, governor=g)
    designs.set_art_settings(novel.store, novel.id, auto=True)
    for _ in range(12):  # automatic work starts: profiles, then options (the image model is now loaded)
        sch.step()
    assert "anima-turbo" in sch.fake.loaded
    level["v"] = 2  # the Mac gets short of memory
    designs.save_profile(novel.store, novel.ids["Dunn"], {"hair": {"value": "dark hair", "guessed": False}}, user=True)
    designs.queue_candidates(novel.store, novel.ak, novel.ids["Dunn"], 1, manual=True)
    # every image briefly needs several GB more, so even what you asked for waits (and says why)
    assert sch.step() is False and "pressure" in (sch.state["detail"] or "")
    assert not sch.fake.running  # …and the automatic work let go of its memory
    level["v"] = 1  # pressure eases: what you asked for runs now…
    assert sch.step() is True
    for _ in range(3):  # (its quality check, if any)
        if not sch.step():
            break
    # …while automatic work waits a few minutes before trying again
    assert sch.step() is False and "resumes in about" in sch.state["detail"]


def test_one_image_model_at_a_time(novel, tmp_path):
    sch = checked_scheduler(novel.store, tmp_path, None)
    eid = novel.ids["Klein"]
    draft_profile(novel.store, novel.ak, eid, StubLLM())
    designs.queue_candidates(novel.store, novel.ak, eid, 1)
    drain(sch)
    assert sch.fake.loaded == {"anima-turbo"}
    designs.approve_candidate(novel.store, designs.design_view(novel.store, novel.ak, eid)["candidates"][0]["id"])
    sch.step()
    assert sch.fake.loaded == {"flux2-klein-4b"}  # Anima was unloaded before FLUX.2 loaded


def test_a_crashed_draw_is_retried_once(novel, tmp_path):
    sch = checked_scheduler(novel.store, tmp_path, None)
    real = sch.fake.call
    crashes = {"n": 1}

    def flaky(req):
        if req["op"] == "generate" and crashes["n"]:
            crashes["n"] -= 1
            raise RuntimeError("image worker exited")
        return real(req)

    sch.fake.call = flaky
    eid = novel.ids["Klein"]
    designs.save_profile(novel.store, eid, {"hair": {"value": "black hair", "guessed": False}}, user=True)
    designs.queue_candidates(novel.store, novel.ak, eid, 2)
    drain(sch)
    v = designs.design_view(novel.store, novel.ak, eid)
    assert v["status"] == "choose" and [c["status"] for c in v["candidates"]] == ["done", "done"]


def test_under_pressure_checks_wait_for_drawing_to_finish(novel, tmp_path):
    """Short of memory: drawing doesn't keep the checker loaded, and checks wait until drawing is done
    (pressure starts while drawing is under way, so the queued drawing finishes first)."""
    from babel.system import Governor, Policy
    level = {"v": 1}
    g = Governor(Policy(), probes={"available_gb": lambda: 30.0, "idle_seconds": lambda: 999.0,
                                   "on_battery": lambda: False, "pressure_level": lambda: level["v"],
                                   "ollama_loaded": lambda: {"fake-vl": 4.0}, "ollama_size_gb": lambda m: None})
    approver = FakeApprover()
    sch = checked_scheduler(novel.store, tmp_path, approver, governor=g)
    eid = novel.ids["Klein"]
    designs.save_profile(novel.store, eid, {"hair": {"value": "black hair", "guessed": False}}, user=True)
    designs.queue_candidates(novel.store, novel.ak, eid, 1, manual=True)
    assert sch.step() and approver.n == 0  # drew it (memory was fine)
    level["v"] = 2  # now memory gets short: the check runs only after releasing the image model
    sch.step()
    assert not sch.fake.running


def test_restyle_keeps_the_old_look_on_stage_until_a_new_one_is_chosen(novel, scheduler):
    from babel.vn.stage import _sheet

    store, eid = novel.store, novel.ids["Klein"]
    draft_profile(store, novel.ak, eid, StubLLM())
    designs.queue_candidates(store, novel.ak, eid)
    drain(scheduler)
    designs.approve_candidate(store, designs.design_view(store, novel.ak, eid)["candidates"][0]["id"])
    drain(scheduler)
    old = _sheet(store, eid)
    assert set(old) == set(EMOTIONS)

    assert designs.restyle(store, novel.ak, eid)
    d = designs.get_design(store, eid)
    assert d["status"] == "candidates" and d["base_image_id"]
    assert _sheet(store, eid) == old  # still on stage
    assert "Klein" not in sum((b["missing"] for b in plan.readiness(store, novel.ak)["blocked"]), [])
    queued = store.q("SELECT manual FROM art_images WHERE design_id=? AND status='queued'", (d["id"],))
    assert queued and not any(r["manual"] for r in queued)  # automatic: it waits until you're idle

    store.x("UPDATE art_images SET manual=1 WHERE design_id=? AND status='queued'", (d["id"],))
    drain(scheduler)
    v = designs.design_view(store, novel.ak, eid)
    assert v["status"] == "choose" and _sheet(store, eid) == old
    designs.approve_candidate(store, v["candidates"][0]["id"])
    new = _sheet(store, eid)
    assert set(new) == {"neutral"} and new["neutral"] != old["neutral"]  # the new look takes over


def test_house_style_is_anime():
    prompt, _ = base_prompt({"hair": {"value": "black"}, "tags": ["black hair"]}, "m", {"style": "manhwa"})
    assert "anime" in prompt and "semi-realistic" not in prompt
