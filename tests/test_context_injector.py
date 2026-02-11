"""
Unit tests for ContextInjector.

Tests Markdown formatting, token counting, truncation behavior, and empty
glossary handling.
"""

import pytest
from pathlib import Path

from babel.context.models import Glossary, GlossaryEntry
from babel.context.store import GlossaryStore
from babel.context.injector import ContextInjector


@pytest.fixture
def sample_glossary():
    """Create a sample glossary for testing."""
    return Glossary(
        characters=[
            GlossaryEntry(
                name="Chung Myung",
                raw="청명|Chung Myung",
                aliases=["The Divine Dragon", "Sahyung"],
                desc="Protagonist. Former Divine Dragon, reincarnated."
            ),
            GlossaryEntry(
                name="Baek Cheon",
                raw="백천|Baek Cheon",
                aliases=["Righteous Sword"],
                desc="Senior disciple of Mount Hua Sect."
            )
        ],
        factions=[
            GlossaryEntry(
                name="Mount Hua Sect",
                raw="화산파|Mount Hua Sect",
                aliases=["Plum Blossom Sect"],
                desc="One of the Nine Great Sects."
            )
        ],
        locations=[
            GlossaryEntry(
                name="Mount Hua",
                raw="화산|Mount Hua",
                aliases=["Hua Mountain"],
                desc="Sacred mountain where Mount Hua Sect is located."
            )
        ],
        terms=[
            GlossaryEntry(
                name="Qi",
                raw="기|Qi",
                aliases=["Internal Energy", "Ki"],
                desc="Life force energy used in martial arts."
            )
        ]
    )


@pytest.fixture
def empty_glossary():
    """Create an empty glossary for testing."""
    return Glossary()


@pytest.fixture
def glossary_store(tmp_path, sample_glossary):
    """Create a GlossaryStore with sample glossary."""
    glossary_path = tmp_path / "test_glossary.yaml"
    store = GlossaryStore(glossary_path)
    store.save(sample_glossary)
    return store


@pytest.fixture
def empty_glossary_store(tmp_path):
    """Create a GlossaryStore with no glossary file."""
    glossary_path = tmp_path / "nonexistent_glossary.yaml"
    return GlossaryStore(glossary_path)


def test_context_injector_initialization(glossary_store):
    """Test ContextInjector initialization."""
    injector = ContextInjector(glossary_store)
    
    assert injector.store == glossary_store
    assert injector.logger is not None


def test_inject_context_with_glossary(glossary_store):
    """Test context injection with a populated glossary."""
    injector = ContextInjector(glossary_store)
    
    base_prompt = "Transform this chapter into screenplay format."
    enhanced_prompt = injector.inject_context(base_prompt)
    
    # Verify base prompt is present
    assert base_prompt in enhanced_prompt
    
    # Verify glossary section is present
    assert "## NARRATIVE CONTEXT & GLOSSARY" in enhanced_prompt
    assert "**CRITICAL**" in enhanced_prompt
    assert "**REMINDER**" in enhanced_prompt
    
    # Verify categories are present
    assert "### Characters" in enhanced_prompt
    assert "### Factions" in enhanced_prompt
    assert "### Locations" in enhanced_prompt
    assert "### Terms" in enhanced_prompt
    
    # Verify specific entries are present
    assert "Chung Myung" in enhanced_prompt
    assert "Mount Hua Sect" in enhanced_prompt
    assert "Qi" in enhanced_prompt


def test_inject_context_with_empty_glossary(empty_glossary_store):
    """Test context injection with an empty glossary."""
    injector = ContextInjector(empty_glossary_store)
    
    base_prompt = "Transform this chapter into screenplay format."
    enhanced_prompt = injector.inject_context(base_prompt)
    
    # Verify base prompt is returned unchanged
    assert enhanced_prompt == base_prompt
    
    # Verify no glossary section is added
    assert "## NARRATIVE CONTEXT & GLOSSARY" not in enhanced_prompt


