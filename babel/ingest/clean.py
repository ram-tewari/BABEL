"""Text cleanup shared by all ingesters."""

from __future__ import annotations

import re
import unicodedata

CHAPTER_HEADING_RE = re.compile(
    r"""^\s*(?:
        (?:chapter|ch\.?|episode|ep\.?|part|book|volume|vol\.?)\s*[\dIVXLCivxlc一二三四五六七八九十百千零]+
        |第\s*[\d一二三四五六七八九十百千零〇两]+\s*[章回节話话]
        |\d{1,5}\s*[.:：、\-–—]\s*\S
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# Lines injected by aggregator sites / scanlators. Only whole lines are removed.
_JUNK_LINE_RES = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"^\s*(?:https?://|www\.)\S+\s*$",
        r"^.{0,40}\b(?:read|find|visit)\b.{0,40}\b(?:at|on)\b.{0,30}\.(?:com|net|org|co|io)\b.{0,40}$",
        r"^.{0,60}\b(?:novel(?:full|bin|updates|fire|hall)|lightnovel\w*|webnovel|wuxiaworld|boxnovel|readnovel\w*|freewebnovel)\b.{0,60}$",
        r"^\s*(?:this chapter (?:is|was) (?:updated|uploaded|translated) by|support (?:the|us) (?:at|on)|if you find any errors).{0,120}$",
        r"^\s*(?:previous|next)\s+chapter\s*(?:\|.*)?$",
        r"^\s*(?:table of contents|toc)\s*$",
        r"^\s*[†‡§¶※]+\s*$",  # orphaned footnote markers
    ]
]
_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_SPACES_RE = re.compile(r"[ \t 　]+")


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("​", "").replace("﻿", "")
    lines = []
    for line in text.split("\n"):
        line = _SPACES_RE.sub(" ", line).strip()
        if line and any(rx.match(line) for rx in _JUNK_LINE_RES):
            continue
        lines.append(line)
    out = "\n".join(lines)
    return _MULTI_BLANK_RE.sub("\n\n", out).strip()


def is_heading(line: str) -> bool:
    line = line.strip()
    return 0 < len(line) <= 120 and bool(CHAPTER_HEADING_RE.match(line))


def drop_leading_title(text: str, title: str) -> str:
    """Remove the chapter title when it is repeated as the first line of the body."""
    first, _, rest = text.partition("\n")
    norm = lambda s: re.sub(r"\W+", "", s).lower()  # noqa: E731
    if first and title and (norm(first) == norm(title) or (is_heading(first) and norm(first) in norm(title))):
        return rest.lstrip("\n")
    return text
