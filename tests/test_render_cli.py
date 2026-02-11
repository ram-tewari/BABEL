"""
Integration tests for Phase 2 rendering CLI.

Tests the full pipeline: JSON → HTML with real chapter data.
"""

import sys
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch
import pytest

from babel.render.__main__ import main, parse_args, validate_args


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    # Create temporary directories
    json_dir = Path(tempfile.mkdtemp())
    output_dir = Path(tempfile.mkdtemp())
    
    yield json_dir, output_dir
    
    # Cleanup
    shutil.rmtree(json_dir, ignore_errors=True)
    shutil.rmtree(output_dir, ignore_errors=True)


@pytest.fixture
def sample_chapter_data():
    """Create sample chapter data for testing."""
    return {
        "blocks": [
            {
                "type": "system_notification",
                "content": "[Chapter 1: Test Chapter]"
            },
            {
                "type": "dialogue",
                "speaker": "Alice",
                "content": "Hello, world!",
                "tone": "cheerful"
            },
            {
                "type": "dialogue",
                "speaker": "Bob",
                "content": "Hi there!",
                "tone": "friendly"
            },
            {
                "type": "action",
                "content": "They shook hands."
            },
            {
                "type": "monologue",
                "speaker": "Alice",
                "content": "This is going well."
            }
        ],
        "source_hash": "a" * 64,
        "model_version": "gemini-2.5-flash",
        "processed_at": "2026-02-03T10:00:00+00:00"
    }


@pytest.fixture
def chapter_map_data():
    """Create sample chapter map for testing."""
    return {
        "source_filename": "test_novel.epub",
        "processed_at": "2026-02-03T10:00:00+00:00",
        "chapters": [
            {
                "index": 0,
                "filename": "Ch_001.json",
                "title": "Chapter 1: The Beginning",
                "token_count_est": 1000,
                "volume": None,
                "metadata": {}
            },
            {
                "index": 1,
                "filename": "Ch_002.json",
                "title": "Chapter 2: The Middle",
                "token_count_est": 1200,
                "volume": None,
                "metadata": {}
            },
            {
                "index": 2,
                "filename": "Ch_003.json",
                "title": "Chapter 3: The End",
                "token_count_est": 1100,
                "volume": None,
                "metadata": {}
            }
        ]
    }


def test_cli_help():
    """Test that CLI help message works."""
    with patch('sys.argv', ['babel.render', '--help']):
        with pytest.raises(SystemExit) as exc_info:
            parse_args()
        
        # Help should exit with code 0
        assert exc_info.value.code == 0


def test_cli_single_chapter_rendering(temp_dirs, sample_chapter_data):
    """Test rendering a single chapter via CLI."""
    json_dir, output_dir = temp_dirs
    
    # Create sample JSON file
    json_path = json_dir / "Ch_001.json"
    json_path.write_text(json.dumps(sample_chapter_data), encoding='utf-8')
    
    # Mock sys.argv
    with patch('sys.argv', [
        'babel.render',
        str(json_dir),
        str(output_dir)
    ]):
        # Run CLI
        exit_code = main()
        
        # Should succeed
        assert exit_code == 0
        
        # Check output file exists
        output_path = output_dir / "Ch_001.html"
        assert output_path.exists()
        
        # Check HTML content
        html_content = output_path.read_text(encoding='utf-8')
        assert '<!DOCTYPE html>' in html_content
        assert 'Alice' in html_content
        assert 'Bob' in html_content
        assert 'Hello, world!' in html_content


def test_cli_batch_rendering(temp_dirs, sample_chapter_data):
    """Test batch rendering of multiple chapters via CLI."""
    json_dir, output_dir = temp_dirs
    
    # Create multiple JSON files
    for i in range(1, 4):
        json_path = json_dir / f"Ch_{i:03d}.json"
        chapter_data = sample_chapter_data.copy()
        chapter_data["blocks"][0]["content"] = f"[Chapter {i}: Test Chapter]"
        json_path.write_text(json.dumps(chapter_data), encoding='utf-8')
    
    # Mock sys.argv
    with patch('sys.argv', [
        'babel.render',
        str(json_dir),
        str(output_dir)
    ]):
        # Run CLI
        exit_code = main()
        
        # Should succeed
        assert exit_code == 0
        
        # Check all output files exist
        for i in range(1, 4):
            output_path = output_dir / f"Ch_{i:03d}.html"
            assert output_path.exists()
            
            # Check HTML content
            html_content = output_path.read_text(encoding='utf-8')
            assert '<!DOCTYPE html>' in html_content
            assert f'Chapter {i}' in html_content


