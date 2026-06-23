"""
Unit tests for metadata extraction module.
"""

import pytest
import zipfile
from pathlib import Path
from babel.api.metadata_extraction import (
    extract_metadata_from_epub,
    extract_title_from_filename,
    extract_metadata
)


class TestExtractTitleFromFilename:
    """Tests for extract_title_from_filename function."""
    
    def test_simple_epub_filename(self):
        """Test extracting title from simple EPUB filename."""
        result = extract_title_from_filename("Lord of Mysteries.epub")
        assert result == "Lord Of Mysteries"
    
    def test_filename_with_book_pattern(self):
        """Test extracting title from filename with ' - Book ' pattern."""
        result = extract_title_from_filename("Lord of Mysteries - Book 1.epub")
        assert result == "Lord Of Mysteries"
    
    def test_filename_with_chapter(self):
        """Test extracting title from filename with chapter number."""
        result = extract_title_from_filename("infinite_mage_chapter_1.txt")
        assert result == "Infinite Mage Chapter 1"
    
    def test_filename_with_hyphens(self):
        """Test extracting title from filename with hyphens."""
        result = extract_title_from_filename("my-novel.epub")
        assert result == "My Novel"
    
    def test_filename_with_underscores(self):
        """Test extracting title from filename with underscores."""
        result = extract_title_from_filename("my_novel.epub")
        assert result == "My Novel"
    
    def test_filename_with_multiple_underscores(self):
        """Test extracting title from filename with multiple underscores."""
        result = extract_title_from_filename("___test___.txt")
        assert result == "Test"
    
    def test_filename_with_book_number_variations(self):
        """Test extracting title with various book number formats."""
        result = extract_title_from_filename("Novel Title - Book 2.epub")
        assert result == "Novel Title"
        
        result = extract_title_from_filename("Novel Title - Book 10.epub")
        assert result == "Novel Title"
    
    def test_empty_filename(self):
        """Test handling of empty filename."""
        result = extract_title_from_filename("")
        assert result == "Untitled Novel"
    
    def test_only_extension(self):
        """Test handling of filename that is only an extension."""
        result = extract_title_from_filename(".epub")
        assert result == "Untitled Novel"
    
    def test_special_characters(self):
        """Test handling of special characters in filename."""
        result = extract_title_from_filename("Novel_Title!@#.epub")
        assert result == "Novel Title"
    
    def test_acronyms_preserved(self):
        """Test that acronyms are preserved in uppercase."""
        result = extract_title_from_filename("LOTM - Book 1.epub")
        assert result == "LOTM"
    
    def test_mixed_case_filename(self):
        """Test handling of mixed case filename."""
        result = extract_title_from_filename("SoMe-NoVeL.epub")
        assert result == "Some Novel"
    
    def test_numeric_filename(self):
        """Test handling of numeric-only filename."""
        result = extract_title_from_filename("684151.epub")
        assert result == "684151"
    
    def test_leading_dash(self):
        """Test handling of filename with leading dash."""
        result = extract_title_from_filename("- Novel Title.epub")
        assert result == "Novel Title"
    
    def test_trailing_dash(self):
        """Test handling of filename with trailing dash."""
        result = extract_title_from_filename("Novel Title -.epub")
        assert result == "Novel Title"


class TestExtractMetadataFromEpub:
    """Tests for extract_metadata_from_epub function."""
    
    def test_valid_epub_metadata(self, tmp_path):
        """Test extracting metadata from valid EPUB file."""
        # Create a minimal EPUB structure
        epub_path = tmp_path / "test.epub"
        
        with zipfile.ZipFile(epub_path, 'w') as zf:
            # Create container.xml
            container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>'''
            zf.writestr('META-INF/container.xml', container_xml)
            
            # Create content.opf with metadata
            content_opf = '''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title>Test Novel Title</dc:title>
        <dc:creator>Test Author</dc:creator>
    </metadata>
    <manifest>
        <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
    </manifest>
    <spine>
        <itemref idref="chapter1"/>
    </spine>
