"""Deterministic character styling (colors, lanes, classes, tone emoji).

All functions use a stable MD5-based hash so the same character name always
maps to the same color/lane/class across sessions, processes and machines.
The TypeScript port lives in babel-ui/src/lib/style.ts and must stay in sync.

Reconstructed from babel-ui/src/lib/style.ts (which documents the exact
original Python) and the render test suite.
"""

import hashlib
from typing import Optional


def get_stable_hash(s: str) -> int:
    """Stable 128-bit integer hash of a string (MD5, for determinism)."""
    return int(hashlib.md5(s.encode("utf-8")).hexdigest(), 16)


def get_character_color(character_name: str) -> str:
    """Deterministic HSL color for a character name.

    Hue spans the full spectrum; saturation 65-75% and lightness 70-75% keep
    colors vibrant and WCAG-AA readable on the dark (#1a1a1a) background.
    Empty name -> neutral grey.
    """
    if not character_name:
        return "hsl(0, 0%, 70%)"

    stable_hash = get_stable_hash(character_name)
    hue = stable_hash % 360
    saturation = 65 + (stable_hash % 11)  # 65-75%
    lightness = 70 + (stable_hash % 6)    # 70-75%
    return f"hsl({hue}, {saturation}%, {lightness}%)"


def get_character_lane(character_name: Optional[str]) -> str:
    """Stable conversation lane: 'left', 'right', or 'center' (null/empty)."""
    if not character_name:
        return "center"
    return "right" if get_stable_hash(character_name) % 2 == 0 else "left"


def get_char_class(character_name: Optional[str]) -> str:
    """Stable CSS class name ('char-<16hexhash>' or 'char-none')."""
    if not character_name:
        return "char-none"
    hash_hex = format(get_stable_hash(character_name), "x")[:16]
    return f"char-{hash_hex}"


def get_tone_emoji(tone: Optional[str]) -> str:
    """Map a tone keyword to a floating emoji indicator (or '')."""
    if not tone:
        return ""

    tone_lower = tone.lower()

    if any(k in tone_lower for k in ["angry", "furious", "rage", "mad", "irritated"]):
        return "💢"
    if any(k in tone_lower for k in ["sad", "cry", "sob", "weep", "tears"]):
        return "💧"
    if any(k in tone_lower for k in ["laugh", "happy", "joy", "cheerful", "amused", "giggle"]):
        return "✨"
    if any(k in tone_lower for k in ["shock", "gasp", "surprise", "astonish", "startle"]):
        return "❗"
    if any(k in tone_lower for k in ["whisper", "quiet", "murmur", "soft"]):
        return "🤫"
    if any(k in tone_lower for k in ["shout", "yell", "scream", "roar", "bellow"]):
        return "📢"

    return ""
