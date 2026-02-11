"""
Unit tests for FileWriter class

Tests cover filename generation, directory creation, file writing,
and error handling scenarios.
"""

import tempfile
import os
from pathlib import Path
import pytest
from babel.sanitize import FileWriter, CleanChapter


# ============================================================================
# Filename Generation Tests
# ============================================================================

def test_generate_filename_basic():
    """Test basic filename generation with simple title."""
    filename = FileWriter._generate_filename(0, "Prologue")
    assert filename == "000_prologue.txt"


def test_generate_filename_with_spaces():
    """Test filename generation with spaces in title."""
    filename = FileWriter._generate_filename(1, "Chapter 1 The Beginning")
    assert filename == "001_chapter_1_the_beginning.txt"


def test_generate_filename_with_special_chars():
    """Test filename generation removes special characters."""
    filename = FileWriter._generate_filename(42, "Chapter 42: The Answer!")
    assert filename == "042_chapter_42_the_answer.txt"


def test_generate_filename_with_complex_title():
    """Test filename generation with complex title containing various special chars."""
    filename = FileWriter._generate_filename(10, "Chapter 10.5 (Side Story) - Part A")
    # Hyphens are preserved, parentheses removed, spaces become underscores
    assert filename == "010_chapter_105_side_story_-_part_a.txt"


def test_generate_filename_zero_padding():
    """Test that index is zero-padded to 3 digits."""
    assert FileWriter._generate_filename(0, "Test") == "000_test.txt"
    assert FileWriter._generate_filename(9, "Test") == "009_test.txt"
    assert FileWriter._generate_filename(99, "Test") == "099_test.txt"
    assert FileWriter._generate_filename(999, "Test") == "999_test.txt"


def test_generate_filename_long_title():
    """Test that very long titles are truncated."""
    long_title = "A" * 100
    filename = FileWriter._generate_filename(1, long_title)
    
    # Should be truncated to 50 chars + index + extension
    # Format: 001_{50 chars}.txt
    assert len(filename) <= 58  # 3 (index) + 1 (_) + 50 (title) + 4 (.txt)
    assert filename.startswith("001_")
    assert filename.endswith(".txt")


def test_generate_filename_empty_title():
    """Test filename generation with empty title."""
    filename = FileWriter._generate_filename(5, "")
    assert filename == "005_chapter_6.txt"  # Falls back to generic name


def test_generate_filename_only_special_chars():
    """Test filename generation when title is only special characters."""
    filename = FileWriter._generate_filename(3, "!@#$%^&*()")
    assert filename == "003_chapter_4.txt"  # Falls back to generic name


def test_generate_filename_trailing_underscores():
    """Test that trailing underscores/hyphens are removed."""
    filename = FileWriter._generate_filename(1, "Chapter 1:")
    assert not filename.endswith("_.txt")
    assert filename == "001_chapter_1.txt"


def test_generate_filename_unicode_chars():
    """Test filename generation with unicode characters."""
    filename = FileWriter._generate_filename(1, "Chapter 1: 日本語")
    # Unicode chars should be removed, leaving only ASCII
    assert filename == "001_chapter_1.txt"


# ============================================================================
# Directory Creation Tests
# ============================================================================

def test_ensure_directory_exists_creates_new():
    """Test that _ensure_directory_exists creates a new directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = Path(tmpdir) / "new_directory"
        
        # Directory should not exist yet
        assert not test_path.exists()
        
        # Create directory
        FileWriter._ensure_directory_exists(test_path)
        
        # Directory should now exist
        assert test_path.exists()
        assert test_path.is_dir()


def test_ensure_directory_exists_nested():
    """Test that _ensure_directory_exists creates nested directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = Path(tmpdir) / "level1" / "level2" / "level3"
        
        # Create nested directories
        FileWriter._ensure_directory_exists(test_path)
        
        # All levels should exist
        assert test_path.exists()
        assert test_path.is_dir()


