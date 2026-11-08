"""Tiers 2/3: questions, model backends and the cascade policy."""

import json

import pytest

from babel.llm.providers import LLMError, Router
from babel.memory.akashic import Akashic
from babel.models import BlockType, Decision
from babel.scenario.ask import OTHER, Plan, build_batches, parse_answers, plan
from babel.scenario.cascade import Cascade, TransformFailed
from babel.scenario.segment import segment_text
from tests.conftest import SAMPLE_ORACLE, FakeLLM, make_cloud, make_local, make_provider


def chapter(store, text, n=1):
    nid = store.create_novel("N", [(f"Chapter {i + 1}", text, f"h{i}") for i in range(n)])
    return nid, [store.get_chapter(r["id"]) for r in store.q("SELECT id FROM chapters WHERE novel_id=? ORDER BY idx", (nid,))]


# ── questions ──────────────────────────────────────────────────────────────
def test_batches_mark_lines_and_offer_candidates():
    segs = segment_text('Tobin sorted bolts.\n\n"Hi."\n\n*Odd.*')
    decisions = {
        0: Decision(type=BlockType.ACTION, speaker="Tobin", conf=0.95),
        1: Decision(type=BlockType.DIALOGUE, speaker="Tobin", conf=0.5, candidates=["Tobin", "Mira"]),
        2: Decision(type=BlockType.THOUGHT, speaker=None, conf=0.4, candidates=["Mira"]),
    }
    p = plan(decisions, 0.9)
    assert p.speaker == [1, 2] and p.type == [2]
    [b] = build_batches(segs, decisions, p, cast_lines=["Mira (female)"], story=["Ch1: x"], title="T")
    user = b.messages[-1]["content"]
    assert '⟦Q1⟧"Hi."' in user and "Mira (female)" in user and "STORY SO FAR" in user
    assert "A) Tobin   B) Mira   C) " + OTHER in user
    assert [q.kind for q in b.questions] == ["speaker", "speaker", "type"]


def test_parse_answers_letters_other_and_garbage():
    segs = segment_text('"Hi."\n\n"Yo."')
    decisions = {0: Decision(type=BlockType.DIALOGUE, speaker="A", conf=0.5, candidates=["A", "B"]),
                 1: Decision(type=BlockType.DIALOGUE, speaker="A", conf=0.5, candidates=["A"])}
    [b] = build_batches(segs, decisions, Plan(speaker=[0, 1]), cast_lines=[], story=[], title="T")
    ans = parse_answers('```json\n{"answers":[{"q":1,"choice":"B"},{"q":2,"choice":"B","name":"Old Harrow"},'
                        '{"q":9,"choice":"A"},{"q":1,"choice":"Z"}]}\n```', b)
    assert [(a.seg, a.value, a.other) for a in ans] == [(0, "B", False), (1, "Old Harrow", True)]
    with pytest.raises(ValueError):
        parse_answers("no idea", b)


# ── backends ───────────────────────────────────────────────────────────────
def test_local_model_uses_native_api_with_schema():
    fake = FakeLLM(script=['{"answers": []}'])
    r = make_local(fake).chat([{"role": "user", "content": "x"}], schema={"type": "object"})
    body = fake.calls[0]["body"]
    assert fake.calls[0]["url"].endswith("/api/chat")
    assert body["format"] == {"type": "object"} and body["think"] is False and body["options"]["temperature"] == 0
    assert (r.prompt_tokens, r.completion_tokens) == (100, 10)


def test_cloud_rotation_failover_and_json_mode():
    fake = FakeLLM(script=[429, (400, "response_format unsupported"), '{"ok": 1}'])
    r = make_cloud(fake, keys=["k1", "k2"])
    reply = r.chat([{"role": "user", "content": "x"}])
    assert json.loads(reply.content) == {"ok": 1} and reply.prompt_tokens == 100
    assert [c["auth"] for c in fake.calls] == ["Bearer k1", "Bearer k2", "Bearer k2"]
    assert "response_format" not in fake.calls[-1]["body"]
    bad, good = FakeLLM(script=[500, 500]), FakeLLM(script=['{"x": 2}'])
    chain = Router([make_provider(bad, "a"), make_provider(good, "b")], retries=0)
    assert chain.chat([]).provider == "b"
    with pytest.raises(LLMError, match="auth"):
        Router([make_provider(FakeLLM(script=[401]))], retries=0).chat([])


# ── cascade policy ─────────────────────────────────────────────────────────
TEXT = '"Run," Kai said.\n\n"Where?"\n\n"Anywhere!"\n\n"Fine."'


def test_rules_mode_makes_no_calls(store):
    nid, [ch] = chapter(store, TEXT)
    fake = FakeLLM()
    out = Cascade(local=make_local(fake), cloud=make_cloud(fake)).transform(store, Akashic(store, nid), ch, mode="rules")
    assert fake.calls == [] and out.stats["asked"] == {"local": 0, "cloud": 0}


def test_local_answers_only_uncertain_lines_and_is_free(store):
    nid, [ch] = chapter(store, TEXT)
    fake = FakeLLM(oracle={"Where": "Mara", "Anywhere": "Kai", "Fine": "Mara"}, people={"Kai": "m"})
    out = Cascade(local=make_local(fake)).transform(store, Akashic(store, nid), ch)
    asked = fake.asked()
    assert not any("Run," in a for a in asked)  # the tagged line is never asked about
    who = {Decision.from_compact(v).speaker for v in out.decisions.values() if v[1]}
    assert {"Kai", "Mara"} <= who
    usage = store.usage_summary(nid)
    assert {u["tier"] for u in usage} == {"local"} and sum(u["questions"] for u in usage) >= 3


