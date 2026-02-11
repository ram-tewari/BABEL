"""
Unit tests for The Cartographer (entity extraction agent).

Tests extraction prompt generation, JSON response parsing, retry logic,
and token estimation with mocked Gemini API.
"""

import pytest
import json
from pathlib import Path
from pydantic import ValidationError

from babel.context.cartographer import Cartographer, CartographerError
from babel.context.models import Glossary, GlossaryEntry
from babel.transform.gemini_client import GeminiClient, RateLimitError


@pytest.fixture
def mock_gemini_client(mocker):
    """Mock Gemini client for testing."""
    mock_client = mocker.Mock(spec=GeminiClient)
    return mock_client


@pytest.fixture
def sample_chapters(tmp_path):
    """Create sample chapter files for testing."""
    chapters = []
    for i in range(5):
        chapter_path = tmp_path / f"Ch_{i+1:03d}.txt"
        content = f"""Chapter {i+1}

Chung Myung stood at the peak of Mount Hua, looking down at the valley below.
The Mount Hua Sect had been his home for many years.

"Sahyung!" called Baek Cheon, running up the mountain path.

Chung Myung turned to face his junior brother. "What is it?"

"The Demonic Cult is attacking the village!" Baek Cheon said urgently.

Chung Myung's eyes narrowed. He gathered his Qi and prepared to descend.
"""
        chapter_path.write_text(content, encoding='utf-8')
        chapters.append(chapter_path)
    
    return chapters


# Test: Extraction prompt generation
def test_extraction_prompt_generation(mock_gemini_client, sample_chapters):
    """
    Test that extraction prompt is correctly formatted with chapter texts.
    
    Validates: Requirements 2.3, 6.1-6.8
    """
    cartographer = Cartographer(mock_gemini_client)
    
    # Read chapter texts
    chapter_texts = []
    for chapter_path in sample_chapters[:3]:
        with open(chapter_path, 'r', encoding='utf-8') as f:
            chapter_texts.append(f.read())
    
    # Build prompt
    prompt = cartographer._build_extraction_prompt(chapter_texts)
    
    # Verify prompt structure
    assert "# ENTITY EXTRACTION TASK" in prompt
    assert "## CATEGORIES TO EXTRACT" in prompt
    assert "Characters" in prompt
    assert "Factions" in prompt
    assert "Locations" in prompt
    assert "Terms" in prompt
    assert "## EXTRACTION RULES" in prompt
    assert "## OUTPUT FORMAT" in prompt
    assert "## CHAPTERS TO ANALYZE" in prompt
    
    # Verify chapter texts are included
    for text in chapter_texts:
        assert text in prompt
    
    # Verify chapter breaks
    assert "---CHAPTER BREAK---" in prompt
    # Should have 2 breaks for 3 chapters
    assert prompt.count("---CHAPTER BREAK---") == 2


# Test: JSON response parsing (valid response)
def test_json_response_parsing_valid(mock_gemini_client):
    """
    Test parsing of valid JSON response into Glossary object.
    
    Validates: Requirements 2.3, 2.4
    """
    cartographer = Cartographer(mock_gemini_client)
    
    # Valid JSON response
    response = json.dumps({
        "characters": [
            {
                "name": "Chung Myung",
                "raw": "청명|Chung Myung",
                "aliases": ["The Divine Dragon", "Sahyung"],
                "desc": "Protagonist. Former Divine Dragon, reincarnated."
            },
            {
                "name": "Baek Cheon",
                "raw": "백천|Baek Cheon",
                "aliases": ["Righteous Sword"],
                "desc": "Senior disciple of Mount Hua Sect."
            }
        ],
        "factions": [
            {
                "name": "Mount Hua Sect",
                "raw": "화산파|Mount Hua Sect",
                "aliases": ["Plum Blossom Sect"],
                "desc": "One of the Nine Great Sects."
            }
        ],
        "locations": [
            {
                "name": "Mount Hua",
                "raw": "화산|Mount Hua",
                "aliases": ["Hua Mountain"],
                "desc": "Sacred mountain where Mount Hua Sect is located."
            }
        ],
        "terms": [
            {
                "name": "Qi",
                "raw": "기|Qi",
                "aliases": ["Internal Energy", "Ki"],
                "desc": "Life force energy used in martial arts."
            }
        ]
    })
    
    # Parse response
    glossary = cartographer._parse_extraction_response(response)
    
    # Verify glossary structure
    assert isinstance(glossary, Glossary)
    assert len(glossary.characters) == 2
    assert len(glossary.factions) == 1
    assert len(glossary.locations) == 1
    assert len(glossary.terms) == 1
    
    # Verify character entries
    assert glossary.characters[0].name == "Chung Myung"
    assert glossary.characters[0].raw == "청명|Chung Myung"
    assert "The Divine Dragon" in glossary.characters[0].aliases
    
    assert glossary.characters[1].name == "Baek Cheon"
    assert glossary.characters[1].raw == "백천|Baek Cheon"


