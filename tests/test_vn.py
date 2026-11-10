"""Step 4: emotions per line, scenes and places, the shared extras/background library, the staged chapter."""

import json

import pytest
from fastapi.testclient import TestClient

from babel.api.app import create_app
from babel.art import designs
from babel.art.runner import ArtScheduler
from babel.config import Settings
from babel.memory.akashic import Akashic
from babel.scenario.cascade import Cascade
from babel.vn import emotion as emo
from babel.vn import library as lib
from babel.vn import scenes as sc
from babel.vn import stage
from tests.test_art import FakeApprover, FakeBackend, drain


def test_emotion_rules():
    assert emo.rule_emotion('"Ha!"', "laugh", "")[0] == "laugh"
    assert emo.rule_emotion('"Fine."', None, "Klein smiled and said")[0] == "happy"
    assert emo.rule_emotion('"Fine."', None, "her hands trembled")[0] == "afraid"
    assert emo.rule_emotion('"What?!"', None, "")[0] == "surprised"
    e, c = emo.rule_emotion('"I see."', None, "")
    assert e == "neutral" and c < stage.REFINE_BELOW  # no cue: the model gets asked
    assert emo.rule_emotion('"Fine."', None, "he frowned")[1] < stage.REFINE_BELOW  # paragraph hints get confirmed


def test_emotion_refine_round_trip():
    blocks = [{"type": "narration", "text": "Rain.", "speaker": None, "para": 0, "seg": [0]},
              {"type": "dialogue", "text": "Go away!", "speaker": "Mira", "para": 1, "seg": [1]},
              {"type": "dialogue", "text": "Never.", "speaker": "Tobin", "para": 2, "seg": [2]}]
    msgs, schema, targets = emo.refine_messages(blocks, [1, 2])
    assert "⟦Q1⟧Mira: Go away!" in msgs[1]["content"] and schema["properties"]["choices"]["maxItems"] == 2
    assert emo.parse_refine('{"choices": ["D", "H"]}', targets) == {1: "angry", 2: "serious"}
    assert emo.parse_refine('{"choices": ["D"]}', targets) == {}  # wrong count: ignored


def test_scenes_places_and_venues(store):
    nid = store.create_novel("t", [("c", "x", "h")])
    ak = Akashic(store, nid)
    ak.create("Ironcross Street", kind="location")
    ak.create("Tingen", kind="location")
    ak.reload()
    assert sc.venue_kind("Ironcross Street") == "street" and sc.venue_kind("Old Will's Restaurant") == "tavern"
    assert sc.venue_kind("Tingen") is None  # a city isn't a backdrop
    B = lambda t, text: {"type": t, "text": text, "speaker": None, "para": 0, "seg": [0]}  # noqa: E731
    blocks = [B("narration", "Klein walked down Ironcross Street in Tingen under the morning sun."),
              B("dialogue", "Hello."), B("break", "◆"),
              B("narration", "Late at night, the pub was loud. The bartender wiped the bar under the moonlight."),
              B("dialogue", "Beer?")]
    scenes = sc.locate(blocks, ak)
    assert [s["start"] for s in scenes] == [0, 3]
    assert scenes[0]["place"]["kind"] == "named" and scenes[0]["place"]["name"] == "Ironcross Street"
    filler = [B("dialogue", f"Line {k}.") for k in range(9)]
    moved = sc.split_scenes([B("narration", "He sat at his desk in his room.")] + filler +
                            [B("narration", "He walked out onto the street, where hawkers shouted.")])
    assert moved == [0, 10]  # walking out to the street starts a new scene
    assert not scenes[0]["night"] and scenes[1]["place"]["key"] == "tavern" and scenes[1]["night"]


