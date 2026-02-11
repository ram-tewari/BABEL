"""
Unit tests for the corrections API endpoint.

Tests the update_block function to ensure it correctly handles:
- Content changes
- Type changes
- Speaker changes
- Combined changes
- Field preservation
"""

import json
import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, AsyncMock
from babel.api.corrections import update_block
from babel.api.models import BlockCorrection
from babel.data.db import DatabaseManager


@pytest.fixture
def mock_db():
    """Mock database manager."""
    db = Mock(spec=DatabaseManager)
    db.log_correction.return_value = 123  # Mock correction ID
    return db


@pytest.fixture
def sample_chapter_data():
    """Sample chapter JSON data."""
    return {
        "title": "Chapter 1",
        "blocks": [
            {
                "type": "dialogue",
                "speaker": "Alice",
                "content": "Hello, world!",
                "tone": "cheerful"
            },
            {
                "type": "narrator",
                "speaker": None,
                "content": "She smiled warmly.",
                "tone": None
            },
            {
                "type": "thought",
                "speaker": "Bob",
                "content": "What a strange day.",
                "tone": "confused"
            }
        ]
    }


class TestUpdateBlockContentOnly:
    """Test updating only the content field."""
    
    @pytest.mark.asyncio
    async def test_content_change_preserves_other_fields(self, mock_db, sample_chapter_data):
        """Changing content should preserve type, speaker, and tone."""
        correction = BlockCorrection(
            type="DIALOGUE",  # Same as original
            speaker="Alice",  # Same as original
            text="Hello, universe!",  # Changed
            correction_reason="Testing content change"
        )
        
        with patch('babel.api.corrections.Path') as mock_path:
            # Mock file reading
            mock_file = mock_open(read_data=json.dumps(sample_chapter_data))
            with patch('builtins.open', mock_file):
                # Mock file existence check
                mock_path.return_value.exists.return_value = True
                
                # Call the function
                result = await update_block("Ch_001", 0, correction, mock_db)
        
        # Verify the updated block
        updated = result.updated_block
        assert updated["content"] == "Hello, universe!"
        assert updated["type"] == "dialogue"
        assert updated["speaker"] == "Alice"
        assert updated["tone"] == "cheerful"  # Should be preserved
        assert updated["corrected"] is True
        assert updated["correction_id"] == 123


class TestUpdateBlockTypeOnly:
    """Test updating only the type field."""
    
    @pytest.mark.asyncio
    async def test_type_change_preserves_content_and_speaker(self, mock_db, sample_chapter_data):
        """Changing type should preserve content and speaker."""
        correction = BlockCorrection(
            type="THOUGHT",  # Changed from DIALOGUE
            speaker="Alice",  # Same as original
            text="Hello, world!",  # Same as original
            correction_reason="Misclassified as dialogue"
        )
        
        with patch('babel.api.corrections.Path') as mock_path:
            mock_file = mock_open(read_data=json.dumps(sample_chapter_data))
            with patch('builtins.open', mock_file):
                mock_path.return_value.exists.return_value = True
                result = await update_block("Ch_001", 0, correction, mock_db)
        
        updated = result.updated_block
        assert updated["type"] == "thought"  # Changed
        assert updated["content"] == "Hello, world!"  # Preserved
        assert updated["speaker"] == "Alice"  # Preserved
        assert updated["tone"] == "cheerful"  # Preserved from original
    
    @pytest.mark.asyncio
    async def test_type_change_to_narrator_removes_speaker(self, mock_db, sample_chapter_data):
        """Changing to NARRATION should handle speaker correctly."""
        correction = BlockCorrection(
            type="NARRATION",  # Changed from DIALOGUE
            speaker=None,  # Narrator has no speaker
            text="Hello, world!",
            correction_reason="Should be narration"
        )
        
        with patch('babel.api.corrections.Path') as mock_path:
            mock_file = mock_open(read_data=json.dumps(sample_chapter_data))
            with patch('builtins.open', mock_file):
                mock_path.return_value.exists.return_value = True
                result = await update_block("Ch_001", 0, correction, mock_db)
        
        updated = result.updated_block
        assert updated["type"] == "narration"
        assert updated["content"] == "Hello, world!"
        assert "speaker" not in updated  # Should not have speaker field


