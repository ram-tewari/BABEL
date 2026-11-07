"""Runtime configuration, read from environment variables (and an optional .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _csv(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path("data"))
    # Ordered provider chain, e.g. "nvidia,groq,ollama". Empty = auto-detect.
    providers: list[str] = field(default_factory=list)
    # Optional per-provider model overrides, e.g. {"nvidia": "deepseek-ai/deepseek-v3.1"}.
    models: dict[str, str] = field(default_factory=dict)
    # Number of chapters transformed concurrently per job.
    concurrency: int = 2
    # Max source tokens per LLM request (a chapter larger than this is split).
    chunk_tokens: int = 6000
    # Previous-chapter summaries injected as "story so far" context.
    summary_window: int = 3
    host: str = "127.0.0.1"
    port: int = 8000

    @property
    def db_path(self) -> Path:
        return self.data_dir / "babel.db"

    @property
    def covers_dir(self) -> Path:
        return self.data_dir / "covers"

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()
        models = {}
        for name in ("nvidia", "groq", "openrouter", "openai", "ollama", "gemini", "custom"):
            m = os.getenv(f"BABEL_{name.upper()}_MODEL")
            if m:
                models[name] = m
        return cls(
            data_dir=Path(os.getenv("BABEL_DATA_DIR", "data")),
            providers=_csv(os.getenv("BABEL_PROVIDERS")),
            models=models,
            concurrency=max(1, int(os.getenv("BABEL_CONCURRENCY", "2"))),
            chunk_tokens=int(os.getenv("BABEL_CHUNK_TOKENS", "6000")),
            summary_window=int(os.getenv("BABEL_SUMMARY_WINDOW", "3")),
            host=os.getenv("BABEL_HOST", "127.0.0.1"),
            port=int(os.getenv("BABEL_PORT", "8000")),
        )
