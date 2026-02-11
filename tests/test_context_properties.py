"""
Property-based tests for The Akashic Record (Phase 4).

These tests validate universal correctness properties using Hypothesis.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from pydantic import ValidationError

from babel.context.models import GlossaryEntry, Glossary


# Feature: akashic-record, Property 2: GlossaryEntry Field Requirements
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    name=st.text(min_size=1, max_size=100),
    raw=st.text(min_size=1, max_size=200),
    aliases=st.lists(st.text(min_size=1, max_size=50), max_size=10),
    desc=st.one_of(st.none(), st.text(min_size=1, max_size=500))
)
def test_property_2_glossary_entry_field_requirements(name, raw, aliases, desc):
    """
    Property 2: GlossaryEntry Field Requirements
    
    For any GlossaryEntry object, it must have required fields (name, raw)
    and may have optional fields (aliases, desc), and all fields must pass
    Pydantic validation.
    
    Validates: Requirements 1.3, 1.4, 1.5, 1.6
    """
    # Create entry with all fields
    entry = GlossaryEntry(
        name=name,
        raw=raw,
        aliases=aliases,
        desc=desc
    )
    
    # Verify required fields are present
    assert entry.name == name
    assert entry.raw == raw
    
    # Verify optional fields
    assert entry.aliases == aliases
    assert entry.desc == desc
    
    # Verify entry can be serialized and deserialized
    entry_dict = entry.model_dump()
    reconstructed = GlossaryEntry(**entry_dict)
    assert reconstructed == entry


# Feature: akashic-record, Property 2: GlossaryEntry Field Requirements (missing required fields)
def test_property_2_glossary_entry_missing_required_fields():
    """
    Property 2: GlossaryEntry Field Requirements (negative test)
    
    GlossaryEntry must fail validation when required fields are missing.
    
    Validates: Requirements 1.3, 1.4
    """
    # Missing 'name' field
    with pytest.raises(ValidationError) as exc_info:
        GlossaryEntry(raw="test")
    assert "name" in str(exc_info.value).lower()
    
    # Missing 'raw' field
    with pytest.raises(ValidationError) as exc_info:
        GlossaryEntry(name="Test")
    assert "raw" in str(exc_info.value).lower()
    
    # Missing both required fields
    with pytest.raises(ValidationError):
        GlossaryEntry()


# Feature: akashic-record, Property 1: Glossary Schema Completeness
@settings(max_examples=100)
@given(
    characters=st.lists(
        st.builds(
            GlossaryEntry,
            name=st.text(min_size=1, max_size=50),
            raw=st.text(min_size=1, max_size=100),
            aliases=st.lists(st.text(min_size=1, max_size=30), max_size=5),
            desc=st.one_of(st.none(), st.text(min_size=1, max_size=200))
        ),
        max_size=10
    ),
    factions=st.lists(
        st.builds(
            GlossaryEntry,
            name=st.text(min_size=1, max_size=50),
            raw=st.text(min_size=1, max_size=100),
            aliases=st.lists(st.text(min_size=1, max_size=30), max_size=5),
            desc=st.one_of(st.none(), st.text(min_size=1, max_size=200))
        ),
        max_size=10
    ),
    locations=st.lists(
        st.builds(
            GlossaryEntry,
            name=st.text(min_size=1, max_size=50),
            raw=st.text(min_size=1, max_size=100),
            aliases=st.lists(st.text(min_size=1, max_size=30), max_size=5),
            desc=st.one_of(st.none(), st.text(min_size=1, max_size=200))
        ),
        max_size=10
    ),
    terms=st.lists(
        st.builds(
            GlossaryEntry,
            name=st.text(min_size=1, max_size=50),
            raw=st.text(min_size=1, max_size=100),
            aliases=st.lists(st.text(min_size=1, max_size=30), max_size=5),
            desc=st.one_of(st.none(), st.text(min_size=1, max_size=200))
        ),
        max_size=10
    )
)
def test_property_1_glossary_schema_completeness(characters, factions, locations, terms):
    """
    Property 1: Glossary Schema Completeness
    
    For any Glossary object, it must contain all four categories (characters,
    factions, locations, terms), and each category must be a list of
    GlossaryEntry objects.
    
    Validates: Requirements 1.2
    """
    # Create glossary with all categories
    glossary = Glossary(
        characters=characters,
        factions=factions,
        locations=locations,
        terms=terms
    )
    
    # Verify all four categories exist
    assert hasattr(glossary, 'characters')
    assert hasattr(glossary, 'factions')
    assert hasattr(glossary, 'locations')
    assert hasattr(glossary, 'terms')
    
    # Verify each category is a list
    assert isinstance(glossary.characters, list)
    assert isinstance(glossary.factions, list)
    assert isinstance(glossary.locations, list)
    assert isinstance(glossary.terms, list)
    
    # Verify all entries are GlossaryEntry objects
    for entry in glossary.characters:
        assert isinstance(entry, GlossaryEntry)
    for entry in glossary.factions:
        assert isinstance(entry, GlossaryEntry)
    for entry in glossary.locations:
        assert isinstance(entry, GlossaryEntry)
    for entry in glossary.terms:
        assert isinstance(entry, GlossaryEntry)
    
    # Verify total_entries() method works correctly
    expected_total = len(characters) + len(factions) + len(locations) + len(terms)
    assert glossary.total_entries() == expected_total
    
    # Verify glossary can be serialized and deserialized
    glossary_dict = glossary.model_dump()
    reconstructed = Glossary(**glossary_dict)
    assert reconstructed == glossary



# Feature: akashic-record, Property 3: YAML Round-Trip Preservation
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    glossary=st.builds(
        Glossary,
        characters=st.lists(
            st.builds(
                GlossaryEntry,
                name=st.text(
                    min_size=1,
                    max_size=50,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                raw=st.text(
                    min_size=1,
                    max_size=100,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                aliases=st.lists(
                    st.text(
                        min_size=1,
                        max_size=30,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    ),
                    max_size=5
                ),
                desc=st.one_of(
                    st.none(),
                    st.text(
                        min_size=1,
                        max_size=200,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    )
                )
            ),
            max_size=5
        ),
        factions=st.lists(
            st.builds(
                GlossaryEntry,
                name=st.text(
                    min_size=1,
                    max_size=50,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                raw=st.text(
                    min_size=1,
                    max_size=100,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                aliases=st.lists(
                    st.text(
                        min_size=1,
                        max_size=30,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    ),
                    max_size=5
                ),
                desc=st.one_of(
                    st.none(),
                    st.text(
                        min_size=1,
                        max_size=200,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    )
                )
            ),
            max_size=5
        ),
        locations=st.lists(
            st.builds(
                GlossaryEntry,
                name=st.text(
                    min_size=1,
                    max_size=50,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                raw=st.text(
                    min_size=1,
                    max_size=100,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                aliases=st.lists(
                    st.text(
                        min_size=1,
                        max_size=30,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    ),
                    max_size=5
                ),
                desc=st.one_of(
                    st.none(),
                    st.text(
                        min_size=1,
                        max_size=200,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    )
                )
            ),
            max_size=5
        ),
        terms=st.lists(
            st.builds(
                GlossaryEntry,
                name=st.text(
                    min_size=1,
                    max_size=50,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                raw=st.text(
                    min_size=1,
                    max_size=100,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                aliases=st.lists(
                    st.text(
                        min_size=1,
                        max_size=30,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    ),
                    max_size=5
                ),
                desc=st.one_of(
                    st.none(),
                    st.text(
                        min_size=1,
                        max_size=200,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    )
                )
            ),
            max_size=5
        )
    )
)
def test_property_3_yaml_round_trip_preservation(glossary, tmp_path):
    """
    Property 3: YAML Round-Trip Preservation
    
    For any valid Glossary object, saving to YAML and loading back should
    produce an equivalent Glossary object with identical data.
    
    Validates: Requirements 1.1, 1.7
    """
    from babel.context.store import GlossaryStore
    
    # Create temporary glossary file
    glossary_path = tmp_path / "test_glossary.yaml"
    store = GlossaryStore(glossary_path)
    
    # Save glossary
    store.save(glossary)
    
    # Verify file was created
    assert glossary_path.exists()
    
    # Load glossary back
    loaded = store.load()
    
    # Verify data is identical
    assert loaded == glossary
    assert loaded.total_entries() == glossary.total_entries()
    
    # Verify each category
    assert loaded.characters == glossary.characters
    assert loaded.factions == glossary.factions
    assert loaded.locations == glossary.locations
    assert loaded.terms == glossary.terms


# Feature: akashic-record, Property 4: Comment Preservation During Updates
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    initial_glossary=st.builds(
        Glossary,
        characters=st.lists(
            st.builds(
                GlossaryEntry,
                name=st.text(
                    min_size=1,
                    max_size=50,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                raw=st.text(
                    min_size=1,
                    max_size=100,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                aliases=st.lists(
                    st.text(
                        min_size=1,
                        max_size=30,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    ),
                    max_size=3
                ),
                desc=st.one_of(
                    st.none(),
                    st.text(
                        min_size=1,
                        max_size=100,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    )
                )
            ),
            min_size=1,
            max_size=3
        )
    ),
    new_entry=st.builds(
        GlossaryEntry,
        name=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
        ),
        raw=st.text(
            min_size=1,
            max_size=100,
            alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
        ),
        aliases=st.lists(
            st.text(
                min_size=1,
                max_size=30,
                alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
            ),
            max_size=3
        ),
        desc=st.one_of(
            st.none(),
            st.text(
                min_size=1,
                max_size=100,
                alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
            )
        )
    )
)
def test_property_4_comment_preservation_during_updates(initial_glossary, new_entry, tmp_path):
    """
    Property 4: Comment Preservation During Updates
    
    For any YAML file with comments, loading, modifying entries, and saving
    should preserve all original comments and formatting.
    
    Validates: Requirements 5.6
    """
    from babel.context.store import GlossaryStore
    
    # Create temporary glossary file
    glossary_path = tmp_path / "test_glossary.yaml"
    store = GlossaryStore(glossary_path)
    
    # Save initial glossary
    store.save(initial_glossary)
    
    # Add comments manually to the YAML file
    with open(glossary_path, 'r', encoding='utf-8') as f:
        original_content = f.read()
    
    # Insert comments at the beginning and between sections
    commented_content = (
        "# This is a test glossary\n"
        "# Generated for property testing\n"
        + original_content
    )
    
    # Also add inline comments if there are characters
    if initial_glossary.characters:
        commented_content = commented_content.replace(
            "characters:",
            "# Character definitions\ncharacters:"
        )
    
    with open(glossary_path, 'w', encoding='utf-8') as f:
        f.write(commented_content)
    
    # Read the commented content
    with open(glossary_path, 'r', encoding='utf-8') as f:
        content_with_comments = f.read()
    
    # Verify comments are present
    assert "# This is a test glossary" in content_with_comments
    assert "# Generated for property testing" in content_with_comments
    
    # Load glossary (should preserve comments internally)
    loaded = store.load()
    
    # Add a new entry to the characters category
    loaded.characters.append(new_entry)
    
    # Save the modified glossary
    store.save(loaded)
    
    # Read the file again
    with open(glossary_path, 'r', encoding='utf-8') as f:
        content_after_update = f.read()
    
    # Verify comments are still present after update
    # Note: ruamel.yaml preserves comments, but their exact position may vary
    # We verify that the comment text is still in the file
    assert "# This is a test glossary" in content_after_update
    assert "# Generated for property testing" in content_after_update
    
    # Verify the new entry was added
    reloaded = store.load()
    assert len(reloaded.characters) == len(initial_glossary.characters) + 1
    assert new_entry in reloaded.characters



# Feature: akashic-record, Property 5: Merge Idempotency
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    existing_glossary=st.builds(
        Glossary,
        characters=st.lists(
            st.builds(
                GlossaryEntry,
                name=st.text(
                    min_size=1,
                    max_size=50,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                raw=st.text(
                    min_size=1,
                    max_size=100,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                aliases=st.lists(
                    st.text(
                        min_size=1,
                        max_size=30,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    ),
                    max_size=3
                ),
                desc=st.one_of(
                    st.none(),
                    st.text(
                        min_size=1,
                        max_size=100,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    )
                )
            ),
            min_size=1,
            max_size=5
        ),
        factions=st.lists(
            st.builds(
                GlossaryEntry,
                name=st.text(
                    min_size=1,
                    max_size=50,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                raw=st.text(
                    min_size=1,
                    max_size=100,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                aliases=st.lists(
                    st.text(
                        min_size=1,
                        max_size=30,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    ),
                    max_size=3
                ),
                desc=st.one_of(
                    st.none(),
                    st.text(
                        min_size=1,
                        max_size=100,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    )
                )
            ),
            max_size=5
        ),
        locations=st.lists(
            st.builds(
                GlossaryEntry,
                name=st.text(
                    min_size=1,
                    max_size=50,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                raw=st.text(
                    min_size=1,
                    max_size=100,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                aliases=st.lists(
                    st.text(
                        min_size=1,
                        max_size=30,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    ),
                    max_size=3
                ),
                desc=st.one_of(
                    st.none(),
                    st.text(
                        min_size=1,
                        max_size=100,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    )
                )
            ),
            max_size=5
        ),
        terms=st.lists(
            st.builds(
                GlossaryEntry,
                name=st.text(
                    min_size=1,
                    max_size=50,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                raw=st.text(
                    min_size=1,
                    max_size=100,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                aliases=st.lists(
                    st.text(
                        min_size=1,
                        max_size=30,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    ),
                    max_size=3
                ),
                desc=st.one_of(
                    st.none(),
                    st.text(
                        min_size=1,
                        max_size=100,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    )
                )
            ),
            max_size=5
        )
    ),
    new_glossary=st.builds(
        Glossary,
        characters=st.lists(
            st.builds(
                GlossaryEntry,
                name=st.text(
                    min_size=1,
                    max_size=50,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                raw=st.text(
                    min_size=1,
                    max_size=100,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                aliases=st.lists(
                    st.text(
                        min_size=1,
                        max_size=30,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    ),
                    max_size=3
                ),
                desc=st.one_of(
                    st.none(),
                    st.text(
                        min_size=1,
                        max_size=100,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    )
                )
            ),
            max_size=5
        ),
        factions=st.lists(
            st.builds(
                GlossaryEntry,
                name=st.text(
                    min_size=1,
                    max_size=50,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                raw=st.text(
                    min_size=1,
                    max_size=100,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                aliases=st.lists(
                    st.text(
                        min_size=1,
                        max_size=30,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    ),
                    max_size=3
                ),
                desc=st.one_of(
                    st.none(),
                    st.text(
                        min_size=1,
                        max_size=100,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    )
                )
            ),
            max_size=5
        ),
        locations=st.lists(
            st.builds(
                GlossaryEntry,
                name=st.text(
                    min_size=1,
                    max_size=50,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                raw=st.text(
                    min_size=1,
                    max_size=100,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                aliases=st.lists(
                    st.text(
                        min_size=1,
                        max_size=30,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    ),
                    max_size=3
                ),
                desc=st.one_of(
                    st.none(),
                    st.text(
                        min_size=1,
                        max_size=100,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    )
                )
            ),
            max_size=5
        ),
        terms=st.lists(
            st.builds(
                GlossaryEntry,
                name=st.text(
                    min_size=1,
                    max_size=50,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                raw=st.text(
                    min_size=1,
                    max_size=100,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                aliases=st.lists(
                    st.text(
                        min_size=1,
                        max_size=30,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    ),
                    max_size=3
                ),
                desc=st.one_of(
                    st.none(),
                    st.text(
                        min_size=1,
                        max_size=100,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    )
                )
            ),
            max_size=5
        )
    )
)
def test_property_5_merge_idempotency(existing_glossary, new_glossary, tmp_path):
    """
    Property 5: Merge Idempotency
    
    For any existing Glossary and newly extracted Glossary, merging twice
    should produce the same result as merging once (idempotent operation).
    
    Validates: Requirements 2.6
    """
    from babel.context.store import GlossaryStore
    
    # Create temporary glossary file
    glossary_path = tmp_path / "test_glossary.yaml"
    store = GlossaryStore(glossary_path)
    
    # Save existing glossary
    store.save(existing_glossary)
    
    # Merge once
    merged_once = store.merge(new_glossary)
    
    # Save the merged result
    store.save(merged_once)
    
    # Merge again with the same new glossary
    merged_twice = store.merge(new_glossary)
    
    # Verify idempotency: merging twice produces same result as merging once
    assert merged_once == merged_twice
    assert merged_once.total_entries() == merged_twice.total_entries()
    
    # Verify each category
    assert merged_once.characters == merged_twice.characters
    assert merged_once.factions == merged_twice.factions
    assert merged_once.locations == merged_twice.locations
    assert merged_once.terms == merged_twice.terms



# Feature: akashic-record, Property 6: User Edit Preservation During Merge
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    # Generate an entry that will be in both glossaries (same name)
    shared_name=st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
    ),
    # Original entry (user-edited version)
    original_raw=st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
    ),
    original_aliases=st.lists(
        st.text(
            min_size=1,
            max_size=30,
            alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
        ),
        min_size=1,
        max_size=3
    ),
    original_desc=st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
    ),
    # New entry (from extraction, different raw but same name)
    new_raw=st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
    ),
    new_aliases=st.lists(
        st.text(
            min_size=1,
            max_size=30,
            alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
        ),
        max_size=3
    ),
    new_desc=st.one_of(
        st.none(),
        st.text(
            min_size=1,
            max_size=100,
            alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
        )
    )
)
def test_property_6_user_edit_preservation_during_merge(
    shared_name,
    original_raw,
    original_aliases,
    original_desc,
    new_raw,
    new_aliases,
    new_desc,
    tmp_path
):
    """
    Property 6: User Edit Preservation During Merge
    
    For any Glossary with user-edited fields (name, aliases, desc), merging
    with a new extraction should preserve all user edits and only add new
    entries or update raw fields.
    
    Validates: Requirements 2.7
    """
    from babel.context.store import GlossaryStore
    
    # Create existing glossary with user-edited entry
    existing_entry = GlossaryEntry(
        name=shared_name,
        raw=original_raw,
        aliases=original_aliases,
        desc=original_desc
    )
    
    existing_glossary = Glossary(
        characters=[existing_entry]
    )
    
    # Create new glossary with same name but different fields
    # (simulating a new extraction that might have different data)
    new_entry = GlossaryEntry(
        name=shared_name,  # Same name (identifies the entry)
        raw=new_raw,  # Different raw (from new extraction)
        aliases=new_aliases,  # Different aliases (from new extraction)
        desc=new_desc  # Different desc (from new extraction)
    )
    
    new_glossary = Glossary(
        characters=[new_entry]
    )
    
    # Create temporary glossary file
    glossary_path = tmp_path / "test_glossary.yaml"
    store = GlossaryStore(glossary_path)
    
    # Save existing glossary (with user edits)
    store.save(existing_glossary)
    
    # Merge with new glossary
    merged = store.merge(new_glossary)
    
    # Verify user edits are preserved
    assert len(merged.characters) == 1  # Should still have only one entry
    merged_entry = merged.characters[0]
    
    # User-edited fields should be preserved from original
    assert merged_entry.name == shared_name  # Name preserved
    assert merged_entry.aliases == original_aliases  # User-edited aliases preserved
    assert merged_entry.desc == original_desc  # User-edited desc preserved
    
    # Raw field should be updated from new extraction (if different)
    if original_raw != new_raw:
        assert merged_entry.raw == new_raw  # Raw updated from new extraction
    else:
        assert merged_entry.raw == original_raw  # Raw unchanged if same



# Feature: akashic-record, Property 7: Configurable Chapter Scanning
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    num_chapters=st.integers(min_value=1, max_value=100)
)
def test_property_7_configurable_chapter_scanning(num_chapters, tmp_path, mocker):
    """
    Property 7: Configurable Chapter Scanning
    
    For any valid num_chapters parameter (1-100), The Cartographer should
    process exactly that many chapters, no more, no less.
    
    Validates: Requirements 2.2, 8.1
    """
    from babel.context.cartographer import Cartographer
    from babel.transform.gemini_client import GeminiClient
    import json
    
    # Create temporary chapter files (more than num_chapters to test limiting)
    total_chapters = max(num_chapters + 10, 110)  # Always have more than requested
    chapter_paths = []
    for i in range(total_chapters):
        chapter_path = tmp_path / f"Ch_{i+1:03d}.txt"
        chapter_path.write_text(f"Chapter {i+1} content with character names and locations.")
        chapter_paths.append(chapter_path)
    
    # Mock GeminiClient
    mock_client = mocker.Mock(spec=GeminiClient)
    
    # Mock response with valid glossary JSON
    mock_response = json.dumps({
        "characters": [
            {
                "name": "Test Character",
                "raw": "테스트",
                "aliases": ["TC"],
                "desc": "A test character"
            }
        ],
        "factions": [],
        "locations": [],
        "terms": []
    })
    mock_client.generate_content.return_value = mock_response
    
    # Create Cartographer
    cartographer = Cartographer(mock_client)
    
    # Extract glossary with specified num_chapters
    glossary = cartographer.extract_glossary(chapter_paths, num_chapters=num_chapters)
    
    # Verify API was called (extraction happened)
    assert mock_client.generate_content.called
    
    # Get the prompt that was sent to the API
    call_args = mock_client.generate_content.call_args
    prompt = call_args[0][0]  # First positional argument
    
    # Count chapter breaks in the prompt to verify correct number of chapters processed
    chapter_breaks = prompt.count("---CHAPTER BREAK---")
    
    # Number of breaks = num_chapters - 1 (breaks between chapters)
    expected_breaks = num_chapters - 1
    assert chapter_breaks == expected_breaks, (
        f"Expected {expected_breaks} chapter breaks for {num_chapters} chapters, "
        f"but found {chapter_breaks}"
    )
    
    # Verify glossary was returned (even if empty)
    assert isinstance(glossary, Glossary)



# Feature: akashic-record, Property 8: Glossary Section Completeness
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    glossary=st.builds(
        Glossary,
        characters=st.lists(
            st.builds(
                GlossaryEntry,
                name=st.text(
                    min_size=1,
                    max_size=50,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                raw=st.text(
                    min_size=1,
                    max_size=100,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                aliases=st.lists(
                    st.text(
                        min_size=1,
                        max_size=30,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    ),
                    min_size=1,
                    max_size=3
                ),
                desc=st.one_of(
                    st.none(),
                    st.text(
                        min_size=1,
                        max_size=100,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    )
                )
            ),
            min_size=1,
            max_size=5
        ),
        factions=st.lists(
            st.builds(
                GlossaryEntry,
                name=st.text(
                    min_size=1,
                    max_size=50,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                raw=st.text(
                    min_size=1,
                    max_size=100,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                aliases=st.lists(
                    st.text(
                        min_size=1,
                        max_size=30,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    ),
                    min_size=1,
                    max_size=3
                ),
                desc=st.one_of(
                    st.none(),
                    st.text(
                        min_size=1,
                        max_size=100,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    )
                )
            ),
            min_size=1,
            max_size=5
        ),
        locations=st.lists(
            st.builds(
                GlossaryEntry,
                name=st.text(
                    min_size=1,
                    max_size=50,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                raw=st.text(
                    min_size=1,
                    max_size=100,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                aliases=st.lists(
                    st.text(
                        min_size=1,
                        max_size=30,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    ),
                    min_size=1,
                    max_size=3
                ),
                desc=st.one_of(
                    st.none(),
                    st.text(
                        min_size=1,
                        max_size=100,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    )
                )
            ),
            min_size=1,
            max_size=5
        ),
        terms=st.lists(
            st.builds(
                GlossaryEntry,
                name=st.text(
                    min_size=1,
                    max_size=50,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                raw=st.text(
                    min_size=1,
                    max_size=100,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                aliases=st.lists(
                    st.text(
                        min_size=1,
                        max_size=30,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    ),
                    min_size=1,
                    max_size=3
                ),
                desc=st.one_of(
                    st.none(),
                    st.text(
                        min_size=1,
                        max_size=100,
                        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                    )
                )
            ),
            min_size=1,
            max_size=5
        )
    )
)
def test_property_8_glossary_section_completeness(glossary, tmp_path):
    """
    Property 8: Glossary Section Completeness
    
    For any Glossary with entries in any category, the formatted Markdown
    section must include all entries from all four categories with their
    names, raw patterns, and aliases.
    
    Validates: Requirements 3.3, 3.5, 3.6, 3.7, 3.8
    """
    from babel.context.store import GlossaryStore
    from babel.context.injector import ContextInjector
    
    # Create temporary glossary file
    glossary_path = tmp_path / "test_glossary.yaml"
    store = GlossaryStore(glossary_path)
    
    # Save glossary
    store.save(glossary)
    
    # Create ContextInjector
    injector = ContextInjector(store)
    
    # Format glossary section
    formatted = injector._format_glossary_section(glossary)
    
    # Verify section header is present
    assert "## NARRATIVE CONTEXT & GLOSSARY" in formatted
    assert "**CRITICAL**" in formatted
    assert "**REMINDER**" in formatted
    
    # Verify all categories with entries are present
    if glossary.characters:
        assert "### Characters" in formatted
        for entry in glossary.characters:
            # Verify name is present
            assert entry.name in formatted
            # Verify raw pattern is present
            assert entry.raw in formatted
            # Verify aliases are present
            for alias in entry.aliases:
                assert alias in formatted
    
    if glossary.factions:
        assert "### Factions" in formatted
        for entry in glossary.factions:
            assert entry.name in formatted
            assert entry.raw in formatted
            for alias in entry.aliases:
                assert alias in formatted
    
    if glossary.locations:
        assert "### Locations" in formatted
        for entry in glossary.locations:
            assert entry.name in formatted
            assert entry.raw in formatted
            for alias in entry.aliases:
                assert alias in formatted
    
    if glossary.terms:
        assert "### Terms" in formatted
        for entry in glossary.terms:
            assert entry.name in formatted
            assert entry.raw in formatted
            for alias in entry.aliases:
                assert alias in formatted
    
    # Verify entry format includes all required elements
    for entry in (glossary.characters + glossary.factions + 
                  glossary.locations + glossary.terms):
        # Each entry should have: **Name** (raw)
        expected_format = f"**{entry.name}** ({entry.raw})"
        assert expected_format in formatted
        
        # If aliases exist, they should be listed
        if entry.aliases:
            # Check that "Aliases:" appears after the entry name
            name_pos = formatted.find(entry.name)
            aliases_pos = formatted.find("Aliases:", name_pos)
            # Verify aliases section exists for this entry
            assert aliases_pos > name_pos, f"Aliases section not found for {entry.name}"
        
        # If description exists, it should be listed
        if entry.desc:
            # Check that "Context:" appears after the entry name
            name_pos = formatted.find(entry.name)
            context_pos = formatted.find("Context:", name_pos)
            # Verify context section exists for this entry
            assert context_pos > name_pos, f"Context section not found for {entry.name}"
            # Verify the actual description text is present
            assert entry.desc in formatted



# Feature: akashic-record, Property 9: Context Injection Token Limit
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    # Generate a large glossary that might exceed token limits
    num_entries_per_category=st.integers(min_value=50, max_value=200)
)
def test_property_9_context_injection_token_limit(num_entries_per_category, tmp_path):
    """
    Property 9: Context Injection Token Limit
    
    For any Glossary, the formatted context section must not exceed 1M tokens
    (Gemini's context window limit).
    
    Validates: Requirements 3.10
    """
    from babel.context.store import GlossaryStore
    from babel.context.injector import ContextInjector
    
    # Create a large glossary with many entries
    characters = []
    for i in range(num_entries_per_category):
        characters.append(GlossaryEntry(
            name=f"Character_{i}",
            raw=f"キャラクター_{i}|Character_{i}",
            aliases=[f"Alias_{i}_1", f"Alias_{i}_2", f"Alias_{i}_3"],
            desc=f"This is a detailed description for character {i}. " * 10  # Long description
        ))
    
    factions = []
    for i in range(num_entries_per_category):
        factions.append(GlossaryEntry(
            name=f"Faction_{i}",
            raw=f"派閥_{i}|Faction_{i}",
            aliases=[f"Faction_Alias_{i}_1", f"Faction_Alias_{i}_2"],
            desc=f"This is a detailed description for faction {i}. " * 10
        ))
    
    locations = []
    for i in range(num_entries_per_category):
        locations.append(GlossaryEntry(
            name=f"Location_{i}",
            raw=f"場所_{i}|Location_{i}",
            aliases=[f"Location_Alias_{i}_1", f"Location_Alias_{i}_2"],
            desc=f"This is a detailed description for location {i}. " * 10
        ))
    
    terms = []
    for i in range(num_entries_per_category):
        terms.append(GlossaryEntry(
            name=f"Term_{i}",
            raw=f"用語_{i}|Term_{i}",
            aliases=[f"Term_Alias_{i}_1", f"Term_Alias_{i}_2"],
            desc=f"This is a detailed description for term {i}. " * 10
        ))
    
    glossary = Glossary(
        characters=characters,
        factions=factions,
        locations=locations,
        terms=terms
    )
    
    # Create temporary glossary file
    glossary_path = tmp_path / "test_glossary.yaml"
    store = GlossaryStore(glossary_path)
    
    # Save glossary
    store.save(glossary)
    
    # Create ContextInjector
    injector = ContextInjector(store)
    
    # Inject context into a base prompt
    base_prompt = "Transform this chapter into screenplay format."
    enhanced_prompt = injector.inject_context(base_prompt)
    
    # Estimate token count
    token_count = injector._estimate_token_count(enhanced_prompt)
    
    # Verify token limit is not exceeded
    MAX_TOKENS = 1_000_000
    assert token_count <= MAX_TOKENS, (
        f"Enhanced prompt exceeds token limit: {token_count:,} tokens > {MAX_TOKENS:,} tokens"
    )
    
    # Verify base prompt is still present
    assert base_prompt in enhanced_prompt
    
    # If glossary was truncated, verify truncation notice is present
    if glossary.total_entries() > 0:
        glossary_section = injector._format_glossary_section(glossary)
        section_tokens = injector._estimate_token_count(glossary_section)
        
        if section_tokens > MAX_TOKENS:
            # Should have been truncated
            assert "truncated" in enhanced_prompt.lower() or "Truncated" in enhanced_prompt



# Feature: akashic-record, Property 10: Truncation Prioritization
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    # Generate a very large glossary that will definitely exceed token limits
    num_characters=st.integers(min_value=100, max_value=300),
    num_factions=st.integers(min_value=100, max_value=300),
    num_locations=st.integers(min_value=100, max_value=300),
    num_terms=st.integers(min_value=100, max_value=300)
)
def test_property_10_truncation_prioritization(
    num_characters,
    num_factions,
    num_locations,
    num_terms,
    tmp_path
):
    """
    Property 10: Truncation Prioritization
    
    For any Glossary that exceeds token limits, truncation must preserve all
    character entries before removing entries from other categories.
    
    Priority order: characters > factions > locations > terms
    
    Validates: Requirements 7.6
    """
    from babel.context.store import GlossaryStore
    from babel.context.injector import ContextInjector
    
    # Create a very large glossary with many entries in each category
    characters = []
    for i in range(num_characters):
        characters.append(GlossaryEntry(
            name=f"Character_{i}",
            raw=f"キャラクター_{i}|Character_{i}",
            aliases=[f"Alias_{i}_1", f"Alias_{i}_2", f"Alias_{i}_3"],
            desc=f"This is a very detailed description for character {i}. " * 20  # Very long
        ))
    
    factions = []
    for i in range(num_factions):
        factions.append(GlossaryEntry(
            name=f"Faction_{i}",
            raw=f"派閥_{i}|Faction_{i}",
            aliases=[f"Faction_Alias_{i}_1", f"Faction_Alias_{i}_2"],
            desc=f"This is a very detailed description for faction {i}. " * 20
        ))
    
    locations = []
    for i in range(num_locations):
        locations.append(GlossaryEntry(
            name=f"Location_{i}",
            raw=f"場所_{i}|Location_{i}",
            aliases=[f"Location_Alias_{i}_1", f"Location_Alias_{i}_2"],
            desc=f"This is a very detailed description for location {i}. " * 20
        ))
    
    terms = []
    for i in range(num_terms):
        terms.append(GlossaryEntry(
            name=f"Term_{i}",
            raw=f"用語_{i}|Term_{i}",
            aliases=[f"Term_Alias_{i}_1", f"Term_Alias_{i}_2"],
            desc=f"This is a very detailed description for term {i}. " * 20
        ))
    
    glossary = Glossary(
        characters=characters,
        factions=factions,
        locations=locations,
        terms=terms
    )
    
    # Create temporary glossary file
    glossary_path = tmp_path / "test_glossary.yaml"
    store = GlossaryStore(glossary_path)
    
    # Save glossary
    store.save(glossary)
    
    # Create ContextInjector
    injector = ContextInjector(store)
    
    # Set a very low token limit to force truncation
    low_token_limit = 10_000  # Much lower than 1M to force truncation
    
    # Truncate glossary
    truncated_section = injector._truncate_glossary(glossary, max_tokens=low_token_limit)
    
    # Verify token limit is respected
    token_count = injector._estimate_token_count(truncated_section)
    assert token_count <= low_token_limit, (
        f"Truncated section exceeds token limit: {token_count:,} tokens > {low_token_limit:,} tokens"
    )
    
    # Parse the truncated section to count entries by category
    # Count how many entries from each category are present
    character_count = sum(1 for char in characters if char.name in truncated_section)
    faction_count = sum(1 for faction in factions if faction.name in truncated_section)
    location_count = sum(1 for location in locations if location.name in truncated_section)
    term_count = sum(1 for term in terms if term.name in truncated_section)
    
    # Verify prioritization: if any lower-priority category has entries,
    # then all higher-priority categories should be complete
    
    # If terms are present, all characters, factions, and locations should be present
    if term_count > 0:
        assert character_count == num_characters, (
            "Terms present but not all characters included (priority violation)"
        )
        assert faction_count == num_factions, (
            "Terms present but not all factions included (priority violation)"
        )
        assert location_count == num_locations, (
            "Terms present but not all locations included (priority violation)"
        )
    
    # If locations are present, all characters and factions should be present
    if location_count > 0:
        assert character_count == num_characters, (
            "Locations present but not all characters included (priority violation)"
        )
        assert faction_count == num_factions, (
            "Locations present but not all factions included (priority violation)"
        )
    
    # If factions are present, all characters should be present
    if faction_count > 0:
        assert character_count == num_characters, (
            "Factions present but not all characters included (priority violation)"
        )
    
    # Characters should always be prioritized (included first)
    # If any entries are present, characters should be present
    if character_count + faction_count + location_count + term_count > 0:
        assert character_count > 0, (
            "Some entries present but no characters (priority violation)"
        )


# Feature: akashic-record, Property 11: Schema Validation Enforcement
def test_property_11_schema_validation_enforcement(tmp_path):
    """
    Property 11: Schema Validation Enforcement
    
    For any glossary data loaded from YAML, all entries must pass Pydantic
    schema validation, and invalid entries must be skipped with warnings logged.
    
    Validates: Requirements 7.7, 7.8
    """
    from babel.context.store import GlossaryStore
    import logging
    
    # Create temporary glossary file with mixed valid and invalid entries
    glossary_path = tmp_path / "test_glossary.yaml"
    
    # Create YAML content with some invalid entries
    yaml_content = """
characters:
  - name: "Valid Character"
    raw: "valid_raw"
    aliases: ["Alias1", "Alias2"]
    desc: "A valid character entry"
  
  - name: "Missing Raw Field"
    aliases: ["Alias"]
    desc: "This entry is missing the required 'raw' field"
  
  - name: "Valid Character 2"
    raw: "another_valid_raw"
    aliases: []
    desc: null

factions:
  - name: "Valid Faction"
    raw: "faction_raw"
    aliases: []
    desc: "A valid faction"
  
  - raw: "missing_name_field"
    aliases: ["Alias"]
    desc: "This entry is missing the required 'name' field"

locations:
  - name: "Valid Location"
    raw: "location_raw"
    aliases: ["Loc1"]
    desc: "A valid location"

terms:
  - name: "Valid Term"
    raw: "term_raw"
    aliases: []
    desc: null
"""
    
    # Write YAML content to file
    with open(glossary_path, 'w', encoding='utf-8') as f:
        f.write(yaml_content)
    
    # Set up logging capture
    log_messages = []
    
    class ListHandler(logging.Handler):
        def emit(self, record):
            log_messages.append(record)
    
    handler = ListHandler()
    handler.setLevel(logging.WARNING)
    store_logger = logging.getLogger('babel.context.store')
    store_logger.addHandler(handler)
    
    try:
        # Load glossary (should skip invalid entries)
        store = GlossaryStore(glossary_path)
        glossary = store.load()
        
        # Verify that valid entries were loaded
        assert len(glossary.characters) == 2, (
            f"Expected 2 valid characters, got {len(glossary.characters)}"
        )
        assert len(glossary.factions) == 1, (
            f"Expected 1 valid faction, got {len(glossary.factions)}"
        )
        assert len(glossary.locations) == 1, (
            f"Expected 1 valid location, got {len(glossary.locations)}"
        )
        assert len(glossary.terms) == 1, (
            f"Expected 1 valid term, got {len(glossary.terms)}"
        )
        
        # Verify that warnings were logged for invalid entries
        warning_messages = [
            record.getMessage() for record in log_messages
            if record.levelno == logging.WARNING
        ]
        
        # Should have warnings for the 2 invalid entries
        assert len(warning_messages) >= 2, (
            f"Expected at least 2 warnings for invalid entries, got {len(warning_messages)}"
        )
        
        # Verify warning messages mention "Skipping invalid"
        assert any("Skipping invalid" in msg for msg in warning_messages), (
            "Warning messages should mention 'Skipping invalid'"
        )
        
        # Verify that valid entries have correct data
        valid_char_names = {entry.name for entry in glossary.characters}
        assert "Valid Character" in valid_char_names
        assert "Valid Character 2" in valid_char_names
        assert "Missing Raw Field" not in valid_char_names
        
        valid_faction_names = {entry.name for entry in glossary.factions}
        assert "Valid Faction" in valid_faction_names
        
    finally:
        # Remove the handler
        store_logger.removeHandler(handler)



# Feature: akashic-record, Property 12: Glossary Store CRUD Operations
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    # Initial glossary with some entries
    initial_characters=st.lists(
        st.builds(
            GlossaryEntry,
            name=st.text(
                min_size=1,
                max_size=50,
                alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
            ),
            raw=st.text(
                min_size=1,
                max_size=100,
                alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
            ),
            aliases=st.lists(
                st.text(
                    min_size=1,
                    max_size=30,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                ),
                max_size=3
            ),
            desc=st.one_of(
                st.none(),
                st.text(
                    min_size=1,
                    max_size=100,
                    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
                )
            )
        ),
        min_size=1,
        max_size=5
    ),
    # New entry to add
    new_entry=st.builds(
        GlossaryEntry,
        name=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
        ),
        raw=st.text(
            min_size=1,
            max_size=100,
            alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
        ),
        aliases=st.lists(
            st.text(
                min_size=1,
                max_size=30,
                alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
            ),
            max_size=3
        ),
        desc=st.one_of(
            st.none(),
            st.text(
                min_size=1,
                max_size=100,
                alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
            )
        )
    ),
    # Updated entry data
    updated_raw=st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
    ),
    updated_aliases=st.lists(
        st.text(
            min_size=1,
            max_size=30,
            alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
        ),
        max_size=3
    ),
    updated_desc=st.one_of(
        st.none(),
        st.text(
            min_size=1,
            max_size=100,
            alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))
        )
    )
)
def test_property_12_glossary_store_crud_operations(
    initial_characters,
    new_entry,
    updated_raw,
    updated_aliases,
    updated_desc,
    tmp_path
):
    """
    Property 12: Glossary Store CRUD Operations
    
    For any Glossary, programmatic add/update/delete operations should
    correctly modify the glossary and persist changes to YAML.
    
    Validates: Requirements 5.5
    """
    from babel.context.store import GlossaryStore
    
    # Create temporary glossary file
    glossary_path = tmp_path / "test_glossary.yaml"
    store = GlossaryStore(glossary_path)
    
    # Create initial glossary
    initial_glossary = Glossary(characters=initial_characters)
    store.save(initial_glossary)
    
    # Verify initial state
    loaded = store.load()
    assert len(loaded.characters) == len(initial_characters)
    
    # TEST 1: ADD operation
    # Ensure new entry has a unique name (not in initial_characters)
    existing_names = {entry.name for entry in initial_characters}
    if new_entry.name in existing_names:
        # Modify the name to make it unique
        new_entry = GlossaryEntry(
            name=f"{new_entry.name}_unique",
            raw=new_entry.raw,
            aliases=new_entry.aliases,
            desc=new_entry.desc
        )
    
    # Add new entry
    store.add_entry('characters', new_entry)
    
    # Verify entry was added
    loaded = store.load()
    assert len(loaded.characters) == len(initial_characters) + 1
    assert new_entry in loaded.characters
    
    # Verify persistence (reload from file)
    store2 = GlossaryStore(glossary_path)
    reloaded = store2.load()
    assert len(reloaded.characters) == len(initial_characters) + 1
    assert new_entry in reloaded.characters
    
    # TEST 2: UPDATE operation
    # Update the first entry from initial_characters
    # Save original values BEFORE updating (for TEST 4 verification)
    original_entry_name = None
    original_entry_raw = None
    original_entry_aliases = None
    original_entry_desc = None
    
    if initial_characters:
        entry_to_update = initial_characters[0]
        # Save original values before modification
        original_entry_name = entry_to_update.name
        original_entry_raw = entry_to_update.raw
        original_entry_aliases = entry_to_update.aliases
        original_entry_desc = entry_to_update.desc
        
        updated_entry = GlossaryEntry(
            name=entry_to_update.name,  # Keep same name (identifier)
            raw=updated_raw,
            aliases=updated_aliases,
            desc=updated_desc
        )
        
        # Update entry
        store.update_entry('characters', entry_to_update.name, updated_entry)
        
        # Verify entry was updated
        loaded = store.load()
        updated_in_store = next(
            (e for e in loaded.characters if e.name == entry_to_update.name),
            None
        )
        assert updated_in_store is not None
        assert updated_in_store.raw == updated_raw
        assert updated_in_store.aliases == updated_aliases
        assert updated_in_store.desc == updated_desc
        
        # Verify persistence (reload from file)
        store3 = GlossaryStore(glossary_path)
        reloaded = store3.load()
        updated_in_file = next(
            (e for e in reloaded.characters if e.name == entry_to_update.name),
            None
        )
        assert updated_in_file is not None
        assert updated_in_file.raw == updated_raw
        assert updated_in_file.aliases == updated_aliases
        assert updated_in_file.desc == updated_desc
    
    # TEST 3: DELETE operation
    # Delete the new entry we added
    store.delete_entry('characters', new_entry.name)
    
    # Verify entry was deleted
    loaded = store.load()
    assert new_entry not in loaded.characters
    assert len(loaded.characters) == len(initial_characters)
    
    # Verify persistence (reload from file)
    store4 = GlossaryStore(glossary_path)
    reloaded = store4.load()
    assert new_entry not in reloaded.characters
    assert len(reloaded.characters) == len(initial_characters)
    
    # TEST 4: ADD duplicate (should not add)
    # Try to add an entry with a name that already exists
    if initial_characters and original_entry_name is not None:
        duplicate_entry = GlossaryEntry(
            name=original_entry_name,  # Same name as existing entry
            raw="different_raw",
            aliases=["different_alias"],
            desc="different description"
        )
        
        # Try to add duplicate
        store.add_entry('characters', duplicate_entry)
        
        # Verify entry was NOT added (count should remain the same)
        loaded = store.load()
        assert len(loaded.characters) == len(initial_characters)
        
        # Verify the original entry is unchanged (still has updated values from TEST 2)
        entry_in_store = next(
            (e for e in loaded.characters if e.name == original_entry_name),
            None
        )
        assert entry_in_store is not None
        # Should still have the updated values from TEST 2, not the duplicate values
        assert entry_in_store.raw == updated_raw  # Updated value from TEST 2
        assert entry_in_store.aliases == updated_aliases  # Updated value from TEST 2
        assert entry_in_store.desc == updated_desc  # Updated value from TEST 2
    
    # TEST 5: UPDATE non-existent entry (should log warning but not crash)
    non_existent_entry = GlossaryEntry(
        name="NonExistentCharacter_12345",
        raw="test",
        aliases=[],
        desc=None
    )
    
    # Try to update non-existent entry (should not crash)
    store.update_entry('characters', "NonExistentCharacter_12345", non_existent_entry)
    
    # Verify glossary is unchanged
    loaded = store.load()
    assert len(loaded.characters) == len(initial_characters)
    
    # TEST 6: DELETE non-existent entry (should log warning but not crash)
    # Try to delete non-existent entry (should not crash)
    store.delete_entry('characters', "NonExistentCharacter_12345")
    
    # Verify glossary is unchanged
    loaded = store.load()
    assert len(loaded.characters) == len(initial_characters)