class TestUpdateBlockSpeakerOnly:
    """Test updating only the speaker field."""
    
    @pytest.mark.asyncio
    async def test_speaker_change_preserves_content_and_type(self, mock_db, sample_chapter_data):
        """Changing speaker should preserve content and type."""
        correction = BlockCorrection(
            type="DIALOGUE",  # Same as original
            speaker="Bob",  # Changed from Alice
            text="Hello, world!",  # Same as original
            correction_reason="Wrong speaker"
        )
        
        with patch('babel.api.corrections.Path') as mock_path:
            mock_file = mock_open(read_data=json.dumps(sample_chapter_data))
            with patch('builtins.open', mock_file):
                mock_path.return_value.exists.return_value = True
                result = await update_block("Ch_001", 0, correction, mock_db)
        
        updated = result.updated_block
        assert updated["speaker"] == "Bob"  # Changed
        assert updated["content"] == "Hello, world!"  # Preserved
        assert updated["type"] == "dialogue"  # Preserved
        assert updated["tone"] == "cheerful"  # Preserved


class TestUpdateBlockMultipleFields:
    """Test updating multiple fields simultaneously."""
    
    @pytest.mark.asyncio
    async def test_change_type_and_speaker(self, mock_db, sample_chapter_data):
        """Changing both type and speaker should work."""
        correction = BlockCorrection(
            type="THOUGHT",  # Changed
            speaker="Bob",  # Changed
            text="Hello, world!",  # Same
            correction_reason="Wrong type and speaker"
        )
        
        with patch('babel.api.corrections.Path') as mock_path:
            mock_file = mock_open(read_data=json.dumps(sample_chapter_data))
            with patch('builtins.open', mock_file):
                mock_path.return_value.exists.return_value = True
                result = await update_block("Ch_001", 0, correction, mock_db)
        
        updated = result.updated_block
        assert updated["type"] == "thought"
        assert updated["speaker"] == "Bob"
        assert updated["content"] == "Hello, world!"
        assert updated["tone"] == "cheerful"  # Still preserved
    
    @pytest.mark.asyncio
    async def test_change_all_fields(self, mock_db, sample_chapter_data):
        """Changing type, speaker, and content should all work."""
        correction = BlockCorrection(
            type="THOUGHT",
            speaker="Charlie",
            text="Goodbye, world!",
            correction_reason="Complete rewrite"
        )
        
        with patch('babel.api.corrections.Path') as mock_path:
            mock_file = mock_open(read_data=json.dumps(sample_chapter_data))
            with patch('builtins.open', mock_file):
                mock_path.return_value.exists.return_value = True
                result = await update_block("Ch_001", 0, correction, mock_db)
        
        updated = result.updated_block
        assert updated["type"] == "thought"
        assert updated["speaker"] == "Charlie"
        assert updated["content"] == "Goodbye, world!"
        assert updated["tone"] == "cheerful"  # Original tone preserved


class TestFieldPreservation:
    """Test that original fields are preserved correctly."""
    
    @pytest.mark.asyncio
    async def test_preserves_tone_field(self, mock_db, sample_chapter_data):
        """Tone field should be preserved from original block."""
        correction = BlockCorrection(
            type="DIALOGUE",
            speaker="Alice",
            text="New text",
            correction_reason=None
        )
        
        with patch('babel.api.corrections.Path') as mock_path:
            mock_file = mock_open(read_data=json.dumps(sample_chapter_data))
            with patch('builtins.open', mock_file):
                mock_path.return_value.exists.return_value = True
                result = await update_block("Ch_001", 0, correction, mock_db)
        
        assert result.updated_block["tone"] == "cheerful"
    
    @pytest.mark.asyncio
    async def test_preserves_metadata_if_present(self, mock_db, sample_chapter_data):
        """Custom metadata fields should be preserved."""
        # Add metadata to original block
        sample_chapter_data["blocks"][0]["metadata"] = {"custom": "value"}
        
        correction = BlockCorrection(
            type="DIALOGUE",
            speaker="Alice",
            text="New text",
            correction_reason=None
        )
        
        with patch('babel.api.corrections.Path') as mock_path:
            mock_file = mock_open(read_data=json.dumps(sample_chapter_data))
            with patch('builtins.open', mock_file):
                mock_path.return_value.exists.return_value = True
                result = await update_block("Ch_001", 0, correction, mock_db)
        
        assert result.updated_block["metadata"] == {"custom": "value"}
    
    @pytest.mark.asyncio
    async def test_preserves_emotion_if_present(self, mock_db, sample_chapter_data):
        """Emotion field should be preserved if it exists."""
        sample_chapter_data["blocks"][0]["emotion"] = "happy"
        
        correction = BlockCorrection(
            type="DIALOGUE",
            speaker="Alice",
            text="New text",
            correction_reason=None
        )
        
        with patch('babel.api.corrections.Path') as mock_path:
            mock_file = mock_open(read_data=json.dumps(sample_chapter_data))
            with patch('builtins.open', mock_file):
                mock_path.return_value.exists.return_value = True
                result = await update_block("Ch_001", 0, correction, mock_db)
        
        assert result.updated_block["emotion"] == "happy"


