"""Pydantic models for the Visual Scenario transform output.

Reconstructed from the test specifications in tests/test_serialization.py,
tests/test_transform_properties.py and tests/test_transformer.py.

A transformed chapter is a ``ChapterData`` containing an ordered list of
``ScriptBlock`` items plus provenance metadata (source hash, model version,
processing timestamp).
"""

from enum import Enum
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


class ScriptBlockType(str, Enum):
    """The seven narrative block types in a Visual Scenario."""

    DIALOGUE = "dialogue"
    THOUGHT = "thought"
    NARRATOR = "narrator"
    ACTION = "action"
    MONOLOGUE = "monologue"
    SFX = "sfx"
    SYSTEM_NOTIFICATION = "system_notification"


class ScriptBlock(BaseModel):
    """A single narrative unit (one line of dialogue, an action beat, etc.).

    ``type`` is kept as the enum (not coerced to str) so callers can use
    ``block.type.value``; pydantic still serializes it to the string value in
    JSON output.
    """

    type: ScriptBlockType
    content: str
    speaker: Optional[str] = None
    tone: Optional[str] = None


def _utcnow() -> datetime:
    """Timezone-aware current UTC time (used as the default timestamp)."""
    return datetime.now(timezone.utc)


class ChapterData(BaseModel):
    """A fully transformed chapter plus its provenance metadata.

    ``blocks``, ``source_hash`` and ``model_version`` are required; an empty
    blocks list is allowed but the field must be present. ``processed_at`` is
    auto-populated with the current UTC time when omitted.
    """

    blocks: List[ScriptBlock]
    source_hash: str
    model_version: str
    processed_at: datetime = Field(default_factory=_utcnow)