def test_ensure_directory_exists_already_exists():
    """Test that _ensure_directory_exists handles existing directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = Path(tmpdir)
        
        # Directory already exists
        assert test_path.exists()
        
        # Should not raise error
        FileWriter._ensure_directory_exists(test_path)
        
        # Directory should still exist
        assert test_path.exists()


def test_ensure_directory_exists_invalid_path():
    """Test that _ensure_directory_exists raises IOError for invalid paths."""
    # Try to create directory in a location that doesn't allow it
    # On most systems, trying to create a directory with null bytes will fail
    invalid_path = Path("\0invalid")
    
    with pytest.raises(IOError) as exc_info:
        FileWriter._ensure_directory_exists(invalid_path)
    
    assert "Cannot create output directory" in str(exc_info.value)


# ============================================================================
# File Writing Tests
# ============================================================================

def test_write_chapters_basic():
    """Test basic chapter writing functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        # Create test chapters
        chapters = [
            CleanChapter(
                index=0,
                title="Prologue",
                content="This is the prologue content.",
                token_count_est=100,
                filename="000_prologue.txt"
            ),
            CleanChapter(
                index=1,
                title="Chapter 1",
                content="This is chapter 1 content.",
                token_count_est=150,
                filename="001_chapter_1.txt"
            )
        ]
        
        # Write chapters
        FileWriter.write_chapters(chapters, output_dir)
        
        # Verify files were created
        assert (output_dir / "000_prologue.txt").exists()
        assert (output_dir / "001_chapter_1.txt").exists()
        
        # Verify content
        with open(output_dir / "000_prologue.txt", 'r', encoding='utf-8') as f:
            assert f.read() == "This is the prologue content."
        
        with open(output_dir / "001_chapter_1.txt", 'r', encoding='utf-8') as f:
            assert f.read() == "This is chapter 1 content."


def test_write_chapters_creates_directory():
    """Test that write_chapters creates output directory if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "new_output_dir"
        
        # Directory should not exist yet
        assert not output_dir.exists()
        
        # Create test chapter
        chapters = [
            CleanChapter(
                index=0,
                title="Test",
                content="Test content",
                token_count_est=50,
                filename="000_test.txt"
            )
        ]
        
        # Write chapters
        FileWriter.write_chapters(chapters, output_dir)
        
        # Directory should be created
        assert output_dir.exists()
        assert (output_dir / "000_test.txt").exists()


def test_write_chapters_overwrites_existing(caplog):
    """Test that write_chapters overwrites existing files with warning."""
    import logging
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        # Create existing file
        existing_file = output_dir / "000_test.txt"
        with open(existing_file, 'w', encoding='utf-8') as f:
            f.write("Old content")
        
        # Create test chapter with same filename
        chapters = [
            CleanChapter(
                index=0,
                title="Test",
                content="New content",
                token_count_est=50,
                filename="000_test.txt"
            )
        ]
        
        # Write chapters (should overwrite)
        with caplog.at_level(logging.WARNING):
            FileWriter.write_chapters(chapters, output_dir)
        
        # Verify warning was logged
        assert any("Overwriting existing file" in record.message for record in caplog.records)
        
        # Verify file was overwritten
        with open(existing_file, 'r', encoding='utf-8') as f:
            assert f.read() == "New content"


def test_write_chapters_empty_list():
    """Test that write_chapters handles empty chapter list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        # Write empty list
        FileWriter.write_chapters([], output_dir)
        
        # Directory should still be created
        assert output_dir.exists()


def test_write_chapters_with_unicode_content():
    """Test writing chapters with unicode content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        # Create chapter with unicode content
        chapters = [
            CleanChapter(
                index=0,
                title="Test",
                content="Unicode content: 日本語 中文 한글 Ελληνικά",
                token_count_est=100,
                filename="000_test.txt"
            )
        ]
        
        # Write chapters
        FileWriter.write_chapters(chapters, output_dir)
        
        # Verify content is preserved
        with open(output_dir / "000_test.txt", 'r', encoding='utf-8') as f:
            content = f.read()
            assert "日本語" in content
            assert "中文" in content
            assert "한글" in content
            assert "Ελληνικά" in content


def test_write_chapters_with_volume_and_tags():
    """Test writing chapters with volume and tag metadata."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        # Create chapter with volume and tags
        chapters = [
            CleanChapter(
                index=0,
                title="Chapter 1",
                content="Content with LitRPG elements",
                token_count_est=100,
                filename="000_chapter_1.txt",
                volume="Volume 1",
                tags=["litrpg", "stat_sheet"]
            )
        ]
        
        # Write chapters (metadata is in CleanChapter but not written to file)
        FileWriter.write_chapters(chapters, output_dir)
        
        # Verify file was created
        assert (output_dir / "000_chapter_1.txt").exists()
        
        # Verify content (metadata is not written to the text file itself)
        with open(output_dir / "000_chapter_1.txt", 'r', encoding='utf-8') as f:
            assert f.read() == "Content with LitRPG elements"


