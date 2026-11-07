"""Deterministic segmentation of chapter text.

Paragraphs are split into spans by surface form: quoted speech, *emphasis*
(italics preserved from EPUBs, usually inner thoughts), [bracketed] system text,
and plain prose. The segmenter never changes characters inside a span, so
joining segment texts reproduces the paragraph (modulo whitespace).
"""

from __future__ import annotations

import re

from babel.models import Segment, SegmentKind

_BREAK_RE = re.compile(r"^\s*(?:[*#~=_•·◇◆✦★☆◎○●\-–—]\s*){3,}\s*$")
_PARA_SPLIT_RE = re.compile(r"\n\s*\n|\n")

OPEN_TO_CLOSE = {"“": "”", "「": "」", "『": "』", "«": "»", '"': '"'}
_BRACKET_PAIRS = {"[": "]", "【": "】", "〖": "〗", "〈": "〉"}
_PUNCT_ONLY_RE = re.compile(r"^[\s\W_]*$", re.UNICODE)


def split_paragraphs(text: str) -> list[str]:
    paras = [p.strip() for p in _PARA_SPLIT_RE.split(text.replace("\r\n", "\n"))]
    return [p for p in paras if p]


def _scan(para: str) -> list[tuple[SegmentKind, str]]:
    """Split one paragraph into (kind, text) spans.

    Speech left unclosed at the end of a paragraph (the multi-paragraph speech
    convention, or a typo) runs to the end of that paragraph.
    """
    spans: list[tuple[SegmentKind, str]] = []
    buf: list[str] = []
    close: str | None = None  # closing char while inside a quote
    i, n = 0, len(para)

    def flush(k: SegmentKind) -> None:
        s = "".join(buf).strip()
        buf.clear()
        if s:
            spans.append((k, s))

    while i < n:
        ch = para[i]
        if close is not None:
            buf.append(ch)
            if ch == close and i > 0:
                flush(SegmentKind.QUOTE)
                close = None
            i += 1
            continue
        if ch in OPEN_TO_CLOSE:
            flush(SegmentKind.PROSE)
            close = OPEN_TO_CLOSE[ch]
            buf.append(ch)
            i += 1
            # a straight quote closes on the *next* straight quote
            continue
        if ch == "*" and i + 1 < n and para[i + 1] not in " *":
            end = para.find("*", i + 1)
            if end > i + 1 and para[end - 1] != " ":
                flush(SegmentKind.PROSE)
                spans.append((SegmentKind.EMPHASIS, para[i : end + 1]))
                i = end + 1
                continue
        if ch in _BRACKET_PAIRS:
            end = para.find(_BRACKET_PAIRS[ch], i + 1)
            if end > i + 1:
                flush(SegmentKind.PROSE)
                spans.append((SegmentKind.BRACKET, para[i : end + 1]))
                i = end + 1
                continue
        buf.append(ch)
        i += 1

    flush(SegmentKind.QUOTE if close is not None else SegmentKind.PROSE)
    return spans


def _merge_fragments(spans: list[tuple[SegmentKind, str]]) -> list[tuple[SegmentKind, str]]:
    """Attach punctuation-only prose fragments (", " / "—") to the previous span."""
    out: list[tuple[SegmentKind, str]] = []
    for kind, text in spans:
        if kind == SegmentKind.PROSE and _PUNCT_ONLY_RE.match(text) and out:
            pk, pt = out[-1]
            out[-1] = (pk, pt + text)
            continue
        out.append((kind, text))
    return out


def segment_text(text: str) -> list[Segment]:
    segments: list[Segment] = []
    for p_idx, para in enumerate(split_paragraphs(text)):
        if _BREAK_RE.match(para):
            segments.append(Segment(id=len(segments), para=p_idx, kind=SegmentKind.BREAK, text=para))
            continue
        for kind, s in _merge_fragments(_scan(para)):
            segments.append(Segment(id=len(segments), para=p_idx, kind=kind, text=s))
    return segments


def strip_marks(text: str, kind: SegmentKind) -> str:
    """Display text: drop enclosing quote/emphasis marks for bubbles."""
    t = text.strip()
    if kind == SegmentKind.EMPHASIS and len(t) >= 2 and t[0] == "*" and t[-1] == "*":
        return t[1:-1].strip()
    if kind == SegmentKind.QUOTE and t:
        if t[0] in OPEN_TO_CLOSE:
            close = OPEN_TO_CLOSE[t[0]]
            t = t[1:]
            if t.endswith(close):
                t = t[: -len(close)]
            elif t[-2:-1] == close and t[-1:] in ",.":  # e.g. ”, (rare)
                t = t[:-2] + t[-1]
        return t.strip()
    return t


def estimate_tokens(text: str) -> int:
    """Cheap token estimate (~4 chars/token for English, ~1.5 for CJK)."""
    cjk = sum(1 for c in text if "　" <= c <= "鿿" or "가" <= c <= "힯")
    return (len(text) - cjk) // 4 + int(cjk / 1.5) + 1


def chunk_segments(segments: list[Segment], max_tokens: int) -> list[list[Segment]]:
    """Group segments into LLM-sized chunks, splitting only at paragraph boundaries."""
    chunks: list[list[Segment]] = []
    cur: list[Segment] = []
    cur_tokens = 0
    for seg in segments:
        t = estimate_tokens(seg.text) + 4
        boundary = not cur or cur[-1].para != seg.para
        if cur and cur_tokens + t > max_tokens and boundary:
            chunks.append(cur)
            cur, cur_tokens = [], 0
        cur.append(seg)
        cur_tokens += t
    if cur:
        chunks.append(cur)
    return chunks
