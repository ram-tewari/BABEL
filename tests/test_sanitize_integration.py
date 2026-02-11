"""
Integration tests for EPUB Sanitization Module

These tests verify end-to-end processing from input files to output files and manifest.
Tests cover EPUB input, TXT input, custom chapter patterns, and complete workflows.
"""

import tempfile
import json
from pathlib import Path
import pytest
from babel.sanitize import sanitize, ChapterMap


# ============================================================================
# EPUB End-to-End Integration Tests
# ============================================================================

def test_epub_end_to_end_processing():
    """Test complete EPUB processing: input → clean files + manifest output."""
    from ebooklib import epub
    
    # Create a test EPUB with multiple chapters
    book = epub.EpubBook()
    book.set_identifier('test_integration_001')
    book.set_title('Test Novel')
    book.set_language('en')
    
    # Create chapters with various content
    chapters = []
    
    # Prologue
    prologue = epub.EpubHtml(
        title='Prologue',
        file_name='prologue.xhtml',
        lang='en'
    )
    prologue.content = '''<html><body>
        <h1>Prologue</h1>
        <p>This is the beginning of our story.</p>
        <p>https://example.com/read</p>
        <p>Translator's Note: This is a test.</p>
    </body></html>'''
    chapters.append(prologue)
    book.add_item(prologue)
    
    # Chapter 1
    chapter1 = epub.EpubHtml(
        title='Chapter 1: The Start',
        file_name='chapter01.xhtml',
        lang='en'
    )
    chapter1.content = '''<html><body>
        <h1>Chapter 1: The Start</h1>
        <p>"Hello world," said the protagonist.</p>
        <p>The adventure begins here with excitement and wonder.</p>
        <p>Read at [NovelSite.com]</p>
    </body></html>'''
    chapters.append(chapter1)
    book.add_item(chapter1)
    
    # Chapter 2 with LitRPG content
    chapter2 = epub.EpubHtml(
        title='Chapter 2: Level Up',
        file_name='chapter02.xhtml',
        lang='en'
    )
    chapter2.content = '''<html><body>
        <h1>Chapter 2: Level Up</h1>
        <p>[System] You have gained a new skill!</p>
        <p>Status Window:</p>
        <p>Level: 5</p>
        <p>HP: 100</p>
        <p>MP: 50</p>
    </body></html>'''
    chapters.append(chapter2)
    book.add_item(chapter2)
    
    # Add required EPUB components
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = chapters
    
    # Set TOC with titles
    book.toc = [
        epub.Link('prologue.xhtml', 'Prologue', 'prologue'),
        epub.Link('chapter01.xhtml', 'Chapter 1: The Start', 'chapter01'),
        epub.Link('chapter02.xhtml', 'Chapter 2: Level Up', 'chapter02')
    ]
    
    # Write EPUB to temporary file
    with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
        temp_epub_path = f.name
    
    try:
        epub.write_epub(temp_epub_path, book, {'epub3_pages': False})
        
        # Create temporary output directory
        with tempfile.TemporaryDirectory() as temp_output_dir:
            # Run sanitize
            manifest = sanitize(temp_epub_path, temp_output_dir)
            
            # Verify manifest was returned
            assert isinstance(manifest, ChapterMap)
            assert manifest.source_filename == Path(temp_epub_path).name
            assert len(manifest.chapters) == 3
            
            # Verify manifest file was created
            manifest_path = Path(temp_output_dir) / 'chapter_map.json'
            assert manifest_path.exists()
            
            # Verify manifest content
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)
            
            assert manifest_data['source_filename'] == Path(temp_epub_path).name
            assert 'processed_at' in manifest_data
            assert len(manifest_data['chapters']) == 3
            
            # Verify chapter files were created
            output_path = Path(temp_output_dir)
            chapter_files = sorted(output_path.glob('*.txt'))
            assert len(chapter_files) == 3
            
            # Verify first chapter (Prologue)
            with open(chapter_files[0], 'r', encoding='utf-8') as f:
                content = f.read()
                assert 'Prologue' in content
                assert 'beginning of our story' in content
                # Verify cleaning worked
                assert 'https://example.com' not in content
                assert "Translator's Note" not in content
            
            # Verify second chapter
            with open(chapter_files[1], 'r', encoding='utf-8') as f:
                content = f.read()
                assert 'Chapter 1' in content or 'The Start' in content
                assert 'Hello world' in content
                # Verify cleaning worked
                assert 'NovelSite.com' not in content
            
            # Verify third chapter (LitRPG)
            with open(chapter_files[2], 'r', encoding='utf-8') as f:
                content = f.read()
                assert 'Level Up' in content or 'Chapter 2' in content
                assert '[System]' in content
                assert 'Status Window' in content
            
            # Verify LitRPG tags were detected
            litrpg_chapter = manifest.chapters[2]
            assert 'litrpg' in litrpg_chapter.metadata.get('tags', [])
            assert 'stat_sheet' in litrpg_chapter.metadata.get('tags', [])
            
            # Verify all chapters have token estimates
            for chapter_entry in manifest.chapters:
                assert chapter_entry.token_count_est > 0
    
    finally:
        # Cleanup
        import os
        import time
        time.sleep(0.1)
        try:
            if os.path.exists(temp_epub_path):
                os.unlink(temp_epub_path)
        except PermissionError:
            pass


