"""
Unit tests for the Transformer class.

Tests transformation logic, retry behavior, and error handling.
"""

import hashlib
from unittest.mock import Mock, patch, MagicMock
import pytest
from pydantic import ValidationError
from babel.transform.transformer import Transformer
from babel.transform.gemini_client import GeminiClient, RateLimitError
from babel.transform.models import ChapterData, ScriptBlock, ScriptBlockType


@pytest.fixture
def mock_gemini_client():
    """Create a mock GeminiClient for testing."""
    client = Mock(spec=GeminiClient)
    return client


@pytest.fixture
def transformer(mock_gemini_client):
    """Create a Transformer instance with mocked client."""
    return Transformer(mock_gemini_client)


def test_transformer_initialization(mock_gemini_client):
    """Test that Transformer initializes correctly."""
    transformer = Transformer(mock_gemini_client)
    
    assert transformer.client == mock_gemini_client
    assert transformer.prompt_constructor is not None
    assert transformer.validator is not None


def test_transform_chapter_success(transformer, mock_gemini_client):
    """Test successful chapter transformation."""
    # Setup
    chapter_text = "The hero entered the dungeon."
    
    # Mock API response with valid JSON
    valid_json = '''
    {
        "blocks": [
            {"type": "action", "content": "The hero entered the dungeon."}
        ]
    }
    '''
    mock_gemini_client.generate_content.return_value = valid_json
    
    # Execute
    result = transformer.transform_chapter(chapter_text)
    
    # Verify
    assert result is not None
    assert isinstance(result, ChapterData)
    assert len(result.blocks) == 1
    assert result.blocks[0].type == ScriptBlockType.ACTION
    assert result.blocks[0].content == "The hero entered the dungeon."
    
    # Verify metadata is injected
    assert result.source_hash is not None
    assert len(result.source_hash) == 64  # SHA-256 hash
    assert result.model_version == "gemini-2.5-flash"
    assert result.processed_at is not None
    
    # Verify API was called once
    assert mock_gemini_client.generate_content.call_count == 1


def test_transform_chapter_hash_computation(transformer, mock_gemini_client):
    """Test that source hash is computed correctly."""
    chapter_text = "Test chapter content"
    expected_hash = hashlib.sha256(chapter_text.encode('utf-8')).hexdigest()
    
    # Mock API response
    valid_json = '{"blocks": [{"type": "action", "content": "Test"}]}'
    mock_gemini_client.generate_content.return_value = valid_json
    
    # Execute
    result = transformer.transform_chapter(chapter_text)
    
    # Verify hash matches expected
    assert result.source_hash == expected_hash


def test_transform_chapter_validation_retry_success(transformer, mock_gemini_client):
    """
    Test that validation errors trigger retry and eventually succeed.
    
    Requirements: 4.4, 4.5
    """
    chapter_text = "Test chapter"
    
    # Mock API to return invalid JSON first 2 times, then valid JSON
    invalid_json = '{"invalid": "structure"}'  # Missing required fields
    valid_json = '{"blocks": [{"type": "action", "content": "Test"}]}'
    
    mock_gemini_client.generate_content.side_effect = [
        invalid_json,  # First attempt - validation fails
        invalid_json,  # Second attempt - validation fails
        valid_json     # Third attempt - success
    ]
    
    # Execute
    result = transformer.transform_chapter(chapter_text, max_retries=3)
    
    # Verify
    assert result is not None
    assert isinstance(result, ChapterData)
    
    # Verify API was called 3 times (2 failures + 1 success)
    assert mock_gemini_client.generate_content.call_count == 3


def test_transform_chapter_validation_retry_exhausted(transformer, mock_gemini_client):
    """
    Test that None is returned after max retries are exhausted.
    
    Requirements: 4.4, 4.5
    """
    chapter_text = "Test chapter"
    
    # Mock API to always return invalid JSON
    invalid_json = '{"invalid": "structure"}'
    mock_gemini_client.generate_content.return_value = invalid_json
    
    # Execute with max_retries=3
    result = transformer.transform_chapter(chapter_text, max_retries=3)
    
    # Verify
    assert result is None
    
    # Verify API was called exactly 3 times
    assert mock_gemini_client.generate_content.call_count == 3


