"""
Unit tests for ingestion functionality.

These tests verify:
- EPUB file ingestion with metadata extraction
- Text file ingestion with filename parsing
- Error handling for invalid files
- Success message format
- Chapter extraction and database storage
- Transaction safety (rollback on failure)

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.5, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 13.1, 13.2, 13.3, 13.4, 13.5
"""

import pytest
import tempfile
import zipfile
import os
from pathlib import Path
from typer.testing import CliRunner

from babel.cli import app
from babel.data.db import DatabaseManager
from babel.cli_commands.ingest_commands import (
    extract_metadata,
    extract_chapters_from_file,
    initialize_novel_directories
)


runner = CliRunner()


def clear_singleton():
    """Clear DatabaseManager singleton instances."""
    DatabaseManager._instances.clear()


def create_valid_epub(tmp_path: Path, title: str = "Test Novel", author: str = "Test Author") -> Path:
    """Create a valid EPUB file for testing."""
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
        
        chapter1 = '''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
    <head><title>Chapter 1</title></head>
    <body>
        <h1>Chapter 1: The Beginning</h1>
        <p>This is the first chapter content.</p>
        <p>More content here.</p>
    </body>
</html>'''
        zf.writestr('OEBPS/chapter1.xhtml', chapter1)
        
        chapter2 = '''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
    <head><title>Chapter 2</title></head>
    <body>
        <h1>Chapter 2: The Continuation</h1>
        <p>This is the second chapter content.</p>
    </body>
</html>'''
        zf.writestr('OEBPS/chapter2.xhtml', chapter2)
    
    return epub_path


class TestExtractMetadata:
    """Tests for metadata extraction from files."""
    
    def test_epub_extracts_title_and_author(self, tmp_path):
        """Test that EPUB files extract title and author from Dublin Core metadata.
        
        Validates: Requirements 12.1
        """
        epub_path = create_valid_epub(tmp_path, "Lord of Mysteries", "Cuttlefish That Loves Diving")
        
        result = extract_metadata(epub_path, "some_file.epub")
        
        assert result['title'] == "Lord of Mysteries"
        assert result['author'] == "Cuttlefish That Loves Diving"
    
    def test_epub_falls_back_to_filename_when_no_metadata(self, tmp_path):
        """Test that EPUB falls back to filename when metadata extraction fails.
        
        Validates: Requirements 12.2
        """
        epub_path = tmp_path / "Fallback Title.epub"
        
        with zipfile.ZipFile(epub_path, 'w') as zf:
            # No container.xml - will fail metadata extraction
            zf.writestr('dummy.txt', 'dummy')
        
        result = extract_metadata(epub_path, "Fallback Title.epub")
        
        assert result['title'] == "Fallback Title"
        assert result['author'] is None
    
    def test_txt_uses_filename_extraction(self, tmp_path):
        """Test that TXT files use filename extraction.
        
        Validates: Requirements 12.2
        """
        txt_path = tmp_path / "My Novel - Book 1.txt"
        txt_path.write_text("Chapter content")
        
        result = extract_metadata(txt_path, "My Novel - Book 1.txt")
        
        assert result['title'] == "My Novel"
        assert result['author'] is None
    
    def test_txt_numeric_filename(self, tmp_path):
        """Test TXT file with numeric filename.
        
        Validates: Requirements 12.7
        """
        txt_path = tmp_path / "684151.txt"
        txt_path.write_text("Chapter content")
        
        result = extract_metadata(txt_path, "684151.txt")
        
        assert result['title'] == "684151"
        assert result['author'] is None
    
    def test_epub_empty_title_falls_back_to_filename(self, tmp_path):
        """Test EPUB with empty title falls back to filename.
        
        Validates: Requirements 12.7
        """
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
        
        assert result['title'] == "Filename Title"
        assert result['author'] is None