class TestDatabaseLogging:
    """Test that corrections are logged to database correctly."""
    
    @pytest.mark.asyncio
    async def test_logs_content_change(self, mock_db, sample_chapter_data):
        """Content changes should be logged with correct original values."""
        correction = BlockCorrection(
            type="DIALOGUE",
            speaker="Alice",
            text="New content",
            correction_reason="Testing"
        )
        
        with patch('babel.api.corrections.Path') as mock_path:
            mock_file = mock_open(read_data=json.dumps(sample_chapter_data))
            with patch('builtins.open', mock_file):
                mock_path.return_value.exists.return_value = True
                await update_block("Ch_001", 0, correction, mock_db)
        
        # Verify database was called with correct original values
        mock_db.log_correction.assert_called_once()
        call_args = mock_db.log_correction.call_args[1]
        
        assert call_args["chapter_id"] == "Ch_001"
        assert call_args["block_index"] == 0
        assert call_args["original_type"] == "dialogue"
        assert call_args["original_speaker"] == "Alice"
        assert call_args["original_text"] == "Hello, world!"  # Original content
        assert call_args["corrected_type"] == "DIALOGUE"
        assert call_args["corrected_speaker"] == "Alice"
        assert call_args["corrected_text"] == "New content"
    
    @pytest.mark.asyncio
    async def test_logs_type_change(self, mock_db, sample_chapter_data):
        """Type changes should be logged correctly."""
        correction = BlockCorrection(
            type="THOUGHT",
            speaker="Alice",
            text="Hello, world!",
            correction_reason="Wrong type"
        )
        
        with patch('babel.api.corrections.Path') as mock_path:
            mock_file = mock_open(read_data=json.dumps(sample_chapter_data))
            with patch('builtins.open', mock_file):
                mock_path.return_value.exists.return_value = True
                await update_block("Ch_001", 0, correction, mock_db)
        
        call_args = mock_db.log_correction.call_args[1]
        assert call_args["original_type"] == "dialogue"
        assert call_args["corrected_type"] == "THOUGHT"


class TestErrorCases:
    """Test error handling."""
    
    @pytest.mark.asyncio
    async def test_invalid_block_index(self, mock_db, sample_chapter_data):
        """Should raise HTTPException for out-of-range index."""
        from fastapi import HTTPException
        
        correction = BlockCorrection(
            type="DIALOGUE",
            speaker="Alice",
            text="Test",
            correction_reason=None
        )
        
        with patch('babel.api.corrections.Path') as mock_path:
            mock_file = mock_open(read_data=json.dumps(sample_chapter_data))
            with patch('builtins.open', mock_file):
                mock_path.return_value.exists.return_value = True
                
                with pytest.raises(HTTPException) as exc_info:
                    await update_block("Ch_001", 999, correction, mock_db)
                
                assert exc_info.value.status_code == 400
                assert "out of range" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_chapter_not_found(self, mock_db):
        """Should raise HTTPException for missing chapter."""
        from fastapi import HTTPException
        
        correction = BlockCorrection(
            type="DIALOGUE",
            speaker="Alice",
            text="Test",
            correction_reason=None
        )
        
        with patch('babel.api.corrections.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            
            with pytest.raises(HTTPException) as exc_info:
                await update_block("Ch_999", 0, correction, mock_db)
            
            assert exc_info.value.status_code == 404
            assert "not found" in str(exc_info.value.detail)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

