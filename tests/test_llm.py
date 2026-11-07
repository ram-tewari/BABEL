import json

import pytest

from babel.llm.providers import LLMError, Router
from babel.models import BlockType
from babel.transform.llm_labeler import ParseError, StoryContext, build_messages, parse_response
from babel.transform.segment import segment_text
from tests.conftest import FakeLLM, make_provider


def test_parse_ranges_fences_and_unknowns():
    raw = """```json
{"labels":[{"id":0,"type":"d","speaker":"Klein"},{"ids":"2-4","type":"system"},
 {"id":5,"type":"dialogue","speaker":"?"},{"id":99,"type":"d","speaker":"X"},{"id":1,"type":"bogus"},],
 "characters":[{"name":"Klein Moretti","aliases":["Klein"," "]}], "summary":"  stuff  "}
```"""
    res = parse_response(raw, set(range(6)))
    assert res.labels[0] == (BlockType.DIALOGUE, "Klein")
    assert res.labels[2] == res.labels[3] == res.labels[4] == (BlockType.SYSTEM, None)
    assert res.labels[5] == (BlockType.DIALOGUE, None)
    assert 99 not in res.labels and 1 not in res.labels
    assert res.characters[0].aliases == ["Klein"]
    assert res.summary == "stuff"


def test_parse_rejects_garbage():
    with pytest.raises(ParseError):
        parse_response("I cannot help with that.", {0})


def test_messages_include_context_and_numbered_segments():
    segs = segment_text('"Hi," Ann said.\n\n*Odd.*')
    msgs = build_messages(segs, StoryContext(cast=["Ann — aka Annie"], story_so_far=["Ch1: things"], pov="Ann"))
    user = msgs[-1]["content"]
    assert "Ann — aka Annie" in user and "STORY SO FAR" in user and "Point-of-view" in user
    assert '0|q| "Hi,"' in user and "2|e| *Odd.*" in user


def test_provider_success_and_think_stripping():
    fake = FakeLLM(script=['<think>hmm</think>{"labels": []}'])
    p = make_provider(fake)
    assert p.chat([{"role": "user", "content": "x"}]) == '{"labels": []}'
    assert fake.calls[0]["body"]["response_format"] == {"type": "json_object"}
    assert fake.calls[0]["auth"] == "Bearer k1"


def test_provider_drops_json_mode_when_unsupported():
    fake = FakeLLM(script=[(400, "response_format is not supported"), '{"ok": 1}'])
    p = make_provider(fake)
    assert p.chat([{"role": "user", "content": "x"}]) == '{"ok": 1}'
    assert "response_format" not in fake.calls[1]["body"]


def test_rate_limit_rotates_keys():
    fake = FakeLLM(script=[429, '{"ok": 1}'])
    p = make_provider(fake, keys=["k1", "k2"])
    r = Router([p])
    r._sleep = lambda s: None
    content, label = r.chat([{"role": "user", "content": "x"}])
    assert content == '{"ok": 1}'
    assert [c["auth"] for c in fake.calls] == ["Bearer k1", "Bearer k2"]


def test_router_falls_back_to_next_provider():
    bad = FakeLLM(script=[500, 500, 500])
    good = FakeLLM(script=['{"ok": 2}'])
    r = Router([make_provider(bad, name="a"), make_provider(good, name="b")], retries=0)
    content, label = r.chat([{"role": "user", "content": "x"}])
    assert json.loads(content) == {"ok": 2} and label.startswith("b:")


def test_router_raises_when_everything_fails():
    r = Router([make_provider(FakeLLM(script=[401]))], retries=0)
    with pytest.raises(LLMError, match="auth failed"):
        r.chat([{"role": "user", "content": "x"}])


def test_empty_router_raises():
    with pytest.raises(LLMError):
        Router([]).chat([])
