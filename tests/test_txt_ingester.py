"""
Unit tests for TXTIngester class

These tests verify specific examples and edge cases for TXT file ingestion.
"""

import pytest
import tempfile
import os
from pathlib import Path
from babel.sanitize import TXTIngester, IngestionError, SafetyLimitExceeded, RawChapter


class TestTXTIngester:
    """Test suite for TXTIngester class."""
    
    def test_extract_chapters_with_chapter_markers(self):
        """Test extraction with standard 'Chapter N' markers."""
        content = """Chapter 1: The Beginning

This is the first chapter content.
It has multiple lines.

Chapter 2: The Middle

This is the second chapter content.

Chapter 3: The End

This is the third chapter content."""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        try:
            chapters = TXTIngester.extract_chapters(temp_path)
            
            assert len(chapters) == 3
            assert chapters[0].index == 0
            assert chapters[0].title == "Chapter 1: The Beginning"
            assert "first chapter content" in chapters[0].content
            
            assert chapters[1].index == 1
            assert chapters[1].title == "Chapter 2: The Middle"
            assert "second chapter content" in chapters[1].content
            
            assert chapters[2].index == 2
            assert chapters[2].title == "Chapter 3: The End"
            assert "third chapter content" in chapters[2].content
        finally:
            os.unlink(temp_path)
    
    def test_extract_chapters_with_ch_dot_markers(self):
        """Test extraction with 'Ch.' markers."""
        content = """Ch. 1 - First

Content of chapter 1.

Ch. 2 - Second

Content of chapter 2."""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        try:
            chapters = TXTIngester.extract_chapters(temp_path)
            
            assert len(chapters) == 2
            assert chapters[0].title == "Ch. 1 - First"
            assert chapters[1].title == "Ch. 2 - Second"
        finally:
            os.unlink(temp_path)
    
    def test_extract_chapters_with_episode_markers(self):
        """Test extraction with 'Episode' markers."""
        content = """Episode 1

First episode content.

Episode 2

Second episode content."""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        try:
            chapters = TXTIngester.extract_chapters(temp_path)
            
            assert len(chapters) == 2
            assert "Episode 1" in chapters[0].title
            assert "Episode 2" in chapters[1].title
        finally:
            os.unlink(temp_path)
    
    def test_extract_chapters_with_standalone_numbers(self):
        """Test extraction with standalone sequential numbers."""
        content = """1

First chapter content.

2

Second chapter content.

3

Third chapter content."""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        try:
            chapters = TXTIngester.extract_chapters(temp_path)
            
            assert len(chapters) == 3
            assert chapters[0].index == 0
            assert chapters[1].index == 1
            assert chapters[2].index == 2
        finally:
            os.unlink(temp_path)
    
    def test_extract_chapters_no_markers_single_chapter(self):
        """Test that file with no markers is treated as single chapter."""
        content = """This is a story without chapter markers.

It just has regular text content.
Multiple paragraphs.

But no chapter divisions."""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        try:
            chapters = TXTIngester.extract_chapters(temp_path)
            
            assert len(chapters) == 1
            assert chapters[0].index == 0
            assert chapters[0].title == "Chapter 1"
            assert "story without chapter markers" in chapters[0].content
        finally:
            os.unlink(temp_path)
    
    def test_extract_chapters_with_custom_pattern(self):
        """Test extraction with custom regex pattern."""
        content = """Part One

Content of part one.

Part Two

Content of part two."""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        try:
            chapters = TXTIngester.extract_chapters(temp_path, custom_pattern=r'^Part \w+')
            
            assert len(chapters) == 2
            assert "Part One" in chapters[0].title
            assert "Part Two" in chapters[1].title
        finally:
            os.unlink(temp_path)
    
    def test_extract_chapters_utf8_encoding(self):
        """Test reading UTF-8 encoded file with special characters."""
        content = """Chapter 1: 日本語

Content with unicode: café, naïve, 中文

Chapter 2: More Unicode

More content."""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        try:
            chapters = TXTIngester.extract_chapters(temp_path)
            
            assert len(chapters) == 2
            assert "日本語" in chapters[0].title
            assert "café" in chapters[0].content
        finally:
            os.unlink(temp_path)
    
    def test_extract_chapters_latin1_fallback(self):
        """Test fallback to latin-1 encoding."""
        # Create file with latin-1 encoding
        content = "Chapter 1\n\nContent with special chars: café"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='latin-1') as f:
            f.write(content)
            temp_path = f.name
        
        try:
            chapters = TXTIngester.extract_chapters(temp_path)
            
            assert len(chapters) == 1
            assert "Chapter 1" in chapters[0].title
        finally:
            os.unlink(temp_path)
    
    def test_extract_chapters_file_not_found(self):
        """Test that missing file raises IngestionError."""
        with pytest.raises(IngestionError, match="Input file not found"):
            TXTIngester.extract_chapters("nonexistent_file.txt")
    
    def test_validate_chapter_size_within_limit(self):
        """Test that normal-sized chapters pass validation."""
        chapter = RawChapter(
            index=0,
            title="Test Chapter",
            content="A" * 10000,  # 10k chars = ~2.5k tokens
            source_location="test.txt"
        )
        
        # Should not raise
        TXTIngester._validate_chapter_size(chapter)
    
    def test_validate_chapter_size_exceeds_limit(self):
        """Test that oversized chapters raise SafetyLimitExceeded warning."""
        # Create chapter with >50k tokens (>200k chars)
        chapter = RawChapter(
            index=0,
            title="Huge Chapter",
            content="A" * 250000,  # 250k chars = ~62.5k tokens
            source_location="test.txt"
        )
        
        with pytest.warns(SafetyLimitExceeded, match="exceeds safety limit"):
            TXTIngester._validate_chapter_size(chapter)
    
    def test_detect_chapter_boundaries_mixed_patterns(self):
        """Test detection with mixed chapter marker styles."""
        content = """Chapter 1

Content.

Ch. 2

More content.

Episode 3

Even more content."""
        
        boundaries = TXTIngester._detect_chapter_boundaries(content)
        
        # Should find all three chapter markers
        assert len(boundaries) == 3
    
    def test_detect_standalone_numbers_sequential(self):
        """Test standalone number detection with sequential numbers."""
        content = """1

First.

2

Second.

3

Third."""
        
        boundaries = TXTIngester._detect_standalone_numbers(content)
        
        assert len(boundaries) == 3
    
    def test_detect_standalone_numbers_non_sequential(self):
        """Test that non-sequential numbers are not detected."""
        content = """1

First.

5

Not sequential.

10

Also not sequential."""
        
        boundaries = TXTIngester._detect_standalone_numbers(content)
        
        # Should return empty list because we need at least 2 sequential numbers
        # and only "1" is found before the sequence breaks
        assert len(boundaries) == 0
    
    def test_detect_standalone_numbers_with_text(self):
        """Test that numbers with other text are not detected."""
        content = """1. Introduction

First.

2. Chapter Two

Second."""
        
        boundaries = TXTIngester._detect_standalone_numbers(content)
        
        # Should not detect these as they have additional text
        assert len(boundaries) == 0


    def test_extract_chapters_mixed_markers_comprehensive(self):
        """Test file with no chapter markers (single chapter output) - comprehensive test."""
        content = """Chapter 1: The Start

First chapter with standard marker.

Ch. 2 - Short Form

Second chapter with abbreviated marker.

Episode 3

Third chapter with episode marker.

Ch 4

Fourth chapter without period.

Ep. 5

Fifth chapter with abbreviated episode."""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        try:
            chapters = TXTIngester.extract_chapters(temp_path)
            
            # Should detect all 5 chapters with different marker styles
            assert len(chapters) == 5
            assert "Chapter 1" in chapters[0].title
            assert "Ch. 2" in chapters[1].title
            assert "Episode 3" in chapters[2].title
            assert "Ch 4" in chapters[3].title
            assert "Ep. 5" in chapters[4].title
        finally:
            os.unlink(temp_path)
    
    def test_extract_chapters_empty_file(self):
        """Test that empty file is treated as single empty chapter."""
        content = ""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        try:
            chapters = TXTIngester.extract_chapters(temp_path)
            
            # Should return single chapter with empty content
            assert len(chapters) == 1
            assert chapters[0].index == 0
            assert chapters[0].title == "Chapter 1"
            assert chapters[0].content == ""
        finally:
            os.unlink(temp_path)
    
    def test_extract_chapters_whitespace_only(self):
        """Test that file with only whitespace is treated as single chapter."""
        content = "\n\n   \n\t\n  \n"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        try:
            chapters = TXTIngester.extract_chapters(temp_path)
            
            # Should return single chapter
            assert len(chapters) == 1
            assert chapters[0].index == 0
            # Content should be empty after stripping
            assert chapters[0].content.strip() == ""
        finally:
            os.unlink(temp_path)
    
    def test_extract_chapters_unreadable_encoding(self):
        """Test handling of file with unreadable encoding."""
        # Create a file with binary content that's not valid text
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            # Write invalid UTF-8 bytes
            f.write(b'\x80\x81\x82\x83\x84\x85')
            temp_path = f.name
        
        try:
            # Should fall back to latin-1 and succeed
            chapters = TXTIngester.extract_chapters(temp_path)
            
            # Should return at least one chapter (latin-1 can read anything)
            assert len(chapters) >= 1
        finally:
            os.unlink(temp_path)
    
    def test_extract_chapters_very_long_title(self):
        """Test chapter with extremely long title line."""
        long_title = "Chapter 1: " + "A" * 500 + " - The Beginning"
        content = f"""{long_title}

This is the chapter content."""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        try:
            chapters = TXTIngester.extract_chapters(temp_path)
            
            assert len(chapters) == 1
            # Title should be the full first line
            assert len(chapters[0].title) > 500
            assert "Chapter 1" in chapters[0].title
        finally:
            os.unlink(temp_path)
    
    def test_extract_chapters_chapter_marker_in_content(self):
        """Test that chapter markers within content don't create false boundaries."""
        content = """Chapter 1

This chapter mentions Chapter 2 in the text.
Someone says "Chapter 3 will be exciting!"

Chapter 2

This is the actual second chapter."""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        try:
            chapters = TXTIngester.extract_chapters(temp_path)
            
            # Should only detect 2 chapters (markers at start of line)
            assert len(chapters) == 2
            assert "Chapter 1" in chapters[0].title
            assert "Chapter 2" in chapters[1].title
            # First chapter should contain the mentions
            assert "mentions Chapter 2" in chapters[0].content
        finally:
            os.unlink(temp_path)
    
    def test_extract_chapters_case_insensitive_markers(self):
        """Test that chapter markers are case-insensitive."""
        content = """CHAPTER 1

First chapter in uppercase.

chapter 2

Second chapter in lowercase.

ChApTeR 3

Third chapter in mixed case."""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        try:
            chapters = TXTIngester.extract_chapters(temp_path)
            
            # Should detect all 3 chapters regardless of case
            assert len(chapters) == 3
            assert "CHAPTER 1" in chapters[0].title
            assert "chapter 2" in chapters[1].title
            assert "ChApTeR 3" in chapters[2].title
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
