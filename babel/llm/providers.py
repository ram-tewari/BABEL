"""LLM providers.

Every supported backend speaks the OpenAI chat-completions protocol (NVIDIA NIM,
Groq, OpenRouter, Gemini's OpenAI endpoint, OpenAI, Ollama, LM Studio, vLLM...),
so one HTTP client covers all of them. ``Router`` chains providers with per-key
rate limiting, key rotation and fallback.
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
    """A request failed (after retries) on every configured provider."""


class RateLimited(LLMError):
    def __init__(self, msg: str, retry_after: float | None = None):
        super().__init__(msg)
        self.retry_after = retry_after


@dataclass(frozen=True)
class Preset:
    name: str
    base_url: str
    key_envs: tuple[str, ...]
    model: str
    rpm: int  # default requests/minute per key (0 = unlimited)
    needs_key: bool = True


PRESETS: dict[str, Preset] = {
    p.name: p
    for p in [
        Preset("nvidia", "https://integrate.api.nvidia.com/v1", ("NVIDIA_API_KEYS", "NVIDIA_API_KEY"), "qwen/qwen3-235b-a22b", 40),
        Preset("groq", "https://api.groq.com/openai/v1", ("GROQ_API_KEYS", "GROQ_API_KEY"), "llama-3.3-70b-versatile", 30),
        Preset("openrouter", "https://openrouter.ai/api/v1", ("OPENROUTER_API_KEYS", "OPENROUTER_API_KEY"), "meta-llama/llama-3.3-70b-instruct:free", 20),
        Preset("gemini", "https://generativelanguage.googleapis.com/v1beta/openai", ("GEMINI_API_KEYS", "GEMINI_API_KEY"), "gemini-2.5-flash", 10),
        Preset("openai", "https://api.openai.com/v1", ("OPENAI_API_KEYS", "OPENAI_API_KEY"), "gpt-4.1-mini", 0),
        Preset("ollama", "http://localhost:11434/v1", (), "qwen2.5:7b", 0, needs_key=False),
        Preset("custom", "", ("BABEL_CUSTOM_API_KEY",), "", 0, needs_key=False),
    ]
}

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


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

    def __init__(
        self,
        name: str,
        base_url: str,
        model: str,
        keys: list[str] | None = None,
        rpm: int = 0,
        timeout: float = 180.0,
        transport: httpx.BaseTransport | None = None,
    ):
        if not base_url or not model:
            raise ValueError(f"provider {name!r} needs a base_url and a model")
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._keys = [_KeyState(k, rpm) for k in (keys or [""])]
        self._idx = 0
        self._lock = threading.Lock()
        self._json_mode = True
        self._http = httpx.Client(timeout=timeout, transport=transport)

    @property
    def label(self) -> str:
        return f"{self.name}:{self.model}"

    def _acquire(self) -> _KeyState:
        """Pick the next key that is not cooling down, waiting for its rate slot."""
        with self._lock:
            now = time.monotonic()
            ready = [k for k in self._keys if k.cooldown_until <= now]
            if not ready:
                soonest = min(k.cooldown_until for k in self._keys)
                raise RateLimited(f"{self.name}: all keys cooling down", soonest - now)
            # round-robin among ready keys, preferring the earliest available slot
            ready.sort(key=lambda k: k.next_at)
            ks = ready[0]
            wait = max(0.0, ks.next_at - now)
            ks.next_at = max(now, ks.next_at) + ks.interval
        if wait:
            time.sleep(wait)
        return ks

    def chat(self, messages: list[dict], *, json_mode: bool = True, temperature: float = 0.2, max_tokens: int = 4096) -> str:
        ks = self._acquire()
        body: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode and self._json_mode:
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
        if r.status_code == 400 and "response_format" in r.text and self._json_mode:
            self._json_mode = False  # model has no JSON mode; the prompt still asks for JSON
            return self.chat(messages, json_mode=False, temperature=temperature, max_tokens=max_tokens)
        if r.status_code >= 400:
            raise LLMError(f"{self.name}: HTTP {r.status_code}: {r.text[:300]}")
        try:
            content = r.json()["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise LLMError(f"{self.name}: malformed response: {r.text[:300]}") from e
        content = _THINK_RE.sub("", content).strip()
        if not content:
            raise LLMError(f"{self.name}: empty response")
        return content


def _retry_after(r: httpx.Response) -> float | None:
    v = r.headers.get("retry-after")
    try:
        return float(v) if v else None
    except ValueError:
        return None


def provider_from_preset(name: str, model: str | None = None) -> Provider | None:
    """Build a provider from its preset + environment, or None if it isn't configured."""
    preset = PRESETS.get(name)
    if preset is None:
        raise ValueError(f"unknown provider {name!r}; choose from {', '.join(PRESETS)}")
    keys = _keys_from_env(preset.key_envs)
    base_url = preset.base_url
    model = model or preset.model
    if name == "ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", base_url)
        model = os.getenv("OLLAMA_MODEL", model) if model == preset.model else model
    if name == "custom":
        base_url = os.getenv("BABEL_CUSTOM_BASE_URL", "")
        model = model or os.getenv("BABEL_CUSTOM_MODEL", "")
        if not base_url:
            return None
    if preset.needs_key and not keys:
        return None
    rpm = int(os.getenv(f"BABEL_{name.upper()}_RPM", preset.rpm))
    return Provider(name, base_url, model, keys, rpm=rpm)


def ollama_available(base_url: str | None = None) -> bool:
    url = (base_url or os.getenv("OLLAMA_BASE_URL", PRESETS["ollama"].base_url)).rstrip("/")
    try:
        return httpx.get(url.removesuffix("/v1") + "/api/tags", timeout=1.0).status_code == 200
    except httpx.HTTPError:
        return False


@dataclass
class Router:
    """Try providers in order; skip ones that are rate limited or failing."""

    providers: list[Provider]
    retries: int = 2
    on_event: Callable[[str], None] | None = None
    _sleep: Callable[[float], None] = field(default=time.sleep, repr=False)

    @property
    def label(self) -> str:
        return " → ".join(p.label for p in self.providers) or "none"

    def chat(self, messages: list[dict], **kw) -> tuple[str, str]:
        """Return (content, provider_label)."""
        if not self.providers:
            raise LLMError("no LLM provider configured")
        errors: list[str] = []
        min_wait: float | None = None
        for attempt in range(self.retries + 1):
            for p in self.providers:
                try:
                    return p.chat(messages, **kw), p.label
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
                    self.on_event(f"all providers busy, retrying in {wait:.0f}s")
                self._sleep(wait)
                min_wait = None
        raise LLMError("; ".join(errors[-len(self.providers):]))


def build_router(order: list[str] | None = None, models: dict[str, str] | None = None) -> Router:
    """Build the provider chain from settings/env. Auto-detects when ``order`` is empty."""
    models = models or {}
    names = order or ["nvidia", "groq", "gemini", "openrouter", "openai", "custom", "ollama"]
    providers: list[Provider] = []
    for name in names:
        if name == "ollama" and not order and not ollama_available():
            continue
        p = provider_from_preset(name, models.get(name))
        if p is not None:
            providers.append(p)
    return Router(providers)
