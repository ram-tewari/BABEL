"""Ollama client for local, fully-offline LLM transformation.

Ollama exposes an OpenAI-compatible endpoint at ``http://localhost:11434/v1``
and ignores the API key. Override the host with ``OLLAMA_BASE_URL`` and the
default model with the ``model_name`` argument or ``OLLAMA_MODEL``.
"""

import os

from babel.transform.openai_compatible_client import (
    OpenAICompatibleClient,
    RateLimitError,  # re-exported for callers/tests
)

__all__ = ["OllamaClient", "RateLimitError"]


class OllamaClient(OpenAICompatibleClient):
    """Client for a local Ollama server (OpenAI-compatible mode)."""

    DEFAULT_BASE_URL = "http://localhost:11434/v1"
    DEFAULT_MODEL = "llama3.1"
    KEYS_ENV_VAR = "OLLAMA_API_KEYS"  # unused by Ollama; kept for symmetry
    PROVIDER_NAME = "ollama"

    def __init__(self, api_key: str = None, model_name: str = None, base_url: str = None):
        # Ollama needs no real key, so supply a placeholder if none is set.
        super().__init__(
            api_key=api_key or os.getenv("OLLAMA_API_KEY") or "ollama",
            model_name=model_name or os.getenv("OLLAMA_MODEL"),
            base_url=base_url or os.getenv("OLLAMA_BASE_URL"),
        )