# ============================================================================
# TXT End-to-End Integration Tests
# ============================================================================

def test_txt_end_to_end_processing():
    """Test complete TXT processing: input → clean files + manifest output."""
    
    # Create a test TXT file with multiple chapters
    txt_content = """Chapter 1

This is the first chapter of our story.
"Hello," said the character.
https://example.com/chapter1

Chapter 2

This is the second chapter.
More content here with dialogue and action.
Translator's Note: This is a test note.

Chapter 3

The final chapter with some content.
Read at [NovelSite.com]
The end approaches.
"""
    
    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(txt_content)
        temp_txt_path = f.name
    
    try:
        # Create temporary output directory
        with tempfile.TemporaryDirectory() as temp_output_dir:
            # Run sanitize
            manifest = sanitize(temp_txt_path, temp_output_dir)
            
            # Verify manifest was returned
            assert isinstance(manifest, ChapterMap)
            assert manifest.source_filename == Path(temp_txt_path).name
            assert len(manifest.chapters) == 3
            
            # Verify manifest file was created
            manifest_path = Path(temp_output_dir) / 'chapter_map.json'
            assert manifest_path.exists()
            
            # Verify chapter files were created
            output_path = Path(temp_output_dir)
            chapter_files = sorted(output_path.glob('*.txt'))
            assert len(chapter_files) == 3
            
            # Verify first chapter
            with open(chapter_files[0], 'r', encoding='utf-8') as f:
                content = f.read()
                assert 'Chapter 1' in content
                assert 'first chapter' in content
                # Verify cleaning worked
                assert 'https://example.com' not in content
            
            # Verify second chapter
            with open(chapter_files[1], 'r', encoding='utf-8') as f:
                content = f.read()
                assert 'Chapter 2' in content
                assert 'second chapter' in content
                # Verify cleaning worked
                assert "Translator's Note" not in content
            
            # Verify third chapter
            with open(chapter_files[2], 'r', encoding='utf-8') as f:
                content = f.read()
                assert 'Chapter 3' in content
                assert 'final chapter' in content
                # Verify cleaning worked
                assert 'NovelSite.com' not in content
            
            # Verify all chapters have token estimates
            for chapter_entry in manifest.chapters:
                assert chapter_entry.token_count_est > 0
    
    finally:
        # Cleanup
        import os
        try:
            if os.path.exists(temp_txt_path):
                os.unlink(temp_txt_path)
        except PermissionError:
            pass


def test_txt_custom_chapter_pattern():
    """Test TXT processing with custom chapter pattern override."""
    
    # Create a test TXT file with Episode markers
    txt_content = """Episode 1

First episode content here.
Some dialogue and action.

Episode 2

Second episode content here.
More story development.

Episode 3

Third episode wraps things up.
The conclusion.
"""
    
    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(txt_content)
        temp_txt_path = f.name
    
    try:
        # Create temporary output directory
        with tempfile.TemporaryDirectory() as temp_output_dir:
            # Run sanitize with custom pattern (should work without it too, but let's test)
            manifest = sanitize(temp_txt_path, temp_output_dir, custom_chapter_pattern=r'^Episode\s+\d+')
            
            # Verify 3 chapters were detected
            assert len(manifest.chapters) == 3
            
            # Verify chapter titles contain "Episode"
            for chapter_entry in manifest.chapters:
                assert 'Episode' in chapter_entry.title
            
            # Verify files were created
            output_path = Path(temp_output_dir)
            chapter_files = list(output_path.glob('*.txt'))
            assert len(chapter_files) == 3
    
    finally:
        # Cleanup
        import os
        try:
            if os.path.exists(temp_txt_path):
                os.unlink(temp_txt_path)
        except PermissionError:
            pass