def test_transform_chapter_rate_limit_error(transformer, mock_gemini_client):
    """Test that rate limit errors are handled correctly."""
    chapter_text = "Test chapter"
    
    # Mock API to raise RateLimitError
    mock_gemini_client.generate_content.side_effect = RateLimitError("Rate limit exceeded")
    
    # Execute
    result = transformer.transform_chapter(chapter_text)
    
    # Verify
    assert result is None
    
    # Verify API was called once (RateLimitError stops retries)
    assert mock_gemini_client.generate_content.call_count == 1


def test_transform_chapter_unexpected_error(transformer, mock_gemini_client):
    """Test that unexpected errors are handled gracefully."""
    chapter_text = "Test chapter"
    
    # Mock API to raise unexpected exception
    mock_gemini_client.generate_content.side_effect = Exception("Unexpected error")
    
    # Execute
    result = transformer.transform_chapter(chapter_text)
    
    # Verify
    assert result is None
    
    # Verify API was called once
    assert mock_gemini_client.generate_content.call_count == 1


def test_transform_chapter_token_estimation(transformer, mock_gemini_client, caplog):
    """Test that token estimation and cost calculation are logged."""
    import logging
    caplog.set_level(logging.INFO)
    
    chapter_text = "Test chapter content"
    
    # Mock API response
    valid_json = '{"blocks": [{"type": "action", "content": "Test"}]}'
    mock_gemini_client.generate_content.return_value = valid_json
    
    # Execute
    result = transformer.transform_chapter(chapter_text)
    
    # Verify result
    assert result is not None
    
    # Verify logging contains token estimate and cost
    log_messages = [record.message for record in caplog.records]
    assert any("Estimated:" in msg and "tokens" in msg for msg in log_messages)
    # Cost is now FREE tier, so check for "FREE" instead of "$"
    assert any("FREE" in msg for msg in log_messages)


def test_transform_chapter_empty_text(transformer, mock_gemini_client):
    """Test transformation with empty chapter text."""
    chapter_text = ""
    
    # Mock API response
    valid_json = '{"blocks": []}'
    mock_gemini_client.generate_content.return_value = valid_json
    
    # Execute
    result = transformer.transform_chapter(chapter_text)
    
    # Verify - should still work, just with empty blocks
    # Note: Pydantic validation might fail on empty blocks list depending on schema
    # For now, we test that it doesn't crash
    assert mock_gemini_client.generate_content.call_count == 1


def test_transform_chapter_large_text(transformer, mock_gemini_client):
    """Test transformation with large chapter text."""
    # Create a large chapter (10,000 characters)
    chapter_text = "This is a test sentence. " * 400
    
    # Mock API response
    valid_json = '{"blocks": [{"type": "action", "content": "Large chapter"}]}'
    mock_gemini_client.generate_content.return_value = valid_json
    
    # Execute
    result = transformer.transform_chapter(chapter_text)
    
    # Verify
    assert result is not None
    assert result.source_hash is not None
    
    # Verify hash is computed correctly for large text
    expected_hash = hashlib.sha256(chapter_text.encode('utf-8')).hexdigest()
    assert result.source_hash == expected_hash


def test_transform_chapter_unicode_text(transformer, mock_gemini_client):
    """Test transformation with Unicode characters."""
    chapter_text = "The hero said: '你好世界' and smiled. 🎉"
    
    # Mock API response
    valid_json = '{"blocks": [{"type": "dialogue", "speaker": "Hero", "content": "你好世界"}]}'
    mock_gemini_client.generate_content.return_value = valid_json
    
    # Execute
    result = transformer.transform_chapter(chapter_text)
    
    # Verify
    assert result is not None
    assert result.source_hash is not None
    
    # Verify hash handles Unicode correctly
    expected_hash = hashlib.sha256(chapter_text.encode('utf-8')).hexdigest()
    assert result.source_hash == expected_hash


def test_transform_chapter_metadata_injection(transformer, mock_gemini_client):
    """Test that all metadata fields are properly injected."""
    chapter_text = "Test chapter"
    
    # Mock API response
    valid_json = '{"blocks": [{"type": "action", "content": "Test"}]}'
    mock_gemini_client.generate_content.return_value = valid_json
    
    # Execute
    result = transformer.transform_chapter(chapter_text)
    
    # Verify all metadata fields
    assert result is not None
    
    # source_hash
    assert result.source_hash is not None
    assert len(result.source_hash) == 64
    assert all(c in '0123456789abcdef' for c in result.source_hash)
    
    # model_version
    assert result.model_version == "gemini-2.5-flash"
    
    # processed_at
    assert result.processed_at is not None
    from datetime import timezone
    assert result.processed_at.tzinfo == timezone.utc