def test_write_chapters_io_error():
    """Test that write_chapters raises IOError when write fails."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        # Create a file where we want to write a directory
        conflict_path = output_dir / "conflict"
        with open(conflict_path, 'w') as f:
            f.write("blocking file")
        
        # Try to write to a subdirectory of the file (should fail)
        chapters = [
            CleanChapter(
                index=0,
                title="Test",
                content="Test content",
                token_count_est=50,
                filename="test.txt"
            )
        ]
        
        # This should raise IOError because we can't create directory
        invalid_output_dir = conflict_path / "subdir"
        with pytest.raises(IOError) as exc_info:
            FileWriter.write_chapters(chapters, invalid_output_dir)
        
        assert "Cannot create output directory" in str(exc_info.value)


def test_write_chapters_large_content():
    """Test writing chapters with large content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        # Create chapter with large content (simulate a long chapter)
        large_content = "A" * 100000  # 100k characters
        
        chapters = [
            CleanChapter(
                index=0,
                title="Large Chapter",
                content=large_content,
                token_count_est=25000,
                filename="000_large_chapter.txt"
            )
        ]
        
        # Write chapters
        FileWriter.write_chapters(chapters, output_dir)
        
        # Verify file was created and content is correct
        with open(output_dir / "000_large_chapter.txt", 'r', encoding='utf-8') as f:
            content = f.read()
            assert len(content) == 100000
            assert content == large_content


# ============================================================================
# Edge Case Tests (Task 6.4)
# ============================================================================

def test_overwrite_existing_file_multiple_times(caplog):
    """Test overwriting the same file multiple times logs warnings each time."""
    import logging
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        # Create initial file
        test_file = output_dir / "000_test.txt"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("Initial content")
        
        # Overwrite multiple times
        for i in range(3):
            chapters = [
                CleanChapter(
                    index=0,
                    title="Test",
                    content=f"Content version {i}",
                    token_count_est=50,
                    filename="000_test.txt"
                )
            ]
            
            with caplog.at_level(logging.WARNING):
                FileWriter.write_chapters(chapters, output_dir)
            
            # Verify warning was logged
            assert any("Overwriting existing file" in record.message for record in caplog.records)
            
            # Verify content was updated
            with open(test_file, 'r', encoding='utf-8') as f:
                assert f.read() == f"Content version {i}"
            
            caplog.clear()


def test_write_permission_error_readonly_directory():
    """Test that write_chapters raises IOError when directory is read-only."""
    import sys
    
    # Skip on Windows as read-only directories behave differently
    if sys.platform == "win32":
        pytest.skip("Read-only directory test not applicable on Windows")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "readonly_dir"
        output_dir.mkdir()
        
        # Make directory read-only (remove write permissions)
        os.chmod(output_dir, 0o444)
        
        try:
            chapters = [
                CleanChapter(
                    index=0,
                    title="Test",
                    content="Test content",
                    token_count_est=50,
                    filename="000_test.txt"
                )
            ]
            
            # Should raise IOError due to permission denied
            with pytest.raises(IOError) as exc_info:
                FileWriter.write_chapters(chapters, output_dir)
            
            assert "Cannot write file" in str(exc_info.value)
        
        finally:
            # Restore permissions for cleanup
            os.chmod(output_dir, 0o755)


def test_filename_generation_with_path_separators():
    """Test filename generation removes path separators to prevent directory traversal."""
    # Test with forward slash
    filename = FileWriter._generate_filename(1, "Chapter 1/Part A")
    assert "/" not in filename
    assert filename == "001_chapter_1part_a.txt"
    
    # Test with backslash
    filename = FileWriter._generate_filename(2, "Chapter 2\\Part B")
    assert "\\" not in filename
    assert filename == "002_chapter_2part_b.txt"
    
    # Test with multiple separators
    filename = FileWriter._generate_filename(3, "Vol/1/Ch/3")
    assert "/" not in filename
    assert filename == "003_vol1ch3.txt"