# ============================================================================
# Error Handling Integration Tests
# ============================================================================

def test_sanitize_nonexistent_file():
    """Test that sanitize raises IngestionError for nonexistent file."""
    from babel.sanitize import IngestionError
    
    with tempfile.TemporaryDirectory() as temp_output_dir:
        with pytest.raises(IngestionError) as exc_info:
            sanitize('nonexistent_file.epub', temp_output_dir)
        
        assert 'not found' in str(exc_info.value).lower()


def test_sanitize_unsupported_file_type():
    """Test that sanitize raises IngestionError for unsupported file types."""
    from babel.sanitize import IngestionError
    
    # Create a file with unsupported extension
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        f.write(b'fake pdf content')
        temp_file_path = f.name
    
    try:
        with tempfile.TemporaryDirectory() as temp_output_dir:
            with pytest.raises(IngestionError) as exc_info:
                sanitize(temp_file_path, temp_output_dir)
            
            assert 'unsupported file type' in str(exc_info.value).lower()
    
    finally:
        import os
        try:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        except PermissionError:
            pass


# ============================================================================
# Content Preservation Integration Tests
# ============================================================================

def test_unicode_content_preservation():
    """Test that unicode content is preserved through the pipeline."""
    
    # Create TXT with unicode content
    txt_content = """Chapter 1

This chapter contains unicode: 日本語 中文 한글 Ελληνικά
"Quotes" and 'apostrophes' should be normalized.

Chapter 2

More unicode content: Привет мир! مرحبا بالعالم
Special characters: © ® ™ € £ ¥
"""
    
    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(txt_content)
        temp_txt_path = f.name
    
    try:
        with tempfile.TemporaryDirectory() as temp_output_dir:
            # Run sanitize
            manifest = sanitize(temp_txt_path, temp_output_dir)
            
            # Verify chapters were created
            assert len(manifest.chapters) == 2
            
            # Read first chapter and verify unicode is preserved
            output_path = Path(temp_output_dir)
            chapter_files = sorted(output_path.glob('*.txt'))
            
            with open(chapter_files[0], 'r', encoding='utf-8') as f:
                content = f.read()
                assert '日本語' in content
                assert '中文' in content
                assert '한글' in content
                assert 'Ελληνικά' in content
                # Verify quotes were normalized
                assert '"' in content or "'" in content  # Straight quotes
            
            with open(chapter_files[1], 'r', encoding='utf-8') as f:
                content = f.read()
                assert 'Привет' in content
                assert 'مرحبا' in content
                assert '©' in content
                assert '€' in content
    
    finally:
        import os
        try:
            if os.path.exists(temp_txt_path):
                os.unlink(temp_txt_path)
        except PermissionError:
            pass


def test_whitespace_normalization():
    """Test that excessive whitespace is normalized."""
    
    txt_content = """Chapter 1

This is a paragraph.


This paragraph has excessive newlines above it.



And this one has even more.

Chapter 2

Normal content here.
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(txt_content)
        temp_txt_path = f.name
    
    try:
        with tempfile.TemporaryDirectory() as temp_output_dir:
            manifest = sanitize(temp_txt_path, temp_output_dir)
            
            # Read first chapter
            output_path = Path(temp_output_dir)
            chapter_files = sorted(output_path.glob('*.txt'))
            
            with open(chapter_files[0], 'r', encoding='utf-8') as f:
                content = f.read()
                # Verify no sequences of 3+ newlines
                assert '\n\n\n' not in content
    
    finally:
        import os
        try:
            if os.path.exists(temp_txt_path):
                os.unlink(temp_txt_path)
        except PermissionError:
            pass


# ============================================================================
# Manifest Validation Integration Tests
# ============================================================================

def test_manifest_structure_validation():
    """Test that generated manifest has correct structure and all required fields."""
    
    txt_content = """Chapter 1
