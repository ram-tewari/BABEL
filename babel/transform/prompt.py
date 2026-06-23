"""Prompt construction for the Visual Scenario transform.

Reconstructed from tests/test_prompt.py.
"""

from babel.transform.models import ChapterData


class PromptConstructor:
    """Builds the system + user prompt for converting prose to Visual Scenario."""

    SYSTEM_PROMPT = """You are an Expert Screenwriter and adaptation specialist. \
Your job is to convert raw webnovel prose into a structured "Visual Scenario" \
JSON format that separates the narrative into typed blocks. Convert the ENTIRE \
chapter faithfully.

BLOCK TYPES:

- DIALOGUE: A character's spoken words (speech in quotes). Always attribute the
  speaker by name when identifiable; use the most specific name available rather
  than a generic label.

- ACTION: Convert prose descriptions of events, movement and scenery into concise
  action lines. Describe what happens; no speaker.

- MONOLOGUE: A character's internal thoughts / inner voice (unspoken reflection).
  Attribute the speaker whose internal thoughts these are.

- SFX: Sound effects and onomatopoeia (e.g. BOOM, crash, sizzling).

- SYSTEM_NOTIFICATION: Game-like system messages such as a level up, quest
  update, skill acquisition or status window text.

RULES:
- Do NOT summarize, abridge, or skip any content. Preserve every beat of the
  chapter in order.
- Always include a "speaker" for dialogue and monologue (null for action, sfx
  and system_notification).
- Keep each block's "content" faithful to the source text.
- Output ONLY valid JSON matching the required schema."""

    @staticmethod
    def get_token_estimate(text: str) -> int:
        """Rough token estimate: ~4 characters per token (integer division)."""
        return len(text) // 4

    @classmethod
    def construct_prompt(cls, chapter_text: str) -> str:
        """Build the full prompt: system instructions + schema + chapter text."""
        schema = ChapterData.model_json_schema()
        # Pull the block field names into the prompt for format guidance.
        schema_keys = ", ".join(sorted(schema.get("properties", {}).keys()))

        return (
            f"{cls.SYSTEM_PROMPT}\n\n"
            f"OUTPUT JSON SCHEMA (fields: {schema_keys}):\n"
            f"The top-level object must contain 'blocks' (a list of typed blocks), "
            f"'source_hash' and 'model_version'.\n\n"
            f"CHAPTER TEXT TO CONVERT:\n{chapter_text}"
        )
