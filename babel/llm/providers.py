"""Model backends for the two LLM tiers.

* **local** — a small model on this machine via Ollama's native API, with JSON-schema
  structured output (always well-formed) and thinking disabled for speed. Free.
* **cloud** — any OpenAI-compatible endpoint (NVIDIA NIM, Groq, Gemini, OpenRouter,
  OpenAI, LM Studio/vLLM…), chained with per-key rate limits, key rotation and
  failover. Used only for the questions the cheaper tiers couldn't settle.

Every call returns a ``Reply`` with token usage so the pipeline can account cost.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

log = logging.getLogger(__name__)


class LLMError(Exception):
    """A request failed (after retries)."""


class RateLimited(LLMError):
    def __init__(self, msg: str, retry_after: float | None = None):
        super().__init__(msg)
        self.retry_after = retry_after


@dataclass
class Reply:
    content: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_NO_THINK_RE = re.compile(r"qwen3(?!.*instruct)", re.IGNORECASE)  # hybrid-thinking Qwen3 models
_REASONING_RE = re.compile(r"qwen3(?!.*instruct)|deepseek-r1|qwq|magistral|thinking", re.IGNORECASE)


# ── local tier ─────────────────────────────────────────────────────────────
# Measured on the QC + gold sets (README): the 30B mixture-of-experts model is both the most accurate
# and the fastest where it fits (~18 GB, needs 32 GB+ of RAM); qwen3:8b is the pick for smaller machines.
PREFERRED_LOCAL = ("qwen3:30b-a3b", "qwen3:8b", "qwen3:14b", "qwen2.5:14b", "qwen2.5:7b", "llama3.1:8b", "gemma3:12b",
                   "mistral-nemo", "qwen3:4b", "llama3.2:3b")


class LocalModel:
    """A model served by Ollama (native /api/chat, structured outputs)."""

    def __init__(self, model: str, base_url: str = "http://localhost:11434", timeout: float = 300.0,
                 transport: httpx.BaseTransport | None = None, num_ctx: int = 8192):
        self.name = "ollama"
        self.model = model
        self.base_url = base_url.rstrip("/").removesuffix("/v1")
        self.num_ctx = num_ctx
        self._http = httpx.Client(timeout=timeout, transport=transport)
        self._lock = threading.Lock()  # one request at a time: a local GPU doesn't parallelize well

    @property
    def label(self) -> str:
        return f"ollama:{self.model}"

    def chat(self, messages: list[dict], *, schema: dict | None = None, max_tokens: int = 1024,
             temperature: float = 0.0) -> Reply:
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": schema or "json",
            "think": False,
            "keep_alive": "30m",
            "options": {"temperature": temperature, "num_predict": max_tokens, "num_ctx": self.num_ctx},
        }
        with self._lock:
            try:
                r = self._http.post(f"{self.base_url}/api/chat", json=body)
            except httpx.HTTPError as e:
                raise LLMError(f"ollama: {e}") from e
        if r.status_code == 400 and "think" in r.text:  # model without a thinking switch
            body.pop("think")
            with self._lock:
                r = self._http.post(f"{self.base_url}/api/chat", json=body)
        if r.status_code >= 400:
            raise LLMError(f"ollama: HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        content = _THINK_RE.sub("", (data.get("message") or {}).get("content") or "").strip()
        if not content:
            raise LLMError("ollama: empty response")
        return Reply(content, "ollama", self.model, data.get("prompt_eval_count") or 0, data.get("eval_count") or 0)


def ollama_models(base_url: str | None = None) -> list[str]:
    url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/").removesuffix("/v1")
    try:
        r = httpx.get(f"{url}/api/tags", timeout=1.5)
        return [m["name"] for m in r.json().get("models", [])] if r.status_code == 200 else []
    except (httpx.HTTPError, ValueError):
        return []


def build_local(setting: str | None = None, model: str | None = None) -> LocalModel | None:
    """BABEL_LOCAL=auto (default) | off ; BABEL_LOCAL_MODEL picks the model."""
    setting = (setting or os.getenv("BABEL_LOCAL", "auto")).lower()
    if setting in ("off", "none", "0", "false"):
        return None
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    installed = ollama_models(base)
    if not installed:
        return None
    want = model or os.getenv("BABEL_LOCAL_MODEL")
    if want:
        match = next((m for m in installed if m == want or m.split(":")[0] == want or m == f"{want}:latest"), None)
        if match is None:
            log.warning("local model %s is not installed (ollama pull %s)", want, want)
            return None
        return LocalModel(match, base)
    for pref in PREFERRED_LOCAL:
        if pref in installed:
            return LocalModel(pref, base)
    return LocalModel(installed[0], base)


# ── cloud tier ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Preset:
    name: str
    base_url: str
    key_envs: tuple[str, ...]
    model: str
    rpm: int


PRESETS: dict[str, Preset] = {
    p.name: p
    for p in [
        Preset("nvidia", "https://integrate.api.nvidia.com/v1", ("NVIDIA_API_KEYS", "NVIDIA_API_KEY"),
               "deepseek-ai/deepseek-v3.1", 40),
        Preset("groq", "https://api.groq.com/openai/v1", ("GROQ_API_KEYS", "GROQ_API_KEY"),
               "llama-3.3-70b-versatile", 30),
        Preset("gemini", "https://generativelanguage.googleapis.com/v1beta/openai", ("GEMINI_API_KEYS", "GEMINI_API_KEY"),
               "gemini-2.5-flash", 10),
        Preset("openrouter", "https://openrouter.ai/api/v1", ("OPENROUTER_API_KEYS", "OPENROUTER_API_KEY"),
               "deepseek/deepseek-chat-v3.1:free", 20),
        Preset("openai", "https://api.openai.com/v1", ("OPENAI_API_KEYS", "OPENAI_API_KEY"), "gpt-4.1-mini", 0),
        Preset("custom", "", ("BABEL_CUSTOM_API_KEY",), "", 0),
    ]
}


def _keys_from_env(envs: tuple[str, ...]) -> list[str]:
    keys: list[str] = []
    for env in envs:
        keys += [k.strip() for k in os.getenv(env, "").split(",") if k.strip()]
    return list(dict.fromkeys(keys))


class _KeyState:
    def __init__(self, key: str, rpm: int):
        self.key = key
        self.interval = 60.0 / rpm if rpm else 0.0
        self.next_at = 0.0
        self.cooldown_until = 0.0


class Provider:
    """One OpenAI-compatible endpoint with a pool of keys."""

    def __init__(self, name: str, base_url: str, model: str, keys: list[str] | None = None, rpm: int = 0,
                 timeout: float = 180.0, transport: httpx.BaseTransport | None = None):
        if not base_url or not model:
            raise ValueError(f"provider {name!r} needs a base_url and a model")
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._keys = [_KeyState(k, rpm) for k in (keys or [""])]
        self._lock = threading.Lock()
        self._json_mode = True
        # hybrid reasoning models (Qwen3, R1-style) should answer directly, not think for 1000 tokens
        self._no_reasoning = bool(_REASONING_RE.search(model))
        self._http = httpx.Client(timeout=timeout, transport=transport)

    @property
    def label(self) -> str:
        return f"{self.name}:{self.model}"

    def _acquire(self) -> _KeyState:
        with self._lock:
            t = time.monotonic()
            ready = [k for k in self._keys if k.cooldown_until <= t]
            if not ready:
                raise RateLimited(f"{self.name}: all keys cooling down", min(k.cooldown_until for k in self._keys) - t)
            ready.sort(key=lambda k: k.next_at)
            ks = ready[0]
            wait = max(0.0, ks.next_at - t)
            ks.next_at = max(t, ks.next_at) + ks.interval
        if wait:
            time.sleep(wait)
        return ks

    def chat(self, messages: list[dict], *, schema: dict | None = None, max_tokens: int = 1024,
             temperature: float = 0.0, _retry: bool = True) -> Reply:
        ks = self._acquire()
        if _NO_THINK_RE.search(self.model) and messages and "/no_think" not in messages[-1]["content"]:
            # Qwen3 chat templates honor this soft switch (vLLM / NIM / LM Studio)
            messages = [*messages[:-1], {**messages[-1], "content": messages[-1]["content"] + "\n/no_think"}]
        body: dict = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        if self._no_reasoning:
            body["reasoning_effort"] = "none"
        if self._json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        if ks.key:
            headers["Authorization"] = f"Bearer {ks.key}"
        try:
            r = self._http.post(f"{self.base_url}/chat/completions", json=body, headers=headers)
        except httpx.HTTPError as e:
            raise LLMError(f"{self.name}: network error: {e}") from e
        if r.status_code == 429:
            ra = _retry_after(r)
            ks.cooldown_until = time.monotonic() + (ra or 20.0)
            raise RateLimited(f"{self.name}: rate limited", ra)
        if r.status_code in (401, 403):
            ks.cooldown_until = time.monotonic() + 3600
            raise LLMError(f"{self.name}: auth failed ({r.status_code}) — check the API key")
        if r.status_code == 400 and "reasoning_effort" in r.text and self._no_reasoning:
            self._no_reasoning = False
            return self.chat(messages, schema=schema, max_tokens=max_tokens, temperature=temperature, _retry=_retry)
        if r.status_code == 400 and "response_format" in r.text and self._json_mode:
            self._json_mode = False
            return self.chat(messages, schema=schema, max_tokens=max_tokens, temperature=temperature)
        if r.status_code >= 400:
            raise LLMError(f"{self.name}: HTTP {r.status_code}: {r.text[:300]}")
        try:
            data = r.json()
            choice = data["choices"][0]
            content = choice["message"].get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise LLMError(f"{self.name}: malformed response: {r.text[:300]}") from e
        content = _THINK_RE.sub("", content).strip()
        if not content:
            # reasoning models can spend the whole budget thinking: give them room once
            if _retry and choice.get("finish_reason") == "length":
                if not self._no_reasoning:
                    self._no_reasoning = True  # it was reasoning: ask it not to, from now on
                    return self.chat(messages, schema=schema, max_tokens=max_tokens, temperature=temperature, _retry=False)
                return self.chat(messages, schema=schema, max_tokens=max_tokens * 4 + 512,
                                 temperature=temperature, _retry=False)
            raise LLMError(f"{self.name}: empty response")
        usage = data.get("usage") or {}
        return Reply(content, self.name, self.model, usage.get("prompt_tokens") or 0, usage.get("completion_tokens") or 0)


def _retry_after(r: httpx.Response) -> float | None:
    try:
        v = r.headers.get("retry-after")
        return float(v) if v else None
    except ValueError:
        return None


def provider_from_preset(name: str, model: str | None = None) -> Provider | None:
    preset = PRESETS.get(name)
    if preset is None:
        raise ValueError(f"unknown provider {name!r}; choose from {', '.join(PRESETS)}")
    keys = _keys_from_env(preset.key_envs)
    base_url, model = preset.base_url, model or preset.model
    if name == "custom":
        base_url = os.getenv("BABEL_CUSTOM_BASE_URL", "")
        model = model or os.getenv("BABEL_CUSTOM_MODEL", "")
        if not base_url:
            return None
    elif not keys:
        return None
    rpm = int(os.getenv(f"BABEL_{name.upper()}_RPM", preset.rpm))
    return Provider(name, base_url, model, keys, rpm=rpm)


@dataclass
class Router:
    """Cloud chain: try providers in order; skip ones that are rate limited or failing."""

    providers: list[Provider]
    retries: int = 2
    on_event: Callable[[str], None] | None = None
    _sleep: Callable[[float], None] = field(default=time.sleep, repr=False)

    @property
    def label(self) -> str:
        return " → ".join(p.label for p in self.providers) or "none"

    def chat(self, messages: list[dict], **kw) -> Reply:
        if not self.providers:
            raise LLMError("no cloud provider configured")
        errors: list[str] = []
        min_wait: float | None = None
        for attempt in range(self.retries + 1):
            for p in self.providers:
                try:
                    return p.chat(messages, **kw)
                except RateLimited as e:
                    errors.append(str(e))
                    if e.retry_after is not None:
                        min_wait = e.retry_after if min_wait is None else min(min_wait, e.retry_after)
                except LLMError as e:
                    errors.append(str(e))
                    log.warning("%s", e)
            if attempt < self.retries:
                wait = min(max(min_wait or 0, 2.0 * (attempt + 1)), 90.0)
                if self.on_event:
                    self.on_event(f"cloud providers busy, retrying in {wait:.0f}s")
                self._sleep(wait)
                min_wait = None
        raise LLMError("; ".join(errors[-len(self.providers):]))


def build_cloud(order: list[str] | None = None, models: dict[str, str] | None = None) -> Router:
    models = models or {}
    if order and [n.lower() for n in order] in (["none"], ["off"], ["offline"]):
        return Router([])
    names = [n for n in (order or ["nvidia", "groq", "gemini", "openrouter", "openai", "custom"]) if n != "ollama"]
    return Router([p for n in names if (p := provider_from_preset(n, models.get(n))) is not None])