# Test: JSON response parsing (invalid JSON)
def test_json_response_parsing_invalid_json(mock_gemini_client):
    """
    Test that invalid JSON raises CartographerError.
    
    Validates: Requirements 2.3, 7.3
    """
    cartographer = Cartographer(mock_gemini_client)
    
    # Invalid JSON
    invalid_response = "This is not valid JSON {broken"
    
    with pytest.raises(CartographerError) as exc_info:
        cartographer._parse_extraction_response(invalid_response)
    
    assert "Invalid JSON response" in str(exc_info.value)


# Test: JSON response parsing (invalid schema)
def test_json_response_parsing_invalid_schema(mock_gemini_client):
    """
    Test that JSON with invalid schema raises CartographerError.
    
    Validates: Requirements 2.3, 6.7, 7.7
    """
    cartographer = Cartographer(mock_gemini_client)
    
    # Valid JSON but missing required fields
    invalid_response = json.dumps({
        "characters": [
            {
                "name": "Test Character"
                # Missing 'raw' field (required)
            }
        ],
        "factions": [],
        "locations": [],
        "terms": []
    })
    
    with pytest.raises(CartographerError) as exc_info:
        cartographer._parse_extraction_response(invalid_response)
    
    assert "Response validation failed" in str(exc_info.value)


# Test: Successful extraction
def test_extract_glossary_success(mock_gemini_client, sample_chapters):
    """
    Test successful glossary extraction from chapters.
    
    Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.8
    """
    # Mock successful API response
    mock_response = json.dumps({
        "characters": [
            {
                "name": "Chung Myung",
                "raw": "청명",
                "aliases": ["The Divine Dragon"],
                "desc": "Protagonist"
            }
        ],
        "factions": [
            {
                "name": "Mount Hua Sect",
                "raw": "화산파",
                "aliases": [],
                "desc": "Main sect"
            }
        ],
        "locations": [],
        "terms": []
    })
    mock_gemini_client.generate_content.return_value = mock_response
    
    cartographer = Cartographer(mock_gemini_client)
    
    # Extract glossary from 3 chapters
    glossary = cartographer.extract_glossary(sample_chapters, num_chapters=3)
    
    # Verify API was called
    assert mock_gemini_client.generate_content.called
    
    # Verify glossary structure
    assert isinstance(glossary, Glossary)
    assert len(glossary.characters) == 1
    assert len(glossary.factions) == 1
    assert glossary.characters[0].name == "Chung Myung"
    assert glossary.factions[0].name == "Mount Hua Sect"


# Test: Extract glossary with default num_chapters
def test_extract_glossary_default_num_chapters(mock_gemini_client, sample_chapters):
    """
    Test that default num_chapters is 3.
    
    Validates: Requirements 2.2, 8.1
    """
    mock_response = json.dumps({
        "characters": [],
        "factions": [],
        "locations": [],
        "terms": []
    })
    mock_gemini_client.generate_content.return_value = mock_response
    
    cartographer = Cartographer(mock_gemini_client)
    
    # Extract without specifying num_chapters (should default to 3)
    glossary = cartographer.extract_glossary(sample_chapters)
    
    # Verify API was called
    assert mock_gemini_client.generate_content.called
    
    # Get the prompt
    call_args = mock_gemini_client.generate_content.call_args
    prompt = call_args[0][0]
    
    # Should have 2 chapter breaks for 3 chapters
    assert prompt.count("---CHAPTER BREAK---") == 2