def test_disputes_escalate_to_cloud_and_cloud_wins(store):
    text = '"Hi," Kai said.\n\n"Hello," Mara said.\n\nKai frowned. "Late again."'
    nid, [ch] = chapter(store, text)
    # The beat says Kai (strong evidence); the local model disagrees; the cloud settles it.
    local = FakeLLM(oracle={"Late again": "Mara"})
    cloud = FakeLLM(oracle={"Late again": "Kai"})
    c = Cascade(local=make_local(local), cloud=make_cloud(cloud))
    c.policy.accept = 0.99  # force the beat-attributed line through the local tier
    out = c.transform(store, Akashic(store, nid), ch)
    seg_late = next(s.id for s in segment_text(text) if "Late again" in s.text)
    d = Decision.from_compact(out.decisions[seg_late])
    assert any("Late again" in a for a in cloud.asked())
    assert d.speaker == "Kai" and d.tier.value == "cloud"


def test_local_overrules_weak_heuristic(store):
    nid, [ch] = chapter(store, '"Run," Kai said.\n\n"Hi," Mara said.\n\n"Where?"')
    fake = FakeLLM(oracle={"Where": "Mara"})  # turn-taking would say Kai
    out = Cascade(local=make_local(fake)).transform(store, Akashic(store, nid), ch)
    seg = next(s.id for s in segment_text(ch["source_text"]) if "Where" in s.text)
    d = Decision.from_compact(out.decisions[seg])
    assert d.speaker == "Mara" and d.tier.value == "local"


def test_entity_pass_learns_gender_and_aliases(store):
    text = ('Captain Ilse Varga stood by the window. "Three hundred crowns," Ilse said.\n\n'
            'Aldric looked up. "The ledger balances," Aldric said.')
    nid, [ch] = chapter(store, text)
    fake = FakeLLM(people={"Ilse Varga": "f", "Aldric": "m", "Captain Ilse Varga": "f"},
                   aliases={"Ilse": "Ilse Varga"})
    ak = Akashic(store, nid)
    Cascade(local=make_local(fake)).transform(store, ak, ch)
    ak.reload()
    ilse = ak.lookup("Ilse")
    assert ilse is not None and ak.gender(ilse) == "f"
    assert ak.gender(ak.lookup("Aldric")) == "m"


def test_strict_tiers_require_models(store):
    nid, [ch] = chapter(store, TEXT)
    with pytest.raises(TransformFailed):
        Cascade().transform(store, Akashic(store, nid), ch, mode="cloud")
    with pytest.raises(TransformFailed):
        Cascade().transform(store, Akashic(store, nid), ch, mode="local")


def test_broken_model_degrades_to_rules(store, sample_text):
    nid, [ch] = chapter(store, sample_text.split("\n", 1)[1])
    fake = FakeLLM(script=["nonsense"] * 50)
    out = Cascade(local=make_local(fake)).transform(store, Akashic(store, nid), ch)
    assert out.warnings
    assert any(v[1] == "Tobin" for v in out.decisions.values())


def test_full_sample_with_local_oracle(store, sample_text):
    nid, [ch] = chapter(store, sample_text.split("\n", 1)[1])
    fake = FakeLLM(oracle=SAMPLE_ORACLE, people={"Mira Vell": "f", "Tobin": "m", "Old Harrow": "m"},
                   aliases={"Mira": "Mira Vell"})
    out = Cascade(local=make_local(fake)).transform(store, Akashic(store, nid), ch)
    assert out.summary == "Things happened in this chapter."
    assert out.review_count == 0


def test_reasoning_models_answer_directly():
    from tests.conftest import make_provider

    fake = FakeLLM(script=['{"ok": 1}'])
    p = make_provider(fake)
    p.model = "qwen3-235b-a22b"
    p._no_reasoning = True
    p.chat([{"role": "user", "content": "x"}])
    body = fake.calls[0]["body"]
    assert body["reasoning_effort"] == "none" and body["messages"][-1]["content"].endswith("/no_think")
    # a provider that rejects the parameter gets it dropped automatically
    fake2 = FakeLLM(script=[(400, "unknown parameter reasoning_effort"), '{"ok": 2}'])
    p2 = make_provider(fake2)
    p2._no_reasoning = True
    assert json.loads(p2.chat([{"role": "user", "content": "x"}]).content) == {"ok": 2}
    assert "reasoning_effort" not in fake2.calls[-1]["body"]


def test_question_options_are_one_per_person():
    from babel.scenario.ask import dedupe_names

    assert dedupe_names(["Aldric", "Ilse", "Brother Aldric", "Pell", "Ilse Varga"]) == ["Brother Aldric", "Ilse Varga", "Pell"]


def test_places_never_speak(store):
    nid, [ch] = chapter(store, '"Welcome," Tingen said.\n\n"Thanks," Mira said.')
    ak = Akashic(store, nid)
    ak.create("Tingen", "location", note="a city")
    out = Cascade().transform(store, ak, ch)
    seg = next(s.id for s in segment_text(ch["source_text"]) if "Welcome" in s.text)
    d = Decision.from_compact(out.decisions[seg])
    assert d.speaker is None and d.conf < 0.6 and "location" in d.why
    ak.reload()
    assert ak.lookup("Tingen") is None  # no character was invented