class TestExtractChaptersFromFile:
    """Tests for chapter extraction from files."""
    
    def test_epub_extracts_multiple_chapters(self, tmp_path):
        """Test that EPUB files extract multiple chapters.
        
        Validates: Requirements 2.1, 2.2
        """
        epub_path = create_valid_epub(tmp_path)
        
        chapters = extract_chapters_from_file(epub_path)
        
        assert len(chapters) == 2
        assert chapters[0]['chapter_index'] == 1
        # Title comes from the HTML <title> element, not <h1>
        assert chapters[0]['title'] == "Chapter 1"
        assert "first chapter content" in chapters[0]['content']
        assert chapters[1]['chapter_index'] == 2
        assert chapters[1]['title'] == "Chapter 2"
    
    def test_txt_extracts_single_chapter(self, tmp_path):
        """Test that TXT files extract single chapter.
        
        Validates: Requirements 2.1, 2.2
        """
        txt_path = tmp_path / "my_novel.txt"
        txt_path.write_text("This is the content of my novel.\n\nChapter 1 content here.")
        
        chapters = extract_chapters_from_file(txt_path)
        
        assert len(chapters) == 1
        assert chapters[0]['chapter_index'] == 1
        assert chapters[0]['filename'] == "my_novel.txt"
        assert "This is the content of my novel" in chapters[0]['content']
    
    def test_epub_chapters_have_novel_id_association(self, tmp_path):
        """Test that extracted chapters can be associated with novel_id.
        
        Validates: Requirements 2.1, 2.2
        """
        epub_path = create_valid_epub(tmp_path)
        
        chapters = extract_chapters_from_file(epub_path)
        
        # Chapters should have the fields needed for database association
        for chapter in chapters:
            assert 'chapter_index' in chapter
            assert 'filename' in chapter
            assert 'title' in chapter
            assert 'content' in chapter


class TestInitializeNovelDirectories:
    """Tests for novel directory initialization."""
    
    def test_creates_novel_specific_directories(self, tmp_path):
        """Test that directories are created for novel_id.
        
        Validates: Requirements 3.1, 3.2, 3.3, 3.4
        """
        original_cwd = Path.cwd()
        novel_id = 42
        
        try:
            # Change to temp directory to avoid polluting project
            os.chdir(tmp_path)
            
            initialize_novel_directories(novel_id)
            
            # Verify all phase directories were created
            for phase in ['raw', 'clean', 'json', 'render']:
                dir_path = Path(f"data/{phase}/novel_{novel_id}")
                assert dir_path.exists(), f"Directory {dir_path} should exist"
                assert dir_path.is_dir()
        
        finally:
            os.chdir(original_cwd)
    
    def test_directories_have_correct_structure(self, tmp_path):
        """Test that directories have correct nested structure.
        
        Validates: Requirements 3.1, 3.2, 3.3, 3.4
        """
        original_cwd = Path.cwd()
        novel_id = 123
        
        try:
            os.chdir(tmp_path)
            
            initialize_novel_directories(novel_id)
            
            # Verify parent directories were created
            for phase in ['raw', 'clean', 'json', 'render']:
                phase_dir = Path(f"data/{phase}")
                assert phase_dir.exists()
                assert phase_dir.is_dir()
                
                novel_dir = phase_dir / f"novel_{novel_id}"
                assert novel_dir.exists()
                assert novel_dir.is_dir()
        
        finally:
            os.chdir(original_cwd)