def test_extras_are_matched_by_role_and_keep_their_face(store):
    assert lib.classify("Carriage driver", None, "m") == "driver"
    assert lib.classify("mobile hawkers", None, None) == "worker"
    assert lib.classify("Wendy Smyrin", "seventy-year-old granny who runs the bakery", "f") == "elder_f"
    assert lib.classify("Wendy Smyrin", None, "f", "a seventy-plus year old granny selling bread") == "elder_f"
    assert lib.classify("Baker", None, "f", "the baker waved") == "shopkeeper_f"
    assert lib.classify("Bartender", None, "f") == "barmaid" and lib.classify("Stranger", None, "f") == "woman"
    nid = store.create_novel("t", [("c", "x", "h")])
    ak = Akashic(store, nid)
    guard = ak.create("Gate guard", gender="m")
    ak.reload()
    face = lib.assign_extra(store, ak, guard, "1880s Victorian")
    assert lib.assign_extra(store, ak, guard, "1880s Victorian") == face  # stable
    d = designs.get_design(store, face)
    assert d["kind"] == "extra" and d["auto_pick"] == 1 and d["status"] == "profiled"
    assert json.loads(d["spec"])["archetype"] == "guard"
    twin = lib.other_variant(store, face, {face})
    assert twin != face and json.loads(designs.get_design(store, twin)["spec"])["archetype"] == "guard"
    assert all(n["title"] != "Shared art library" for n in store.list_novels())  # hidden


@pytest.fixture
def sch(store, tmp_path):
    backend = FakeBackend()
    s = ArtScheduler(store, art_dir=tmp_path / "art", portraits_dir=tmp_path / "p", backend_factory=lambda: backend,
                     llm_factory=lambda: None, approver_factory=lambda: FakeApprover())
    s.fake = backend
    return s


def test_library_items_are_drawn_checked_and_picked_automatically(store, sch):
    nid = store.create_novel("t", [("c", "x", "h")])
    ak = Akashic(store, nid)
    eid = ak.create("Gate guard", gender="m")
    ak.reload()
    face = lib.assign_extra(store, ak, eid, "1880s Victorian")
    bg = lib.ensure_generic_background(store, "1880s Victorian", "street")
    lib_ak = Akashic(store, lib.library_novel_id(store))
    designs.queue_candidates(store, lib_ak, face, manual=True)
    designs.queue_candidates(store, lib_ak, bg, manual=True)
    drain(sch, limit=80)
    fv, bv = designs.design_view(store, lib_ak, face), designs.design_view(store, lib_ak, bg)
    assert fv["status"] == "approved" and set(fv["sheet"]) == set(lib.EXTRA_EMOTIONS)
    assert all(fv["sheet"][e] for e in lib.EXTRA_EMOTIONS)
    assert bv["status"] == "approved" and bv["base_image_id"] and bv["sheet"] == {}
    sizes = {(c["width"], c["height"]) for c in sch.fake.calls if c["op"] == "generate"}
    assert (1344, 768) in sizes and (1024, 1536) in sizes  # backgrounds are wide, people are drawn full-body


def test_stage_view_and_api(store, tmp_path, sch):
    text = ('Klein walked into the pub on Ironcross Street. "Beer," Klein said.\n\n'
            '"Four pence," said the bartender, smiling.\n\n"Thanks," Klein said.')
    nid = store.create_novel("t", [("c1", text, "h")])
    ak = Akashic(store, nid)
    klein = ak.create("Klein", gender="m")
    ak.reload()
    cid = store.one("SELECT id FROM chapters WHERE novel_id=?", (nid,))["id"]
    ch = store.get_chapter(cid)  # transform it (rules) so the bartender becomes a known minor character
    out = Cascade().transform(store, ak, ch, mode="rules")
    store.save_doc(cid, out.decisions, summary=out.summary, review_count=out.review_count, tiers=out.tiers,
                   stats=out.stats)
    ak.reload()
    # Klein is the main character with a finished design (pretend: 8 expressions drawn)
    designs.save_profile(store, klein, {"hair": {"value": "black hair", "guessed": False}}, user=True)
    store.x("INSERT INTO chapter_cast (chapter_id, entity_id, lines) VALUES (?,?,50)", (cid, klein))
    designs.queue_candidates(store, ak, klein, 1)
    drain(sch)
    designs.approve_candidate(store, designs.design_view(store, ak, klein)["candidates"][0]["id"])
    drain(sch)
    designs.set_art_settings(store, nid, era="1880s Victorian")
    v = stage.stage_view(store, ak, cid)
    lines = [b for b in v["blocks"] if b["type"] == "dialogue"]
    assert lines[0]["speaker"] == "Klein" and lines[0]["sprite"].endswith("?sprite=1")
    barkeep = next(b for b in lines if b["speaker"] and "artender" in b["speaker"])
    assert barkeep["emotion"] == "happy" and barkeep["sprite"] is None  # extra not drawn yet
    assert any(c["extra"] and not c["has_art"] for c in v["cast"].values())
    assert v["scenes"][0]["background"] is None

    app = create_app(Settings(data_dir=tmp_path), store=store, cascade=Cascade(), start_worker=False, art=sch)
    with TestClient(app) as c:
        r = c.post(f"/api/chapters/{cid}/stage/prepare").json()  # no text model: rules; queue what it needs
        assert r["queued"] >= 2
        drain(sch, limit=120)
        v = c.get(f"/api/chapters/{cid}/stage").json()
        assert v["scenes"][0]["background"] and all(x["has_art"] for x in v["cast"].values())
        assert c.get(lines[0]["sprite"]).headers["content-type"] == "image/png"