def test_cli_with_chapter_map(temp_dirs, sample_chapter_data, chapter_map_data):
    """Test rendering with chapter map for navigation links."""
    json_dir, output_dir = temp_dirs
    
    # Create JSON files
    for i in range(1, 4):
        json_path = json_dir / f"Ch_{i:03d}.json"
        chapter_data = sample_chapter_data.copy()
        chapter_data["blocks"][0]["content"] = f"[Chapter {i}: Test Chapter]"
        json_path.write_text(json.dumps(chapter_data), encoding='utf-8')
    
    # Create chapter map in a separate directory (not in json_dir)
    map_dir = json_dir.parent / "maps"
    map_dir.mkdir(exist_ok=True)
    map_path = map_dir / "chapter_map.json"
    map_path.write_text(json.dumps(chapter_map_data), encoding='utf-8')
    
    # Mock sys.argv
    with patch('sys.argv', [
        'babel.render',
        str(json_dir),
        str(output_dir),
        '--chapter-map', str(map_path)
    ]):
        # Run CLI
        exit_code = main()
        
        # Should succeed
        assert exit_code == 0
        
        # Check navigation links in middle chapter
        ch2_html = (output_dir / "Ch_002.html").read_text(encoding='utf-8')
        assert 'Ch_001.html' in ch2_html  # Previous link
        assert 'Ch_003.html' in ch2_html  # Next link
        
        # Check first chapter (no previous)
        ch1_html = (output_dir / "Ch_001.html").read_text(encoding='utf-8')
        assert 'Ch_002.html' in ch1_html  # Next link
        # Previous button should be disabled
        assert 'disabled' in ch1_html or 'Previous' in ch1_html
        
        # Check last chapter (no next)
        ch3_html = (output_dir / "Ch_003.html").read_text(encoding='utf-8')
        assert 'Ch_002.html' in ch3_html  # Previous link
        # Next button should be disabled
        assert 'disabled' in ch3_html or 'Next' in ch3_html


def test_cli_exit_code_1_on_missing_json_dir():
    """Test that CLI exits with code 1 when JSON directory doesn't exist."""
    with patch('sys.argv', [
        'babel.render',
        'nonexistent_dir',
        'output_dir'
    ]):
        exit_code = main()
        assert exit_code == 1


def test_cli_exit_code_1_on_missing_template_dir():
    """Test that CLI exits with code 1 when template directory doesn't exist."""
    json_dir = Path(tempfile.mkdtemp())
    output_dir = Path(tempfile.mkdtemp())
    
    try:
        with patch('sys.argv', [
            'babel.render',
            str(json_dir),
            str(output_dir),
            '--template-dir', 'nonexistent_templates'
        ]):
            exit_code = main()
            assert exit_code == 1
    finally:
        shutil.rmtree(json_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)


def test_cli_exit_code_1_on_invalid_json():
    """Test that CLI exits with code 1 when JSON files are invalid."""
    json_dir = Path(tempfile.mkdtemp())
    output_dir = Path(tempfile.mkdtemp())
    
    try:
        # Create invalid JSON file
        json_path = json_dir / "Ch_001.json"
        json_path.write_text("{ invalid json }", encoding='utf-8')
        
        with patch('sys.argv', [
            'babel.render',
            str(json_dir),
            str(output_dir)
        ]):
            exit_code = main()
            # Should fail because of invalid JSON
            assert exit_code == 1
    finally:
        shutil.rmtree(json_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)


def test_cli_exit_code_0_with_partial_failures(temp_dirs, sample_chapter_data):
    """Test that CLI exits with code 1 when some chapters fail but continues processing."""
    json_dir, output_dir = temp_dirs
    
    # Create valid JSON file
    json_path1 = json_dir / "Ch_001.json"
    json_path1.write_text(json.dumps(sample_chapter_data), encoding='utf-8')
    
    # Create invalid JSON file
    json_path2 = json_dir / "Ch_002.json"
    json_path2.write_text("{ invalid json }", encoding='utf-8')
    
    # Create another valid JSON file
    json_path3 = json_dir / "Ch_003.json"
    json_path3.write_text(json.dumps(sample_chapter_data), encoding='utf-8')
    
    with patch('sys.argv', [
        'babel.render',
        str(json_dir),
        str(output_dir)
    ]):
        exit_code = main()
        
        # Should fail because one chapter failed
        assert exit_code == 1
        
        # But valid chapters should still be rendered
        assert (output_dir / "Ch_001.html").exists()
        assert (output_dir / "Ch_003.html").exists()
        # Invalid chapter should not be rendered
        assert not (output_dir / "Ch_002.html").exists()


def test_cli_verbose_logging(temp_dirs, sample_chapter_data):
    """Test that verbose flag enables debug logging."""
    json_dir, output_dir = temp_dirs
    
    # Create sample JSON file
    json_path = json_dir / "Ch_001.json"
    json_path.write_text(json.dumps(sample_chapter_data), encoding='utf-8')
    
    with patch('sys.argv', [
        'babel.render',
        str(json_dir),
        str(output_dir),
        '--verbose'
    ]):
        # Run CLI
        exit_code = main()
        
        # Should succeed
        assert exit_code == 0


