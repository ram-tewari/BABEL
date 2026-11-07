"""Core data model.

A chapter's source text is split deterministically into **segments** (see
``babel.transform.segment``). The transformer assigns each segment a block
**type** and, for spoken/inner lines, a **speaker** label. Because the text of a
segment is never rewritten by the LLM, a transformed chapter is always a
lossless re-presentation of its source.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class BlockType(StrEnum):
    NARRATION = "narration"  # prose: description, action, exposition
    DIALOGUE = "dialogue"  # spoken words, attributed to a speaker
    THOUGHT = "thought"  # inner voice, attributed to a speaker
    SYSTEM = "system"  # game-system windows, notifications, status screens
    SFX = "sfx"  # sound effects / onomatopoeia
    TAG = "tag"  # speech tag around dialogue ("he said, frowning")
    BREAK = "break"  # scene break

    @classmethod
    def parse(cls, value: str | None) -> BlockType | None:
        if not value:
            return None
        v = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        return _ALIASES.get(v)


_ALIASES: dict[str, BlockType] = {t.value: t for t in BlockType}
_ALIASES.update(
    {
        # short codes the prompt allows
        "n": BlockType.NARRATION,
        "d": BlockType.DIALOGUE,
        "t": BlockType.THOUGHT,
        "s": BlockType.SYSTEM,
        "x": BlockType.SFX,
        "g": BlockType.TAG,
        # legacy BABEL v1 / common LLM variants
        "narrator": BlockType.NARRATION,
        "action": BlockType.NARRATION,
        "description": BlockType.NARRATION,
        "prose": BlockType.NARRATION,
        "speech": BlockType.DIALOGUE,
        "monologue": BlockType.THOUGHT,
        "inner_monologue": BlockType.THOUGHT,
        "internal": BlockType.THOUGHT,
        "system_notification": BlockType.SYSTEM,
        "notification": BlockType.SYSTEM,
        "status": BlockType.SYSTEM,
        "sound": BlockType.SFX,
        "speech_tag": BlockType.TAG,
        "attribution": BlockType.TAG,
        "scene_break": BlockType.BREAK,
    }
)

SPOKEN = {BlockType.DIALOGUE, BlockType.THOUGHT}


class SegmentKind(StrEnum):
    """Surface form detected by the deterministic segmenter (a hint, not a label)."""

    PROSE = "prose"
    QUOTE = "quote"  # inside quotation marks
    EMPHASIS = "emphasis"  # *italic* span from the source (often a thought)
    BRACKET = "bracket"  # [bracketed] / 【system】 text
    BREAK = "break"  # *** / --- scene separator


class Segment(BaseModel):
    id: int
    para: int  # paragraph index within the chapter
    kind: SegmentKind
    text: str


class Block(BaseModel):
    """A labeled segment (or a run of merged segments) ready for display."""

    type: BlockType
    text: str
    speaker: str | None = None  # raw label as produced; resolved via the codex at read time
    para: int = 0
    seg: list[int] = Field(default_factory=list)  # source segment ids


class Script(BaseModel):
    """The transformed form of one chapter."""

    version: int = 2
    blocks: list[Block]
    method: str = "llm"  # "llm" | "heuristic" | "mixed"
    model: str | None = None
    summary: str | None = None


class CharacterHint(BaseModel):
    """A character the LLM noticed in a chapter."""

    name: str
    aliases: list[str] = Field(default_factory=list)
    note: str | None = None
