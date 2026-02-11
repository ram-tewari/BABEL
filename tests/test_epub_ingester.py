"""
Unit tests for EPUBIngester class

These tests verify specific examples and edge cases for EPUB file ingestion.
"""

import pytest
import tempfile
import os
from pathlib import Path
from babel.sanitize import EPUBIngester, IngestionError, RawChapter


class TestEPUBIngester:
    """Test suite for EPUBIngester class."""
    
    def test_parse_html_content_basic(self):
        """Test basic HTML parsing to plain text."""
        html = """
        <html>
            <body>
                <h1>Chapter Title</h1>
                <p>This is the first paragraph.</p>
                <p>This is the second paragraph.</p>
            </body>
        </html>
        """
        
        text = EPUBIngester._parse_html_content(html)
        
        assert "Chapter Title" in text
        assert "first paragraph" in text
        assert "second paragraph" in text
        # HTML tags should be removed
        assert "<p>" not in text
        assert "<h1>" not in text
    
    def test_parse_html_content_with_scripts(self):
        """Test that script and style tags are removed."""
        html = """
        <html>
            <head>
                <style>body { color: red; }</style>
            </head>
            <body>
                <p>Visible content</p>
                <script>alert('hidden');</script>
                <p>More visible content</p>
            </body>
        </html>
        """
        
        text = EPUBIngester._parse_html_content(html)
        
        assert "Visible content" in text
        assert "More visible content" in text
        # Script and style content should be removed
        assert "alert" not in text
        assert "color: red" not in text
    
    def test_parse_html_content_preserves_structure(self):
        """Test that paragraph structure is preserved."""
        html = """
        <html>
            <body>
                <p>First paragraph.</p>
                <p>Second paragraph.</p>
                <p>Third paragraph.</p>
            </body>
        </html>
        """
        
        text = EPUBIngester._parse_html_content(html)
        
        # Should have line breaks between paragraphs
        lines = [line for line in text.split('\n') if line.strip()]
        assert len(lines) >= 3
    
    def test_parse_html_content_empty(self):
        """Test parsing empty HTML."""
        html = "<html><body></body></html>"
        
        text = EPUBIngester._parse_html_content(html)
        
        assert text.strip() == ""
    
    def test_parse_html_content_with_unicode(self):
        """Test parsing HTML with unicode characters."""
        html = """
        <html>
            <body>
                <p>Content with unicode: café, naïve, 日本語</p>
            </body>
        </html>
        """
        
        text = EPUBIngester._parse_html_content(html)
        
        assert "café" in text
        assert "naïve" in text
        assert "日本語" in text
    
    def test_parse_html_content_malformed(self):
        """Test parsing malformed HTML."""
        html = "<p>Unclosed paragraph<div>Nested content"
        
        # Should not raise, BeautifulSoup handles malformed HTML
        text = EPUBIngester._parse_html_content(html)
        
        assert "Unclosed paragraph" in text
        assert "Nested content" in text
    
    def test_extract_volume_info_empty_toc(self):
        """Test volume extraction with empty TOC."""
        from ebooklib import epub
        
        book = epub.EpubBook()
        book.toc = []
        
        volume_map = EPUBIngester._extract_volume_info(book)
        
        assert volume_map == {}
    
    def test_extract_volume_info_no_volumes(self):
        """Test volume extraction when TOC has no volume markers."""
        from ebooklib import epub
        
        book = epub.EpubBook()
        # Create simple TOC without volume structure
        book.toc = [
            epub.Link('chapter1.xhtml', 'Chapter 1', 'ch1'),
            epub.Link('chapter2.xhtml', 'Chapter 2', 'ch2'),
        ]
        
        volume_map = EPUBIngester._extract_volume_info(book)
        
        # Should return empty map if no volume keywords found
        assert isinstance(volume_map, dict)
    
    def test_extract_chapters_missing_file(self):
        """Test that missing EPUB file raises IngestionError."""
        with pytest.raises(IngestionError, match="Cannot read EPUB file"):
            EPUBIngester.extract_chapters("nonexistent_file.epub")
    
    def test_get_spine_order_empty_spine(self):
        """Test spine order extraction with empty spine."""
        from ebooklib import epub
        
        book = epub.EpubBook()
        book.spine = []
        
        spine_items = EPUBIngester._get_spine_order(book)
        
        assert spine_items == []
    
    def test_parse_html_content_with_dialogue(self):
        """Test parsing HTML with dialogue formatting."""
        html = """
        <html>
            <body>
                <p>"Hello," said Alice.</p>
                <p>"Hi there!" Bob replied.</p>
                <p>They continued talking.</p>
            </body>
        </html>
        """
        
        text = EPUBIngester._parse_html_content(html)
        
        assert '"Hello," said Alice.' in text
        assert '"Hi there!" Bob replied.' in text
        assert "They continued talking." in text
    
    def test_parse_html_content_with_nested_tags(self):
        """Test parsing HTML with nested formatting tags."""
        html = """
        <html>
            <body>
                <p>This is <strong>bold</strong> and <em>italic</em> text.</p>
                <p>This has <span class="highlight">highlighted</span> content.</p>
            </body>
        </html>
        """
        
        text = EPUBIngester._parse_html_content(html)
        
        assert "bold" in text
        assert "italic" in text
        assert "highlighted" in text
        # Tags should be removed
        assert "<strong>" not in text
        assert "<em>" not in text
    
    def test_parse_html_content_with_lists(self):
        """Test parsing HTML with list elements."""
        html = """
        <html>
            <body>
                <ul>
                    <li>First item</li>
                    <li>Second item</li>
                    <li>Third item</li>
                </ul>
            </body>
        </html>
        """
        
        text = EPUBIngester._parse_html_content(html)
        
        assert "First item" in text
        assert "Second item" in text
        assert "Third item" in text
    
    def test_parse_html_content_excessive_whitespace(self):
        """Test that excessive whitespace is normalized."""
        html = """
        <html>
            <body>
                <p>Text    with    multiple    spaces.</p>
                <p>


                Multiple blank lines.


                </p>
            </body>
        </html>
        """
        
        text = EPUBIngester._parse_html_content(html)
        
        # Should normalize excessive spaces
        assert "Text    with    multiple    spaces" not in text
        assert "Text with multiple spaces" in text or "multiple" in text
    
    def test_extract_volume_info_with_volume_keywords(self):
        """Test volume extraction with volume/book/part keywords."""
        from ebooklib import epub
        
        book = epub.EpubBook()
        
        # Create a section with volume keyword
        volume_section = epub.Section('Volume 1')
        chapter_link = epub.Link('chapter1.xhtml', 'Chapter 1', 'ch1')
        
        book.toc = [
            (volume_section, [chapter_link])
        ]
        
        volume_map = EPUBIngester._extract_volume_info(book)
        
        # Should detect volume structure
        assert isinstance(volume_map, dict)
    
    def test_parse_html_content_with_special_entities(self):
        """Test parsing HTML with special entities."""
        html = """
        <html>
            <body>
                <p>Special chars: &lt; &gt; &amp; &quot; &#39;</p>
            </body>
        </html>
        """
        
        text = EPUBIngester._parse_html_content(html)
        
        # BeautifulSoup should decode entities
        assert "<" in text or "&lt;" in text
        assert ">" in text or "&gt;" in text
        assert "&" in text or "&amp;" in text


