"""Transformer class for converting text to Visual Scenario format."""

import json
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ValidationError

from babel.transform.prompt import PromptConstructor
from babel.transform.validator import JSONValidator
from babel.transform.models import ChapterData
from babel.transform.gemini_client import RateLimitError

logger = logging.getLogger(__name__)


class TransformResult(BaseModel):
    """Result of text transformation."""
    blocks: list[Dict[str, Any]] = Field(default_factory=list)
    
    class Config:
        extra = "allow"


class Transformer:
    """Transforms text using an LLM client."""
    
    SYSTEM_PROMPT = """You are a text transformation assistant. Convert the input text into Visual Scenario format with the following block types:

- dialogue: Character speech with speaker name
- thought: Internal character thoughts
- narrator: Third-person exposition
- action: Physical actions and scene descriptions
- monologue: Extended character speech
- sfx: Sound effects
- system_notification: System notifications or meta-text

IMPORTANT - SPEAKER ATTRIBUTION:
- Use SPECIFIC character names whenever identifiable from context
- Avoid generic labels like "Student", "Teacher", "Person" when you can determine the actual character
- Common characters in Infinite Mage: Shirone, Amy, Neid, Iluki, Mark, Seriel, Alpheas (Headmaster), Siena/Sienna (Teacher), Sard (Teacher)
- When multiple students speak, try to identify which specific student based on context clues
- If truly ambiguous, use descriptive labels like "Class Four Student" or "Senior Student" rather than just "Student"

Output ONLY valid JSON in this exact format:
{
  "blocks": [
    {"type": "dialogue", "speaker": "Name", "content": "...", "tone": "neutral"},
    {"type": "thought", "speaker": "Name", "content": "..."},
    {"type": "narrator", "speaker": null, "content": "...", "tone": null},
    {"type": "action", "speaker": null, "content": "...", "tone": null}
  ]
}

Rules:
- Use "dialogue" for character speech
- Use "thought" for internal monologue
- Use "narrator" for third-person narrative
- Use "action" for scene descriptions
- Always include "speaker" field (use null for narrator/action)
- Always include "content" field with the text
- Include "tone" field when appropriate (neutral, happy, sad, angry, etc.)
- Keep text concise and readable
- Output ONLY the JSON, no additional text"""
    
    MODEL_VERSION_DEFAULT = "gemini-2.5-flash"

    def __init__(self, client, glossary_path=None):
        """Initialize the transformer with an LLM client and optional glossary.

        When ``glossary_path`` is given, glossary context is injected into the
        prompt for every chapter (gracefully degrading to no context if the
        glossary is missing or empty).
        """
        self.client = client
        self.prompt_constructor = PromptConstructor()
        self.validator = JSONValidator()
        model_name = getattr(client, "model_name", None)
        self.model_version = model_name if isinstance(model_name, str) else self.MODEL_VERSION_DEFAULT

        self.glossary_store = None
        self.context_injector = None
        if glossary_path is not None:
            from babel.context.store import GlossaryStore
            from babel.context.injector import ContextInjector

            self.glossary_store = GlossaryStore(Path(glossary_path))
            self.context_injector = ContextInjector(self.glossary_store)
            glossary = self.glossary_store.load()
            logger.info(
                f"Glossary loaded: {glossary.total_entries()} entries "
                f"({len(glossary.characters)} characters, "
                f"{len(glossary.factions)} factions, "
                f"{len(glossary.locations)} locations, "
                f"{len(glossary.terms)} terms)"
            )

    def transform_chapter(self, text: str, max_retries: int = 3) -> Optional[ChapterData]:
        """Transform a chapter into a validated ChapterData with metadata.

        Computes a SHA-256 source hash, prompts the LLM, validates the JSON and
        injects provenance metadata. Returns None on rate-limit, unexpected
        errors, or after exhausting validation retries.
        """
        source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        prompt = self.prompt_constructor.construct_prompt(text)
        if self.context_injector is not None:
            prompt = self.context_injector.inject_context(prompt)

        tokens = self.prompt_constructor.get_token_estimate(prompt)
        logger.info("Estimated: %d tokens (FREE tier, $0.00)", tokens)

        for attempt in range(max_retries):
            try:
                response = self.client.generate_content(prompt)
            except RateLimitError as e:
                logger.error("Rate limit error, aborting chapter: %s", e)
                return None
            except Exception as e:
                logger.error("Unexpected error during generation: %s", e)
                return None

            try:
                cleaned = self.validator.clean_response(response)
                data = json.loads(cleaned)
                data["source_hash"] = source_hash
                data["model_version"] = self.model_version
                data["processed_at"] = datetime.now(timezone.utc)
                return ChapterData(**data)
            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(
                    "Validation failed (attempt %d/%d): %s", attempt + 1, max_retries, e
                )
                continue

        logger.error("Failed to transform chapter after %d attempts", max_retries)
        return None
    
    def transform(self, text: str) -> TransformResult:
        """Transform text to Visual Scenario format."""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                result = self.client.transform_text(text, self.SYSTEM_PROMPT)
                
                # Validate the result
                return TransformResult(**result)
                
            except Exception as e:
                error_msg = str(e)
                
                # If it's a validation error and we have retries left, try again
                if "validation error" in error_msg.lower() and attempt < max_retries - 1:
                    continue
                
                # On last attempt, raise the error
                raise
