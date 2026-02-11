"""
Unit tests for JSON serialization formatting.
"""

import json
from datetime import datetime, timezone
from babel.transform.models import ChapterData, ScriptBlock, ScriptBlockType


def test_json_has_2_space_indentation():
    """Test that JSON output has 2-space indentation."""
    chapter_data = ChapterData(
        blocks=[
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Test",
                content="Test content"
            )
        ],
        source_hash="a" * 64,
        model_version="gemini-1.5-flash"
    )
    
    json_str = chapter_data.model_dump_json(indent=2)
    
    # Check for 2-space indentation
    lines = json_str.split('\n')
    
    # Find indented lines
    indented_lines = [line for line in lines if line.startswith('  ') and not line.startswith('    ')]
    
    # Should have some lines with 2-space indentation
    assert len(indented_lines) > 0, "Should have lines with 2-space indentation"
    
    # Check that indented lines use 2 spaces, not tabs or 4 spaces
    for line in indented_lines:
        if line.strip():  # Skip empty lines
            # Count leading spaces
            leading_spaces = len(line) - len(line.lstrip(' '))
            assert leading_spaces % 2 == 0, f"Indentation should be multiples of 2 spaces, got {leading_spaces}"


def test_datetime_is_iso8601_format():
    """Test that datetime is in ISO 8601 format."""
    chapter_data = ChapterData(
        blocks=[
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Test",
                content="Test content"
            )
        ],
        source_hash="a" * 64,
        model_version="gemini-1.5-flash"
    )
    
    json_str = chapter_data.model_dump_json(indent=2)
    parsed = json.loads(json_str)
    
    # Get processed_at field
    processed_at_str = parsed["processed_at"]
    
    # Should be a string
    assert isinstance(processed_at_str, str), "processed_at should be a string"
    
    # Should contain 'T' separator (ISO 8601)
    assert 'T' in processed_at_str, "processed_at should contain 'T' separator (ISO 8601)"
    
    # Should be parseable as datetime
    try:
        parsed_dt = datetime.fromisoformat(processed_at_str.replace('Z', '+00:00'))
        assert parsed_dt is not None
    except ValueError as e:
        raise AssertionError(f"processed_at is not valid ISO 8601: {processed_at_str}, error: {e}")


def test_json_is_valid():
    """Test that output is valid JSON."""
    chapter_data = ChapterData(
        blocks=[
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Test",
                content="Test content"
            ),
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="Action content"
            )
        ],
        source_hash="a" * 64,
        model_version="gemini-1.5-flash"
    )
    
    json_str = chapter_data.model_dump_json(indent=2)
    
    # Should be parseable as JSON
    try:
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict), "Parsed JSON should be a dictionary"
    except json.JSONDecodeError as e:
        raise AssertionError(f"Output is not valid JSON: {e}")


def test_json_contains_all_required_fields():
    """Test that JSON contains all required fields."""
    chapter_data = ChapterData(
        blocks=[
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Test",
                content="Test content"
            )
        ],
        source_hash="a" * 64,
        model_version="gemini-1.5-flash"
    )
    
    json_str = chapter_data.model_dump_json(indent=2)
    parsed = json.loads(json_str)
    
    # Check required fields
    assert "blocks" in parsed, "JSON should contain 'blocks' field"
    assert "source_hash" in parsed, "JSON should contain 'source_hash' field"
    assert "model_version" in parsed, "JSON should contain 'model_version' field"
    assert "processed_at" in parsed, "JSON should contain 'processed_at' field"
    
    # Check blocks structure
    assert isinstance(parsed["blocks"], list), "blocks should be a list"
    assert len(parsed["blocks"]) > 0, "blocks should not be empty"
    
    # Check first block structure
    first_block = parsed["blocks"][0]
    assert "type" in first_block, "Block should contain 'type' field"
    assert "content" in first_block, "Block should contain 'content' field"


def test_json_formatting_is_human_readable():
    """Test that JSON formatting is human-readable."""
    chapter_data = ChapterData(
        blocks=[
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Test",
                content="Test content"
            )
        ],
        source_hash="a" * 64,
        model_version="gemini-1.5-flash"
    )
    
    json_str = chapter_data.model_dump_json(indent=2)
    
    # Should contain newlines (not minified)
    assert '\n' in json_str, "JSON should contain newlines (not minified)"
    
    # Should have multiple lines
    lines = json_str.split('\n')
    assert len(lines) > 5, "JSON should have multiple lines for readability"
    
    # Should not be excessively long (no single-line output)
    max_line_length = max(len(line) for line in lines)
    assert max_line_length < 500, "No single line should be excessively long"