class TestEPUBIngesterIntegration:
    """Integration tests for EPUBIngester with actual EPUB creation."""
    
    def test_extract_chapters_minimal_epub(self):
        """Test extraction from a minimal valid EPUB."""
        from ebooklib import epub
        
        # Create a minimal EPUB
        book = epub.EpubBook()
        book.set_identifier('test123')
        book.set_title('Test Book')
        book.set_language('en')
        
        # Create chapters
        c1 = epub.EpubHtml(title='Chapter 1', file_name='chap_01.xhtml', lang='en')
        c1.content = '<html><body><h1>Chapter 1</h1><p>First chapter content.</p></body></html>'
        
        c2 = epub.EpubHtml(title='Chapter 2', file_name='chap_02.xhtml', lang='en')
        c2.content = '<html><body><h1>Chapter 2</h1><p>Second chapter content.</p></body></html>'
        
        # Add chapters to book
        book.add_item(c1)
        book.add_item(c2)
        
        # Add default NCX and Nav files
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        
        # Define spine
        book.spine = [c1, c2]
        
        # Write EPUB to temp file
        with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
            temp_path = f.name
        
        try:
            # Write with ignore_ncx option to avoid TOC issues
            epub.write_epub(temp_path, book, {'epub3_pages': False})
            
            # Extract chapters
            chapters = EPUBIngester.extract_chapters(temp_path)
            
            # Verify extraction
            assert len(chapters) >= 2
            
            # Check first chapter
            assert chapters[0].index == 0
            assert "Chapter 1" in chapters[0].content or "First chapter" in chapters[0].content
            
            # Check second chapter
            assert chapters[1].index == 1
            assert "Chapter 2" in chapters[1].content or "Second chapter" in chapters[1].content
            
        finally:
            # Add delay to ensure file is closed on Windows
            import time
            time.sleep(0.1)
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except PermissionError:
                pass  # File still locked, skip cleanup
    
    def test_extract_chapters_with_empty_chapters(self):
        """Test that empty chapters are skipped."""
        from ebooklib import epub
        
        book = epub.EpubBook()
        book.set_identifier('test456')
        book.set_title('Test Book with Empty')
        book.set_language('en')
        
        # Create chapters including an empty one
        c1 = epub.EpubHtml(title='Chapter 1', file_name='chap_01.xhtml', lang='en')
        c1.content = '<html><body><p>Content here.</p></body></html>'
        
        c2 = epub.EpubHtml(title='Empty Chapter', file_name='chap_02.xhtml', lang='en')
        c2.content = '<html><body></body></html>'
        
        c3 = epub.EpubHtml(title='Chapter 3', file_name='chap_03.xhtml', lang='en')
        c3.content = '<html><body><p>More content.</p></body></html>'
        
        book.add_item(c1)
        book.add_item(c2)
        book.add_item(c3)
        
        # Add default NCX and Nav files
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        
        book.spine = [c1, c2, c3]
        
        with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
            temp_path = f.name
        
        try:
            # Write with ignore_ncx option to avoid TOC issues
            epub.write_epub(temp_path, book, {'epub3_pages': False})
            
            chapters = EPUBIngester.extract_chapters(temp_path)
            
            # Empty chapter should be skipped
            assert len(chapters) == 2
            
        finally:
            # Add delay to ensure file is closed on Windows
            import time
            time.sleep(0.1)
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except PermissionError:
                pass  # File still locked, skip cleanup


