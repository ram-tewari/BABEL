"""LLM labeling: the model classifies numbered segments instead of rewriting text.

Output is tiny compared to the chapter (only non-narration segments are listed),
so long chapters never truncate, free-tier token budgets go ~10x further, and
the model cannot drop or invent prose.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from babel.models import BlockType, CharacterHint, Segment, SegmentKind

SYSTEM_PROMPT = """You annotate webnovel chapters for a chat-style "visual scenario" reader.

The chapter has been split into numbered segments. Each line is:
  <id>|<hint>| <text>
hint: q = inside quotation marks, e = *italic* in the source, b = [bracketed], p = plain prose, k = scene break.

Label segments with one of these types:
  d  dialogue  — words spoken aloud (give the speaker)
  t  thought   — a character's unspoken inner voice (give the speaker)
  s  system    — game/system windows, notifications, status panels, quest text
  x  sfx       — sound effects / onomatopoeia ("BOOM!", "Clang—")
  g  tag       — a speech tag around dialogue ("he said, frowning")
  n  narration — everything else (description, action, exposition)

Rules:
- List ONLY segments that are not plain narration. Anything you omit is narration.
- Always list every q segment (dialogue, or another type if it is not speech, e.g. a quoted sign is n).
- speaker: the character's canonical name from the CAST list when they are in it; otherwise the most
  specific name the text supports ("Old Neil", "the guard captain"). Use "?" only if truly unknowable.
  Resolve pronouns and unattributed lines from context and turn-taking.
- A run of consecutive segments with the same label can be given as "ids": "12-15".
- Report characters who speak or are named for the first time (not already in CAST), with aliases the
  text uses for them (nicknames, titles, surnames).
- summary: 1–2 sentences on what happens in this part, for continuity with later chapters.

Reply with JSON only:
{"labels":[{"id":3,"type":"d","speaker":"Klein"},{"ids":"7-8","type":"s"}],
 "characters":[{"name":"Klein Moretti","aliases":["Klein","Zhou Mingrui"],"note":"protagonist, transmigrator"}],
 "summary":"..."}"""

_HINT = {
    SegmentKind.QUOTE: "q",
    SegmentKind.EMPHASIS: "e",
    SegmentKind.BRACKET: "b",
    SegmentKind.PROSE: "p",
    SegmentKind.BREAK: "k",
}


@dataclass
class StoryContext:
    """What the model should know before reading this chunk (the Akashic Record view)."""

    cast: list[str] = field(default_factory=list)  # formatted cast lines
    story_so_far: list[str] = field(default_factory=list)  # recent chapter summaries
    pov: str | None = None
    chapter_title: str | None = None


def build_messages(segments: list[Segment], ctx: StoryContext) -> list[dict]:
    parts: list[str] = []
    if ctx.cast:
        parts.append("CAST (canonical name — aliases — notes):\n" + "\n".join(f"- {c}" for c in ctx.cast))
    if ctx.pov:
        parts.append(f"Point-of-view character (default speaker of unattributed thoughts): {ctx.pov}")
    if ctx.story_so_far:
        parts.append("STORY SO FAR:\n" + "\n".join(f"- {s}" for s in ctx.story_so_far))
    if ctx.chapter_title:
        parts.append(f"CHAPTER: {ctx.chapter_title}")
    lines = [f"{s.id}|{_HINT[s.kind]}| {s.text}" for s in segments]
    parts.append("SEGMENTS:\n" + "\n".join(lines))
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


@dataclass
class LabelResult:
    labels: dict[int, tuple[BlockType, str | None]]
    characters: list[CharacterHint]
    summary: str | None


class ParseError(ValueError):
    pass


_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")
_RANGE_RE = re.compile(r"^\s*(\d+)\s*(?:-|–|\.\.)\s*(\d+)\s*$")
_UNKNOWN = {"?", "", "unknown", "none", "null", "n/a", "narrator"}


def extract_json(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end <= start:
        raise ParseError("no JSON object in response")
    t = t[start : end + 1]
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        try:
            return json.loads(_TRAILING_COMMA_RE.sub(r"\1", t))
        except json.JSONDecodeError as e:
            raise ParseError(f"invalid JSON: {e}") from e


def _ids(item: dict) -> list[int]:
    raw = item.get("ids", item.get("id"))
    out: list[int] = []
    values = raw if isinstance(raw, list) else [raw]
    for v in values:
        if isinstance(v, int):
            out.append(v)
        elif isinstance(v, str):
            m = _RANGE_RE.match(v)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                if 0 <= b - a <= 500:
                    out.extend(range(a, b + 1))
            elif v.strip().isdigit():
                out.append(int(v))
            else:  # "3,4,5"
                out.extend(int(x) for x in re.findall(r"\d+", v))
    return out


def parse_response(text: str, valid_ids: set[int]) -> LabelResult:
    data = extract_json(text)
    if not isinstance(data, dict):
        raise ParseError("response is not an object")
    raw_labels = data.get("labels") or data.get("segments") or []
    if not isinstance(raw_labels, list):
        raise ParseError("'labels' is not a list")
    labels: dict[int, tuple[BlockType, str | None]] = {}
    for item in raw_labels:
        if not isinstance(item, dict):
            continue
        btype = BlockType.parse(item.get("type"))
        if btype is None:
            continue
        speaker = item.get("speaker")
        speaker = str(speaker).strip() if speaker is not None else None
        if speaker and speaker.lower() in _UNKNOWN:
            speaker = None
        if btype not in (BlockType.DIALOGUE, BlockType.THOUGHT):
            speaker = None
        for i in _ids(item):
            if i in valid_ids:
                labels[i] = (btype, speaker)

    chars: list[CharacterHint] = []
    for c in data.get("characters") or []:
        if isinstance(c, dict) and isinstance(c.get("name"), str) and c["name"].strip():
            aliases = [a.strip() for a in c.get("aliases") or [] if isinstance(a, str) and a.strip()]
            note = c.get("note") if isinstance(c.get("note"), str) else None
            chars.append(CharacterHint(name=c["name"].strip(), aliases=aliases, note=note))
    summary = data.get("summary")
    return LabelResult(labels, chars, summary.strip() if isinstance(summary, str) and summary.strip() else None)
