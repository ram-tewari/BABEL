from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pytest

from babel.llm.providers import LocalModel, Provider, Router
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


_Q_RE = re.compile(r"^Q(\d+)\. (Who \w+|What is) ⟦Q\d+⟧ (.*)\n\s+(.*)$", re.M)
_OPT_RE = re.compile(r"([A-H])\) (.+?)(?=\s{3}[A-H]\) |$)")


class FakeLLM:
    """httpx transport that answers BABEL's questions like a (configurable) model.

    Speaks both Ollama's native /api/chat and OpenAI's /chat/completions.
    ``oracle`` maps a snippet of a questioned line → the speaker name to choose.
    ``people`` maps new names → gender, for the entity pass.
    ``script`` queues raw responses (int status code, or a content string) before falling back.
    """

    def __init__(self, oracle: dict[str, str] | None = None, people: dict[str, str] | None = None,
                 script: list | None = None, aliases: dict[str, str] | None = None):
        self.oracle = oracle or {}
        self.people = people or {}
        self.aliases = aliases or {}
        self.script = list(script or [])
        self.calls: list[dict] = []

    def answer(self, system: str, user: str) -> dict:
        if "NEW NAMES" in system or "NEW NAMES" in user:
            names = re.findall(r"^- ([^:\n]+):", user.split("NEW NAMES", 1)[1], re.M)
            return {"entities": [{"name": n, "kind": "person", "gender": self.people.get(n, "u"),
                                  "same_as": self.aliases.get(n, ""), "note": "seen in text"} for n in names]}
        if "previously on" in system:
            return {"summary": "Things happened in this chapter."}
        answers = []
        for m in _Q_RE.finditer(user):
            n, kind, text, opts = int(m.group(1)), m.group(2), m.group(3), m.group(4)
            options = [(letter, label.strip()) for letter, label in _OPT_RE.findall(opts)]
            choice, name = "A", None
            if kind.startswith("Who"):
                want = next((v for k, v in self.oracle.items() if k in text), None)
                if want:
                    hit = next((letter for letter, label in options if label == want), None)
                    if hit:
                        choice = hit
                    else:
                        choice, name = options[-1][0], want
            answers.append({"q": n, "choice": choice, **({"name": name} if name else {})})
        return {"choices": [a["choice"] for a in answers],
                "names": {str(a["q"]): a["name"] for a in answers if a.get("name")}}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.calls.append({"url": str(request.url), "body": body, "auth": request.headers.get("authorization")})
        if self.script:
            item = self.script.pop(0)
            if isinstance(item, int):
                return httpx.Response(item, json={"error": f"status {item}"}, headers={"retry-after": "0"} if item == 429 else {})
            if isinstance(item, tuple):
                return httpx.Response(item[0], text=item[1])
            content = item
        else:
            msgs = body["messages"]
            content = json.dumps(self.answer(msgs[0]["content"], msgs[-1]["content"]))
        if request.url.path.endswith("/api/chat"):
            return httpx.Response(200, json={"message": {"content": content}, "prompt_eval_count": 100, "eval_count": 10})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}],
                                         "usage": {"prompt_tokens": 100, "completion_tokens": 10}})

    def asked(self) -> list[str]:
        """Text of every questioned line, across calls."""
        out = []
        for c in self.calls:
            user = c["body"]["messages"][-1]["content"]
            out += [m.group(3) for m in _Q_RE.finditer(user)]
        return out


def make_local(fake: FakeLLM) -> LocalModel:
    return LocalModel("fake-local", "http://ollama.test", transport=httpx.MockTransport(fake))


def make_provider(fake: FakeLLM, name: str = "fake", keys: list[str] | None = None) -> Provider:
    return Provider(name, "http://cloud.test/v1", "fake-cloud", keys or ["k1"], transport=httpx.MockTransport(fake))


def make_cloud(fake: FakeLLM, **kw) -> Router:
    r = Router([make_provider(fake, **kw)])
    r._sleep = lambda s: None
    return r


SAMPLE_ORACLE = {
    "You're late": "Tobin", "early for tomorrow": "Mira Vell", "courier come": "Mira Vell", "Not yet": "Tobin",
    "Then we wait.": "Mira Vell", "Then we wait,": "Tobin", "Tobin,": "Mira Vell", "do you see": "Mira Vell",
    "See what": "Tobin", "hiding something": "Mira Vell", "counts the bolts": "Mira Vell",
}
