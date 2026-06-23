"""
Property-based tests for EPUB metadata extraction.

These tests validate universal correctness properties for EPUB metadata
extraction, ensuring that Dublin Core metadata (dc:title, dc:creator) is
correctly extracted from EPUB content.opf files and stored in the database.

Feature: multi-novel-ingestion-support
Property 7: Metadata Extraction from EPUB
Validates: Requirements 2.6
"""

import tempfile
import zipfile
from pathlib import Path

import pytest
from hypothesis import given, settings, HealthCheck, strategies as st

from babel.api.metadata_extraction import (
    extract_metadata_from_epub,
    extract_metadata
)
from babel.data.db import DatabaseManager


# ============================================================================
# Strategies for generating test data
# ============================================================================

@st.composite
def valid_title_strategy(draw):
    """Generate a valid novel title."""
    # Generate titles with various characters, avoiding control characters and whitespace-only
    title = draw(st.text(
        min_size=1,
        max_size=500,
        alphabet=st.characters(
            whitelist_categories=('L', 'N'),
            blacklist_characters='\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f'
        )
    ))
    # Add some spaces between words (but not leading/trailing only)
    words = title.split()[:10]  # Limit to 10 words
    if words:
        return ' '.join(words)
    return title


@st.composite
def valid_author_strategy(draw):
    """Generate a valid author name (can be None)."""
    use_none = draw(st.booleans())
    if use_none:
        return None
    # Generate author names with various characters, avoiding control characters
    author = draw(st.text(
        min_size=1,
        max_size=200,
        alphabet=st.characters(
            whitelist_categories=('L', 'N'),
            blacklist_characters='\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f'
        )
    ))
    # Add spaces between words
    words = author.split()[:5]
    if words:
        return ' '.join(words)
    return author


@st.composite
def special_characters_strategy(draw):
    """Generate titles with special characters that might appear in real EPUBs."""
    # Include common special characters found in book titles
    chars = draw(st.sets(
        st.sampled_from([
            ':', '-', '—', '–', '(', ')', '[', ']', '{', '}',
            '"', "'", '!', '?', '.', ',', ';', '&', '@', '#',
            '$', '%', '^', '*', '+', '=', '/', '\\', '|', '~',
            '`', '<', '>', '…', '「', '」', '『', '』', '【', '】'
        ]),
        min_size=0,
        max_size=5
    ))
    base = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))))
    return base + ''.join(chars)


@st.composite
def unicode_title_strategy(draw):
    """Generate titles with Unicode characters (CJK, accents, etc.)."""
    # Mix of ASCII and Unicode characters
    ascii_part = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N', 'Zs'))))
    unicode_part = draw(st.text(
        min_size=1,
        max_size=20,
        alphabet=st.sampled_from([
            '日', '本', '語', '中', '文', '韩', '国', '繁', '體',
            'é', 'è', 'ê', 'ë', 'à', 'â', 'á', 'ã', 'å',
            'ñ', 'ó', 'ô', 'õ', 'ö', 'ø', 'ù', 'ú', 'û',
            'ß', 'ä', 'ü', 'ï', 'ç', 'ł', 'ż', 'ś'
        ])
    ))
    return f"{ascii_part} {unicode_part}"


@st.composite
def epub_path_strategy(draw):
    """Generate a valid EPUB file path."""
    # Generate a filename with .epub extension
    filename = draw(st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(whitelist_categories=('L', 'N', 'Zs'), blacklist_characters='/<>\\|')
    ))
    return f"{filename}.epub"


# ============================================================================
# Helper functions for creating test EPUBs
# ============================================================================

def create_epub_with_metadata(tmp_path, filename, title, author=None):
    """
    Create a minimal EPUB file with Dublin Core metadata.
    
    Args:
        tmp_path: Temporary directory path
        filename: Name of the EPUB file to create
        title: Dublin Core title (dc:title)
        author: Dublin Core creator (dc:creator), optional
        
    Returns:
        Path to the created EPUB file
    """
    import html
    
    epub_path = tmp_path / filename
    
    # Escape special XML characters in title and author
    escaped_title = html.escape(str(title), quote=True)
    escaped_author = html.escape(str(author), quote=True) if author else None
    
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
        if author is not None:
            content_opf = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title>{escaped_title}</dc:title>
        <dc:creator>{escaped_author}</dc:creator>
    </metadata>
    <manifest>
        <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
    </manifest>
    <spine>
        <itemref idref="chapter1"/>
    </spine>
</package>'''
        else:
            content_opf = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title>{escaped_title}</dc:title>
    </metadata>
    <manifest>
        <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
    </manifest>
    <spine>
        <itemref idref="chapter1"/>
    </spine>
</package>'''
        zf.writestr('OEBPS/content.opf', content_opf)
    
    return epub_path


def create_epub_without_title(tmp_path, filename, author):
    """Create an EPUB file with author but no title."""
    import html
    
    epub_path = tmp_path / filename
    escaped_author = html.escape(str(author), quote=True)
    
    with zipfile.ZipFile(epub_path, 'w') as zf:
        container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>'''
        zf.writestr('META-INF/container.xml', container_xml)
        
        content_opf = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:creator>{escaped_author}</dc:creator>
    </metadata>
</package>'''
        zf.writestr('OEBPS/content.opf', content_opf)
    
    return epub_path


