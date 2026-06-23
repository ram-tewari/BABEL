"""
Unit tests for transform CLI commands with novel support.

These tests validate:
- Transform with novel_id (database-first processing)
- Transform without novel_id (legacy processing)
- Error handling for non-existent novel_id
- Novel-specific directory path construction
- Chapter database filtering by novel_id
- Pipeline state updates
- Backward compatibility for legacy chapters

Validates: Requirements 3.1, 3.4, 3.7
"""

import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
import pytest
from typer.testing import CliRunner
from babel.cli import app


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    data_dir = Path(tempfile.mkdtemp())
    clean_dir = data_dir / "clean"
    json_dir = data_dir / "json"
    clean_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)
    
    yield data_dir, clean_dir, json_dir
    
    # Cleanup
    shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture
def runner():
    """Create Typer CLI runner."""
    return CliRunner()


def test_transform_batch_novel_id_option_exists(runner):
    """
    Test: Transform batch command has --novel-id option.
    
    Validates: Requirements 3.1
    """
    result = runner.invoke(app, ["transform", "batch", "--help"])
    
    # Verify --novel-id option exists in help
    assert "--novel-id" in result.output or "-n" in result.output


def test_transform_batch_input_dir_is_optional(runner):
    """
    Test: Transform batch command has optional input_dir (now an option, not argument).
    
    Validates: Requirements 3.1
    """
    result = runner.invoke(app, ["transform", "batch", "--help"])
    
    # Verify input is now an option (--input or -i)
    assert "--input" in result.output or "-i" in result.output


def test_transform_batch_with_input_and_output_options(temp_dirs, runner):
    """
    Test: Transform batch with --input and --output options works.
    
    Validates: Requirements 3.1
    """
    _, clean_dir, json_dir = temp_dirs
    
    # Create test files
    (clean_dir / "ch_001.txt").write_text("Chapter 1 content")
    
    # Mock at the CLI command module where classes are imported and used
    with patch('babel.cli_commands.transform_commands.NvidiaClient') as mock_nvidia, \
         patch('babel.cli_commands.transform_commands.BatchProcessor') as mock_processor:
        
        mock_client = Mock()
        mock_nvidia.return_value = mock_client
        
        mock_instance = Mock()
        mock_instance.process_all_chapters.return_value = (0, 0, 0)
        mock_processor.return_value = mock_instance
        
        # Run transform batch with options
        result = runner.invoke(
            app,
            ["transform", "batch", "--input", str(clean_dir), "--output", str(json_dir)]
        )
        
        # Should succeed
        assert result.exit_code == 0


def test_transform_batch_with_novel_id_option(temp_dirs, runner):
    """
    Test: Transform batch with --novel-id option.
    
    Validates: Requirements 3.1, 3.2, 3.3
    """
    data_dir, clean_dir, json_dir = temp_dirs
    novel_id = 1
    
    # Create test files
    (clean_dir / "ch_001.txt").write_text("Chapter 1 content")
    
    # Mock at the CLI command module where classes are imported and used
    with patch('babel.cli_commands.transform_commands.NvidiaClient') as mock_nvidia, \
         patch('babel.cli_commands.transform_commands.BatchProcessor') as mock_processor, \
         patch('babel.data.db.DatabaseManager') as mock_db:
        
        mock_client = Mock()
        mock_nvidia.return_value = mock_client
        
        db_instance = MagicMock()
        mock_db.return_value = db_instance
        
        # Setup mock novel and chapters
        db_instance.get_novel.return_value = {
            'id': novel_id,
            'title': 'Test Novel',
            'author': 'Test Author'
        }
        db_instance.get_chapters_by_novel.return_value = [
            {'id': 1, 'chapter_index': 0, 'filename': 'ch_001.txt', 'title': 'Chapter 1'}
        ]
        
        mock_instance = Mock()
        mock_instance.process_all_chapters.return_value = (0, 0, 0)
        mock_processor.return_value = mock_instance
        
        # Run transform batch with novel_id
        result = runner.invoke(
            app,
            ["transform", "batch", "--novel-id", str(novel_id), "--input", str(clean_dir), "--output", str(json_dir)]
        )
        
        # Verify novel was looked up
        db_instance.get_novel.assert_called_once_with(novel_id)
        
        # Verify chapters were retrieved
        db_instance.get_chapters_by_novel.assert_called_once_with(novel_id)
        
        # Verify pipeline state was updated (running and complete)
        assert db_instance.update_pipeline_state.call_count == 2
        
        # Should succeed
        assert result.exit_code == 0


