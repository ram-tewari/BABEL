"""Unit tests for the OpenAI-compatible NVIDIA NIM client."""

import json
from unittest.mock import MagicMock, patch

import pytest

from babel.transform.nvidia_client import NvidiaClient, RateLimitError
from babel.transform.ollama_client import OllamaClient


def _make_response(content: str):
    """Build a fake OpenAI chat-completion response object."""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    return resp


@pytest.fixture
def patched_openai():
    """Patch the OpenAI SDK used by the base client; yield the instance mock."""
    with patch("babel.transform.openai_compatible_client.OpenAI") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        yield instance


class TestConfiguration:
    def test_missing_keys_raises(self, monkeypatch):
        monkeypatch.delenv("NVIDIA_API_KEYS", raising=False)
        with pytest.raises(ValueError, match="No API keys"):
            NvidiaClient()

    def test_explicit_key_and_defaults(self, patched_openai):
        client = NvidiaClient(api_key="nvapi-test")
        assert client.model_name == "qwen/qwen3-235b-a22b"
        assert client.base_url == "https://integrate.api.nvidia.com/v1"

    def test_model_alias_resolution(self, patched_openai):
        client = NvidiaClient(api_key="nvapi-test", model_name="deepseek")
        assert client.model_name == "deepseek-ai/deepseek-v3.1"

    def test_full_model_id_passthrough(self, patched_openai):
        client = NvidiaClient(api_key="nvapi-test", model_name="meta/llama-3.1-8b-instruct")
        assert client.model_name == "meta/llama-3.1-8b-instruct"

    def test_keys_from_env_csv(self, patched_openai, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEYS", "k1, k2 , k3")
        client = NvidiaClient()
        assert client.api_keys == ["k1", "k2", "k3"]


class TestTransform:
    def test_successful_transform(self, patched_openai):
        payload = {"blocks": [{"type": "narrator", "content": "Hi"}]}
        patched_openai.chat.completions.create.return_value = _make_response(
            json.dumps(payload)
        )
        client = NvidiaClient(api_key="nvapi-test")
        assert client.transform_text("text", "system") == payload

    def test_strips_think_block(self, patched_openai):
        content = '<think>reasoning here</think>{"blocks": []}'
        patched_openai.chat.completions.create.return_value = _make_response(content)
        client = NvidiaClient(api_key="nvapi-test")
        assert client.transform_text("t", "s") == {"blocks": []}

    def test_strips_json_fence(self, patched_openai):
        content = '```json\n{"blocks": [1]}\n```'
        patched_openai.chat.completions.create.return_value = _make_response(content)
        client = NvidiaClient(api_key="nvapi-test")
        assert client.transform_text("t", "s") == {"blocks": [1]}

    def test_rotates_key_on_rate_limit(self, patched_openai):
        good = _make_response('{"blocks": []}')
        patched_openai.chat.completions.create.side_effect = [
            Exception("429 rate limit exceeded"),
            good,
        ]
        client = NvidiaClient(api_key="k1")
        client.api_keys = ["k1", "k2"]
        client.current_key_index = 0
        with patch("time.sleep"):
            result = client.transform_text("t", "s")
        assert result == {"blocks": []}
        assert client.current_key_index == 1  # rotated

    def test_drops_json_mode_when_unsupported(self, patched_openai):
        good = _make_response('{"blocks": []}')
        patched_openai.chat.completions.create.side_effect = [
            Exception("response_format is not supported by this model"),
            good,
        ]
        client = NvidiaClient(api_key="nvapi-test")
        with patch("time.sleep"):
            result = client.transform_text("t", "s")
        assert result == {"blocks": []}
        assert client._use_json_mode is False

    def test_raises_after_max_retries(self, patched_openai):
        patched_openai.chat.completions.create.side_effect = Exception("boom")
        client = NvidiaClient(api_key="nvapi-test")
        with patch("time.sleep"), pytest.raises(Exception):
            client.transform_text("t", "s", max_retries=2)


class TestOllamaClient:
    def test_defaults_and_placeholder_key(self, patched_openai, monkeypatch):
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
        client = OllamaClient()
        assert client.base_url == "http://localhost:11434/v1"
        assert client.api_keys == ["ollama"]
