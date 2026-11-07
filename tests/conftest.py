from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pytest

from babel.llm.providers import Provider, Router
from babel.store.db import Store

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_text() -> str:
    return (FIXTURES / "sample_chapter.txt").read_text()


@pytest.fixture
def store(tmp_path) -> Store:
    s = Store(tmp_path / "babel.db")
    yield s
    s.close()


_SEG_LINE = re.compile(r"^(\d+)\|(\w)\| (.*)$", re.M)


def fake_llm_reply(user_msg: str, speakers: dict[str, str] | None = None) -> dict:
    """A deterministic stand-in for a good LLM: labels quotes using a phrase→speaker map."""
    speakers = speakers or {}
    labels, chars = [], []
    for m in _SEG_LINE.finditer(user_msg):
        sid, hint, text = int(m.group(1)), m.group(2), m.group(3)
        if hint == "q":
            who = next((v for k, v in speakers.items() if k in text), "?")
            labels.append({"id": sid, "type": "d", "speaker": who})
        elif hint == "e":
            labels.append({"id": sid, "type": "t", "speaker": "Mira Vell"})
        elif hint == "b":
            labels.append({"id": sid, "type": "s"})
        elif text.strip() == "CRASH!":
            labels.append({"id": sid, "type": "x"})
    if "Mira" in user_msg:
        chars.append({"name": "Mira Vell", "aliases": ["Mira"], "note": "protagonist"})
    return {"labels": labels, "characters": chars, "summary": "Mira waits for a courier who never comes."}


class FakeLLM:
    """httpx transport speaking the OpenAI chat-completions protocol."""

    def __init__(self, speakers: dict[str, str] | None = None, script: list | None = None):
        self.speakers = speakers or {}
        self.script = list(script or [])  # optional queued responses: int status or str content
        self.calls: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.calls.append({"body": body, "auth": request.headers.get("authorization")})
        if self.script:
            item = self.script.pop(0)
            if isinstance(item, int):
                return httpx.Response(item, json={"error": {"message": f"status {item}"}},
                                      headers={"retry-after": "0"} if item == 429 else {})
            if isinstance(item, tuple):
                return httpx.Response(item[0], text=item[1])
            content = item
        else:
            content = json.dumps(fake_llm_reply(body["messages"][-1]["content"], self.speakers))
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def make_provider(fake: FakeLLM, name: str = "fake", keys: list[str] | None = None) -> Provider:
    return Provider(name, "http://fake.test/v1", "fake-model", keys or ["k1"],
                    transport=httpx.MockTransport(fake))


def make_router(fake: FakeLLM, **kw) -> Router:
    r = Router([make_provider(fake, **kw)])
    r._sleep = lambda s: None
    return r


SAMPLE_SPEAKERS = {
    "You're late": "Tobin",
    "early for tomorrow": "Mira Vell",
    "courier come": "Mira",
    "Not yet": "Tobin",
    "Then we wait.": "Mira",
    "Then we wait,": "Tobin",
    "Tobin,": "Mira",
    "do you see": "Mira",
    "See what": "Tobin",
}
