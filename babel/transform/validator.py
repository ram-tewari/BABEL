"""Validate and clean LLM responses into ChapterData models.

Reconstructed from tests/test_validator.py.
"""

import json
import logging

from babel.transform.models import ChapterData

logger = logging.getLogger(__name__)


class JSONValidator:
    """Cleans markdown-fenced LLM output and validates it against ChapterData."""

    @staticmethod
    def clean_response(raw: str) -> str:
        """Strip ``` / ```json code fences and surrounding whitespace."""
        text = raw.strip()

        if text.startswith("```"):
            # Drop the opening fence line (``` or ```json).
            newline = text.find("\n")
            if newline != -1:
                text = text[newline + 1:]
            else:
                text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        return text.strip()

    @staticmethod
    def validate(raw: str) -> ChapterData:
        """Clean, parse and validate an LLM response into a ChapterData.

        Raises ValueError on malformed JSON and pydantic ValidationError on
        schema mismatch (both are logged).
        """
        cleaned = JSONValidator.clean_response(raw)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("JSON parsing failed: %s", e)
            raise ValueError(f"Invalid JSON: {e}") from e

        try:
            return ChapterData(**data)
        except Exception as e:
            # pydantic.ValidationError is re-raised as-is for the caller.
            logger.error("Pydantic validation failed: %s", e)
            raise