# Test: Extract glossary with custom num_chapters
def test_extract_glossary_custom_num_chapters(mock_gemini_client, sample_chapters):
    """
    Test extraction with custom num_chapters parameter.
    
    Validates: Requirements 2.2, 8.1
    """
    mock_response = json.dumps({
        "characters": [],
        "factions": [],
        "locations": [],
        "terms": []
    })
    mock_gemini_client.generate_content.return_value = mock_response
    
    cartographer = Cartographer(mock_gemini_client)
    
    # Extract with 2 chapters
    glossary = cartographer.extract_glossary(sample_chapters, num_chapters=2)
    
    # Get the prompt
    call_args = mock_gemini_client.generate_content.call_args
    prompt = call_args[0][0]
    
    # Should have 1 chapter break for 2 chapters
    assert prompt.count("---CHAPTER BREAK---") == 1


# Test: Invalid num_chapters parameter
def test_extract_glossary_invalid_num_chapters(mock_gemini_client, sample_chapters):
    """
    Test that invalid num_chapters raises ValueError.
    
    Validates: Requirements 2.2, 8.1
    """
    cartographer = Cartographer(mock_gemini_client)
    
    # Test num_chapters < 1
    with pytest.raises(ValueError) as exc_info:
        cartographer.extract_glossary(sample_chapters, num_chapters=0)
    assert "must be between 1 and 100" in str(exc_info.value)
    
    # Test num_chapters > 100
    with pytest.raises(ValueError) as exc_info:
        cartographer.extract_glossary(sample_chapters, num_chapters=101)
    assert "must be between 1 and 100" in str(exc_info.value)


# Test: Empty chapter list
def test_extract_glossary_empty_chapters(mock_gemini_client):
    """
    Test that empty chapter list raises ValueError.
    
    Validates: Requirements 2.1
    """
    cartographer = Cartographer(mock_gemini_client)
    
    with pytest.raises(ValueError) as exc_info:
        cartographer.extract_glossary([], num_chapters=3)
    assert "No chapter paths provided" in str(exc_info.value)


# Test: Retry logic on rate limit error
def test_retry_logic_on_rate_limit(mock_gemini_client, sample_chapters):
    """
    Test that rate limit errors trigger retry logic.
    
    Validates: Requirements 2.9, 6.1
    """
    # Mock rate limit error on first call, success on second
    mock_gemini_client.generate_content.side_effect = [
        RateLimitError("Rate limit exceeded"),
        json.dumps({
            "characters": [],
            "factions": [],
            "locations": [],
            "terms": []
        })
    ]
    
    cartographer = Cartographer(mock_gemini_client)
    
    # Should succeed after retry
    glossary = cartographer.extract_glossary(sample_chapters, num_chapters=1)
    
    # Verify API was called twice (initial + retry)
    assert mock_gemini_client.generate_content.call_count == 2
    
    # Verify glossary was returned
    assert isinstance(glossary, Glossary)


# Test: Retry logic exhausted
def test_retry_logic_exhausted(mock_gemini_client, sample_chapters):
    """
    Test that exhausted retries raise CartographerError.
    
    Validates: Requirements 2.9, 7.3, 7.4
    """
    # Mock rate limit error on all attempts
    mock_gemini_client.generate_content.side_effect = RateLimitError("Rate limit exceeded")
    
    cartographer = Cartographer(mock_gemini_client)
    
    # Should fail after all retries
    with pytest.raises(CartographerError) as exc_info:
        cartographer.extract_glossary(sample_chapters, num_chapters=1)
    
    assert "Failed to extract glossary" in str(exc_info.value)
    
    # Verify API was called 3 times (max retries)
    assert mock_gemini_client.generate_content.call_count == 3


