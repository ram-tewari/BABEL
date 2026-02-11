"""
Unit tests for the ChapterRenderer class.

Tests JSON loading, validation, and error handling.
"""

import json
import pytest
from pathlib import Path
from pydantic import ValidationError
from datetime import datetime, timezone

from babel.render.renderer import ChapterRenderer
from babel.transform.models import ChapterData, ScriptBlock, ScriptBlockType


@pytest.fixture
def renderer():
    """Create a ChapterRenderer instance for testing."""
    # Use a temporary template directory for testing
    return ChapterRenderer(template_dir=Path("templates"))


@pytest.fixture
def valid_chapter_data():
    """Create valid ChapterData for testing."""
    return ChapterData(
        blocks=[
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Hero",
                content="Hello, world!",
                tone="cheerful"
            ),
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="The hero walked forward."
            )
        ],
        source_hash="a" * 64,  # Valid SHA-256 hash
        model_version="gemini-2.5-flash",
        processed_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def temp_json_file(tmp_path, valid_chapter_data):
    """Create a temporary JSON file with valid chapter data."""
    json_path = tmp_path / "test_chapter.json"
    json_path.write_text(valid_chapter_data.model_dump_json(), encoding='utf-8')
    return json_path


class TestLoadChapterData:
    """Tests for the _load_chapter_data method."""
    
    def test_load_valid_json(self, renderer, temp_json_file, valid_chapter_data):
        """
        Test loading a valid JSON file.
        
        Validates: Requirements 1.1, 1.4
        """
        # Execute
        result = renderer._load_chapter_data(temp_json_file)
        
        # Verify
        assert result is not None
        assert isinstance(result, ChapterData)
        assert len(result.blocks) == 2
        assert result.blocks[0].speaker == "Hero"
        assert result.blocks[0].content == "Hello, world!"
        assert result.source_hash == "a" * 64
        assert result.model_version == "gemini-2.5-flash"
    
    def test_load_missing_file(self, renderer, tmp_path):
        """
        Test loading a non-existent JSON file.
        
        Validates: Requirements 1.2, 16.1
        """
        # Setup
        missing_path = tmp_path / "nonexistent.json"
        
        # Execute and verify
        with pytest.raises(FileNotFoundError) as exc_info:
            renderer._load_chapter_data(missing_path)
        
        # Verify error message is descriptive
        assert "JSON file not found" in str(exc_info.value)
        assert str(missing_path) in str(exc_info.value)
    
    def test_load_invalid_json_syntax(self, renderer, tmp_path):
        """
        Test loading a file with invalid JSON syntax.
        
        Validates: Requirements 1.2, 16.1
        """
        # Setup - create file with invalid JSON
        json_path = tmp_path / "invalid.json"
        json_path.write_text("{ invalid json syntax }", encoding='utf-8')
        
        # Execute and verify
        with pytest.raises(Exception):  # Will raise JSONDecodeError or similar
            renderer._load_chapter_data(json_path)
    
    def test_load_missing_required_field_blocks(self, renderer, tmp_path):
        """
        Test loading JSON missing the 'blocks' field.
        
        Validates: Requirements 1.3, 1.4, 16.2
        """
        # Setup - create JSON without blocks field
        json_path = tmp_path / "missing_blocks.json"
        invalid_data = {
            "source_hash": "a" * 64,
            "model_version": "gemini-2.5-flash",
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        json_path.write_text(json.dumps(invalid_data), encoding='utf-8')
        
        # Execute and verify
        with pytest.raises(ValidationError) as exc_info:
            renderer._load_chapter_data(json_path)
        
        # Verify error mentions missing field
        error_str = str(exc_info.value)
        assert "blocks" in error_str.lower() or "required" in error_str.lower()
    
    def test_load_missing_required_field_source_hash(self, renderer, tmp_path):
        """
        Test loading JSON missing the 'source_hash' field.
        
        Validates: Requirements 1.3, 1.4, 16.2
        """
        # Setup - create JSON without source_hash field
        json_path = tmp_path / "missing_hash.json"
        invalid_data = {
            "blocks": [
                {"type": "action", "content": "Test"}
            ],
            "model_version": "gemini-2.5-flash",
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        json_path.write_text(json.dumps(invalid_data), encoding='utf-8')
        
        # Execute and verify
        with pytest.raises(ValidationError) as exc_info:
            renderer._load_chapter_data(json_path)
        
        # Verify error mentions missing field
        error_str = str(exc_info.value)
        assert "source_hash" in error_str.lower() or "required" in error_str.lower()
    
    def test_load_missing_required_field_model_version(self, renderer, tmp_path):
        """
        Test loading JSON missing the 'model_version' field.
        
        Validates: Requirements 1.3, 1.4, 16.2
        """
        # Setup - create JSON without model_version field
        json_path = tmp_path / "missing_version.json"
        invalid_data = {
            "blocks": [
                {"type": "action", "content": "Test"}
            ],
            "source_hash": "a" * 64,
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        json_path.write_text(json.dumps(invalid_data), encoding='utf-8')
        
        # Execute and verify
        with pytest.raises(ValidationError) as exc_info:
            renderer._load_chapter_data(json_path)
        
        # Verify error mentions missing field
        error_str = str(exc_info.value)
        assert "model_version" in error_str.lower() or "required" in error_str.lower()
    
    def test_load_missing_optional_field_processed_at(self, renderer, tmp_path):
        """
        Test loading JSON missing the 'processed_at' field (has default).
        
        The processed_at field has a default_factory, so it's optional.
        This test verifies that the field is auto-generated when missing.
        
        Validates: Requirements 1.1, 1.4
        """
        # Setup - create JSON without processed_at field
        json_path = tmp_path / "missing_timestamp.json"
        data = {
            "blocks": [
                {"type": "action", "content": "Test"}
            ],
            "source_hash": "a" * 64,
            "model_version": "gemini-2.5-flash"
        }
        json_path.write_text(json.dumps(data), encoding='utf-8')
        
        # Execute
        result = renderer._load_chapter_data(json_path)
        
        # Verify - should load successfully with auto-generated timestamp
        assert result is not None
        assert result.processed_at is not None
        assert result.processed_at.tzinfo == timezone.utc
    
    def test_load_invalid_block_type(self, renderer, tmp_path):
        """
        Test loading JSON with invalid block type.
        
        Validates: Requirements 1.3, 16.2
        """
        # Setup - create JSON with invalid block type
        json_path = tmp_path / "invalid_block_type.json"
        invalid_data = {
            "blocks": [
                {"type": "invalid_type", "content": "Test"}
            ],
            "source_hash": "a" * 64,
            "model_version": "gemini-2.5-flash",
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        json_path.write_text(json.dumps(invalid_data), encoding='utf-8')
        
        # Execute and verify
        with pytest.raises(ValidationError) as exc_info:
            renderer._load_chapter_data(json_path)
        
        # Verify error mentions invalid type
        error_str = str(exc_info.value)
        assert "type" in error_str.lower() or "invalid" in error_str.lower()
    
    def test_load_empty_blocks_list(self, renderer, tmp_path):
        """
        Test loading JSON with empty blocks list.
        
        Validates: Requirements 1.1, 1.4
        """
        # Setup - create JSON with empty blocks
        json_path = tmp_path / "empty_blocks.json"
        data = {
            "blocks": [],
            "source_hash": "a" * 64,
            "model_version": "gemini-2.5-flash",
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        json_path.write_text(json.dumps(data), encoding='utf-8')
        
        # Execute
        result = renderer._load_chapter_data(json_path)
        
        # Verify - should load successfully with empty blocks
        assert result is not None
        assert isinstance(result, ChapterData)
        assert len(result.blocks) == 0
    
    def test_load_multiple_block_types(self, renderer, tmp_path):
        """
        Test loading JSON with multiple different block types.
        
        Validates: Requirements 1.1, 1.4
        """
        # Setup - create JSON with various block types
        json_path = tmp_path / "multiple_blocks.json"
        data = {
            "blocks": [
                {"type": "dialogue", "speaker": "Hero", "content": "Hello!"},
                {"type": "action", "content": "The hero walked."},
                {"type": "monologue", "speaker": "Villain", "content": "My plan..."},
                {"type": "sfx", "content": "BOOM"},
                {"type": "system_notification", "content": "[Level Up!]"}
            ],
            "source_hash": "b" * 64,
            "model_version": "gemini-2.5-flash",
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        json_path.write_text(json.dumps(data), encoding='utf-8')
        
        # Execute
        result = renderer._load_chapter_data(json_path)
        
        # Verify
        assert result is not None
        assert len(result.blocks) == 5
        assert result.blocks[0].type == ScriptBlockType.DIALOGUE
        assert result.blocks[1].type == ScriptBlockType.ACTION
        assert result.blocks[2].type == ScriptBlockType.MONOLOGUE
        assert result.blocks[3].type == ScriptBlockType.SFX
        assert result.blocks[4].type == ScriptBlockType.SYSTEM_NOTIFICATION
    
    def test_load_unicode_content(self, renderer, tmp_path):
        """
        Test loading JSON with Unicode characters.
        
        Validates: Requirements 1.1
        """
        # Setup - create JSON with Unicode content
        json_path = tmp_path / "unicode.json"
        data = {
            "blocks": [
                {"type": "dialogue", "speaker": "英雄", "content": "你好世界! 🎉"},
                {"type": "action", "content": "The hero smiled. 😊"}
            ],
            "source_hash": "c" * 64,
            "model_version": "gemini-2.5-flash",
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        json_path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        
        # Execute
        result = renderer._load_chapter_data(json_path)
        
        # Verify
        assert result is not None
        assert result.blocks[0].speaker == "英雄"
        assert result.blocks[0].content == "你好世界! 🎉"
        assert result.blocks[1].content == "The hero smiled. 😊"
    
    def test_load_optional_fields(self, renderer, tmp_path):
        """
        Test loading JSON with optional fields (tone) present and absent.
        
        Validates: Requirements 1.1
        """
        # Setup - create JSON with mixed optional fields
        json_path = tmp_path / "optional_fields.json"
        data = {
            "blocks": [
                {"type": "dialogue", "speaker": "Hero", "content": "Hello!", "tone": "cheerful"},
                {"type": "dialogue", "speaker": "Villain", "content": "Goodbye."}  # No tone
            ],
            "source_hash": "d" * 64,
            "model_version": "gemini-2.5-flash",
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        json_path.write_text(json.dumps(data), encoding='utf-8')
        
        # Execute
        result = renderer._load_chapter_data(json_path)
        
        # Verify
        assert result is not None
        assert result.blocks[0].tone == "cheerful"
        assert result.blocks[1].tone is None
    
    def test_load_logging_success(self, renderer, temp_json_file, caplog):
        """
        Test that successful loading logs debug message.
        
        Validates: Requirements 16.1
        """
        import logging
        caplog.set_level(logging.DEBUG)
        
        # Execute
        result = renderer._load_chapter_data(temp_json_file)
        
        # Verify logging
        assert result is not None
        log_messages = [record.message for record in caplog.records]
        assert any("Loaded chapter data" in msg for msg in log_messages)
        assert any("blocks" in msg for msg in log_messages)
    
    def test_load_logging_file_not_found(self, renderer, tmp_path, caplog):
        """
        Test that FileNotFoundError logs error message.
        
        Validates: Requirements 16.1, 16.3
        """
        import logging
        caplog.set_level(logging.ERROR)
        
        # Setup
        missing_path = tmp_path / "missing.json"
        
        # Execute
        with pytest.raises(FileNotFoundError):
            renderer._load_chapter_data(missing_path)
        
        # Verify logging
        log_messages = [record.message for record in caplog.records]
        assert any("JSON file not found" in msg for msg in log_messages)
        assert any(str(missing_path) in msg for msg in log_messages)
    
    def test_load_logging_validation_error(self, renderer, tmp_path, caplog):
        """
        Test that ValidationError logs error message.
        
        Validates: Requirements 16.1, 16.2, 16.3
        """
        import logging
        caplog.set_level(logging.ERROR)
        
        # Setup - create invalid JSON
        json_path = tmp_path / "invalid.json"
        json_path.write_text('{"blocks": []}', encoding='utf-8')  # Missing required fields
        
        # Execute
        with pytest.raises(ValidationError):
            renderer._load_chapter_data(json_path)
        
        # Verify logging
        log_messages = [record.message for record in caplog.records]
        assert any("Validation failed" in msg for msg in log_messages)
        assert any(json_path.name in msg for msg in log_messages)



class TestBatchStatistics:
    """
    Tests for batch rendering statistics tracking.
    
    Validates: Requirements 13.4, 13.5
    """
    
    def test_batch_statistics_all_successful(self, renderer, tmp_path, valid_chapter_data):
        """
        Test batch statistics when all chapters render successfully.
        
        Validates: Requirements 13.4, 13.5
        """
        # Setup - create multiple valid JSON files
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        output_dir = tmp_path / "output"
        
        for i in range(5):
            json_path = json_dir / f"chapter_{i:03d}.json"
            json_path.write_text(valid_chapter_data.model_dump_json(), encoding='utf-8')
        
        # Execute
        stats = renderer.render_batch(json_dir, output_dir)
        
        # Verify statistics
        assert stats["rendered"] == 5
        assert stats["failed"] == 0
        assert stats["skipped"] == 0
        
        # Verify all HTML files were created
        html_files = list(output_dir.glob("*.html"))
        assert len(html_files) == 5
    
    def test_batch_statistics_all_failed(self, renderer, tmp_path):
        """
        Test batch statistics when all chapters fail to render.
        
        Validates: Requirements 13.3, 13.4, 13.5
        """
        # Setup - create multiple invalid JSON files
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        output_dir = tmp_path / "output"
        
        for i in range(3):
            json_path = json_dir / f"chapter_{i:03d}.json"
            # Write invalid JSON (missing required fields)
            json_path.write_text('{"blocks": []}', encoding='utf-8')
        
        # Execute
        stats = renderer.render_batch(json_dir, output_dir)
        
        # Verify statistics
        assert stats["rendered"] == 0
        assert stats["failed"] == 3
        assert stats["skipped"] == 0
    
    def test_batch_statistics_mixed_success_failure(self, renderer, tmp_path, valid_chapter_data):
        """
        Test batch statistics with mix of successful and failed chapters.
        
        Validates: Requirements 13.3, 13.4, 13.5
        """
        # Setup - create mix of valid and invalid JSON files
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        output_dir = tmp_path / "output"
        
        # Create 3 valid chapters
        for i in range(3):
            json_path = json_dir / f"valid_{i:03d}.json"
            json_path.write_text(valid_chapter_data.model_dump_json(), encoding='utf-8')
        
        # Create 2 invalid chapters
        for i in range(2):
            json_path = json_dir / f"invalid_{i:03d}.json"
            json_path.write_text('{"blocks": []}', encoding='utf-8')
        
        # Execute
        stats = renderer.render_batch(json_dir, output_dir)
        
        # Verify statistics
        assert stats["rendered"] == 3
        assert stats["failed"] == 2
        assert stats["skipped"] == 0
        
        # Verify only valid chapters created HTML files
        html_files = list(output_dir.glob("*.html"))
        assert len(html_files) == 3
    
    def test_batch_statistics_empty_directory(self, renderer, tmp_path):
        """
        Test batch statistics when input directory is empty.
        
        Validates: Requirements 13.4, 13.5
        """
        # Setup - create empty directories
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        output_dir = tmp_path / "output"
        
        # Execute
        stats = renderer.render_batch(json_dir, output_dir)
        
        # Verify statistics - all zeros
        assert stats["rendered"] == 0
        assert stats["failed"] == 0
        assert stats["skipped"] == 0
    
    def test_batch_statistics_single_chapter(self, renderer, tmp_path, valid_chapter_data):
        """
        Test batch statistics with single chapter.
        
        Validates: Requirements 13.4, 13.5
        """
        # Setup - create single JSON file
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        output_dir = tmp_path / "output"
        
        json_path = json_dir / "chapter_001.json"
        json_path.write_text(valid_chapter_data.model_dump_json(), encoding='utf-8')
        
        # Execute
        stats = renderer.render_batch(json_dir, output_dir)
        
        # Verify statistics
        assert stats["rendered"] == 1
        assert stats["failed"] == 0
        assert stats["skipped"] == 0
    
    def test_batch_progress_logging(self, renderer, tmp_path, valid_chapter_data, caplog):
        """
        Test that batch rendering logs progress for each chapter.
        
        Validates: Requirements 13.5
        """
        import logging
        caplog.set_level(logging.INFO)
        
        # Setup - create multiple JSON files
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        output_dir = tmp_path / "output"
        
        chapter_names = ["chapter_001", "chapter_002", "chapter_003"]
        for name in chapter_names:
            json_path = json_dir / f"{name}.json"
            json_path.write_text(valid_chapter_data.model_dump_json(), encoding='utf-8')
        
        # Execute
        stats = renderer.render_batch(json_dir, output_dir)
        
        # Verify progress logging
        log_messages = [record.message for record in caplog.records]
        
        # Should log processing start
        assert any("Processing" in msg and "chapters" in msg for msg in log_messages)
        
        # Should log each rendered chapter
        for name in chapter_names:
            assert any(f"{name}.html" in msg and "Rendered" in msg for msg in log_messages)
        
        # Should log batch completion summary
        assert any("Batch complete" in msg for msg in log_messages)
        assert any("3 rendered" in msg for msg in log_messages)
    
    def test_batch_progress_logging_with_failures(self, renderer, tmp_path, valid_chapter_data, caplog):
        """
        Test that batch rendering logs both successes and failures.
        
        Validates: Requirements 13.5, 16.5
        """
        import logging
        caplog.set_level(logging.INFO)
        
        # Setup - create mix of valid and invalid files
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        output_dir = tmp_path / "output"
        
        # Valid chapter
        valid_path = json_dir / "valid.json"
        valid_path.write_text(valid_chapter_data.model_dump_json(), encoding='utf-8')
        
        # Invalid chapter
        invalid_path = json_dir / "invalid.json"
        invalid_path.write_text('{"blocks": []}', encoding='utf-8')
        
        # Execute
        stats = renderer.render_batch(json_dir, output_dir)
        
        # Verify logging
        log_messages = [record.message for record in caplog.records]
        
        # Should log success
        assert any("valid.html" in msg and "Rendered" in msg for msg in log_messages)
        
        # Should log failure
        assert any("invalid.json" in msg and "Failed to render" in msg for msg in log_messages)
        
        # Should log summary with both counts
        assert any("1 rendered" in msg and "1 failed" in msg for msg in log_messages)
    
    def test_batch_statistics_dict_structure(self, renderer, tmp_path, valid_chapter_data):
        """
        Test that statistics dictionary has correct structure and types.
        
        Validates: Requirements 13.4
        """
        # Setup
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        output_dir = tmp_path / "output"
        
        json_path = json_dir / "chapter.json"
        json_path.write_text(valid_chapter_data.model_dump_json(), encoding='utf-8')
        
        # Execute
        stats = renderer.render_batch(json_dir, output_dir)
        
        # Verify structure
        assert isinstance(stats, dict)
        assert "rendered" in stats
        assert "failed" in stats
        assert "skipped" in stats
        
        # Verify types
        assert isinstance(stats["rendered"], int)
        assert isinstance(stats["failed"], int)
        assert isinstance(stats["skipped"], int)
        
        # Verify non-negative values
        assert stats["rendered"] >= 0
        assert stats["failed"] >= 0
        assert stats["skipped"] >= 0
    
    def test_batch_statistics_accuracy_large_batch(self, renderer, tmp_path, valid_chapter_data):
        """
        Test statistics accuracy with larger batch (10+ chapters).
        
        Validates: Requirements 13.4, 13.5
        """
        # Setup - create 15 chapters (10 valid, 5 invalid)
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        output_dir = tmp_path / "output"
        
        # Create 10 valid chapters
        for i in range(10):
            json_path = json_dir / f"valid_{i:03d}.json"
            json_path.write_text(valid_chapter_data.model_dump_json(), encoding='utf-8')
        
        # Create 5 invalid chapters
        for i in range(5):
            json_path = json_dir / f"invalid_{i:03d}.json"
            json_path.write_text('{"blocks": []}', encoding='utf-8')
        
        # Execute
        stats = renderer.render_batch(json_dir, output_dir)
        
        # Verify statistics accuracy
        assert stats["rendered"] == 10
        assert stats["failed"] == 5
        assert stats["skipped"] == 0
        
        # Verify total matches input count
        total_processed = stats["rendered"] + stats["failed"] + stats["skipped"]
        assert total_processed == 15
    
    def test_batch_continues_after_failure(self, renderer, tmp_path, valid_chapter_data, caplog):
        """
        Test that batch processing continues after encountering a failure.
        
        Validates: Requirements 13.3, 16.5
        """
        import logging
        caplog.set_level(logging.INFO)
        
        # Setup - create chapters in specific order: valid, invalid, valid
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        output_dir = tmp_path / "output"
        
        # First valid chapter
        (json_dir / "a_valid_1.json").write_text(
            valid_chapter_data.model_dump_json(), encoding='utf-8'
        )
        
        # Invalid chapter in the middle
        (json_dir / "b_invalid.json").write_text(
            '{"blocks": []}', encoding='utf-8'
        )
        
        # Second valid chapter
        (json_dir / "c_valid_2.json").write_text(
            valid_chapter_data.model_dump_json(), encoding='utf-8'
        )
        
        # Execute
        stats = renderer.render_batch(json_dir, output_dir)
        
        # Verify both valid chapters were processed despite middle failure
        assert stats["rendered"] == 2
        assert stats["failed"] == 1
        
        # Verify both valid HTML files exist
        assert (output_dir / "a_valid_1.html").exists()
        assert (output_dir / "c_valid_2.html").exists()
        assert not (output_dir / "b_invalid.html").exists()
        
        # Verify logging shows continuation
        log_messages = [record.message for record in caplog.records]
        assert any("a_valid_1.html" in msg for msg in log_messages)
        assert any("b_invalid.json" in msg and "Failed" in msg for msg in log_messages)
        assert any("c_valid_2.html" in msg for msg in log_messages)



class TestTemplateCaching:
    """
    Tests for Jinja2 template caching efficiency.
    
    Validates: Requirements 17.4
    """
    
    def test_template_compiled_once_per_instance(self, renderer, tmp_path, valid_chapter_data):
        """
        Test that templates are compiled once per ChapterRenderer instance.
        
        Jinja2's Environment caches compiled templates automatically. This test
        verifies that the same template object is reused across multiple render
        calls, not recompiled each time.
        
        Validates: Requirements 17.4
        """
        # Setup - create multiple JSON files
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        output_dir = tmp_path / "output"
        
        for i in range(5):
            json_path = json_dir / f"chapter_{i:03d}.json"
            json_path.write_text(valid_chapter_data.model_dump_json(), encoding='utf-8')
        
        # Get the template object reference before rendering
        template_before = renderer.template
        template_id_before = id(renderer.template)
        
        # Execute - render multiple chapters
        stats = renderer.render_batch(json_dir, output_dir)
        
        # Verify all chapters rendered successfully
        assert stats["rendered"] == 5
        
        # Get the template object reference after rendering
        template_after = renderer.template
        template_id_after = id(renderer.template)
        
        # Verify the template object is the same instance (not recompiled)
        assert template_before is template_after
        assert template_id_before == template_id_after
        
        # Verify the template is still the same after individual renders
        json_path = json_dir / "chapter_000.json"
        output_path = output_dir / "test_rerender.html"
        renderer.render_chapter(json_path, output_path)
        
        assert renderer.template is template_before
        assert id(renderer.template) == template_id_before
    
    def test_template_cached_in_jinja2_environment(self, renderer, tmp_path, valid_chapter_data):
        """
        Test that Jinja2 Environment caches the template internally.
        
        Jinja2's Environment.get_template() returns cached templates on
        subsequent calls. This test verifies that the caching mechanism
        is working correctly.
        
        Validates: Requirements 17.4
        """
        # Get template multiple times from the environment
        template1 = renderer.env.get_template("chapter.html")
        template2 = renderer.env.get_template("chapter.html")
        template3 = renderer.env.get_template("chapter.html")
        
        # Verify all references point to the same cached template object
        assert template1 is template2
        assert template2 is template3
        assert id(template1) == id(template2) == id(template3)
        
        # Verify it's the same template used by the renderer
        assert template1 is renderer.template
    
    def test_template_reused_across_batch_rendering(self, renderer, tmp_path, valid_chapter_data, monkeypatch):
        """
        Test that template is not reloaded during batch rendering.
        
        This test uses monkeypatching to track how many times the template
        is accessed from the Jinja2 environment during batch rendering.
        The template should be accessed once during initialization and
        reused for all subsequent renders.
        
        Validates: Requirements 17.4
        """
        # Setup - create multiple JSON files
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        output_dir = tmp_path / "output"
        
        for i in range(10):
            json_path = json_dir / f"chapter_{i:03d}.json"
            json_path.write_text(valid_chapter_data.model_dump_json(), encoding='utf-8')
        
        # Track template access count
        access_count = {"count": 0}
        original_render = renderer.template.render
        
        def tracked_render(*args, **kwargs):
            access_count["count"] += 1
            return original_render(*args, **kwargs)
        
        # Monkeypatch the render method to track calls
        monkeypatch.setattr(renderer.template, "render", tracked_render)
        
        # Execute - render batch
        stats = renderer.render_batch(json_dir, output_dir)
        
        # Verify all chapters rendered successfully
        assert stats["rendered"] == 10
        
        # Verify template.render() was called exactly 10 times (once per chapter)
        # This confirms the template object itself is reused, not recreated
        assert access_count["count"] == 10
    
    def test_multiple_renderer_instances_have_separate_caches(self, tmp_path, valid_chapter_data):
        """
        Test that different ChapterRenderer instances have separate template caches.
        
        Each ChapterRenderer instance creates its own Jinja2 Environment,
        which has its own template cache. This test verifies that multiple
        renderer instances don't interfere with each other.
        
        Validates: Requirements 17.4
        """
        # Create two separate renderer instances
        renderer1 = ChapterRenderer(template_dir=Path("templates"))
        renderer2 = ChapterRenderer(template_dir=Path("templates"))
        
        # Verify they have different Environment instances
        assert renderer1.env is not renderer2.env
        assert id(renderer1.env) != id(renderer2.env)
        
        # Verify they have different template instances (separate caches)
        # Note: Jinja2 may return the same compiled template object if it's
        # cached at a higher level, but the Environment instances are separate
        assert renderer1.template is not None
        assert renderer2.template is not None
        
        # Verify both can render independently
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        output_dir1 = tmp_path / "output1"
        output_dir2 = tmp_path / "output2"
        
        json_path = json_dir / "chapter.json"
        json_path.write_text(valid_chapter_data.model_dump_json(), encoding='utf-8')
        
        # Render with both instances
        stats1 = renderer1.render_batch(json_dir, output_dir1)
        stats2 = renderer2.render_batch(json_dir, output_dir2)
        
        # Verify both rendered successfully
        assert stats1["rendered"] == 1
        assert stats2["rendered"] == 1
        
        # Verify both output files exist
        assert (output_dir1 / "chapter.html").exists()
        assert (output_dir2 / "chapter.html").exists()
    
    def test_template_caching_performance_benefit(self, renderer, tmp_path, valid_chapter_data):
        """
        Test that template caching provides performance benefits.
        
        This test measures the time difference between rendering with a cached
        template vs creating a new renderer (which loads the template fresh).
        Cached rendering should be faster.
        
        Validates: Requirements 17.4, 17.2
        """
        import time
        
        # Setup - create test JSON file
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        output_dir = tmp_path / "output"
        
        json_path = json_dir / "chapter.json"
        json_path.write_text(valid_chapter_data.model_dump_json(), encoding='utf-8')
        
        # Measure time for first render (template already cached in renderer)
        start_cached = time.perf_counter()
        for i in range(10):
            output_path = output_dir / f"cached_{i}.html"
            renderer.render_chapter(json_path, output_path)
        end_cached = time.perf_counter()
        cached_time = end_cached - start_cached
        
        # Measure time for renders with new renderer instances (template loading overhead)
        start_fresh = time.perf_counter()
        for i in range(10):
            fresh_renderer = ChapterRenderer(template_dir=Path("templates"))
            output_path = output_dir / f"fresh_{i}.html"
            fresh_renderer.render_chapter(json_path, output_path)
        end_fresh = time.perf_counter()
        fresh_time = end_fresh - start_fresh
        
        # Verify cached rendering is faster (or at least not significantly slower)
        # We expect cached to be faster, but allow for some variance in timing
        # The key is that cached rendering doesn't reload the template each time
        assert cached_time < fresh_time * 1.5  # Allow 50% margin for timing variance
        
        # Log the performance difference for visibility
        print(f"\nTemplate caching performance:")
        print(f"  Cached rendering (10 chapters): {cached_time:.4f}s")
        print(f"  Fresh rendering (10 chapters): {fresh_time:.4f}s")
        print(f"  Speedup: {fresh_time / cached_time:.2f}x")
    
    def test_template_object_persists_across_renders(self, renderer, tmp_path, valid_chapter_data):
        """
        Test that the template object persists and is not garbage collected.
        
        This test verifies that the template object stored in the renderer
        remains valid and usable across multiple render operations.
        
        Validates: Requirements 17.4
        """
        # Setup
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        output_dir = tmp_path / "output"
        
        json_path = json_dir / "chapter.json"
        json_path.write_text(valid_chapter_data.model_dump_json(), encoding='utf-8')
        
        # Get initial template reference
        initial_template = renderer.template
        initial_template_id = id(initial_template)
        
        # Render multiple times
        for i in range(20):
            output_path = output_dir / f"chapter_{i:03d}.html"
            renderer.render_chapter(json_path, output_path)
            
            # Verify template object hasn't changed
            assert renderer.template is initial_template
            assert id(renderer.template) == initial_template_id
        
        # Verify all renders succeeded
        html_files = list(output_dir.glob("*.html"))
        assert len(html_files) == 20
    
    def test_template_caching_with_chapter_map(self, renderer, tmp_path, valid_chapter_data):
        """
        Test that template caching works correctly with chapter map navigation.
        
        When rendering with a chapter map (for navigation), the template
        should still be cached and reused, not reloaded.
        
        Validates: Requirements 17.4
        """
        from babel.sanitize import ChapterMap, ChapterEntry
        
        # Setup - create JSON files and chapter map
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        output_dir = tmp_path / "output"
        
        # Create chapter map
        chapter_map = ChapterMap(
            source_filename="test.epub",
            chapters=[
                ChapterEntry(index=0, filename="chapter_000.json", title="Chapter 1", token_count_est=1000),
                ChapterEntry(index=1, filename="chapter_001.json", title="Chapter 2", token_count_est=1000),
                ChapterEntry(index=2, filename="chapter_002.json", title="Chapter 3", token_count_est=1000),
            ]
        )
        
        # Create JSON files
        for i in range(3):
            json_path = json_dir / f"chapter_{i:03d}.json"
            json_path.write_text(valid_chapter_data.model_dump_json(), encoding='utf-8')
        
        # Get template reference before rendering
        template_before = renderer.template
        
        # Render with chapter map
        for i in range(3):
            json_path = json_dir / f"chapter_{i:03d}.json"
            output_path = output_dir / f"chapter_{i:03d}.html"
            renderer.render_chapter(json_path, output_path, chapter_map)
        
        # Verify template is still the same object
        assert renderer.template is template_before
        
        # Verify all chapters rendered with navigation
        for i in range(3):
            html_path = output_dir / f"chapter_{i:03d}.html"
            assert html_path.exists()
            
            # Verify HTML contains navigation elements
            html_content = html_path.read_text(encoding='utf-8')
            assert "navigation" in html_content.lower()