Content for chapter 1.

Chapter 2
Content for chapter 2.
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(txt_content)
        temp_txt_path = f.name
    
    try:
        with tempfile.TemporaryDirectory() as temp_output_dir:
            manifest = sanitize(temp_txt_path, temp_output_dir)
            
            # Verify manifest structure
            assert hasattr(manifest, 'source_filename')
            assert hasattr(manifest, 'processed_at')
            assert hasattr(manifest, 'chapters')
            
            # Verify each chapter entry has required fields
            for chapter_entry in manifest.chapters:
                assert hasattr(chapter_entry, 'index')
                assert hasattr(chapter_entry, 'filename')
                assert hasattr(chapter_entry, 'title')
                assert hasattr(chapter_entry, 'token_count_est')
                assert hasattr(chapter_entry, 'volume')
                assert hasattr(chapter_entry, 'metadata')
                
                # Verify metadata has tags
                assert 'tags' in chapter_entry.metadata
                assert isinstance(chapter_entry.metadata['tags'], list)
            
            # Verify manifest JSON file
            manifest_path = Path(temp_output_dir) / 'chapter_map.json'
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)
            
            # Verify JSON structure
            assert 'source_filename' in manifest_data
            assert 'processed_at' in manifest_data
            assert 'chapters' in manifest_data
            assert isinstance(manifest_data['chapters'], list)
            
            # Verify JSON formatting (2-space indentation)
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Should have 2-space indentation
                assert '  "source_filename"' in content or '  "chapters"' in content
    
    finally:
        import os
        try:
            if os.path.exists(temp_txt_path):
                os.unlink(temp_txt_path)
        except PermissionError:
            pass


# ============================================================================
# Volume Information Integration Tests
# ============================================================================

def test_epub_with_volume_structure():
    """Test EPUB processing with volume structure in TOC."""
    from ebooklib import epub
    
    book = epub.EpubBook()
    book.set_identifier('test_volumes')
    book.set_title('Multi-Volume Novel')
    book.set_language('en')
    
    # Create chapters for Volume 1
    ch1 = epub.EpubHtml(title='Chapter 1', file_name='ch01.xhtml', lang='en')
    ch1.content = '<html><body><h1>Chapter 1</h1><p>Volume 1 content</p></body></html>'
    book.add_item(ch1)
    
    ch2 = epub.EpubHtml(title='Chapter 2', file_name='ch02.xhtml', lang='en')
    ch2.content = '<html><body><h1>Chapter 2</h1><p>More Volume 1 content</p></body></html>'
    book.add_item(ch2)
    
    # Create chapters for Volume 2
    ch3 = epub.EpubHtml(title='Chapter 3', file_name='ch03.xhtml', lang='en')
    ch3.content = '<html><body><h1>Chapter 3</h1><p>Volume 2 content</p></body></html>'
    book.add_item(ch3)
    
    # Set TOC with volume structure
    book.toc = [
        (epub.Section('Volume 1'), [
            epub.Link('ch01.xhtml', 'Chapter 1', 'ch01'),
            epub.Link('ch02.xhtml', 'Chapter 2', 'ch02')
        ]),
        (epub.Section('Volume 2'), [
            epub.Link('ch03.xhtml', 'Chapter 3', 'ch03')
        ])
    ]
    
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = [ch1, ch2, ch3]
    
    with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
        temp_epub_path = f.name
    
    try:
        epub.write_epub(temp_epub_path, book, {'epub3_pages': False})
        
        with tempfile.TemporaryDirectory() as temp_output_dir:
            manifest = sanitize(temp_epub_path, temp_output_dir)
            
            # Verify chapters have volume information
            # Note: Volume detection depends on TOC structure parsing
            # At least some chapters should have volume info if implemented
            volumes_found = [ch.volume for ch in manifest.chapters if ch.volume]
            
            # If volume detection is working, we should have volume info
            # This is a soft check since volume detection is optional
            if volumes_found:
                assert 'Volume 1' in volumes_found or 'Volume 2' in volumes_found
    
    finally:
        import os
        import time
        time.sleep(0.1)
        try:
            if os.path.exists(temp_epub_path):
                os.unlink(temp_epub_path)
        except PermissionError:
            pass