def test_filename_generation_with_dots():
    """Test filename generation handles dots correctly."""
    # Single dot
    filename = FileWriter._generate_filename(1, "Chapter 1.5")
    assert filename == "001_chapter_15.txt"
    
    # Multiple dots
    filename = FileWriter._generate_filename(2, "Chapter 2.5.1")
    assert filename == "002_chapter_251.txt"
    
    # Leading dot
    filename = FileWriter._generate_filename(3, ".hidden")
    assert filename == "003_hidden.txt"
    
    # Trailing dot
    filename = FileWriter._generate_filename(4, "Chapter 4.")
    assert filename == "004_chapter_4.txt"


def test_filename_generation_with_mixed_special_chars():
    """Test filename generation with various combinations of special characters."""
    test_cases = [
        (1, "Chapter #1: @Home!", "001_chapter_1_home.txt"),
        (2, "Episode $5 & Part %2", "002_episode_5__part_2.txt"),
        (10, "Ch. 10 (Part A) [Side Story]", "010_ch_10_part_a_side_story.txt"),
        (3, "Chapter 3 <The Beginning>", "003_chapter_3_the_beginning.txt"),
        (7, "Ch 7 | The End?", "007_ch_7__the_end.txt"),
    ]
    
    for index, title, expected in test_cases:
        filename = FileWriter._generate_filename(index, title)
        assert filename == expected, f"Failed for title: {title}, got {filename}, expected {expected}"


def test_filename_generation_with_whitespace_variations():
    """Test filename generation handles various whitespace patterns."""
    # Multiple spaces - each space becomes an underscore
    filename = FileWriter._generate_filename(1, "Chapter    1")
    assert filename == "001_chapter____1.txt"
    
    # Tabs - tabs are removed by the regex (not alphanumeric)
    filename = FileWriter._generate_filename(2, "Chapter\t2")
    assert filename == "002_chapter2.txt"
    
    # Leading/trailing whitespace - should be stripped
    filename = FileWriter._generate_filename(3, "  Chapter 3  ")
    assert filename == "003_chapter_3.txt"
    
    # Mixed whitespace - tabs and newlines are removed, spaces become underscores
    filename = FileWriter._generate_filename(4, "Chapter \t 4 \n Test")
    # Tabs and newlines are removed by the regex, spaces become underscores
    assert "_" in filename
    assert "chapter" in filename
    assert "4" in filename
    assert "test" in filename


def test_filename_generation_with_emoji():
    """Test filename generation removes emoji characters."""
    filename = FileWriter._generate_filename(1, "Chapter 1 😀 🎉")
    assert "😀" not in filename
    assert "🎉" not in filename
    assert filename == "001_chapter_1.txt"


def test_filename_generation_with_accented_characters():
    """Test filename generation handles accented/diacritical characters."""
    # These should be removed as they're not ASCII alphanumeric
    filename = FileWriter._generate_filename(1, "Café Résumé")
    assert filename == "001_caf_rsum.txt"
    
    filename = FileWriter._generate_filename(2, "Naïve Façade")
    assert filename == "002_nave_faade.txt"


def test_filename_generation_with_numbers_only():
    """Test filename generation when title is only numbers."""
    filename = FileWriter._generate_filename(1, "12345")
    assert filename == "001_12345.txt"


def test_filename_generation_with_hyphens_and_underscores():
    """Test that hyphens and underscores are preserved in filenames."""
    filename = FileWriter._generate_filename(1, "Chapter-1_Part-A")
    assert filename == "001_chapter-1_part-a.txt"
    
    # Multiple consecutive hyphens/underscores
    filename = FileWriter._generate_filename(2, "Chapter--2__Part--B")
    assert filename == "002_chapter--2__part--b.txt"


