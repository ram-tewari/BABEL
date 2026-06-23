"""NVIDIA NIM client for LLM-based text transformation.

Uses the free, OpenAI-compatible hosted catalog at build.nvidia.com
(base URL ``https://integrate.api.nvidia.com/v1``). Sign up for the NVIDIA
Developer Program, generate an API key (prefixed ``nvapi-``) and put one or
more keys (comma-separated) in the ``NVIDIA_API_KEYS`` environment variable.

Free tier: 40 RPM by default (200 RPM available on request) — far above
BABEL's ~1,500 chapters/day target, so we can afford a top-tier model.
"""

from babel.transform.openai_compatible_client import (
    OpenAICompatibleClient,
    RateLimitError,  # re-exported for callers/tests
)

__all__ = ["NvidiaClient", "RateLimitError"]


class NvidiaClient(OpenAICompatibleClient):
    """Client for the NVIDIA NIM hosted API."""

    DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
    # Best-quality default for nuanced speaker/tone attribution. Thinking
    # output (if any) is stripped defensively by the base client.
    DEFAULT_MODEL = "qwen/qwen3-235b-a22b"
    KEYS_ENV_VAR = "NVIDIA_API_KEYS"
    PROVIDER_NAME = "nvidia"

    # Curated high-quality models on the NVIDIA NIM free tier.
    # Pass any of these friendly names (or a full model id) as model_name.
    MODELS = {
        "qwen": "qwen/qwen3-235b-a22b",
        "deepseek": "deepseek-ai/deepseek-v3.1",
        "llama": "meta/llama-3.3-70b-instruct",
        "mistral-nemotron": "mistralai/mistral-nemotron",
        "nemotron": "nvidia/llama-3.3-nemotron-super-49b-v1",
    }
