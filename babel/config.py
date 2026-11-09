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
    # character art: "auto" uses the art environment (.venv-art with mflux) if it exists; "off" disables
    art: str = "auto"
    art_python: Path | None = None
    # quality checker: a vision model in Ollama ("auto" = best installed of qwen3-vl:8b-instruct, …; "off")
    vision: str = "auto"
    # being polite to the computer: automatic art work only while you're away / on mains power
    background: str = "idle"  # idle | always
    idle_minutes: float = 3.0
    pause_on_battery: bool = True
    headroom_gb: float = 2.0

    @property
    def art_dir(self) -> Path:
        return self.data_dir / "art"

    def art_python_path(self) -> Path | None:
        """The art environment's Python, if character art is enabled and installed."""
        if self.art.lower() in ("off", "none", "0", "false"):
            return None
        p = self.art_python or Path(".venv-art/bin/python")
        return p if p.exists() else None

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
            art=e("BABEL_ART", "auto"),
            art_python=Path(e("BABEL_ART_PYTHON")) if e("BABEL_ART_PYTHON") else None,
            vision=e("BABEL_VISION_MODEL", "auto"),
            background=e("BABEL_BACKGROUND", "idle"),
            idle_minutes=float(e("BABEL_IDLE_MINUTES", "3")),
            pause_on_battery=e("BABEL_PAUSE_ON_BATTERY", "1").lower() not in ("0", "false", "no", "off"),
            headroom_gb=float(e("BABEL_HEADROOM_GB", "2")),
        )

    def policy(self):
        from babel.system import Policy

        return Policy(headroom_gb=self.headroom_gb, idle_after_s=self.idle_minutes * 60,
                      background_when=self.background, pause_on_battery=self.pause_on_battery)

    def build_cascade(self):
        from babel.llm.providers import build_cloud, build_local
        from babel.scenario.cascade import Cascade, Policy

        return Cascade(
            local=build_local(self.local, self.local_model),
            cloud=build_cloud(self.providers, self.models),
            policy=Policy(accept=self.accept, escalate=self.escalate, review=self.review, summaries=self.summaries),
            summary_window=self.summary_window,
        )