def test_write_chapters_with_newlines_in_content():
    """Test writing chapters with various newline patterns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        # Test different newline styles
        chapters = [
            CleanChapter(
                index=0,
                title="Unix Style",
                content="Line 1\nLine 2\nLine 3",
                token_count_est=50,
                filename="000_unix_style.txt"
            ),
            CleanChapter(
                index=1,
                title="Windows Style",
                content="Line 1\r\nLine 2\r\nLine 3",
                token_count_est=50,
                filename="001_windows_style.txt"
            ),
            CleanChapter(
                index=2,
                title="Mixed Style",
                content="Line 1\nLine 2\r\nLine 3\n",
                token_count_est=50,
                filename="002_mixed_style.txt"
            )
        ]
        
        # Write chapters
        FileWriter.write_chapters(chapters, output_dir)
        
        # Verify all files were created
        assert (output_dir / "000_unix_style.txt").exists()
        assert (output_dir / "001_windows_style.txt").exists()
        assert (output_dir / "002_mixed_style.txt").exists()
        
        # Verify content is preserved exactly
        with open(output_dir / "000_unix_style.txt", 'r', encoding='utf-8') as f:
            assert f.read() == "Line 1\nLine 2\nLine 3"


def test_write_chapters_with_empty_content():
    """Test writing chapters with empty or whitespace-only content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        chapters = [
            CleanChapter(
                index=0,
                title="Empty",
                content="",
                token_count_est=0,
                filename="000_empty.txt"
            ),
            CleanChapter(
                index=1,
                title="Whitespace Only",
                content="   \n\n   ",
                token_count_est=0,
                filename="001_whitespace_only.txt"
            )
        ]
        
        # Write chapters
        FileWriter.write_chapters(chapters, output_dir)
        
        # Verify files were created
        assert (output_dir / "000_empty.txt").exists()
        assert (output_dir / "001_whitespace_only.txt").exists()
        
        # Verify content
        with open(output_dir / "000_empty.txt", 'r', encoding='utf-8') as f:
            assert f.read() == ""
        
        with open(output_dir / "001_whitespace_only.txt", 'r', encoding='utf-8') as f:
            assert f.read() == "   \n\n   "


def test_filename_generation_case_sensitivity():
    """Test that filename generation produces consistent lowercase output."""
    # Mixed case input
    filename = FileWriter._generate_filename(1, "ChApTeR 1: ThE BeGiNnInG")
    assert filename == "001_chapter_1_the_beginning.txt"
    assert filename.islower() or not filename[4:-4].replace('_', '').replace('-', '').isalpha()
    
    # All uppercase
    filename = FileWriter._generate_filename(2, "CHAPTER 2")
    assert filename == "002_chapter_2.txt"


def test_write_chapters_concurrent_filenames():
    """Test writing multiple chapters with similar titles that could collide."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        # Create chapters with titles that sanitize to similar names
        chapters = [
            CleanChapter(
                index=0,
                title="Chapter 1!",
                content="Content 1",
                token_count_est=50,
                filename=FileWriter._generate_filename(0, "Chapter 1!")
            ),
            CleanChapter(
                index=1,
                title="Chapter 1?",
                content="Content 2",
                token_count_est=50,
                filename=FileWriter._generate_filename(1, "Chapter 1?")
            ),
            CleanChapter(
                index=2,
                title="Chapter 1.",
                content="Content 3",
                token_count_est=50,
                filename=FileWriter._generate_filename(2, "Chapter 1.")
            )
        ]
        
        # Write chapters
        FileWriter.write_chapters(chapters, output_dir)
        
        # All should have unique filenames due to different indices
        assert (output_dir / "000_chapter_1.txt").exists()
        assert (output_dir / "001_chapter_1.txt").exists()
        assert (output_dir / "002_chapter_1.txt").exists()
        
        # Verify each has correct content
        with open(output_dir / "000_chapter_1.txt", 'r') as f:
            assert f.read() == "Content 1"
        with open(output_dir / "001_chapter_1.txt", 'r') as f:
            assert f.read() == "Content 2"
        with open(output_dir / "002_chapter_1.txt", 'r') as f:
            assert f.read() == "Content 3"


# ============================================================================
# Integration Tests
# ============================================================================

def test_filename_generation_integration():
    """Test that generated filenames work correctly with write_chapters."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        # Generate filenames using the _generate_filename method
        titles = [
            "Prologue",
            "Chapter 1: The Beginning",
            "Chapter 2: The Journey",
            "Chapter 10.5 (Side Story)"
        ]
        
        chapters = []
        for i, title in enumerate(titles):
            filename = FileWriter._generate_filename(i, title)
            chapters.append(
                CleanChapter(
                    index=i,
                    title=title,
                    content=f"Content for {title}",
                    token_count_est=100,
                    filename=filename
                )
            )
        
        # Write chapters
        FileWriter.write_chapters(chapters, output_dir)
        
        # Verify all files were created with correct names
        assert (output_dir / "000_prologue.txt").exists()
        assert (output_dir / "001_chapter_1_the_beginning.txt").exists()
        assert (output_dir / "002_chapter_2_the_journey.txt").exists()
        assert (output_dir / "003_chapter_105_side_story.txt").exists()