# Test: Token estimation
def test_token_estimation(mock_gemini_client, sample_chapters, caplog):
    """
    Test that token usage is estimated and logged.
    
    Validates: Requirements 2.10, 8.6, 8.7
    """
    import logging
    caplog.set_level(logging.INFO)
    
    mock_response = json.dumps({
        "characters": [],
        "factions": [],
        "locations": [],
        "terms": []
    })
    mock_gemini_client.generate_content.return_value = mock_response
    
    cartographer = Cartographer(mock_gemini_client)
    
    # Extract glossary
    glossary = cartographer.extract_glossary(sample_chapters, num_chapters=2)
    
    # Verify token estimation was logged
    assert any("Estimated input:" in record.message for record in caplog.records)
    assert any("tokens" in record.message for record in caplog.records)
    assert any("Estimated output:" in record.message for record in caplog.records)
    
    # Verify cost logging (FREE tier)
    assert any("Cost: $0.00" in record.message for record in caplog.records)
    assert any("FREE tier" in record.message for record in caplog.records)


# Test: Logging of extraction results
def test_extraction_results_logging(mock_gemini_client, sample_chapters, caplog):
    """
    Test that extraction results are logged.
    
    Validates: Requirements 2.8
    """
    import logging
    caplog.set_level(logging.INFO)
    
    mock_response = json.dumps({
        "characters": [
            {"name": "Char1", "raw": "C1", "aliases": [], "desc": "Test"}
        ],
        "factions": [
            {"name": "Faction1", "raw": "F1", "aliases": [], "desc": "Test"}
        ],
        "locations": [],
        "terms": []
    })
    mock_gemini_client.generate_content.return_value = mock_response
    
    cartographer = Cartographer(mock_gemini_client)
    
    # Extract glossary
    glossary = cartographer.extract_glossary(sample_chapters, num_chapters=1)
    
    # Verify extraction results were logged
    assert any("Extracted 2 entities" in record.message for record in caplog.records)
    assert any("1 characters" in record.message for record in caplog.records)
    assert any("1 factions" in record.message for record in caplog.records)


# Test: Unreadable chapter file
def test_unreadable_chapter_file(mock_gemini_client, tmp_path, caplog):
    """
    Test that unreadable chapter files are skipped with warning.
    
    Validates: Requirements 7.2
    """
    import logging
    caplog.set_level(logging.WARNING)
    
    # Create a chapter file
    chapter_path = tmp_path / "Ch_001.txt"
    chapter_path.write_text("Test content")
    
    # Create a non-existent path
    bad_path = tmp_path / "nonexistent.txt"
    
    mock_response = json.dumps({
        "characters": [],
        "factions": [],
        "locations": [],
        "terms": []
    })
    mock_gemini_client.generate_content.return_value = mock_response
    
    cartographer = Cartographer(mock_gemini_client)
    
    # Extract with one good and one bad path
    glossary = cartographer.extract_glossary([chapter_path, bad_path], num_chapters=2)
    
    # Verify warning was logged
    assert any("Failed to read" in record.message for record in caplog.records)
    
    # Verify extraction still succeeded with available chapters
    assert isinstance(glossary, Glossary)


# Test: All chapters unreadable
def test_all_chapters_unreadable(mock_gemini_client, tmp_path, caplog):
    """
    Test that if all chapters are unreadable, empty glossary is returned.
    
    Validates: Requirements 7.2
    """
    import logging
    caplog.set_level(logging.WARNING)
    
    # Create non-existent paths
    bad_paths = [tmp_path / f"nonexistent_{i}.txt" for i in range(3)]
    
    cartographer = Cartographer(mock_gemini_client)
    
    # Extract with all bad paths
    glossary = cartographer.extract_glossary(bad_paths, num_chapters=3)
    
    # Verify warning was logged
    assert any("No chapters could be read" in record.message for record in caplog.records)
    
    # Verify empty glossary was returned
    assert isinstance(glossary, Glossary)
    assert glossary.total_entries() == 0
    
    # Verify API was NOT called
    assert not mock_gemini_client.generate_content.called