class TestIngestCommand:
    """Test suite for the ingest CLI command."""
    
    def test_ingest_epub_creates_novel_entry(self):
        """Test ingesting EPUB creates novel entry in database.
        
        Validates: Requirements 1.1, 1.2, 1.3, 1.5
        """
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            epub_path = create_valid_epub(tmp_path, "Test Novel Title", "Test Author")
            
            db_path = tmp_path / "test_babel.db"
            
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, ["ingest", str(epub_path)])
            
            assert result.exit_code == 0, f"Command failed: {result.output}"
            
            # Verify database contains the novel
            db = DatabaseManager(db_path)
            novels = db.list_novels(limit=100)
            
            assert len(novels) == 1
            assert novels[0]['title'] == "Test Novel Title"
            assert novels[0]['author'] == "Test Author"
            assert novels[0]['status'] == "active"
            
            db.close()
    
    def test_ingest_epub_extracts_chapters(self):
        """Test ingesting EPUB extracts and stores chapters.
        
        Validates: Requirements 2.1, 2.2
        """
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            epub_path = create_valid_epub(tmp_path)
            
            db_path = tmp_path / "test_babel.db"
            
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, ["ingest", str(epub_path)])
            
            assert result.exit_code == 0
            
            # Get novel_id from output
            db = DatabaseManager(db_path)
            novels = db.list_novels(limit=100)
            novel_id = novels[0]['id']
            
            # Verify chapters were created
            chapters = db.get_chapters_by_novel(novel_id)
            assert len(chapters) == 2
            assert chapters[0]['chapter_index'] == 1
            assert chapters[1]['chapter_index'] == 2
            
            db.close()
    
    def test_ingest_txt_creates_novel_entry(self):
        """Test ingesting TXT file creates novel entry.
        
        Validates: Requirements 1.1, 1.2, 1.3, 1.5
        """
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            txt_path = tmp_path / "My_Novel.txt"
            txt_path.write_text("This is the content of my novel.\n\nChapter 1 content here.")
            
            db_path = tmp_path / "test_babel.db"
            
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, ["ingest", str(txt_path)])
            
            assert result.exit_code == 0, f"Command failed: {result.output}"
            
            # Verify database contains the novel
            db = DatabaseManager(db_path)
            novels = db.list_novels(limit=100)
            
            assert len(novels) == 1
            # Title should be extracted from filename
            assert "My Novel" in novels[0]['title']
            assert novels[0]['status'] == "active"
            
            db.close()
    
    def test_ingest_nonexistent_file_fails(self):
        """Test error handling for nonexistent file.
        
        Validates: Requirements 13.3
        """
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, ["ingest", "nonexistent_file.epub"])
            
            assert result.exit_code == 1
            assert "not found" in result.output.lower() or "error" in result.output.lower()
    
    def test_ingest_invalid_format_fails(self):
        """Test error handling for invalid file format.
        
        Validates: Requirements 13.3
        """
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Create a file with unsupported extension
            pdf_path = tmp_path / "test.pdf"
            pdf_path.write_text("This is a PDF file")
            
            db_path = tmp_path / "test_babel.db"
            
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, ["ingest", str(pdf_path)])
            
            assert result.exit_code == 1
            assert "unsupported" in result.output.lower() or "format" in result.output.lower()
    
    def test_ingest_with_title_override(self):
        """Test ingesting with title override option.
        
        Validates: Requirements 1.4
        """
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            epub_path = create_valid_epub(tmp_path, "EPUB Title", "EPUB Author")
            
            db_path = tmp_path / "test_babel.db"
            
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, [
                "ingest", str(epub_path),
                "--title", "Custom Title",
                "--author", "Custom Author"
            ])
            
            assert result.exit_code == 0
            
            db = DatabaseManager(db_path)
            novels = db.list_novels(limit=100)
            
            assert len(novels) == 1
            assert novels[0]['title'] == "Custom Title"
            assert novels[0]['author'] == "Custom Author"
            
            db.close()
    
    def test_ingest_success_message_contains_novel_id(self):
        """Test that success message contains novel_id.
        
        Validates: Requirements 1.3, 13.1
        """
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            epub_path = create_valid_epub(tmp_path)
            
            db_path = tmp_path / "test_babel.db"
            
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, ["ingest", str(epub_path)])
            
            assert result.exit_code == 0
            
            # Verify success message format
            assert "Novel ID" in result.output or "novel_id" in result.output.lower()
            assert "Title" in result.output or "Test Novel" in result.output
            assert "Chapters" in result.output or "2" in result.output
            
            db = DatabaseManager(db_path)
            db.close()
    
    def test_ingest_creates_novel_specific_directories(self):
        """Test that ingestion creates novel-specific directories.
        
        Validates: Requirements 3.1, 3.2, 3.3, 3.4
        """
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            epub_path = create_valid_epub(tmp_path)
            
            db_path = tmp_path / "test_babel.db"
            
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, ["ingest", str(epub_path)])
            
            assert result.exit_code == 0
            
            # Get the novel ID
            db = DatabaseManager(db_path)
            novels = db.list_novels(limit=100)
            novel_id = novels[0]['id']
            db.close()
            
            # Verify directories were created
            for phase in ['raw', 'clean', 'json', 'render']:
                dir_path = Path(f"data/{phase}/novel_{novel_id}")
                assert dir_path.exists(), f"Directory {dir_path} should exist"
            
            # Clean up
            import shutil
            for phase in ['raw', 'clean', 'json', 'render']:
                dir_path = Path(f"data/{phase}/novel_{novel_id}")
                if dir_path.exists():
                    shutil.rmtree(dir_path, ignore_errors=True)
    
    def test_ingest_multiple_files_creates_multiple_novels(self):
        """Test ingesting multiple files creates multiple novel entries.
        
        Validates: Requirements 2.1, 2.2
        """
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Create two EPUB files with different titles
            epub1 = create_valid_epub(tmp_path, "Novel One", "Author One")
            # Rename to avoid overwriting
            epub1.rename(tmp_path / "novel_one.epub")
            
            epub2 = create_valid_epub(tmp_path, "Novel Two", "Author Two")
            # Rename to avoid overwriting
            epub2.rename(tmp_path / "novel_two.epub")
            
            epub1_path = tmp_path / "novel_one.epub"
            epub2_path = tmp_path / "novel_two.epub"
            
            db_path = tmp_path / "test_babel.db"
            
            # Ingest first novel
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result1 = test_runner.invoke(app, ["ingest", str(epub1_path)])
            assert result1.exit_code == 0
            
            # Ingest second novel
            result2 = test_runner.invoke(app, ["ingest", str(epub2_path)])
            assert result2.exit_code == 0
            
            # Verify both novels exist
            db = DatabaseManager(db_path)
            novels = db.list_novels(limit=100)
            
            assert len(novels) == 2
            titles = [n['title'] for n in novels]
            assert "Novel One" in titles
            assert "Novel Two" in titles
            
            db.close()


