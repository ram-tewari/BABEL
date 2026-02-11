"""Unit tests for JSON validator."""

import json
import logging
import pytest
from pydantic import ValidationError
from babel.transform.validator import JSONValidator
from babel.transform.models import ChapterData, ScriptBlock, ScriptBlockType


class TestJSONValidatorCleaning:
    """Tests for clean_response method."""
    
    def test_clean_response_removes_json_fence(self):
        """Test that ```json fences are removed."""
        raw = '```json\n{"blocks": [], "source_hash": "abc", "model_version": "test"}\n```'
        cleaned = JSONValidator.clean_response(raw)
        assert not cleaned.startswith('```')
        assert not cleaned.endswith('```')
        assert 'json' not in cleaned or '"' in cleaned  # Either no 'json' or it's in the JSON
    
    def test_clean_response_removes_plain_fence(self):
        """Test that ``` fences without language are removed."""
        raw = '```\n{"blocks": [], "source_hash": "abc", "model_version": "test"}\n```'
        cleaned = JSONValidator.clean_response(raw)
        assert not cleaned.startswith('```')
        assert not cleaned.endswith('```')
    
    def test_clean_response_strips_whitespace(self):
        """Test that leading/trailing whitespace is removed."""
        raw = '  \n  {"blocks": [], "source_hash": "abc", "model_version": "test"}  \n  '
        cleaned = JSONValidator.clean_response(raw)
        assert cleaned.startswith('{')
        assert cleaned.endswith('}')
    
    def test_clean_response_handles_no_fence(self):
        """Test that valid JSON without fences is unchanged."""
        raw = '{"blocks": [], "source_hash": "abc", "model_version": "test"}'
        cleaned = JSONValidator.clean_response(raw)
        assert cleaned == raw
    
    def test_clean_response_handles_fence_without_trailing_newline(self):
        """Test fence removal when there's no trailing newline."""
        raw = '```json\n{"blocks": [], "source_hash": "abc", "model_version": "test"}```'
        cleaned = JSONValidator.clean_response(raw)
        assert not cleaned.startswith('```')
        assert not cleaned.endswith('```')


class TestJSONValidatorValidation:
    """Tests for validate method."""
    
    def test_validate_with_valid_json(self):
        """Test that valid JSON is successfully validated."""
        valid_json = json.dumps({
            "blocks": [
                {"type": "dialogue", "speaker": "Alice", "content": "Hello", "tone": "friendly"}
            ],
            "source_hash": "a" * 64,
            "model_version": "gemini-1.5-flash",
            "processed_at": "2024-02-03T10:30:00Z"
        })
        
        result = JSONValidator.validate(valid_json)
        
        assert isinstance(result, ChapterData)
        assert len(result.blocks) == 1
        assert result.blocks[0].type == ScriptBlockType.DIALOGUE
        assert result.blocks[0].speaker == "Alice"
        assert result.blocks[0].content == "Hello"
        assert result.source_hash == "a" * 64
        assert result.model_version == "gemini-1.5-flash"
    
    def test_validate_with_markdown_fences(self):
        """Test that JSON with markdown fences is successfully validated."""
        valid_json = json.dumps({
            "blocks": [
                {"type": "action", "content": "The door opened."}
            ],
            "source_hash": "b" * 64,
            "model_version": "gemini-1.5-flash"
        })
        
        wrapped = f"```json\n{valid_json}\n```"
        
        result = JSONValidator.validate(wrapped)
        
        assert isinstance(result, ChapterData)
        assert len(result.blocks) == 1
        assert result.blocks[0].type == ScriptBlockType.ACTION
    
    def test_validate_raises_value_error_on_malformed_json(self):
        """Test that invalid JSON raises ValueError."""
        invalid_json = '{"blocks": [invalid json here'
        
        with pytest.raises(ValueError) as exc_info:
            JSONValidator.validate(invalid_json)
        
        assert "Invalid JSON" in str(exc_info.value)
    
    def test_validate_raises_validation_error_on_schema_mismatch(self):
        """Test that schema mismatch raises ValidationError."""
        # Missing required field 'blocks'
        invalid_schema = json.dumps({
            "source_hash": "c" * 64,
            "model_version": "gemini-1.5-flash"
        })
        
        with pytest.raises(ValidationError):
            JSONValidator.validate(invalid_schema)
    
    def test_validate_raises_validation_error_on_invalid_block_type(self):
        """Test that invalid block type raises ValidationError."""
        invalid_type = json.dumps({
            "blocks": [
                {"type": "invalid_type", "content": "Test"}
            ],
            "source_hash": "d" * 64,
            "model_version": "gemini-1.5-flash"
        })
        
        with pytest.raises(ValidationError):
            JSONValidator.validate(invalid_type)
    
    def test_validate_raises_validation_error_on_missing_content(self):
        """Test that missing required content field raises ValidationError."""
        missing_content = json.dumps({
            "blocks": [
                {"type": "dialogue", "speaker": "Alice"}  # Missing 'content'
            ],
            "source_hash": "e" * 64,
            "model_version": "gemini-1.5-flash"
        })
        
        with pytest.raises(ValidationError):
            JSONValidator.validate(missing_content)
    
    def test_validate_logs_validation_errors(self, caplog):
        """Test that validation errors are logged."""
        invalid_json = '{"blocks": [invalid'
        
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError):
                JSONValidator.validate(invalid_json)
        
        # Check that error was logged
        assert any("JSON parsing failed" in record.message for record in caplog.records)
    
    def test_validate_logs_pydantic_errors(self, caplog):
        """Test that Pydantic validation errors are logged."""
        invalid_schema = json.dumps({
            "source_hash": "f" * 64,
            "model_version": "gemini-1.5-flash"
            # Missing 'blocks'
        })
        
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValidationError):
                JSONValidator.validate(invalid_schema)
        
        # Check that Pydantic error was logged
        assert any("Pydantic validation failed" in record.message for record in caplog.records)
    
    def test_validate_with_minimal_valid_json(self):
        """Test validation with minimal required fields."""
        minimal_json = json.dumps({
            "blocks": [],
            "source_hash": "g" * 64,
            "model_version": "test"
        })
        
        result = JSONValidator.validate(minimal_json)
        
        assert isinstance(result, ChapterData)
        assert len(result.blocks) == 0
        assert result.source_hash == "g" * 64
        assert result.model_version == "test"
        assert result.processed_at is not None  # Auto-populated
    
    def test_validate_with_all_block_types(self):
        """Test validation with all supported block types."""
        all_types_json = json.dumps({
            "blocks": [
                {"type": "dialogue", "speaker": "Alice", "content": "Hello"},
                {"type": "action", "content": "Door opens"},
                {"type": "monologue", "speaker": "Bob", "content": "Thinking..."},
                {"type": "sfx", "content": "BOOM"},
                {"type": "system_notification", "content": "Quest complete"}
            ],
            "source_hash": "h" * 64,
            "model_version": "gemini-1.5-flash"
        })
        
        result = JSONValidator.validate(all_types_json)
        
        assert isinstance(result, ChapterData)
        assert len(result.blocks) == 5
        assert result.blocks[0].type == ScriptBlockType.DIALOGUE
        assert result.blocks[1].type == ScriptBlockType.ACTION
        assert result.blocks[2].type == ScriptBlockType.MONOLOGUE
        assert result.blocks[3].type == ScriptBlockType.SFX
        assert result.blocks[4].type == ScriptBlockType.SYSTEM_NOTIFICATION
