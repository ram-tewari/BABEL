"""Runtime configuration from environment variables (and an optional .env)."""

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
    # cloud tier: ordered provider chain ("nvidia,groq"); empty = every configured one; "none" = off
    providers: list[str] = field(default_factory=list)
    models: dict[str, str] = field(default_factory=dict)
    # local tier: "auto" uses Ollama when it's running; "off" disables
    local: str = "auto"
    local_model: str | None = None
    # cascade policy
    accept: float = 0.9
    escalate: float = 0.75
    review: float = 0.6
    summaries: str = "local"  # local | cloud | off
    # throughput
    concurrency: int = 2  # chapters in flight per novel
    parallel_novels: int = 2  # novels transformed at the same time
    summary_window: int = 3
    host: str = "127.0.0.1"
    port: int = 8000

    @property
    def db_path(self) -> Path:
        return self.data_dir / "babel.db"

    @property
    def covers_dir(self) -> Path:
        return self.data_dir / "covers"

    @property
    def portraits_dir(self) -> Path:
        return self.data_dir / "portraits"

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()
        e = os.getenv
        models = {n: m for n in ("nvidia", "groq", "openrouter", "openai", "gemini", "custom")
                  if (m := e(f"BABEL_{n.upper()}_MODEL"))}
        return cls(
            data_dir=Path(e("BABEL_DATA_DIR", "data")),
            providers=_csv(e("BABEL_PROVIDERS")),
            models=models,
            local=e("BABEL_LOCAL", "auto"),
            local_model=e("BABEL_LOCAL_MODEL") or None,
            accept=float(e("BABEL_ACCEPT", "0.9")),
            escalate=float(e("BABEL_ESCALATE", "0.75")),
            review=float(e("BABEL_REVIEW", "0.6")),
            summaries=e("BABEL_SUMMARIES", "local"),
            concurrency=max(1, int(e("BABEL_CONCURRENCY", "2"))),
            parallel_novels=max(1, int(e("BABEL_PARALLEL_NOVELS", "2"))),
            summary_window=int(e("BABEL_SUMMARY_WINDOW", "3")),
            host=e("BABEL_HOST", "127.0.0.1"),
            port=int(e("BABEL_PORT", "8000")),
        )

    def build_cascade(self):
        from babel.llm.providers import build_cloud, build_local
        from babel.scenario.cascade import Cascade, Policy

        return Cascade(
            local=build_local(self.local, self.local_model),
            cloud=build_cloud(self.providers, self.models),
            policy=Policy(accept=self.accept, escalate=self.escalate, review=self.review, summaries=self.summaries),
            summary_window=self.summary_window,
        )