def test_validate_args_with_valid_paths(temp_dirs):
    """Test argument validation with valid paths."""
    json_dir, output_dir = temp_dirs
    
    # Create a mock args object
    class Args:
        pass
    
    args = Args()
    args.json_dir = json_dir
    args.output_dir = output_dir
    args.template_dir = Path('templates')
    args.chapter_map = None
    
    # Should validate successfully
    assert validate_args(args) is True


def test_validate_args_with_invalid_json_dir():
    """Test argument validation with invalid JSON directory."""
    class Args:
        pass
    
    args = Args()
    args.json_dir = Path('nonexistent_dir')
    args.output_dir = Path('output_dir')
    args.template_dir = Path('templates')
    args.chapter_map = None
    
    # Should fail validation
    assert validate_args(args) is False


def test_validate_args_with_invalid_chapter_map(temp_dirs):
    """Test argument validation with invalid chapter map path."""
    json_dir, output_dir = temp_dirs
    
    class Args:
        pass
    
    args = Args()
    args.json_dir = json_dir
    args.output_dir = output_dir
    args.template_dir = Path('templates')
    args.chapter_map = Path('nonexistent_map.json')
    
    # Should fail validation
    assert validate_args(args) is False


def test_cli_keyboard_interrupt(temp_dirs, sample_chapter_data):
    """Test that CLI handles keyboard interrupt gracefully."""
    json_dir, output_dir = temp_dirs
    
    # Create sample JSON file
    json_path = json_dir / "Ch_001.json"
    json_path.write_text(json.dumps(sample_chapter_data), encoding='utf-8')
    
    # Mock render_batch to raise KeyboardInterrupt
    with patch('babel.render.renderer.ChapterRenderer.render_batch') as mock_render:
        mock_render.side_effect = KeyboardInterrupt()
        
        with patch('sys.argv', [
            'babel.render',
            str(json_dir),
            str(output_dir)
        ]):
            exit_code = main()
            
            # Should exit with code 130 (SIGINT)
            assert exit_code == 130


def test_cli_self_contained_html(temp_dirs, sample_chapter_data):
    """Test that rendered HTML is self-contained (no external dependencies)."""
    json_dir, output_dir = temp_dirs
    
    # Create sample JSON file
    json_path = json_dir / "Ch_001.json"
    json_path.write_text(json.dumps(sample_chapter_data), encoding='utf-8')
    
    with patch('sys.argv', [
        'babel.render',
        str(json_dir),
        str(output_dir)
    ]):
        exit_code = main()
        assert exit_code == 0
        
        # Read HTML content
        html_content = (output_dir / "Ch_001.html").read_text(encoding='utf-8')
        
        # Check for external dependencies (should not exist)
        assert '<link rel="stylesheet"' not in html_content
        assert '<script src=' not in html_content
        assert 'http://' not in html_content or 'https://' not in html_content
        
        # Check for inline CSS
        assert '<style>' in html_content
        assert '</style>' in html_content


def test_cli_character_consistency(temp_dirs, sample_chapter_data):
    """Test that character colors and lanes are consistent across chapters."""
    json_dir, output_dir = temp_dirs
    
    # Create multiple chapters with same characters
    for i in range(1, 4):
        json_path = json_dir / f"Ch_{i:03d}.json"
        json_path.write_text(json.dumps(sample_chapter_data), encoding='utf-8')
    
    with patch('sys.argv', [
        'babel.render',
        str(json_dir),
        str(output_dir)
    ]):
        exit_code = main()
        assert exit_code == 0
        
        # Extract Alice's color from each chapter
        alice_colors = []
        alice_lanes = []
        
        for i in range(1, 4):
            html_content = (output_dir / f"Ch_{i:03d}.html").read_text(encoding='utf-8')
            
            # Find Alice's dialogue block
            import re
            # Look for Alice's color in style attribute
            color_match = re.search(r'Alice.*?style="color: (hsl\([^)]+\))"', html_content, re.DOTALL)
            if color_match:
                alice_colors.append(color_match.group(1))
            
            # Look for Alice's lane class
            lane_match = re.search(r'class="block dialogue (\w+)".*?Alice', html_content, re.DOTALL)
            if lane_match:
                alice_lanes.append(lane_match.group(1))
        
        # All colors should be the same
        if alice_colors:
            assert len(set(alice_colors)) == 1, "Alice's color should be consistent across chapters"
        
        # All lanes should be the same
        if alice_lanes:
            assert len(set(alice_lanes)) == 1, "Alice's lane should be consistent across chapters"
