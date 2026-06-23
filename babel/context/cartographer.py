"""The Cartographer: extracts a glossary of entities from chapter text.

Reads the first N chapters, prompts the LLM to extract characters, factions,
locations and terms, and parses the response into a ``Glossary``. Retries on
rate limits and estimates (free-tier) token usage.

Reconstructed from tests/test_cartographer.py.
"""

import json
import logging
from pathlib import Path
from typing import List

from pydantic import ValidationError

from babel.context.models import Glossary
from babel.transform.gemini_client import RateLimitError

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


class CartographerError(Exception):
    """Raised when glossary extraction fails."""
    pass


class Cartographer:
    """Extracts a structured glossary from raw chapter text via an LLM."""

    def __init__(self, client):
        self.client = client

    # --------------------------------------------------------------- prompt
    def _build_extraction_prompt(self, chapter_texts: List[str]) -> str:
        """Build the entity-extraction prompt from a list of chapter texts."""
        chapters_block = "\n\n---CHAPTER BREAK---\n\n".join(chapter_texts)
        return f"""# ENTITY EXTRACTION TASK

You are a meticulous lore archivist. Extract every named entity from the
chapters below so the glossary stays consistent across thousands of chapters.

## CATEGORIES TO EXTRACT
- Characters: named people / beings.
- Factions: sects, organizations, families, groups.
- Locations: places, regions, landmarks.
- Terms: techniques, items, concepts, honorifics and other proper nouns.

## EXTRACTION RULES
- Use the most complete canonical name for "name".
- Put the original / raw form (and any script variants) in "raw".
- List alternate names and titles in "aliases".
- Give a one-line "desc" describing the entity.
- Do not invent entities that do not appear in the text.

## OUTPUT FORMAT
Return ONLY valid JSON of the form:
{{
  "characters": [{{"name": "...", "raw": "...", "aliases": ["..."], "desc": "..."}}],
  "factions": [...],
  "locations": [...],
  "terms": [...]
}}

## CHAPTERS TO ANALYZE

{chapters_block}
"""

    # ---------------------------------------------------------------- parse
    def _parse_extraction_response(self, response: str) -> Glossary:
        """Parse an LLM JSON response into a Glossary."""
        try:
            data = json.loads(response)
        except json.JSONDecodeError as e:
            raise CartographerError(f"Invalid JSON response: {e}") from e

        try:
            return Glossary(**data)
        except ValidationError as e:
            raise CartographerError(f"Response validation failed: {e}") from e

    # -------------------------------------------------------------- extract
    def extract_glossary(self, chapter_paths: List[Path], num_chapters: int = 3) -> Glossary:
        """Extract a glossary from the first ``num_chapters`` chapter files."""
        if not 1 <= num_chapters <= 100:
            raise ValueError(f"num_chapters must be between 1 and 100, got {num_chapters}")
        if not chapter_paths:
            raise ValueError("No chapter paths provided")

        # Read the first num_chapters readable files.
        chapter_texts: List[str] = []
        for path in chapter_paths[:num_chapters]:
            try:
                chapter_texts.append(Path(path).read_text(encoding="utf-8"))
            except OSError as e:
                logger.warning("Failed to read %s: %s", path, e)

        if not chapter_texts:
            logger.warning("No chapters could be read; returning empty glossary")
            return Glossary()

        prompt = self._build_extraction_prompt(chapter_texts)

        input_tokens = len(prompt) // 4
        logger.info("Estimated input: %d tokens", input_tokens)

        last_err = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.client.generate_content(prompt)

                output_tokens = len(response) // 4
                logger.info("Estimated output: %d tokens", output_tokens)
                logger.info("Cost: $0.00 (FREE tier)")

                glossary = self._parse_extraction_response(response)

                logger.info(
                    "Extracted %d entities (%d characters, %d factions, "
                    "%d locations, %d terms)",
                    glossary.total_entries(),
                    len(glossary.characters),
                    len(glossary.factions),
                    len(glossary.locations),
                    len(glossary.terms),
                )
                return glossary

            except RateLimitError as e:
                last_err = e
                logger.warning("Rate limit on attempt %d/%d: %s", attempt, MAX_RETRIES, e)
                continue

        raise CartographerError(
            f"Failed to extract glossary after {MAX_RETRIES} attempts: {last_err}"
        )
