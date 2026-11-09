"""Being a good citizen on the user's computer.

BABEL runs big models (a ~18 GB text model, ~14 GB of image models, a ~4 GB vision
model) on the same machine you work on. This module decides *when* that's OK:

- **memory**: never load a model unless there's room for it plus headroom, so the
  Mac doesn't start swapping; wait (and say so) instead;
- **idle**: background art only runs while you're away from the keyboard; anything
  you explicitly ask for runs right away;
- **power**: background art pauses on battery;
- **release**: models are unloaded as soon as they're not needed (see the callers).

Probes use built-in macOS tools (vm_stat, pmset, ioreg); elsewhere they report
"unknown" and the policies don't block.
"""

from __future__ import annotations

import os
import platform
import re
import subprocess
import time
from dataclasses import dataclass

import httpx

_MAC = platform.system() == "Darwin"


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout
    except Exception:
        return ""


def available_gb() -> float | None:
    """Memory that can be used without pushing other apps into swap (free + reclaimable)."""
    if _MAC:
        out = _run(["vm_stat"])
        m = re.search(r"page size of (\d+)", out)
        if not m:
            return None
        page = int(m.group(1))
        pages = {k.strip().lower(): int(v.strip(" .")) for k, v in re.findall(r"^([^:]+):\s+(\d+)\.?$", out, re.M)}
        free = sum(pages.get(k, 0) for k in ("pages free", "pages inactive", "pages speculative", "pages purgeable"))
        return free * page / 1e9
    try:
        with open("/proc/meminfo") as f:
            m = re.search(r"MemAvailable:\s+(\d+) kB", f.read())
        return int(m.group(1)) / 1e6 if m else None
    except OSError:
        return None


def pressure_level() -> int | None:
    """macOS memory pressure: 1 normal, 2 warning, 4 critical (what Activity Monitor's graph shows)."""
    if not _MAC:
        return None
    out = _run(["sysctl", "-n", "kern.memorystatus_vm_pressure_level"]).strip()
    return int(out) if out.isdigit() else None


def total_gb() -> float | None:
    if _MAC:
        out = _run(["sysctl", "-n", "hw.memsize"]).strip()
        return int(out) / 1e9 if out.isdigit() else None
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9
    except (ValueError, OSError):
        return None


def on_battery() -> bool | None:
    if not _MAC:
        return None
    out = _run(["pmset", "-g", "batt"])
    if not out:
        return None
    return "Battery Power" in out


def idle_seconds() -> float | None:
    """Seconds since the last keyboard/mouse input."""
    if not _MAC:
        return None
    m = re.search(r'"HIDIdleTime" = (\d+)', _run(["ioreg", "-c", "IOHIDSystem"]))
    return int(m.group(1)) / 1e9 if m else None


# ── Ollama ─────────────────────────────────────────────────────────────────
def ollama_loaded(base_url: str) -> dict[str, float]:
    """Models Ollama currently holds in memory → GB."""
    try:
        return {m["name"]: (m.get("size") or 0) / 1e9
                for m in httpx.get(f"{base_url}/api/ps", timeout=3).json().get("models", [])}
    except Exception:
        return {}


def ollama_size_gb(base_url: str, model: str) -> float | None:
    try:
        for m in httpx.get(f"{base_url}/api/tags", timeout=3).json().get("models", []):
            if m["name"] == model:
                return (m.get("size") or 0) / 1e9
    except Exception:
        pass
    return None


def ollama_unload(base_url: str, models: list[str] | None = None) -> list[str]:
    """Ask Ollama to drop models from memory now (all of them by default). Returns what was unloaded."""
    names = models if models is not None else list(ollama_loaded(base_url))
    done = []
    for name in names:
        try:
            httpx.post(f"{base_url}/api/generate", json={"model": name, "keep_alive": 0}, timeout=30)
            done.append(name)
        except Exception:
            pass
    return done


# ── policy ────────────────────────────────────────────────────────────────
@dataclass
class Policy:
    headroom_gb: float = 2.0          # always leave this much for you
    idle_after_s: float = 180.0       # "away" = no keyboard/mouse input for this long
    background_when: str = "idle"     # idle | always — when *automatic* art work may run
    pause_on_battery: bool = True     # automatic art work pauses on battery


