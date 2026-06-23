"""Shared base client for any OpenAI-compatible chat-completions endpoint.

NVIDIA NIM, Ollama and many other backends all expose the same
``/v1/chat/completions`` contract, so a single implementation can drive all of
them by varying the ``base_url``, API key(s) and model name.

Features:
- Rotation across a comma-separated list of API keys (resilience to per-key
  rate limits / quota exhaustion).
- Exponential backoff on rate-limit (429) responses.
- Defensive stripping of ``<think>...</think>`` reasoning blocks that some
  models (Qwen3, DeepSeek, Nemotron) emit before their JSON answer.
- Graceful fallback when a model does not support native JSON mode
  (``response_format``): the request is retried once without it.
"""

import os
import re
import json
import time

from dotenv import load_dotenv
from openai import OpenAI


class RateLimitError(Exception):
    """Raised when rate limit is exceeded after all retries."""
    pass


# Some reasoning models wrap their chain-of-thought in <think>...</think>
# before emitting the final JSON. Strip it so json.loads succeeds.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class OpenAICompatibleClient:
    """Base client for OpenAI-compatible chat-completions APIs.

    Subclasses configure the endpoint via the class attributes below.
    """

    DEFAULT_BASE_URL: str = None
    DEFAULT_MODEL: str = None
    KEYS_ENV_VAR: str = None  # comma-separated list of keys
    PROVIDER_NAME: str = "openai-compatible"

    # Optional friendly-name -> model-id aliases (overridden by subclasses).
    MODELS: dict = {}

    def __init__(self, api_key: str = None, model_name: str = None, base_url: str = None):
        load_dotenv()

        self.base_url = base_url or self.DEFAULT_BASE_URL

        # Resolve model (allow friendly aliases like "qwen" / "deepseek").
        resolved = model_name or self.DEFAULT_MODEL
        self.model_name = self.MODELS.get(resolved, resolved)

        # Collect API keys: explicit param wins, else the env var (CSV).
        if api_key:
            self.api_keys = [api_key]
        else:
            raw = os.getenv(self.KEYS_ENV_VAR or "", "")
            self.api_keys = [k.strip() for k in raw.split(",") if k.strip()]

        if not self.api_keys:
            raise ValueError(
                f"No API keys found for {self.PROVIDER_NAME}. "
                f"Set {self.KEYS_ENV_VAR} (comma-separated) or pass api_key."
            )

        self.current_key_index = 0
        self._use_json_mode = True
        self._build_client()

    def _build_client(self):
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_keys[self.current_key_index],
        )

    def rotate_api_key(self):
        """Rotate to the next configured API key."""
        if len(self.api_keys) <= 1:
            return
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self._build_client()
        print(f"    🔄 Rotated to API key {self.current_key_index + 1}/{len(self.api_keys)}")

    def _completion_kwargs(self) -> dict:
        """Hook for provider-specific request params (overridable)."""
        return {}

    @staticmethod
    def _extract_json(content: str) -> dict:
        """Parse JSON from a model response, tolerating reasoning blocks/fences."""
        cleaned = _THINK_RE.sub("", content).strip()

        # Strip ```json ... ``` fences if present.
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").strip()
            if cleaned[:4].lower() == "json":
                cleaned = cleaned[4:].strip()

        return json.loads(cleaned)

    def generate_content(self, prompt: str, max_retries: int = 5) -> str:
        """Return the raw text completion for a single prompt.

        Mirrors GeminiClient.generate_content so provider-agnostic callers
        (e.g. the Cartographer) can use any OpenAI-compatible backend.
        """
        last_err = None
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=8000,
                    **self._completion_kwargs(),
                )
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Empty response from API")
                return _THINK_RE.sub("", content).strip()
            except Exception as e:
                last_err = e
                msg = str(e).lower()
                is_rate = "429" in msg or "rate limit" in msg or "rate_limit" in msg or "quota" in msg
                if is_rate:
                    self.rotate_api_key()
                    wait = min(2 ** attempt, 30)
                    print(f"    ⚠️  Rate limit hit, waiting {wait}s...")
                    time.sleep(wait)
                    continue
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                raise
        raise RateLimitError(f"Failed after {max_retries} attempts: {last_err}")

    def transform_text(self, text: str, system_prompt: str, max_retries: int = 5) -> dict:
        """Transform text into the Visual Scenario JSON structure."""
        last_err = None

        for attempt in range(max_retries):
            try:
                kwargs = dict(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text},
                    ],
                    temperature=0.3,
                    max_tokens=8000,
                    **self._completion_kwargs(),
                )
                if self._use_json_mode:
                    kwargs["response_format"] = {"type": "json_object"}

                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Empty response from API")

                return self._extract_json(content)

            except json.JSONDecodeError as e:
                last_err = e
                print(f"    ⚠️  JSON decode error (attempt {attempt + 1}/{max_retries})")
                time.sleep(2)
                continue

            except Exception as e:
                last_err = e
                msg = str(e).lower()

                # Model doesn't support native JSON mode: drop it and retry.
                if self._use_json_mode and "response_format" in msg:
                    print("    ⚠️  Model lacks JSON mode, retrying without it...")
                    self._use_json_mode = False
                    continue

                is_auth = "401" in msg or "invalid_api_key" in msg or "unauthorized" in msg
                is_rate = "429" in msg or "rate limit" in msg or "rate_limit" in msg or "quota" in msg

                if is_auth and len(self.api_keys) > 1:
                    print("    ⚠️  Auth error, rotating key...")
                    self.rotate_api_key()
                    continue

                if is_rate:
                    self.rotate_api_key()  # no-op if single key
                    wait = min(2 ** attempt, 30)
                    print(f"    ⚠️  Rate limit hit, waiting {wait}s...")
                    time.sleep(wait)
                    continue

                if attempt < max_retries - 1:
                    print(f"    ⚠️  Error (attempt {attempt + 1}/{max_retries}): {str(e)[:100]}")
                    time.sleep(2)
                    continue
                raise

        raise RateLimitError(f"Failed after {max_retries} attempts: {last_err}")
