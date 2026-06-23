"""Glossary models for the Context Engine.

A ``Glossary`` groups ``GlossaryEntry`` items into four categories
(characters, factions, locations, terms) and is persisted as YAML so the LLM
can be given consistent context across thousands of chapters.

Reconstructed from tests/test_context_store.py and tests/test_context_properties.py.
"""

from typing import ClassVar, List, Optional, Tuple

from pydantic import BaseModel, Field


class GlossaryEntry(BaseModel):
    """A single named entity (character, faction, location or term).

    ``name`` and ``raw`` are required; ``aliases`` and ``desc`` are optional.
    """

    name: str
    raw: str
    aliases: List[str] = Field(default_factory=list)
    desc: Optional[str] = None


class Glossary(BaseModel):
    """The full glossary: four categories of entries."""

    characters: List[GlossaryEntry] = Field(default_factory=list)
    factions: List[GlossaryEntry] = Field(default_factory=list)
    locations: List[GlossaryEntry] = Field(default_factory=list)
    terms: List[GlossaryEntry] = Field(default_factory=list)

    CATEGORIES: ClassVar[Tuple[str, ...]] = ("characters", "factions", "locations", "terms")

    def total_entries(self) -> int:
        """Total number of entries across all categories."""
        return (
            len(self.characters)
            + len(self.factions)
            + len(self.locations)
            + len(self.terms)
        )

    def get_category(self, category: str) -> List[GlossaryEntry]:
        """Return the entry list for a category name."""
        return getattr(self, category)

    def to_dict(self) -> dict:
        """Serialize to a plain dict of category -> list of entry dicts."""
        return self.model_dump()