def test_format_glossary_section(glossary_store, sample_glossary):
    """Test Markdown formatting of glossary section."""
    injector = ContextInjector(glossary_store)
    
    formatted = injector._format_glossary_section(sample_glossary)
    
    # Verify header
    assert "## NARRATIVE CONTEXT & GLOSSARY" in formatted
    assert "**CRITICAL**" in formatted
    
    # Verify all categories are present
    assert "### Characters" in formatted
    assert "### Factions" in formatted
    assert "### Locations" in formatted
    assert "### Terms" in formatted
    
    # Verify entry format: **Name** (raw)
    assert "**Chung Myung** (청명|Chung Myung)" in formatted
    assert "**Mount Hua Sect** (화산파|Mount Hua Sect)" in formatted
    assert "**Mount Hua** (화산|Mount Hua)" in formatted
    assert "**Qi** (기|Qi)" in formatted
    
    # Verify aliases are present
    assert "Aliases: The Divine Dragon, Sahyung" in formatted
    assert "Aliases: Plum Blossom Sect" in formatted
    assert "Aliases: Internal Energy, Ki" in formatted
    
    # Verify descriptions are present
    assert "Context: Protagonist. Former Divine Dragon, reincarnated." in formatted
    assert "Context: One of the Nine Great Sects." in formatted
    assert "Context: Life force energy used in martial arts." in formatted
    
    # Verify footer
    assert "**REMINDER**" in formatted


def test_format_entry(glossary_store):
    """Test formatting of a single glossary entry."""
    injector = ContextInjector(glossary_store)
    
    entry = GlossaryEntry(
        name="Test Character",
        raw="テスト|Test Character",
        aliases=["TC", "Tester"],
        desc="A test character for unit testing."
    )
    
    formatted_lines = injector._format_entry(entry)
    formatted = "\n".join(formatted_lines)
    
    # Verify name and raw pattern
    assert "**Test Character** (テスト|Test Character)" in formatted
    
    # Verify aliases
    assert "Aliases: TC, Tester" in formatted
    
    # Verify description
    assert "Context: A test character for unit testing." in formatted


def test_format_entry_without_optional_fields(glossary_store):
    """Test formatting of entry without aliases or description."""
    injector = ContextInjector(glossary_store)
    
    entry = GlossaryEntry(
        name="Simple Entry",
        raw="シンプル|Simple Entry"
    )
    
    formatted_lines = injector._format_entry(entry)
    formatted = "\n".join(formatted_lines)
    
    # Verify name and raw pattern
    assert "**Simple Entry** (シンプル|Simple Entry)" in formatted
    
    # Verify no aliases or description sections
    assert "Aliases:" not in formatted
    assert "Context:" not in formatted


def test_estimate_token_count(glossary_store):
    """Test token count estimation."""
    injector = ContextInjector(glossary_store)
    
    # Test with known text
    text = "a" * 400  # 400 characters
    token_count = injector._estimate_token_count(text)
    
    # Should be approximately 100 tokens (400 / 4)
    assert token_count == 100
    
    # Test with empty text
    assert injector._estimate_token_count("") == 0
    
    # Test with short text
    assert injector._estimate_token_count("test") == 1  # 4 chars / 4 = 1 token


def test_truncate_glossary(glossary_store, sample_glossary):
    """Test glossary truncation with low token limit."""
    injector = ContextInjector(glossary_store)
    
    # Set a very low token limit to force truncation
    low_limit = 100  # Very low to force truncation
    
    truncated = injector._truncate_glossary(sample_glossary, max_tokens=low_limit)
    
    # Verify token limit is respected
    token_count = injector._estimate_token_count(truncated)
    assert token_count <= low_limit
    
    # Check if truncation actually occurred
    full_formatted = injector._format_glossary_section(sample_glossary)
    full_token_count = injector._estimate_token_count(full_formatted)
    
    if full_token_count > low_limit:
        # Truncation should have occurred
        assert "truncated" in truncated.lower() or "Truncated" in truncated
        # Verify the truncation notice mentions the count
        assert "0 of 5 entries" in truncated or "entries" in truncated.lower()
    else:
        # Glossary was small enough to fit without truncation
        # Just verify it's within the limit
        assert token_count <= low_limit