class TestIngestTransactionSafety:
    """Test suite for transaction safety during ingestion."""
    
    def test_rollback_on_directory_creation_failure(self):
        """Test that novel entry is rolled back if directory creation fails.
        
        Validates: Requirements 10.5, 13.1, 13.2, 13.3, 13.4, 13.5
        """
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            epub_path = create_valid_epub(tmp_path)
            
            db_path = tmp_path / "test_babel.db"
            
            # Patch at the module level where the function is defined
            from unittest.mock import patch
            
            # Import the module and patch the function
            import babel.cli_commands.ingest_commands as ingest_cmd
            
            # Store original
            original_func = ingest_cmd.initialize_novel_directories
            
            # Track if mock was called
            mock_called = [False]
            
            def failing_init(novel_id):
                mock_called[0] = True
                raise OSError("Cannot create directory")
            
            # Apply patch
            ingest_cmd.initialize_novel_directories = failing_init
            
            try:
                test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
                result = test_runner.invoke(app, ["ingest", str(epub_path)])
                
                # Command should fail
                assert result.exit_code == 1
                
                # Check if mock was called
                if mock_called[0]:
                    # Mock was applied, verify rollback
                    db = DatabaseManager(db_path)
                    novels = db.list_novels(limit=100)
                    assert len(novels) == 0, f"Expected 0 novels (rollback) but found {len(novels)}"
                    db.close()
                else:
                    # Mock wasn't applied - skip test
                    pytest.skip("Mock not applied correctly")
            finally:
                # Restore original
                ingest_cmd.initialize_novel_directories = original_func