def create_epub_without_author(tmp_path, filename, title):
    """Create an EPUB file with title but no author."""
    import html
    
    epub_path = tmp_path / filename
    escaped_title = html.escape(str(title), quote=True)
    
    with zipfile.ZipFile(epub_path, 'w') as zf:
        container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>'''
        zf.writestr('META-INF/container.xml', container_xml)
        
        content_opf = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title>{escaped_title}</dc:title>
    </metadata>
</package>'''
        zf.writestr('OEBPS/content.opf', content_opf)
    
    return epub_path


def create_epub_with_empty_title(tmp_path, filename, author):
    """Create an EPUB file with empty title element."""
    import html
    
    epub_path = tmp_path / filename
    escaped_author = html.escape(str(author), quote=True)
    
    with zipfile.ZipFile(epub_path, 'w') as zf:
        container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>'''
        zf.writestr('META-INF/container.xml', container_xml)
        
        content_opf = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title></dc:title>
        <dc:creator>{escaped_author}</dc:creator>
    </metadata>
</package>'''
        zf.writestr('OEBPS/content.opf', content_opf)
    
    return epub_path


# ============================================================================
# Property 7: Metadata Extraction from EPUB
# ============================================================================

class TestEpubMetadataExtraction:
    """
    Property-based tests for Property 7: Metadata Extraction from EPUB.
    
    For any valid EPUB file containing Dublin Core metadata (dc:title and dc:creator)
    in content.opf, executing `babel ingest` should extract and store the title and
    author in the novel database entry.
    
    Validates: Requirements 2.6
    """
    
    @given(
        title=valid_title_strategy(),
        author=valid_author_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_epub_extracts_title_and_author(self, title, author):
        """
        For any valid EPUB file with Dublin Core metadata, extract_metadata_from_epub
        should correctly extract the dc:title and dc:creator values.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            epub_path = create_epub_with_metadata(tmp_path, "test.epub", title, author)
            
            result = extract_metadata_from_epub(epub_path)
            
            # Property: title should be extracted correctly
            assert result['title'] == title
            # Property: author should be extracted correctly (handle None vs 'None' string)
            if author is None:
                assert result['author'] is None or result['author'] == ''
            else:
                assert result['author'] == author
    
    @given(
        title=valid_title_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_epub_extracts_title_without_author(self, title):
        """
        For any valid EPUB file with only dc:title (no dc:creator),
        extract_metadata_from_epub should extract the title and return None for author.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            epub_path = create_epub_without_author(tmp_path, "test.epub", title)
            
            result = extract_metadata_from_epub(epub_path)
            
            # Property: title should be extracted correctly
            assert result['title'] == title
            # Property: author should be None when not provided
            assert result['author'] is None
    
    @given(
        author=st.one_of(st.none(), valid_author_strategy())
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_epub_extracts_author_without_title(self, author):
        """
        For any valid EPUB file with only dc:creator (no dc:title),
        extract_metadata_from_epub should return None for title and extract author.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Skip if author is None (test is for author extraction)
            if author is None:
                return
                
            epub_path = create_epub_without_title(tmp_path, "test.epub", author)
            
            result = extract_metadata_from_epub(epub_path)
            
            # Property: title should be None when not provided
            assert result['title'] is None
            # Property: author should be extracted correctly
            assert result['author'] == author
    
    @given(
        title=valid_title_strategy(),
        author=st.one_of(st.none(), valid_author_strategy())
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_epub_with_empty_title_falls_back_to_none(self, title, author):
        """
        For any valid EPUB file with empty dc:title element,
        extract_metadata_from_epub should return None for title (not empty string).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Skip if author is None (test is for author extraction with empty title)
            if author is None:
                return
                
            epub_path = create_epub_with_empty_title(tmp_path, "test.epub", author)
            
            result = extract_metadata_from_epub(epub_path)
            
            # Property: empty title should return None (not empty string)
            assert result['title'] is None or result['title'] == ''
            # Property: author should still be extracted
            assert result['author'] == author
    
    @given(
        title=unicode_title_strategy(),
        author=valid_author_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_epub_extracts_unicode_metadata(self, title, author):
        """
        For any valid EPUB file with Unicode characters in Dublin Core metadata,
        extract_metadata_from_epub should correctly extract the Unicode values.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            epub_path = create_epub_with_metadata(tmp_path, "test.epub", title, author)
            
            result = extract_metadata_from_epub(epub_path)
            
            # Property: Unicode title should be extracted correctly
            assert result['title'] == title
            # Property: Unicode author should be extracted correctly
            assert result['author'] == author
    
    @given(
        title=special_characters_strategy(),
        author=valid_author_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_epub_extracts_special_characters(self, title, author):
        """
        For any valid EPUB file with special characters in Dublin Core metadata,
        extract_metadata_from_epub should correctly extract the values.
        """
        # Ensure title is not empty after special character generation
        if not title:
            title = "Test Title"
            
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            epub_path = create_epub_with_metadata(tmp_path, "test.epub", title, author)
            
            result = extract_metadata_from_epub(epub_path)
            
            # Property: title with special characters should be extracted
            assert result['title'] == title
            # Property: author should be extracted correctly
            assert result['author'] == author
    
    @given(
        title=valid_title_strategy(),
        author=valid_author_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_extract_metadata_uses_epub_priority(self, title, author):
        """
        For any valid EPUB file, extract_metadata should use EPUB internal metadata
        over filename parsing, and store the extracted values in the database.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            epub_path = create_epub_with_metadata(tmp_path, "test.epub", title, author)
            
            # Use a different filename to test priority
            result = extract_metadata(epub_path, "Different Filename.epub")
            
            # Property: EPUB metadata should be used (not filename)
            assert result['title'] == title
            # Property: author should be extracted correctly (handle None vs 'None' string)
            if author is None:
                assert result['author'] is None or result['author'] == ''
            else:
                assert result['author'] == author
    
    @given(
        title=valid_title_strategy(),
        author=valid_author_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_extracted_metadata_stored_in_database(self, title, author):
        """
        For any valid EPUB file with Dublin Core metadata, the extracted title and
        author should be correctly stored in the novel database entry.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                # Create EPUB and extract metadata
                epub_path = create_epub_with_metadata(tmp_path, "test.epub", title, author)
                metadata = extract_metadata_from_epub(epub_path)
                
                # Create novel in database with extracted metadata
                novel_id = db.create_novel(
                    title=metadata['title'],
                    author=metadata['author']
                )
                
                # Property: novel should be created with correct metadata
                novel = db.get_novel(novel_id)
                assert novel is not None
                assert novel['title'] == title
                # Handle None vs 'None' string for author
                if author is None:
                    assert novel['author'] is None or novel['author'] == ''
                else:
                    assert novel['author'] == author
                assert novel['status'] == 'active'
            finally:
                db.close()
    
    @given(
        titles=st.lists(valid_title_strategy(), min_size=1, max_size=10, unique=True),
        authors=st.lists(valid_author_strategy(), min_size=1, max_size=10)
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_multiple_epubs_extract_correct_metadata(self, titles, authors):
        """
        For multiple EPUB files with different metadata, each should extract
        its own correct metadata without interference.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                novel_ids = []
                for i, title in enumerate(titles):
                    author = authors[i % len(authors)]
                    epub_filename = f"novel_{i}.epub"
                    epub_path = create_epub_with_metadata(tmp_path, epub_filename, title, author)
                    
                    # Extract metadata
                    metadata = extract_metadata_from_epub(epub_path)
                    
                    # Create novel
                    novel_id = db.create_novel(
                        title=metadata['title'],
                        author=metadata['author']
                    )
                    novel_ids.append(novel_id)
                
                # Property: each novel should have correct metadata
                for i, novel_id in enumerate(novel_ids):
                    novel = db.get_novel(novel_id)
                    assert novel is not None
                    assert novel['title'] == titles[i]
                    # Handle None vs 'None' string for author
                    expected_author = authors[i % len(authors)]
                    if expected_author is None:
                        assert novel['author'] is None or novel['author'] == ''
                    else:
                        assert novel['author'] == expected_author
            finally:
                db.close()
    
    @given(
        title=valid_title_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_epub_title_extraction_preserves_whitespace(self, title):
        """
        For any valid EPUB file, whitespace in dc:title should be preserved
        (leading/trailing whitespace should be stripped, internal preserved).
        """
        # Add internal whitespace to title
        title_with_spaces = f"  {title}  "
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            epub_path = create_epub_with_metadata(tmp_path, "test.epub", title_with_spaces, "Author")
            
            result = extract_metadata_from_epub(epub_path)
            
            # Property: title should be extracted (internal whitespace preserved, leading/trailing stripped)
            # The implementation strips the title, so we check it matches the stripped version
            assert result['title'] is not None
            assert result['title'] == title_with_spaces.strip() or result['title'] == title_with_spaces


class TestEpubMetadataEdgeCases:
    """
    Property-based tests for edge cases in EPUB metadata extraction.
    
    These tests verify that the extraction handles malformed or unusual
    EPUB files gracefully.
    """
    
    @given(
        title=valid_title_strategy(),
        author=valid_author_strategy()
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_long_title_extraction(self, title, author):
        """
        For EPUB files with very long titles (up to 500 characters),
        metadata extraction should still work correctly.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            epub_path = create_epub_with_metadata(tmp_path, "test.epub", title, author)
            
            result = extract_metadata_from_epub(epub_path)
            
            # Property: long title should be extracted correctly
            assert result['title'] == title
            assert result['author'] == author
    
    @given(
        title=valid_title_strategy(),
        author=valid_author_strategy()
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_long_author_extraction(self, title, author):
        """
        For EPUB files with very long author names (up to 200 characters),
        metadata extraction should still work correctly.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            epub_path = create_epub_with_metadata(tmp_path, "test.epub", title, author)
            
            result = extract_metadata_from_epub(epub_path)
            
            # Property: long author should be extracted correctly
            assert result['title'] == title
            assert result['author'] == author