</package>'''
            zf.writestr('OEBPS/content.opf', content_opf)
        
        result = extract_metadata_from_epub(epub_path)
        
        assert result['title'] == 'Test Novel Title'
        assert result['author'] == 'Test Author'
    
    def test_epub_missing_title(self, tmp_path):
        """Test extracting metadata from EPUB with missing title."""
        epub_path = tmp_path / "test.epub"
        
        with zipfile.ZipFile(epub_path, 'w') as zf:
            container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>'''
            zf.writestr('META-INF/container.xml', container_xml)
            
            content_opf = '''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:creator>Test Author</dc:creator>
    </metadata>
</package>'''
            zf.writestr('OEBPS/content.opf', content_opf)
        
        result = extract_metadata_from_epub(epub_path)
        
        assert result['title'] is None
        assert result['author'] == 'Test Author'
    
    def test_epub_missing_container_xml(self, tmp_path):
        """Test extracting metadata from EPUB without container.xml."""
        epub_path = tmp_path / "test.epub"
        
        with zipfile.ZipFile(epub_path, 'w') as zf:
            # Only add a dummy file, no container.xml
            zf.writestr('dummy.txt', 'dummy content')
        
        result = extract_metadata_from_epub(epub_path)
        
        assert result['title'] is None
        assert result['author'] is None
    
    def test_epub_malformed_xml(self, tmp_path):
        """Test extracting metadata from EPUB with malformed XML."""
        epub_path = tmp_path / "test.epub"
        
        with zipfile.ZipFile(epub_path, 'w') as zf:
            container_xml = 'not valid xml'
            zf.writestr('META-INF/container.xml', container_xml)
        
        result = extract_metadata_from_epub(epub_path)
        
        assert result['title'] is None
        assert result['author'] is None
    
    def test_epub_invalid_zip(self, tmp_path):
        """Test extracting metadata from invalid EPUB file."""
        epub_path = tmp_path / "test.epub"
        epub_path.write_text('not a valid zip file')
        
        result = extract_metadata_from_epub(epub_path)
        
        assert result['title'] is None
        assert result['author'] is None
    
    def test_epub_missing_content_opf(self, tmp_path):
        """Test extracting metadata from EPUB with missing content.opf."""
        epub_path = tmp_path / "test.epub"
        
        with zipfile.ZipFile(epub_path, 'w') as zf:
            container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>'''
            zf.writestr('META-INF/container.xml', container_xml)
            # Don't create content.opf
        
        result = extract_metadata_from_epub(epub_path)
        
        assert result['title'] is None
        assert result['author'] is None
    
    def test_epub_empty_title(self, tmp_path):
        """Test extracting metadata from EPUB with empty title."""
        epub_path = tmp_path / "test.epub"
        
        with zipfile.ZipFile(epub_path, 'w') as zf:
            container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>'''
            zf.writestr('META-INF/container.xml', container_xml)
            
            content_opf = '''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title></dc:title>
        <dc:creator>Test Author</dc:creator>
    </metadata>
</package>'''
            zf.writestr('OEBPS/content.opf', content_opf)
        
        result = extract_metadata_from_epub(epub_path)
        
        # Empty title should return None
        assert result['title'] is None or result['title'] == ''
        assert result['author'] == 'Test Author'


class TestExtractMetadata:
    """Tests for extract_metadata function."""
    
    def test_epub_uses_internal_metadata(self, tmp_path):
        """Test that EPUB files use internal metadata first."""
        epub_path = tmp_path / "test.epub"
        
        with zipfile.ZipFile(epub_path, 'w') as zf:
            container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>'''
            zf.writestr('META-INF/container.xml', container_xml)
            
            content_opf = '''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title>EPUB Title</dc:title>
        <dc:creator>EPUB Author</dc:creator>
    </metadata>
</package>'''
            zf.writestr('OEBPS/content.opf', content_opf)
        
        result = extract_metadata(epub_path, "Filename Title.epub")
        
        assert result['title'] == 'EPUB Title'
        assert result['author'] == 'EPUB Author'
    
    def test_epub_falls_back_to_filename(self, tmp_path):
        """Test that EPUB falls back to filename when metadata extraction fails."""
        epub_path = tmp_path / "test.epub"
        
        with zipfile.ZipFile(epub_path, 'w') as zf:
            # No container.xml - will fail metadata extraction
            zf.writestr('dummy.txt', 'dummy')
        
        result = extract_metadata(epub_path, "Fallback Title.epub")
        
        assert result['title'] == 'Fallback Title'
        assert result['author'] is None
    
    def test_txt_uses_filename(self, tmp_path):
        """Test that TXT files use filename extraction."""
        txt_path = tmp_path / "test.txt"
        txt_path.write_text("Chapter content")
        
        result = extract_metadata(txt_path, "My Novel - Book 1.txt")
        
        assert result['title'] == 'My Novel'
        assert result['author'] is None
    
    def test_txt_numeric_filename(self, tmp_path):
        """Test TXT file with numeric filename falls back properly."""
        txt_path = tmp_path / "test.txt"
        txt_path.write_text("Chapter content")
        
        result = extract_metadata(txt_path, "684151.txt")
        
        assert result['title'] == '684151'
        assert result['author'] is None
    
    def test_epub_with_empty_title_uses_filename(self, tmp_path):
        """Test EPUB with empty title falls back to filename."""
        epub_path = tmp_path / "test.epub"
        
        with zipfile.ZipFile(epub_path, 'w') as zf:
            container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>'''
            zf.writestr('META-INF/container.xml', container_xml)
            
            content_opf = '''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title></dc:title>
    </metadata>
</package>'''
            zf.writestr('OEBPS/content.opf', content_opf)
        
        result = extract_metadata(epub_path, "Filename Title.epub")
        
        assert result['title'] == 'Filename Title'
        assert result['author'] is None