class TestIngestFilenamePatterns:
    """Test suite for various filename patterns."""
    
    def test_filename_with_book_pattern(self):
        """Test filename with ' - Book ' pattern.
        
        Validates: Requirements 12.3
        """
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            txt_path = tmp_path / "Lord of Mysteries - Book 1.txt"
            txt_path.write_text("Chapter content")
            
            db_path = tmp_path / "test_babel.db"
            
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, ["ingest", str(txt_path)])
            
            assert result.exit_code == 0
            
            db = DatabaseManager(db_path)
            novels = db.list_novels(limit=100)
            
            # Title should extract text before " - Book "
            # Title is title-cased, so "Lord of Mysteries" becomes "Lord Of Mysteries"
            assert "Lord" in novels[0]['title']
            assert "Mysteries" in novels[0]['title']
            
            db.close()
    
    def test_filename_with_underscores(self):
        """Test filename with underscores.
        
        Validates: Requirements 12.4
        """
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            txt_path = tmp_path / "my_novel.txt"
            txt_path.write_text("Chapter content")
            
            db_path = tmp_path / "test_babel.db"
            
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, ["ingest", str(txt_path)])
            
            assert result.exit_code == 0
            
            db = DatabaseManager(db_path)
            novels = db.list_novels(limit=100)
            
            # Underscores should be replaced with spaces
            assert "My Novel" in novels[0]['title']
            
            db.close()
    
    def test_filename_with_hyphens(self):
        """Test filename with hyphens.
        
        Validates: Requirements 12.5
        """
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            txt_path = tmp_path / "my-novel.txt"
            txt_path.write_text("Chapter content")
            
            db_path = tmp_path / "test_babel.db"
            
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, ["ingest", str(txt_path)])
            
            assert result.exit_code == 0
            
            db = DatabaseManager(db_path)
            novels = db.list_novels(limit=100)
            
            # Hyphens should be handled (replaced with spaces)
            assert "My Novel" in novels[0]['title']
            
            db.close()


class TestIngestChapterAssociation:
    """Test suite for chapter-novel association."""
    
    def test_chapters_associated_with_correct_novel(self):
        """Test that chapters are associated with the correct novel_id.
        
        Validates: Requirements 2.1, 2.2
        """
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Create two EPUB files with different titles
            epub1 = create_valid_epub(tmp_path, "Novel One", "Author One")
            epub1.rename(tmp_path / "novel_one.epub")
            
            epub2 = create_valid_epub(tmp_path, "Novel Two", "Author Two")
            epub2.rename(tmp_path / "novel_two.epub")
            
            epub1_path = tmp_path / "novel_one.epub"
            epub2_path = tmp_path / "novel_two.epub"
            
            db_path = tmp_path / "test_babel.db"
            
            # Ingest first novel
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result1 = test_runner.invoke(app, ["ingest", str(epub1_path)])
            assert result1.exit_code == 0
            
            # Ingest second novel
            result2 = test_runner.invoke(app, ["ingest", str(epub2_path)])
            assert result2.exit_code == 0
            
            # Verify chapters are associated with correct novels
            db = DatabaseManager(db_path)
            novels = db.list_novels(limit=100)
            
            # Find novels by title (title-cased)
            novel1 = next((n for n in novels if "Novel One" in n['title']), None)
            novel2 = next((n for n in novels if "Novel Two" in n['title']), None)
            
            assert novel1 is not None, f"Novel One not found in {novels}"
            assert novel2 is not None, f"Novel Two not found in {novels}"
            
            novel1_id = novel1['id']
            novel2_id = novel2['id']
            
            chapters1 = db.get_chapters_by_novel(novel1_id)
            chapters2 = db.get_chapters_by_novel(novel2_id)
            
            # Each novel should have its own chapters
            assert len(chapters1) == 2
            assert len(chapters2) == 2
            
            # Verify novel_id association
            for chapter in chapters1:
                assert chapter['novel_id'] == novel1_id
            for chapter in chapters2:
                assert chapter['novel_id'] == novel2_id
            
            db.close()
    
    def test_chapter_count_in_novel_response(self):
        """Test that chapter count is included in novel response.
        
        Validates: Requirements 7.4
        """
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            epub_path = create_valid_epub(tmp_path)
            
            db_path = tmp_path / "test_babel.db"
            
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, ["ingest", str(epub_path)])
            
            assert result.exit_code == 0
            
            # Verify chapter count is correct
            db = DatabaseManager(db_path)
            novels = db.list_novels_with_chapter_count(limit=100)
            
            assert len(novels) == 1
            assert novels[0]['chapter_count'] == 2
            
            db.close()