class Governor:
    """Answers "may I load/run this now?" with None (yes) or a human-readable reason (not yet)."""

    def __init__(self, policy: Policy | None = None, *, ollama_url: str = "http://localhost:11434",
                 probes: dict | None = None):
        self.policy = policy or Policy()
        self.ollama_url = ollama_url
        p = probes or {}
        self._available = p.get("available_gb", available_gb)
        self._battery = p.get("on_battery", on_battery)
        self._idle = p.get("idle_seconds", idle_seconds)
        self._loaded = p.get("ollama_loaded", lambda: ollama_loaded(self.ollama_url))
        self._size = p.get("ollama_size_gb", lambda m: ollama_size_gb(self.ollama_url, m))
        self._pressure = p.get("pressure_level", pressure_level)

    def pressure(self) -> str | None:
        level = self._pressure()
        if level is not None and level >= 4:
            return "memory pressure is critical"
        if level is not None and level >= 2:
            return "memory is under pressure"
        return None

    def critical(self) -> bool:
        level = self._pressure()
        return level is not None and level >= 4

    def memory(self, need_gb: float) -> str | None:
        """May we load something of this size without squeezing your apps?"""
        if reason := self.pressure():
            return f"waiting: {reason}"
        avail = self._available()
        if avail is None or avail >= need_gb + self.policy.headroom_gb:
            return None
        return f"waiting for memory: {avail:.0f} GB free, needs {need_gb + self.policy.headroom_gb:.0f} GB"

    def ollama_need_gb(self, model: str) -> float:
        return (self._size(model) or 6.0) * 1.1 + 0.5  # weights + context/KV cache

    def ollama_model(self, model: str | None) -> str | None:
        """May the text/vision model be used? Fine if already loaded; otherwise it needs room."""
        if not model or model in self._loaded():
            return None
        return self.memory(self.ollama_need_gb(model))

    def pick_ollama_model(self, preferred: list[str]) -> str | None:
        """The best model in ``preferred`` that is loaded or fits right now (None if none fits)."""
        loaded = self._loaded()
        for m in preferred:
            if m in loaded or self.memory(self.ollama_need_gb(m)) is None:
                return m
        return None

    def background(self) -> str | None:
        """May *automatic* (not user-requested) work run right now?"""
        if self.policy.pause_on_battery and self._battery():
            return "paused on battery power — plug in to continue"
        if self.policy.background_when == "idle":
            idle = self._idle()
            if idle is not None and idle < self.policy.idle_after_s:
                mins = max(1, round(self.policy.idle_after_s / 60))
                return f"paused while you're using the computer — resumes after {mins} min away"
        return None

    def wait_until(self, check, *, timeout: float, poll: float = 5.0, stop=None) -> str | None:
        """Block until ``check()`` passes (returns None) or ``timeout``; returns the last reason."""
        deadline = time.time() + timeout
        reason = check()
        while reason and time.time() < deadline and not (stop and stop()):
            time.sleep(poll)
            reason = check()
        return reason


def status() -> dict:
    return {"available_gb": available_gb(), "total_gb": total_gb(), "pressure": pressure_level(),
            "on_battery": on_battery(), "idle_seconds": idle_seconds()}


# ── preferences you change at runtime (stored in the library, override the environment) ──
PREF_KEYS = ("background_when", "pause_on_battery", "idle_after_s")


def load_prefs(store, policy: Policy) -> Policy:
    row = store.one("SELECT value FROM meta WHERE key='prefs'")
    if row and row["value"]:
        import json

        for k, v in json.loads(row["value"]).items():
            if k in PREF_KEYS:
                setattr(policy, k, v)
    return policy


def save_prefs(store, policy: Policy, **changes) -> Policy:
    import json

    if "background_when" in changes and changes["background_when"] not in ("idle", "always"):
        raise ValueError("background_when must be idle or always")
    for k, v in changes.items():
        if k in PREF_KEYS and v is not None:
            setattr(policy, k, v)
    store.x("INSERT OR REPLACE INTO meta (key, value) VALUES ('prefs', ?)",
            (json.dumps({k: getattr(policy, k) for k in PREF_KEYS}),))
    return policy
