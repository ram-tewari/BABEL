"""
Unit tests for CLI entry point.
"""

import sys
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, Mock
import pytest
from babel.transform.__main__ import main


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    clean_dir = Path(tempfile.mkdtemp())
    json_dir = Path(tempfile.mkdtemp())
    
    # Create data directory structure
    data_dir = Path(tempfile.mkdtemp())
    clean_path = data_dir / "clean"
    json_path = data_dir / "json"
    clean_path.mkdir()
    json_path.mkdir()
    
    yield data_dir, clean_path, json_path
    
    # Cleanup
    shutil.rmtree(clean_dir, ignore_errors=True)
    shutil.rmtree(json_dir, ignore_errors=True)
    shutil.rmtree(data_dir, ignore_errors=True)


def test_cli_exit_code_0_on_success(temp_dirs):
    """Test that CLI exits with code 0 on successful processing."""
    data_dir, clean_path, json_path = temp_dirs
    
    # Setup chapter map
    manifest_path = clean_path / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump({"chapters": []}, f)
    
    # Mock Path to use our temp directories
    with patch('babel.transform.__main__.Path') as mock_path:
        mock_path.return_value = clean_path
        mock_path.side_effect = lambda x: clean_path if x == "data/clean" else json_path
        
        # Mock BatchProcessor
        with patch('babel.transform.__main__.BatchProcessor') as mock_processor:
            mock_instance = Mock()
            mock_instance.process_all_chapters.return_value = (5, 3, 0)  # No failures
            mock_processor.return_value = mock_instance
            
            # Run main and expect SystemExit with code 0
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 0


def test_cli_exit_code_1_on_failures(temp_dirs):
    """Test that CLI exits with code 1 when chapters fail."""
    data_dir, clean_path, json_path = temp_dirs
    
    # Setup chapter map
    manifest_path = clean_path / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump({"chapters": []}, f)
    
    # Mock Path to use our temp directories
    with patch('babel.transform.__main__.Path') as mock_path:
        mock_path.return_value = clean_path
        mock_path.side_effect = lambda x: clean_path if x == "data/clean" else json_path
        
        # Mock BatchProcessor
        with patch('babel.transform.__main__.BatchProcessor') as mock_processor:
            mock_instance = Mock()
            mock_instance.process_all_chapters.return_value = (5, 3, 2)  # 2 failures
            mock_processor.return_value = mock_instance
            
            # Run main and expect SystemExit with code 1
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 1


def test_cli_exit_code_1_on_missing_manifest():
    """Test that CLI exits with code 1 when manifest is missing."""
    # Mock Path to use non-existent directories
    with patch('babel.transform.__main__.Path') as mock_path:
        mock_clean = Mock()
        mock_json = Mock()
        mock_path.side_effect = lambda x: mock_clean if x == "data/clean" else mock_json
        
        # Mock BatchProcessor to raise FileNotFoundError
        with patch('babel.transform.__main__.BatchProcessor') as mock_processor:
            mock_processor.side_effect = FileNotFoundError("Chapter manifest not found")
            
            # Run main and expect SystemExit with code 1
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 1


def test_cli_exit_code_1_on_missing_api_key():
    """Test that CLI exits with code 1 when API key is missing."""
    # Mock Path
    with patch('babel.transform.__main__.Path') as mock_path:
        mock_clean = Mock()
        mock_json = Mock()
        mock_path.side_effect = lambda x: mock_clean if x == "data/clean" else mock_json
        
        # Mock BatchProcessor to raise ValueError (missing API key)
        with patch('babel.transform.__main__.BatchProcessor') as mock_processor:
            mock_processor.side_effect = ValueError("GEMINI_API_KEY environment variable not set")
            
            # Run main and expect SystemExit with code 1
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 1


def test_cli_exit_code_1_on_unexpected_error():
    """Test that CLI exits with code 1 on unexpected errors."""
    # Mock Path
    with patch('babel.transform.__main__.Path') as mock_path:
        mock_clean = Mock()
        mock_json = Mock()
        mock_path.side_effect = lambda x: mock_clean if x == "data/clean" else mock_json
        
        # Mock BatchProcessor to raise unexpected error
        with patch('babel.transform.__main__.BatchProcessor') as mock_processor:
            mock_processor.side_effect = RuntimeError("Unexpected error")
            
            # Run main and expect SystemExit with code 1
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 1