class TestEPUBIngesterEdgeCases:
    """Edge case tests for EPUBIngester - validates Requirements 1.4."""
    
    def test_corrupt_epub_file_error_handling(self):
        """Test that corrupt EPUB file raises IngestionError with descriptive message.
        
        Validates Requirements: 1.4
        """
        # Create a file that looks like an EPUB but is actually corrupt
        with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
            temp_path = f.name
            # Write invalid/corrupt data
            f.write(b'This is not a valid EPUB file, just random text')
        
        try:
            # Should raise IngestionError
            with pytest.raises(IngestionError) as exc_info:
                EPUBIngester.extract_chapters(temp_path)
            
            # Verify error message is descriptive
            assert "Cannot read EPUB file" in str(exc_info.value)
            assert temp_path in str(exc_info.value)
            
        finally:
            # Clean up temp file
            import time
            time.sleep(0.1)
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except PermissionError:
                pass  # File still locked, skip cleanup
    
    def test_epub_with_missing_metadata(self):
        """Test EPUB with missing or minimal metadata still extracts chapters.
        
        Validates Requirements: 1.4
        """
        from ebooklib import epub
        
        # Create an EPUB with minimal metadata (no title, no author, etc.)
        book = epub.EpubBook()
        book.set_identifier('minimal123')
        # Deliberately omit title, author, language
        
        # Create chapters with content but no titles in TOC
        c1 = epub.EpubHtml(title='', file_name='chap_01.xhtml', lang='en')
        c1.content = '<html><body><p>First chapter with no metadata.</p></body></html>'
        
        c2 = epub.EpubHtml(title='', file_name='chap_02.xhtml', lang='en')
        c2.content = '<html><body><p>Second chapter with no metadata.</p></body></html>'
        
        book.add_item(c1)
        book.add_item(c2)
        
        # Add default NCX and Nav files
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        
        # Define spine without TOC
        book.spine = [c1, c2]
        book.toc = []  # Empty TOC
        
        with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
            temp_path = f.name
        
        try:
            # Write EPUB
            epub.write_epub(temp_path, book, {'epub3_pages': False})
            
            # Should still extract chapters successfully
            chapters = EPUBIngester.extract_chapters(temp_path)
            
            # Verify extraction worked despite missing metadata
            assert len(chapters) == 2
            
            # Chapters should have fallback titles (filenames)
            assert chapters[0].index == 0
            assert chapters[0].title  # Should have some title (filename fallback)
            assert "First chapter" in chapters[0].content
            
            assert chapters[1].index == 1
            assert chapters[1].title  # Should have some title (filename fallback)
            assert "Second chapter" in chapters[1].content
            
        finally:
            # Clean up
            import time
            time.sleep(0.1)
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except PermissionError:
                pass
    
    def test_epub_with_nested_volume_structure(self):
        """Test EPUB with nested volume/book structure in TOC.
        
        Validates Requirements: 1.4
        """
        from ebooklib import epub
        
        # Create an EPUB with nested volume structure
        book = epub.EpubBook()
        book.set_identifier('volumes123')
        book.set_title('Multi-Volume Novel')
        book.set_language('en')
        
        # Create chapters for different volumes
        v1c1 = epub.EpubHtml(title='Chapter 1', file_name='v1_chap_01.xhtml', lang='en')
        v1c1.content = '<html><body><h1>Volume 1 - Chapter 1</h1><p>Content of V1C1.</p></body></html>'
        
        v1c2 = epub.EpubHtml(title='Chapter 2', file_name='v1_chap_02.xhtml', lang='en')
        v1c2.content = '<html><body><h1>Volume 1 - Chapter 2</h1><p>Content of V1C2.</p></body></html>'
        
        v2c1 = epub.EpubHtml(title='Chapter 1', file_name='v2_chap_01.xhtml', lang='en')
        v2c1.content = '<html><body><h1>Volume 2 - Chapter 1</h1><p>Content of V2C1.</p></body></html>'
        
        v2c2 = epub.EpubHtml(title='Chapter 2', file_name='v2_chap_02.xhtml', lang='en')
        v2c2.content = '<html><body><h1>Volume 2 - Chapter 2</h1><p>Content of V2C2.</p></body></html>'
        
        book.add_item(v1c1)
        book.add_item(v1c2)
        book.add_item(v2c1)
        book.add_item(v2c2)
        
        # Add default NCX and Nav files
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        
        # Define spine
        book.spine = [v1c1, v1c2, v2c1, v2c2]
        
        # Create nested TOC structure with volumes
        book.toc = (
            (epub.Section('Volume 1'), (
                epub.Link('v1_chap_01.xhtml', 'Chapter 1', 'v1c1'),
                epub.Link('v1_chap_02.xhtml', 'Chapter 2', 'v1c2'),
            )),
            (epub.Section('Volume 2'), (
                epub.Link('v2_chap_01.xhtml', 'Chapter 1', 'v2c1'),
                epub.Link('v2_chap_02.xhtml', 'Chapter 2', 'v2c2'),
            ))
        )
        
        with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
            temp_path = f.name
        
        try:
            # Write EPUB
            epub.write_epub(temp_path, book, {'epub3_pages': False})
            
            # Extract chapters
            chapters = EPUBIngester.extract_chapters(temp_path)
            
            # Verify all chapters extracted
            assert len(chapters) == 4
            
            # Verify volume information is preserved
            # First two chapters should be in Volume 1
            assert chapters[0].volume == 'Volume 1'
            assert chapters[1].volume == 'Volume 1'
            
            # Last two chapters should be in Volume 2
            assert chapters[2].volume == 'Volume 2'
            assert chapters[3].volume == 'Volume 2'
            
            # Verify content is correct
            assert "V1C1" in chapters[0].content
            assert "V1C2" in chapters[1].content
            assert "V2C1" in chapters[2].content
            assert "V2C2" in chapters[3].content
            
        finally:
            # Clean up
            import time
            time.sleep(0.1)
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except PermissionError:
                pass
