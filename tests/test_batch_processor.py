"""
Unit tests for batch processor with hash-based idempotency.
"""

import json
import hashlib
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
from babel.transform.batch_processor import BatchProcessor
from babel.transform.models import ChapterData, ScriptBlock, ScriptBlockType


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    clean_dir = Path(tempfile.mkdtemp())
    json_dir = Path(tempfile.mkdtemp())
    
    yield clean_dir, json_dir
    
    # Cleanup
    shutil.rmtree(clean_dir, ignore_errors=True)
    shutil.rmtree(json_dir, ignore_errors=True)


@pytest.fixture
def sample_chapter_map():
    """Create a sample chapter map."""
    return {
        "chapters": [
            {"index": 0, "filename": "ch_001.txt", "title": "Chapter 1"},
            {"index": 1, "filename": "ch_002.txt", "title": "Chapter 2"},
            {"index": 2, "filename": "ch_003.txt", "title": "Chapter 3"}
        ]
    }


@pytest.fixture
def sample_chapter_data():
    """Create sample chapter data."""
    return ChapterData(
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


def test_batch_processor_initialization(temp_dirs):
    """Test that BatchProcessor initializes correctly."""
    clean_dir, json_dir = temp_dirs
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        
        assert processor.clean_dir == clean_dir
        assert processor.json_dir == json_dir
        assert json_dir.exists(), "Output directory should be created"


def test_load_chapter_map_success(temp_dirs, sample_chapter_map):
    """Test loading chapter map successfully."""
    clean_dir, json_dir = temp_dirs
    
    # Write chapter map
    manifest_path = clean_dir / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(sample_chapter_map, f)
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        chapter_map = processor.load_chapter_map()
        
        assert chapter_map == sample_chapter_map
        assert len(chapter_map['chapters']) == 3


def test_load_chapter_map_missing_file(temp_dirs):
    """Test that missing chapter map raises FileNotFoundError."""
    clean_dir, json_dir = temp_dirs
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        
        with pytest.raises(FileNotFoundError) as exc_info:
            processor.load_chapter_map()
        
        assert "Chapter manifest not found" in str(exc_info.value)
        assert "Run Phase 0" in str(exc_info.value)


def test_hash_match_skips_processing(temp_dirs, sample_chapter_map, sample_chapter_data):
    """Test that matching hashes skip processing."""
    clean_dir, json_dir = temp_dirs
    
    # Setup chapter map
    manifest_path = clean_dir / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(sample_chapter_map, f)
    
    # Create source file
    source_text = "Test chapter content"
    source_hash = hashlib.sha256(source_text.encode('utf-8')).hexdigest()
    source_path = clean_dir / "ch_001.txt"
    with open(source_path, 'w', encoding='utf-8') as f:
        f.write(source_text)
    
    # Create existing output with matching hash
    existing_data = sample_chapter_data.model_copy(update={"source_hash": source_hash})
    output_path = json_dir / "ch_001.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(existing_data.model_dump_json(indent=2))
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        
        # Mock transformer to track if it was called
        processor.transformer = Mock()
        processor.transformer.transform_chapter = Mock(return_value=sample_chapter_data)
        
        processed, skipped, failed = processor.process_all_chapters()
        
        # Should skip the first chapter (hash match)
        assert skipped == 1
        assert processed == 0  # Other chapters don't have source files
        assert failed == 2  # Other chapters missing source files
        
        # Transformer should not be called for the skipped chapter
        processor.transformer.transform_chapter.assert_not_called()


def test_hash_mismatch_triggers_reprocessing(temp_dirs, sample_chapter_map, sample_chapter_data):
    """Test that different hashes trigger reprocessing."""
    clean_dir, json_dir = temp_dirs
    
    # Setup chapter map
    manifest_path = clean_dir / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(sample_chapter_map, f)
    
    # Create source file
    source_text = "Test chapter content"
    source_hash = hashlib.sha256(source_text.encode('utf-8')).hexdigest()
    source_path = clean_dir / "ch_001.txt"
    with open(source_path, 'w', encoding='utf-8') as f:
        f.write(source_text)
    
    # Create existing output with DIFFERENT hash
    different_hash = "b" * 64
    existing_data = sample_chapter_data.model_copy(update={"source_hash": different_hash})
    output_path = json_dir / "ch_001.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(existing_data.model_dump_json(indent=2))
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        
        # Mock transformer to return new data
        new_data = sample_chapter_data.model_copy(update={"source_hash": source_hash})
        processor.transformer = Mock()
        processor.transformer.transform_chapter = Mock(return_value=new_data)
        
        processed, skipped, failed = processor.process_all_chapters()
        
        # Should reprocess the first chapter (hash mismatch)
        assert processed == 1
        assert skipped == 0
        assert failed == 2  # Other chapters missing source files
        
        # Transformer should be called for the reprocessed chapter
        processor.transformer.transform_chapter.assert_called_once()


def test_missing_output_triggers_processing(temp_dirs, sample_chapter_map, sample_chapter_data):
    """Test that missing output files trigger processing."""
    clean_dir, json_dir = temp_dirs
    
    # Setup chapter map
    manifest_path = clean_dir / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(sample_chapter_map, f)
    
    # Create source file
    source_text = "Test chapter content"
    source_path = clean_dir / "ch_001.txt"
    with open(source_path, 'w', encoding='utf-8') as f:
        f.write(source_text)
    
    # No existing output file
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        
        # Mock transformer
        processor.transformer = Mock()
        processor.transformer.transform_chapter = Mock(return_value=sample_chapter_data)
        
        processed, skipped, failed = processor.process_all_chapters()
        
        # Should process the first chapter (no existing output)
        assert processed == 1
        assert skipped == 0
        assert failed == 2  # Other chapters missing source files
        
        # Transformer should be called
        processor.transformer.transform_chapter.assert_called_once()


def test_invalid_existing_json_triggers_reprocessing(temp_dirs, sample_chapter_map, sample_chapter_data):
    """Test that invalid existing JSON triggers reprocessing."""
    clean_dir, json_dir = temp_dirs
    
    # Setup chapter map
    manifest_path = clean_dir / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(sample_chapter_map, f)
    
    # Create source file
    source_text = "Test chapter content"
    source_path = clean_dir / "ch_001.txt"
    with open(source_path, 'w', encoding='utf-8') as f:
        f.write(source_text)
    
    # Create invalid JSON output
    output_path = json_dir / "ch_001.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("{ invalid json }")
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        
        # Mock transformer
        processor.transformer = Mock()
        processor.transformer.transform_chapter = Mock(return_value=sample_chapter_data)
        
        processed, skipped, failed = processor.process_all_chapters()
        
        # Should reprocess the first chapter (invalid JSON)
        assert processed == 1
        assert skipped == 0
        assert failed == 2  # Other chapters missing source files
        
        # Transformer should be called
        processor.transformer.transform_chapter.assert_called_once()


def test_missing_source_file_logs_error(temp_dirs, sample_chapter_map):
    """Test that missing source files are logged as errors."""
    clean_dir, json_dir = temp_dirs
    
    # Setup chapter map
    manifest_path = clean_dir / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(sample_chapter_map, f)
    
    # Don't create any source files
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        
        processed, skipped, failed = processor.process_all_chapters()
        
        # All chapters should fail (missing source files)
        assert processed == 0
        assert skipped == 0
        assert failed == 3


def test_empty_chapter_map(temp_dirs):
    """Test handling of empty chapter map."""
    clean_dir, json_dir = temp_dirs
    
    # Setup empty chapter map
    manifest_path = clean_dir / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump({"chapters": []}, f)
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        
        processed, skipped, failed = processor.process_all_chapters()
        
        assert processed == 0
        assert skipped == 0
        assert failed == 0


def test_high_failure_rate_logs_critical(temp_dirs, sample_chapter_map, caplog):
    """Test that >50% failure rate logs CRITICAL warning."""
    clean_dir, json_dir = temp_dirs
    
    # Setup chapter map
    manifest_path = clean_dir / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(sample_chapter_map, f)
    
    # Don't create any source files (all will fail)
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        
        import logging
        with caplog.at_level(logging.CRITICAL):
            processed, skipped, failed = processor.process_all_chapters()
        
        # All chapters should fail
        assert failed == 3
        
        # Should log CRITICAL warning
        assert any("CRITICAL" in record.levelname and "High failure rate" in record.message 
                   for record in caplog.records)



def test_transformation_failure_creates_placeholder(temp_dirs, sample_chapter_map):
    """Test that transformation failure creates placeholder JSON."""
    clean_dir, json_dir = temp_dirs
    
    # Setup chapter map
    manifest_path = clean_dir / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(sample_chapter_map, f)
    
    # Create source file
    source_text = "Test chapter content"
    source_hash = hashlib.sha256(source_text.encode('utf-8')).hexdigest()
    source_path = clean_dir / "ch_001.txt"
    with open(source_path, 'w', encoding='utf-8') as f:
        f.write(source_text)
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        
        # Mock transformer to return None (failure)
        processor.transformer = Mock()
        processor.transformer.transform_chapter = Mock(return_value=None)
        
        processed, skipped, failed = processor.process_all_chapters()
        
        # Should fail the first chapter
        assert processed == 0
        assert skipped == 0
        assert failed == 3  # All chapters fail (1 transformation, 2 missing source)
        
        # Check that placeholder JSON was written
        output_path = json_dir / "ch_001.json"
        assert output_path.exists(), "Placeholder JSON should be written"
        
        # Load and verify placeholder content
        with open(output_path, 'r', encoding='utf-8') as f:
            placeholder_data = json.load(f)
        
        # Verify placeholder structure
        assert "blocks" in placeholder_data
        assert len(placeholder_data["blocks"]) == 2
        
        # First block should be system notification
        assert placeholder_data["blocks"][0]["type"] == "system_notification"
        assert "Transformation Failed" in placeholder_data["blocks"][0]["content"]
        assert "Chapter 1" in placeholder_data["blocks"][0]["content"]
        
        # Second block should contain raw text
        assert placeholder_data["blocks"][1]["type"] == "action"
        assert placeholder_data["blocks"][1]["content"] == source_text
        
        # Verify metadata
        assert placeholder_data["source_hash"] == source_hash
        assert placeholder_data["model_version"] == "gemini-1.5-flash-failed"
        assert "processed_at" in placeholder_data


def test_placeholder_has_correct_model_version(temp_dirs, sample_chapter_map):
    """Test that placeholder has model_version set to 'gemini-1.5-flash-failed'."""
    clean_dir, json_dir = temp_dirs
    
    # Setup chapter map
    manifest_path = clean_dir / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(sample_chapter_map, f)
    
    # Create source file
    source_text = "Test chapter content"
    source_path = clean_dir / "ch_001.txt"
    with open(source_path, 'w', encoding='utf-8') as f:
        f.write(source_text)
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        
        # Mock transformer to return None (failure)
        processor.transformer = Mock()
        processor.transformer.transform_chapter = Mock(return_value=None)
        
        processor.process_all_chapters()
        
        # Load placeholder
        output_path = json_dir / "ch_001.json"
        with open(output_path, 'r', encoding='utf-8') as f:
            placeholder_data = json.load(f)
        
        # Verify model version
        assert placeholder_data["model_version"] == "gemini-1.5-flash-failed"


def test_placeholder_preserves_source_hash(temp_dirs, sample_chapter_map):
    """Test that placeholder preserves the source hash."""
    clean_dir, json_dir = temp_dirs
    
    # Setup chapter map
    manifest_path = clean_dir / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(sample_chapter_map, f)
    
    # Create source file
    source_text = "Test chapter content"
    expected_hash = hashlib.sha256(source_text.encode('utf-8')).hexdigest()
    source_path = clean_dir / "ch_001.txt"
    with open(source_path, 'w', encoding='utf-8') as f:
        f.write(source_text)
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        
        # Mock transformer to return None (failure)
        processor.transformer = Mock()
        processor.transformer.transform_chapter = Mock(return_value=None)
        
        processor.process_all_chapters()
        
        # Load placeholder
        output_path = json_dir / "ch_001.json"
        with open(output_path, 'r', encoding='utf-8') as f:
            placeholder_data = json.load(f)
        
        # Verify source hash matches
        assert placeholder_data["source_hash"] == expected_hash


def test_placeholder_contains_raw_text(temp_dirs, sample_chapter_map):
    """Test that placeholder contains the raw chapter text."""
    clean_dir, json_dir = temp_dirs
    
    # Setup chapter map
    manifest_path = clean_dir / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(sample_chapter_map, f)
    
    # Create source file with specific content
    source_text = "This is the raw chapter text that should be preserved."
    source_path = clean_dir / "ch_001.txt"
    with open(source_path, 'w', encoding='utf-8') as f:
        f.write(source_text)
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        
        # Mock transformer to return None (failure)
        processor.transformer = Mock()
        processor.transformer.transform_chapter = Mock(return_value=None)
        
        processor.process_all_chapters()
        
        # Load placeholder
        output_path = json_dir / "ch_001.json"
        with open(output_path, 'r', encoding='utf-8') as f:
            placeholder_data = json.load(f)
        
        # Verify raw text is in action block
        action_block = placeholder_data["blocks"][1]
        assert action_block["type"] == "action"
        assert action_block["content"] == source_text
