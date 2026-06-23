"""
Unit tests for ingestion commands.

These tests verify specific examples and edge cases for the ingest command.
"""

import pytest
import tempfile
import zipfile
import os
from pathlib import Path
from typer.testing import CliRunner

from babel.cli import app
from babel.data.db import DatabaseManager


runner = CliRunner()


def clear_singleton():
    """Clear DatabaseManager singleton instances."""
    DatabaseManager._instances.clear()


class TestIngestCommand:
    """Test suite for the ingest command."""
    
    def test_ingest_epub_file(self):
        """Test ingesting a valid EPUB file."""
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Create a valid EPUB file
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
            
            db_path = tmp_path / "test_babel.db"
            
            # Run the ingest command
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, ["ingest", str(epub_path)])
            
            # Command should succeed
            assert result.exit_code == 0, f"Command failed: {result.output}"
            
            # Verify output contains success message
            assert "ingested successfully" in result.output.lower() or "Novel ID" in result.output
            
            # Verify database contains the novel
            db = DatabaseManager(db_path)
            novels = db.list_novels(limit=100)
            
            assert len(novels) == 1
            assert novels[0]['title'] == "Test Novel Title"
            assert novels[0]['author'] == "Test Author"
            
            # Verify chapters were created
            chapters = db.get_chapters_by_novel(novels[0]['id'])
            assert len(chapters) == 1
            
            # Close the database connection
            db.close()
    
    def test_ingest_text_file(self):
        """Test ingesting a text file."""
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Create a text file
            txt_path = tmp_path / "my_novel.txt"
            txt_path.write_text("This is the content of my novel.\n\nChapter 1 content here.")
            
            db_path = tmp_path / "test_babel.db"
            
            # Run the ingest command
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, ["ingest", str(txt_path)])
            
            # Command should succeed
            assert result.exit_code == 0, f"Command failed: {result.output}"
            
            # Verify database contains the novel
            db = DatabaseManager(db_path)
            novels = db.list_novels(limit=100)
            
            assert len(novels) == 1
            # Title should be extracted from filename
            assert "My Novel" in novels[0]['title'] or "my_novel" in novels[0]['title'].lower()
            
            # Verify chapters were created
            chapters = db.get_chapters_by_novel(novels[0]['id'])
            assert len(chapters) == 1
            
            # Close the database connection
            db.close()
    
    def test_ingest_nonexistent_file(self):
        """Test error handling for nonexistent file."""
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            
            # Run the ingest command with nonexistent file
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, ["ingest", "nonexistent_file.epub"])
            
            # Command should fail
            assert result.exit_code == 1
            assert "not found" in result.output.lower() or "error" in result.output.lower()
    
    def test_ingest_invalid_format(self):
        """Test error handling for invalid file format."""
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Create a file with unsupported extension
            pdf_path = tmp_path / "test.pdf"
            pdf_path.write_text("This is a PDF file")
            
            db_path = tmp_path / "test_babel.db"
            
            # Run the ingest command
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, ["ingest", str(pdf_path)])
            
            # Command should fail
            assert result.exit_code == 1
            assert "unsupported" in result.output.lower() or "format" in result.output.lower()
    
    def test_ingest_with_title_override(self):
        """Test ingesting with title override option."""
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Create a valid EPUB file
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
    <manifest>
        <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
    </manifest>
    <spine>
        <itemref idref="chapter1"/>
    </spine>
</package>'''
                zf.writestr('OEBPS/content.opf', content_opf)
                
                chapter_content = '''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
    <head><title>Chapter 1</title></head>
    <body><h1>Chapter 1</h1><p>Content.</p></body>
</html>'''
                zf.writestr('OEBPS/chapter1.xhtml', chapter_content)
            
            db_path = tmp_path / "test_babel.db"
            
            # Run the ingest command with title override
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, [
                "ingest", str(epub_path),
                "--title", "Custom Title",
                "--author", "Custom Author"
            ])
            
            # Command should succeed
            assert result.exit_code == 0, f"Command failed: {result.output}"
            
            # Verify database contains the novel with overridden values
            db = DatabaseManager(db_path)
            novels = db.list_novels(limit=100)
            
            assert len(novels) == 1
            assert novels[0]['title'] == "Custom Title"
            assert novels[0]['author'] == "Custom Author"
            
            # Close the database connection
            db.close()
    
    def test_ingest_success_message_format(self):
        """Test that success message contains expected information."""
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Create a valid EPUB file
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
        <dc:title>Success Message Test</dc:title>
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
                
                chapter_content = '''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
    <head><title>Chapter 1</title></head>
    <body><h1>Chapter 1</h1><p>Content.</p></body>
</html>'''
                zf.writestr('OEBPS/chapter1.xhtml', chapter_content)
            
            db_path = tmp_path / "test_babel.db"
            
            # Run the ingest command
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, ["ingest", str(epub_path)])
            
            # Command should succeed
            assert result.exit_code == 0
            
            # Verify success message format
            assert "Novel ID" in result.output or "novel_id" in result.output.lower()
            assert "Title" in result.output or "Success" in result.output
            assert "Chapters" in result.output or "1" in result.output
            
            # Close the database connection
            db = DatabaseManager(db_path)
            db.close()


class TestIngestDirectories:
    """Test suite for directory creation during ingestion."""
    
    def test_directories_created_for_novel(self):
        """Test that novel directories are created after ingestion."""
        clear_singleton()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Create a valid EPUB file
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
        <dc:title>Directory Test</dc:title>
    </metadata>
    <manifest>
        <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
    </manifest>
    <spine>
        <itemref idref="chapter1"/>
    </spine>
</package>'''
                zf.writestr('OEBPS/content.opf', content_opf)
                
                chapter_content = '''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
    <head><title>Chapter 1</title></head>
    <body><h1>Chapter 1</h1><p>Content.</p></body>
</html>'''
                zf.writestr('OEBPS/chapter1.xhtml', chapter_content)
            
            db_path = tmp_path / "test_babel.db"
            
            # Run the ingest command
            test_runner = CliRunner(env={"BABEL_DB_PATH": str(db_path)})
            result = test_runner.invoke(app, ["ingest", str(epub_path)])
            
            # Command should succeed
            assert result.exit_code == 0
            
            # Get the novel ID from output
            db = DatabaseManager(db_path)
            novels = db.list_novels(limit=100)
            novel_id = novels[0]['id']
            
            # Verify directories were created
            for phase in ['raw', 'clean', 'json', 'render']:
                dir_path = Path(f"data/{phase}/novel_{novel_id}")
                assert dir_path.exists(), f"Directory {dir_path} should exist"
            
            # Close the database connection
            db.close()
            
            # Clean up created directories
            import shutil
            for phase in ['raw', 'clean', 'json', 'render']:
                dir_path = Path(f"data/{phase}/novel_{novel_id}")
                if dir_path.exists():
                    shutil.rmtree(dir_path, ignore_errors=True)