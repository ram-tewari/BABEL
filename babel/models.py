"""The standardized Visual Scenario format.

A chapter is converted deterministically into **segments** (exact spans of the
source text). Every segment gets a **Decision**: what kind of block it is, who
speaks it, in what tone — plus how confident we are, which tier of the cascade
made the call, and the runner-up candidates. LLMs never produce text; they only
answer small multiple-choice questions about low-confidence decisions.

    rule   → deterministic converter (patterns, speech tags)
    memory → resolver using the Akashic Record (aliases, gender, scene, turn-taking)
    local  → small local model (Ollama) verifying/answering questions
    cloud  → strong hosted model, only for what is still uncertain or disputed
    user   → a human correction
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class BlockType(StrEnum):
    NARRATION = "narration"  # description, exposition
    ACTION = "action"  # a short beat performed by a character ("Tobin shook his head.")
    DIALOGUE = "dialogue"  # spoken aloud
    THOUGHT = "thought"  # inner voice / monologue
    SYSTEM = "system"  # game-system windows, notifications, status panels
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
_ALIASES.update({
    # BABEL v1 types
    "narrator": BlockType.NARRATION,
    "monologue": BlockType.THOUGHT,
    "system_notification": BlockType.SYSTEM,
    # common variants
    "description": BlockType.NARRATION, "prose": BlockType.NARRATION, "beat": BlockType.ACTION,
    "speech": BlockType.DIALOGUE, "inner_monologue": BlockType.THOUGHT, "internal": BlockType.THOUGHT,
    "notification": BlockType.SYSTEM, "status": BlockType.SYSTEM, "sound": BlockType.SFX,
    "speech_tag": BlockType.TAG, "attribution": BlockType.TAG, "scene_break": BlockType.BREAK,
})

SPOKEN = frozenset({BlockType.DIALOGUE, BlockType.THOUGHT})
HAS_SPEAKER = frozenset({BlockType.DIALOGUE, BlockType.THOUGHT, BlockType.ACTION})

TONES = ("shout", "whisper", "angry", "sad", "laugh", "nervous", "cold")


class Tier(StrEnum):
    RULE = "rule"
    MEMORY = "memory"
    LOCAL = "local"
    CLOUD = "cloud"
    USER = "user"


class SegmentKind(StrEnum):
    """Surface form detected by the segmenter (a hint, not a label)."""

    PROSE = "prose"
    QUOTE = "quote"
    EMPHASIS = "emphasis"
    BRACKET = "bracket"
    BREAK = "break"


class Segment(BaseModel):
    id: int
    para: int
    kind: SegmentKind
    text: str


class Decision(BaseModel):
    type: BlockType
    speaker: str | None = None
    tone: str | None = None
    conf: float = 1.0
    tier: Tier = Tier.RULE
    candidates: list[str] = Field(default_factory=list)  # ranked alternatives for the speaker
    addressee: str | None = None  # who is being spoken to ("Tobin, look!"), if known
    why: str | None = None  # short evidence note

    def compact(self) -> list:
        """Storage form: [type, speaker, tone, conf, tier, candidates, why]."""
        return [self.type.value, self.speaker, self.tone, round(self.conf, 3), self.tier.value,
                self.candidates[:4], (self.why or "")[:160] or None]

    @classmethod
    def from_compact(cls, row: list) -> Decision:
        t, s, o, c, r, k, w = (list(row) + [None] * 7)[:7]
        return cls(type=BlockType.parse(t) or BlockType.NARRATION, speaker=s, tone=o,
                   conf=1.0 if c is None else c, tier=Tier(r or "rule"), candidates=k or [], why=w)


class Block(BaseModel):
    """Display unit: one or more adjacent segments sharing a decision."""

    type: BlockType
    text: str
    speaker: str | None = None
    tone: str | None = None
    conf: float = 1.0
    tier: Tier = Tier.RULE
    para: int = 0
    seg: list[int] = Field(default_factory=list)


class EntityHint(BaseModel):
    """An entity reported by a model or found deterministically."""

    name: str
    kind: str = "character"  # character | location | faction | term
    aliases: list[str] = Field(default_factory=list)
    gender: str | None = None  # m | f | n (neutral/unknown)
    note: str | None = None
