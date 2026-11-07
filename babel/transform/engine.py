"""Transform one chapter: segment → label (LLM with heuristic fallback) → learn characters."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

from babel.llm.providers import LLMError, Router
from babel.memory.codex import Codex
from babel.models import BlockType, CharacterHint, Segment, SegmentKind
from babel.transform.heuristic import label_segments
from babel.transform.llm_labeler import (
    LabelResult,
    ParseError,
    StoryContext,
    build_messages,
    parse_response,
)
from babel.transform.segment import chunk_segments, segment_text

log = logging.getLogger(__name__)

Label = tuple[BlockType, str | None]


@dataclass
class Outcome:
    labels: dict[int, tuple[str, str | None]]
    method: str  # llm | heuristic | mixed
    model: str | None
    summary: str | None
    hints: list[CharacterHint] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class TransformFailed(Exception):
    pass


def merge_labels(segments: list[Segment], llm: dict[int, Label], heur: dict[int, Label]) -> dict[int, Label]:
    out: dict[int, Label] = {}
    for s in segments:
        if s.id in llm:
            t, sp = llm[s.id]
            if t in (BlockType.DIALOGUE, BlockType.THOUGHT) and not sp:
                hsp = heur.get(s.id, (None, None))[1]
                sp = hsp
            out[s.id] = (t, sp)
        elif s.kind == SegmentKind.PROSE:
            out[s.id] = (BlockType.NARRATION, None)  # the model lists everything else
        else:
            out[s.id] = heur[s.id]
    return out


class Engine:
    def __init__(self, router: Router | None, chunk_tokens: int = 6000, summary_window: int = 3):
        self.router = router if router and router.providers else None
        self.chunk_tokens = chunk_tokens
        self.summary_window = summary_window
        self.codex_lock = threading.RLock()

    def _label_chunk(self, chunk: list[Segment], ctx: StoryContext) -> tuple[LabelResult, str]:
        assert self.router is not None
        messages = build_messages(chunk, ctx)
        valid = {s.id for s in chunk}
        last: Exception | None = None
        for attempt in range(2):
            content, label = self.router.chat(messages, json_mode=True, max_tokens=4096)
            try:
                return parse_response(content, valid), label
            except ParseError as e:
                last = e
                log.warning("unparseable response from %s (attempt %d): %s", label, attempt + 1, e)
                messages = messages + [
                    {"role": "assistant", "content": content[:2000]},
                    {"role": "user", "content": "That was not valid JSON. Reply with the JSON object only."},
                ]
        raise ParseError(str(last))

    def transform(self, store, codex: Codex, chapter: dict, mode: str = "auto") -> Outcome:
        """Label a chapter. ``mode``: auto (LLM, fall back per chunk) | llm (strict) | heuristic."""
        segments = segment_text(chapter["source_text"])
        with self.codex_lock:
            known = [a for a in (r["alias"] for r in store.q(
                "SELECT alias FROM aliases WHERE novel_id=?", (codex.novel_id,)))]
        heur = label_segments(segments, known)

        use_llm = mode != "heuristic" and self.router is not None
        if mode == "llm" and self.router is None:
            raise TransformFailed("no LLM provider configured")

        labels: dict[int, Label] = {}
        models: set[str] = set()
        summaries: list[str] = []
        hints: list[CharacterHint] = []
        warnings: list[str] = []
        fell_back = False

        if not use_llm:
            labels = heur
        else:
            story = store.recent_summaries(codex.novel_id, chapter["idx"], self.summary_window)
            for chunk in chunk_segments(segments, self.chunk_tokens):
                chunk_text = "\n".join(s.text for s in chunk)
                with self.codex_lock:
                    ctx = StoryContext(
                        cast=codex.cast_context(chunk_text),
                        story_so_far=story + summaries,
                        pov=codex.pov_name(),
                        chapter_title=chapter.get("title"),
                    )
                try:
                    res, model = self._label_chunk(chunk, ctx)
                except (LLMError, ParseError) as e:
                    if mode == "llm":
                        raise TransformFailed(str(e)) from e
                    warnings.append(f"LLM failed on segments {chunk[0].id}-{chunk[-1].id}: {e}")
                    fell_back = True
                    labels.update({s.id: heur[s.id] for s in chunk})
                    continue
                models.add(model)
                labels.update(merge_labels(chunk, res.labels, heur))
                if res.summary:
                    summaries.append(res.summary)
                hints.extend(res.characters)
                # learn new characters immediately so the next chunk sees them
                with self.codex_lock:
                    for h in res.characters:
                        codex.learn(h, chapter["idx"])

        with self.codex_lock:
            for _t, sp in labels.values():
                if sp:
                    codex.resolve(sp, chapter["idx"])

        if not use_llm:
            method = "heuristic"
        elif fell_back:
            method = "mixed" if models else "heuristic"
        else:
            method = "llm"
        return Outcome(
            labels={i: (t.value, sp) for i, (t, sp) in labels.items()},
            method=method,
            model=", ".join(sorted(models)) or None,
            summary=" ".join(summaries) or None,
            hints=hints,
            warnings=warnings,
        )