def test_model_only_decides_uncertain_places(store):
    nid = store.create_novel("t", [("c", "x", "h")])
    ak = Akashic(store, nid)
    scenes = [{"start": 0, "end": 2, "place": {"kind": "generic", "key": "room", "name": "a room"}, "night": True,
               "conf": 0.7, "tier": "rule", "category": "room", "indoor": True},
              {"start": 2, "end": 4, "place": {"kind": "generic", "key": "room", "name": "a room"}, "night": False,
               "conf": 0.45, "tier": "rule", "category": "room", "indoor": True}]
    out = sc.apply_refine('{"scenes": [{"place": "generic:tavern", "time": "day"}, '
                          '{"place": "generic:tent", "time": "night"}]}', scenes, ak)
    assert out[0]["place"]["key"] == "room" and out[0]["night"]  # confident rule kept
    assert out[1]["place"]["key"] == "tent" and out[1]["night"] and out[1]["indoor"]


def test_background_prompt_lets_the_book_lead():
    from babel.art.profile import background_prompt
    p, _ = background_prompt({"label": "a lecture hall", "era": "1850s Victorian",
                              "description": "A three-story stone building shaded by greenery"})
    assert "Background art: A three-story stone building" in p and "lecture hall" not in p
    assert "eyes" not in p and "no humans" in p
    p, _ = background_prompt({"label": "a crowded pub", "era": "1850s Victorian"})
    assert "Background art: a crowded pub, in the 1850s Victorian period" in p and "no modern technology" in p


def test_background_checker_rejects_cutouts_and_anachronisms():
    from babel.art.approve import score_background
    ok = {"people": "none", "place": "yes", "full_scene": "yes", "modern": "no", "text": "no", "coherent": "yes"}
    assert score_background(ok, "a pub", "1850s Victorian")["pass"]
    assert not score_background({**ok, "full_scene": "no"}, "a tent", "1850s Victorian")["pass"]
    assert not score_background({**ok, "modern": "yes"}, "an office", "1850s Victorian")["pass"]
    assert score_background({**ok, "modern": "yes"}, "an office", "modern-day Korean")["pass"]


def test_a_deck_of_cards_is_not_a_ship():
    assert sc.generic_place("She stacked the cards into a deck and shuffled the deck.")[0] != "ship"
    assert sc.generic_place("The sailors ran across the ship's deck as the mast creaked.")[0] == "ship"
    assert sc.generic_place("He came to the centre of the room and walked in the shape of a square.")[0] == "room"


def test_place_plaques_are_short_and_gender_is_read_from_the_book():
    assert lib.infer_gender("the woman whose face was painted; she smiled") == "f"
    assert lib.infer_gender("the man tipped his hat") == "m" and lib.infer_gender("someone") is None
    assert sc.SHORT["tent"] == "The fortune-teller's tent" and set(sc.SHORT) == set(sc.GENERIC)
