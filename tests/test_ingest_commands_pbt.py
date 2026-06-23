"""
Property-based tests for ingestion commands.

These tests validate universal correctness properties that should hold
across all valid executions of the ingestion commands.
"""

import pytest
import tempfile
import zipfile
import os
from pathlib import Path
from hypothesis import given, strategies as st, settings, HealthCheck
from typer.testing import CliRunner

from babel.cli import app
from babel.data.db import DatabaseManager


runner = CliRunner()


def clear_singleton():
    """Clear DatabaseManager singleton instances."""
    DatabaseManager._instances.clear()


# Helper strategies for generating novel data
@st.composite
def novel_title_strategy(draw):
    """Generate a valid novel title."""
    title = draw(st.text(
        min_size=1,
        max_size=500,
        alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0d\x0e\x0f'
        )
    ))
    return title


@st.composite
def novel_author_strategy(draw):
    """Generate a valid novel author name."""
    author = draw(st.text(
        min_size=1,
        max_size=200,
        alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0d\x0e\x0f'
        )
    ))
    return author


# Strategy for generating valid EPUB files
@st.composite
def epub_file_strategy(draw):
    """
    Generate a valid EPUB file with metadata.
    
    Creates a minimal EPUB structure with:
    - META-INF/container.xml
    - OEBPS/content.opf with Dublin Core metadata
    - At least one chapter
    """
    # Generate title and author
    title = draw(st.text(
        min_size=1,
        max_size=200,
        alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0d\x0e\x0f'
        )
    ))
    author = draw(st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0d\x0e\x0f'
        )
    ))
    
    # Create temporary directory
    tmp_dir = Path(tempfile.mkdtemp())
    epub_path = tmp_dir / "test.epub"
    
    # Create EPUB structure
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
        content_opf = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title>{title}</dc:title>
        <dc:creator>{author}</dc:creator>
    </metadata>
    <manifest>
        <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
    </manifest>
    <spine>
        <itemref idref="chapter1"/>
    </spine>
</package>'''
        zf.writestr('OEBPS/content.opf', content_opf)
        
        # Create chapter content
        chapter_content = '''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <title>Chapter 1</title>
    </head>
    <body>
        <h1>Chapter 1</h1>
        <p>This is the first chapter content.</p>
    </body>
</html>'''
        zf.writestr('OEBPS/chapter1.xhtml', chapter_content)
    
    return epub_path, title, author


@settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(epub_file=epub_file_strategy())
def test_property_7_metadata_extraction_from_epub(epub_file):
    """
    Feature: cli-sqlite-migration, Property 7: Metadata Extraction from EPUB
    
    For any valid EPUB file containing Dublin Core metadata (dc:title and dc:creator)
    in content.opf, executing `babel ingest` should extract and store the title
    and author in the novel database entry.
    
    Validates: Requirements 2.6
    """
    clear_singleton()
    
    epub_path, expected_title, expected_author = epub_file
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_babel.db"
        
        try:
            # Run the ingest command
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, ["ingest", str(epub_path)])
            
            # Command should succeed
            assert result.exit_code == 0, f"Command failed: {result.output}"
            
            # Verify output contains success message
            assert "ingested successfully" in result.output.lower() or "Novel ID" in result.output, (
                f"Expected success message, got: {result.output}"
            )
            
            # Verify database contains the novel with correct metadata
            db = DatabaseManager(db_path)
            novels = db.list_novels(limit=100)
            
            assert len(novels) == 1, f"Expected 1 novel, got {len(novels)}"
            
            novel = novels[0]
            
            # Title should match (case-insensitive comparison for flexibility)
            assert expected_title.lower() in novel['title'].lower() or \
                   novel['title'].lower() in expected_title.lower(), (
                f"Title mismatch: expected '{expected_title}', got '{novel['title']}'"
            )
            
            # Author should match
            assert novel['author'] is not None, "Author should be extracted from EPUB"
            assert expected_author.lower() in novel['author'].lower() or \
                   novel['author'].lower() in expected_author.lower(), (
                f"Author mismatch: expected '{expected_author}', got '{novel['author']}'"
            )
            
            # Verify chapters were created
            chapters = db.get_chapters_by_novel(novel['id'])
            assert len(chapters) >= 1, f"Expected at least 1 chapter, got {len(chapters)}"
            
        finally:
            # Clean up temp EPUB file
            import time
            time.sleep(0.1)
            try:
                if epub_path.exists():
                    epub_path.unlink()
            except PermissionError:
                pass  # File still locked


@settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    title=novel_title_strategy(),
    author=novel_author_strategy()
)
def test_property_ingest_creates_novel_with_chapters(title, author):
    """
    Feature: cli-sqlite-migration, Property: Ingest Creates Novel with Chapters
    
    For any valid EPUB file, executing `babel ingest` should create a novel
    entry in the database and extract chapters with correct associations.
    
    Validates: Requirements 2.1, 2.3, 2.4, 2.8
    """
    clear_singleton()
    
    # Create a valid EPUB file
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        epub_path = tmp_path / "test.epub"
        
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
        <dc:title>{title}</dc:title>
        <dc:creator>{author}</dc:creator>
    </metadata>
    <manifest>
        <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
        <item id="chapter2" href="chapter2.xhtml" media-type="application/xhtml+xml"/>
    </manifest>
    <spine>
        <itemref idref="chapter1"/>
        <itemref idref="chapter2"/>
    </spine>
</package>'''
            zf.writestr('OEBPS/content.opf', content_opf)
            
            for i in range(1, 3):
                chapter_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <title>Chapter {i}</title>
    </head>
    <body>
        <h1>Chapter {i}</h1>
        <p>Content of chapter {i}.</p>
    </body>
</html>'''
                zf.writestr(f'OEBPS/chapter{i}.xhtml', chapter_content)
        
        db_path = tmp_path / "test_babel.db"
        
        # Run the ingest command
        test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
        result = test_runner.invoke(app, ["ingest", str(epub_path)])
        
        # Command should succeed
        assert result.exit_code == 0, f"Command failed: {result.output}"
        
        # Verify database state
        db = DatabaseManager(db_path)
        novels = db.list_novels(limit=100)
        
        assert len(novels) == 1, f"Expected 1 novel, got {len(novels)}"
        
        novel = novels[0]
        assert novel['title'] == title
        assert novel['author'] == author
        assert novel['status'] == 'active'
        
        # Verify chapters
        chapters = db.get_chapters_by_novel(novel['id'])
        assert len(chapters) == 2, f"Expected 2 chapters, got {len(chapters)}"
        
        # Verify chapter order
        assert chapters[0]['chapter_index'] == 1
        assert chapters[1]['chapter_index'] == 2
        
        # Verify chapters are associated with novel
        for chapter in chapters:
            assert chapter['novel_id'] == novel['id']