def test_transform_batch_novel_not_found_error(runner):
    """
    Test: Transform with non-existent novel_id shows error and exits with code 1.
    
    Validates: Requirements 3.5, 3.7
    """
    novel_id = 999
    
    # Mock at the CLI command module where classes are imported and used
    with patch('babel.cli_commands.transform_commands.NvidiaClient') as mock_nvidia, \
         patch('babel.data.db.DatabaseManager') as mock_db:
        
        mock_client = Mock()
        mock_nvidia.return_value = mock_client
        
        db_instance = MagicMock()
        mock_db.return_value = db_instance
        db_instance.get_novel.return_value = None
        
        # Run transform batch with non-existent novel_id
        result = runner.invoke(
            app,
            ["transform", "batch", "--novel-id", str(novel_id)]
        )
        
        # Verify novel lookup was attempted
        db_instance.get_novel.assert_called_once_with(novel_id)
        
        # Should fail with error message
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or str(novel_id) in result.output


def test_transform_batch_default_novel_directories(temp_dirs, runner):
    """
    Test: Transform with novel_id uses default novel-specific directories.
    
    Validates: Requirements 3.3, 8.1, 8.2
    """
    data_dir, clean_dir, json_dir = temp_dirs
    novel_id = 1
    
    # Create test file in novel-specific directory
    novel_clean_dir = data_dir / f"clean/novel_{novel_id}"
    novel_clean_dir.mkdir(parents=True, exist_ok=True)
    (novel_clean_dir / "ch_001.txt").write_text("Chapter 1 content")
    
    # Mock at the CLI command module where classes are imported and used
    with patch('babel.cli_commands.transform_commands.NvidiaClient') as mock_nvidia, \
         patch('babel.cli_commands.transform_commands.BatchProcessor') as mock_processor, \
         patch('babel.data.db.DatabaseManager') as mock_db:
        
        mock_client = Mock()
        mock_nvidia.return_value = mock_client
        
        db_instance = MagicMock()
        mock_db.return_value = db_instance
        
        # Setup mock novel and chapters
        db_instance.get_novel.return_value = {
            'id': novel_id,
            'title': 'Test Novel',
            'author': 'Test Author'
        }
        db_instance.get_chapters_by_novel.return_value = [
            {'id': 1, 'chapter_index': 0, 'filename': 'ch_001.txt', 'title': 'Chapter 1'}
        ]
        
        mock_instance = Mock()
        mock_instance.process_all_chapters.return_value = (0, 0, 0)
        mock_processor.return_value = mock_instance
        
        # Run transform batch with novel_id but no input/output dirs
        result = runner.invoke(
            app,
            ["transform", "batch", "--novel-id", str(novel_id)]
        )
        
        # Should succeed
        assert result.exit_code == 0
        
        # Verify BatchProcessor was called with novel-specific directories
        mock_processor.assert_called_once()
        call_args = mock_processor.call_args
        # Use Path to handle cross-platform path separators
        assert Path(call_args[0][0]).as_posix() == f"data/clean/novel_{novel_id}"
        assert Path(call_args[0][1]).as_posix() == f"data/json/novel_{novel_id}"


def test_transform_batch_legacy_default_directories(runner):
    """
    Test: Transform without novel_id uses default legacy directories.
    
    Validates: Requirements 10.1, 10.2
    """
    # Mock at the CLI command module where classes are imported and used
    with patch('babel.cli_commands.transform_commands.NvidiaClient') as mock_nvidia, \
         patch('babel.cli_commands.transform_commands.BatchProcessor') as mock_processor:
        
        mock_client = Mock()
        mock_nvidia.return_value = mock_client
        
        mock_instance = Mock()
        mock_instance.process_all_chapters.return_value = (0, 0, 0)
        mock_processor.return_value = mock_instance
        
        # Run transform batch without novel_id and without input/output dirs
        result = runner.invoke(
            app,
            ["transform", "batch"]
        )
        
        # Should succeed
        assert result.exit_code == 0
        
        # Verify BatchProcessor was called with legacy directories
        mock_processor.assert_called_once()
        call_args = mock_processor.call_args
        # Use Path to handle cross-platform path separators
        assert Path(call_args[0][0]).as_posix() == "data/clean"
        assert Path(call_args[0][1]).as_posix() == "data/json"