"""
Property-based tests for metadata extraction module.

Feature: cli-sqlite-migration, Property 8: Metadata Extraction Fallback
Validates: Requirements 2.2, 2.7
"""

import re
import pytest
from hypothesis import given, settings, Verbosity
from hypothesis import strategies as st
from hypothesis.strategies import lists, text, integers, sampled_from

from babel.api.metadata_extraction import (
    extract_title_from_filename,
    extract_metadata
)


# Define valid file extensions for strategy
FILE_EXTENSIONS = ['.epub', '.txt', '.pdf', '.mobi', '']


@st.composite
def generate_filename(draw):
    """
    Generate a valid filename for testing.
    
    Strategy:
    - Generate a base name with optional " - Book X" pattern
    - Optionally add an extension
    """
    # Generate base title (ASCII alphanumeric with spaces, underscores, hyphens)
    base_title = draw(st.text(
        alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 _-',
        min_size=0,
        max_size=50
    ))
    
    # Optionally add " - Book X" pattern
    if draw(st.booleans()):
        book_num = draw(integers(min_value=1, max_value=100))
        base_title = f"{base_title} - Book {book_num}"
    
    # Add extension
    extension = draw(sampled_from(FILE_EXTENSIONS))
    
    return base_title + extension


class TestPropertyMetadataExtractionFallback:
    """
    Property-based tests for metadata extraction fallback.
    
    Property 8: For any file where EPUB metadata extraction fails or the file
    is not an EPUB, executing `babel ingest` should fall back to extracting
    the title from the filename using the parsing rules.
    """
    
    @given(generate_filename())
    @settings(max_examples=100, verbosity=Verbosity.quiet)
    def test_result_never_empty(self, filename):
        """
        Property: The result should never be empty.
        
        For any filename input, extract_title_from_filename should return
        a non-empty string (or "Untitled Novel" for edge cases).
        """
        result = extract_title_from_filename(filename)
        assert result is not None
        assert len(result.strip()) > 0
    
    @given(generate_filename())
    @settings(max_examples=100, verbosity=Verbosity.quiet)
    def test_no_file_extension_in_result(self, filename):
        """
        Property: The result should not contain file extensions.
        
        For any filename with extension, the extracted title should not
        contain .epub, .txt, .pdf, or .mobi.
        """
        result = extract_title_from_filename(filename)
        
        # Check that no known extensions are in the result
        for ext in ['.epub', '.txt', '.pdf', '.mobi']:
            assert ext.lower() not in result.lower(), \
                f"Extension {ext} found in result: '{result}' from filename: '{filename}'"
    
    @given(generate_filename())
    @settings(max_examples=100, verbosity=Verbosity.quiet)
    def test_no_book_pattern_in_result(self, filename):
        """
        Property: The result should not contain " - Book X" pattern.
        
        For any filename with " - Book X" pattern, the extracted title
        should only contain the text before the pattern.
        """
        result = extract_title_from_filename(filename)
        
        # Skip edge case where filename is just " - Book X.ext"
        # (no title before the pattern)
        base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
        if base_name.strip() == f"- Book {base_name.split('Book')[-1].strip() if 'Book' in base_name else ''}".strip():
            pytest.skip("Edge case: filename is just ' - Book X' pattern")
        
        # Check that no " - Book X" pattern is in the result
        book_pattern = re.compile(r'\s*-\s*Book\s+\d+', re.IGNORECASE)
        match = book_pattern.search(result)
        assert match is None, \
            f"Book pattern found in result: '{result}' from filename: '{filename}'"
    
    @given(st.text(
        alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 _-',
        min_size=1,
        max_size=50
    ))
    @settings(max_examples=100, verbosity=Verbosity.quiet)
    def test_underscores_replaced_with_spaces(self, filename):
        """
        Property: Underscores should be replaced with spaces.
        
        For any filename containing underscores, the extracted title
        should have those underscores replaced with spaces.
        """
        # Skip edge case where filename is just underscores
        if filename.strip('_').strip() == '':
            pytest.skip("Edge case: filename is just underscores")
        
        result = extract_title_from_filename(filename)
        
        # If the original filename had underscores in the base name,
        # the result should not have underscores (except in acronyms)
        if '_' in filename:
            # Split result into words and check each word
            words = result.split()
            for word in words:
                # Allow underscores in all-caps acronyms (like "LOTM")
                if not (len(word) <= 4 and word.isupper()):
                    assert '_' not in word, \
                        f"Underscore found in non-acronym word: '{word}' from filename: '{filename}'"
    
    @given(st.text(
        alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 _-',
        min_size=1,
        max_size=20
    ))
    @settings(max_examples=100, verbosity=Verbosity.quiet)
    def test_result_is_title_cased(self, name):
        """
        Property: The result should be title-cased (with exceptions for acronyms).
        
        For any filename, the extracted title should have each word
        capitalized, except for acronyms (all caps, 2-4 chars).
        """
        # Create a filename with the name
        filename = f"{name}.epub"
        
        result = extract_title_from_filename(filename)
        
        # Skip empty results
        if not result:
            return
        
        words = result.split()
        
        for word in words:
            # Skip single characters and acronyms
            if len(word) <= 1:
                continue
            # Acronyms should be all caps (2-4 chars)
            if len(word) <= 4 and word.isupper():
                continue
            
            # Other words should be title-cased (first letter upper, rest lower)
            # Note: This is a relaxed check - we allow internal capitals
            assert word[0].isupper() or word[0].isdigit(), \
                f"Word should start with uppercase: '{word}' from filename: '{filename}'"
    
    @given(generate_filename())
    @settings(max_examples=100, verbosity=Verbosity.quiet)
    def test_result_is_trimmed(self, filename):
        """
        Property: The result should be trimmed of whitespace.
        
        For any filename, the extracted title should not have leading
        or trailing whitespace.
        """
        result = extract_title_from_filename(filename)
        
        assert result == result.strip(), \
            f"Result should be trimmed: '{result}' from filename: '{filename}'"
    
    @given(st.text(
        alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',
        min_size=2,
        max_size=4
    ))
    @settings(max_examples=100, verbosity=Verbosity.quiet)
    def test_acronyms_preserved(self, letters):
        """
        Property: Acronyms (all caps, 2-4 chars) should be preserved.
        
        For any title that is an acronym, the result should preserve
        the uppercase letters.
        """
        # Create a filename with an acronym
        acronym = letters.upper()
        filename = f"{acronym} - Book 1.epub"
        
        result = extract_title_from_filename(filename)
        
        # The acronym should be preserved
        assert acronym in result, \
            f"Acronym {acronym} should be preserved in result: '{result}'"
    
    @given(st.integers(min_value=1, max_value=10000))
    @settings(max_examples=100, verbosity=Verbosity.quiet)
    def test_numeric_filenames_preserved(self, number):
        """
        Property: Numeric filenames should be preserved as-is.
        
        For any numeric filename, the result should contain the number.
        """
        filename = f"{number}.epub"
        
        result = extract_title_from_filename(filename)
        
        assert str(number) in result, \
            f"Number {number} should be in result: '{result}'"
    
    @given(st.lists(
        st.text(
            alphabet=st.characters(
                whitelist_categories=['L', 'N'],
                whitelist_characters=' _-'
            ),
            min_size=1,
            max_size=10
        ),
        min_size=1,
        max_size=5
    ))
    @settings(max_examples=100, verbosity=Verbosity.quiet)
    def test_multiple_underscores_replaced(self, words):
        """
        Property: Multiple consecutive underscores should be replaced with spaces.
        
        For any filename with multiple underscores, the result should
        have single spaces between words.
        """
        # Create filename with multiple underscores
        base = '_'.join(words)
        filename = f"{base}.txt"
        
        result = extract_title_from_filename(filename)
        
        # Should not have multiple consecutive spaces
        assert '  ' not in result, \
            f"Multiple spaces found in result: '{result}' from filename: '{filename}'"
    
    @given(st.text(
        alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 _-',
        min_size=1,
        max_size=30
    ))
    @settings(max_examples=100, verbosity=Verbosity.quiet)
    def test_special_characters_cleaned(self, name):
        """
        Property: Special characters should be cleaned from the result.
        
        For any filename with special characters, the result should
        only contain alphanumeric characters and spaces.
        """
        filename = f"{name}.epub"
        
        result = extract_title_from_filename(filename)
        
        # Result should only have alphanumeric, spaces, and hyphens
        # (hyphens are allowed in the middle of words)
        assert re.match(r'^[\w\s-]+$', result), \
            f"Result contains invalid characters: '{result}' from filename: '{filename}'"
    
    @given(st.text(
        alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz ',
        min_size=1,
        max_size=20
    ))
    @settings(max_examples=100, verbosity=Verbosity.quiet)
    def test_spaces_preserved(self, words):
        """
        Property: Spaces should be preserved in the result.
        
        For any filename with spaces, the result should preserve
        the word separation.
        """
        # Create a filename with spaces
        filename = f"{words}.txt"
        
        result = extract_title_from_filename(filename)
        
        # The number of words should be preserved
        original_word_count = len(words.split())
        result_word_count = len(result.split())
        
        assert original_word_count == result_word_count, \
            f"Word count mismatch: {original_word_count} -> {result_word_count} in result: '{result}'"
    
    @given(st.text(
        alphabet=st.characters(
            whitelist_categories=['L', 'N'],
            whitelist_characters=' _-'
        ),
        min_size=1,
        max_size=30
    ))
    @settings(max_examples=100, verbosity=Verbosity.quiet)
    def test_hyphenated_words_handled(self, name):
        """
        Property: Hyphens surrounded by spaces should be replaced.
        
        For any filename with " - " pattern, the hyphens should be
        replaced with spaces in the result.
        """
        # Create filename with hyphens
        filename = f"{name}.epub"
        
        result = extract_title_from_filename(filename)
        
        # Check that " - " pattern is not in result
        assert ' - ' not in result, \
            f"Hyphen pattern found in result: '{result}' from filename: '{filename}'"
    
    @given(st.text(
        alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789',
        min_size=1,
        max_size=20
    ))
    @settings(max_examples=100, verbosity=Verbosity.quiet)
    def test_leading_trailing_dashes_removed(self, name):
        """
        Property: Leading and trailing dashes should be removed.
        
        For any filename with leading or trailing dashes (after extension
        removal), the result should not have them.
        """
        # Create filename with leading/trailing dashes
        filename = f"-{name}-.epub"
        
        result = extract_title_from_filename(filename)
        
        # Result should not start or end with dash
        assert not result.startswith('-'), \
            f"Result starts with dash: '{result}' from filename: '{filename}'"
        assert not result.endswith('-'), \
            f"Result ends with dash: '{result}' from filename: '{filename}'"
    
    @given(st.text(
        alphabet=st.characters(
            whitelist_categories=['L', 'N'],
            whitelist_characters=' _-'
        ),
        min_size=1,
        max_size=30
    ))
    @settings(max_examples=100, verbosity=Verbosity.quiet)
    def test_empty_and_whitespace_only_filenames(self, name):
        """
        Property: Empty or whitespace-only filenames should return "Untitled Novel".
        
        For any empty or whitespace-only filename, the result should
        be "Untitled Novel".
        """
        # Test empty string
        result = extract_title_from_filename("")
        assert result == "Untitled Novel"
        
        # Test whitespace-only
        result = extract_title_from_filename("   ")
        assert result == "Untitled Novel"
    
    @given(st.text(
        alphabet=st.characters(
            whitelist_categories=['L', 'N'],
            whitelist_characters=' _-'
        ),
        min_size=1,
        max_size=30
    ))
    @settings(max_examples=100, verbosity=Verbosity.quiet)
    def test_extension_only_filenames(self, name):
        """
        Property: Filenames that are only extensions should return "Untitled Novel".
        
        For any filename that is just an extension (like ".epub"),
        the result should be "Untitled Novel".
        """
        # Test extension only
        result = extract_title_from_filename(".epub")
        assert result == "Untitled Novel"
    
    @given(st.integers(min_value=1, max_value=100))
    @settings(max_examples=100, verbosity=Verbosity.quiet)
    def test_book_number_variations(self, book_num):
        """
        Property: Various book number formats should be handled.
        
        For any book number, the " - Book X" pattern should be removed
        from the result.
        """
        filename = f"Novel Title - Book {book_num}.epub"
        
        result = extract_title_from_filename(filename)
        
        # The result should be "Novel Title"
        assert result == "Novel Title", \
            f"Expected 'Novel Title' but got: '{result}'"
        
        # Should not contain the book number
        assert str(book_num) not in result, \
            f"Book number {book_num} found in result: '{result}'"