def test_truncation_prioritization(glossary_store):
    """Test that truncation prioritizes characters over other categories."""
    injector = ContextInjector(glossary_store)
    
    # Create a large glossary with many entries
    large_glossary = Glossary(
        characters=[
            GlossaryEntry(
                name=f"Character_{i}",
                raw=f"キャラクター_{i}",
                aliases=[f"Alias_{i}"],
                desc=f"Description for character {i}. " * 10
            )
            for i in range(50)
        ],
        factions=[
            GlossaryEntry(
                name=f"Faction_{i}",
                raw=f"派閥_{i}",
                aliases=[f"Faction_Alias_{i}"],
                desc=f"Description for faction {i}. " * 10
            )
            for i in range(50)
        ],
        locations=[
            GlossaryEntry(
                name=f"Location_{i}",
                raw=f"場所_{i}",
                aliases=[f"Location_Alias_{i}"],
                desc=f"Description for location {i}. " * 10
            )
            for i in range(50)
        ],
        terms=[
            GlossaryEntry(
                name=f"Term_{i}",
                raw=f"用語_{i}",
                aliases=[f"Term_Alias_{i}"],
                desc=f"Description for term {i}. " * 10
            )
            for i in range(50)
        ]
    )
    
    # Set a moderate token limit
    moderate_limit = 5000
    
    truncated = injector._truncate_glossary(large_glossary, max_tokens=moderate_limit)
    
    # Verify token limit is respected
    token_count = injector._estimate_token_count(truncated)
    assert token_count <= moderate_limit
    
    # Count how many entries from each category are present
    character_count = sum(1 for i in range(50) if f"Character_{i}" in truncated)
    faction_count = sum(1 for i in range(50) if f"Faction_{i}" in truncated)
    location_count = sum(1 for i in range(50) if f"Location_{i}" in truncated)
    term_count = sum(1 for i in range(50) if f"Term_{i}" in truncated)
    
    # Verify prioritization: characters should have the most entries
    assert character_count >= faction_count
    assert character_count >= location_count
    assert character_count >= term_count
    
    # If any lower-priority category has entries, higher-priority should be complete
    if term_count > 0:
        assert character_count == 50
        assert faction_count == 50
        assert location_count == 50
    
    if location_count > 0:
        assert character_count == 50
        assert faction_count == 50
    
    if faction_count > 0:
        assert character_count == 50


def test_empty_glossary_formatting(glossary_store):
    """Test formatting of an empty glossary."""
    injector = ContextInjector(glossary_store)
    
    empty = Glossary()
    formatted = injector._format_glossary_section(empty)
    
    # Should still have header and footer
    assert "## NARRATIVE CONTEXT & GLOSSARY" in formatted
    assert "**CRITICAL**" in formatted
    assert "**REMINDER**" in formatted
    
    # Should not have category headers (no entries)
    assert "### Characters" not in formatted
    assert "### Factions" not in formatted
    assert "### Locations" not in formatted
    assert "### Terms" not in formatted


def test_partial_glossary_formatting(glossary_store):
    """Test formatting of glossary with only some categories populated."""
    injector = ContextInjector(glossary_store)
    
    partial = Glossary(
        characters=[
            GlossaryEntry(
                name="Solo Character",
                raw="ソロ|Solo Character",
                aliases=["SC"],
                desc="The only character."
            )
        ],
        # Other categories empty
        factions=[],
        locations=[],
        terms=[]
    )
    
    formatted = injector._format_glossary_section(partial)
    
    # Should have characters section
    assert "### Characters" in formatted
    assert "Solo Character" in formatted
    
    # Should not have empty category headers
    assert "### Factions" not in formatted
    assert "### Locations" not in formatted
    assert "### Terms" not in formatted
