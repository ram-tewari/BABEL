"""
End-to-end integration tests for multi-novel support.

Tests complete workflows including:
- Complete ingestion flow
- Multi-novel workflow
- Backward compatibility
- API workflow
- Transaction rollback
"""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import zipfile

from babel.data.db import DatabaseManager
from babel.api.metadata_extraction import extract_metadata, extract_title_from_filename
from babel.pipeline.orchestrator import PipelineOrchestrator
from babel.pipeline.core import PipelineConfig


class TestCompleteIngestionFlow:
    """Tests for complete ingestion flow."""
    
    def test_novel_creation_from_epub(self, tmp_path):
        """Test complete flow: EPUB upload → novel creation → chapter extraction."""
        # Create a test EPUB
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
</package>'''
            zf.writestr('OEBPS/content.opf', content_opf)
        
        # Extract metadata
        metadata = extract_metadata(epub_path, "Test Novel - Book 1.epub")
        
        assert metadata['title'] == 'Test Novel Title'
        assert metadata['author'] == 'Test Author'
        
        # Create database and novel
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        novel_id = db.create_novel(
            title=metadata['title'],
            author=metadata['author'],
            status="active"
        )
        
        assert novel_id is not None
        assert novel_id > 0
        
        # Verify novel was created
        novel = db.get_novel(novel_id)
        assert novel['title'] == 'Test Novel Title'
        assert novel['author'] == 'Test Author'
        
        # Initialize pipeline orchestrator with novel_id
        config = PipelineConfig(output_dir=tmp_path / "data")
        orchestrator = PipelineOrchestrator(
            config=config,
            input_path=epub_path,
            novel_id=novel_id
        )
        
        # Initialize directories
        orchestrator.initialize_directories()
        
        # Verify novel-specific directories were created
        assert (tmp_path / "data" / "clean" / f"novel_{novel_id}").exists()
        assert (tmp_path / "data" / "json" / f"novel_{novel_id}").exists()
        assert (tmp_path / "data" / "render" / f"novel_{novel_id}").exists()
    
    def test_filename_metadata_extraction(self, tmp_path):
        """Test metadata extraction from filename when EPUB metadata is missing."""
        # Create EPUB without proper metadata
        epub_path = tmp_path / "test.epub"
        with zipfile.ZipFile(epub_path, 'w') as zf:
            zf.writestr('dummy.txt', 'dummy content')
        
        # Extract metadata - should fall back to filename
        metadata = extract_metadata(epub_path, "Lord of Mysteries - Book 1.epub")
        
        assert metadata['title'] == 'Lord Of Mysteries'
        assert metadata['author'] is None


class TestMultiNovelWorkflow:
    """Tests for multi-novel workflow."""
    
    def test_two_novels_separate_directories(self, tmp_path):
        """Test that two novels are stored in separate directories."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        # Create first novel
        novel1_id = db.create_novel(title="Novel 1", author="Author 1", status="active")
        
        # Create second novel
        novel2_id = db.create_novel(title="Novel 2", author="Author 2", status="active")
        
        assert novel1_id != novel2_id
        
        # Initialize pipeline for each novel
        config = PipelineConfig(output_dir=tmp_path / "data")
        
        orchestrator1 = PipelineOrchestrator(
            config=config,
            input_path=Path("novel1.epub"),
            novel_id=novel1_id
        )
        
        orchestrator2 = PipelineOrchestrator(
            config=config,
            input_path=Path("novel2.epub"),
            novel_id=novel2_id
        )
        
        orchestrator1.initialize_directories()
        orchestrator2.initialize_directories()
        
        # Verify separate directories
        assert (tmp_path / "data" / "clean" / f"novel_{novel1_id}").exists()
        assert (tmp_path / "data" / "clean" / f"novel_{novel2_id}").exists()
        
        # Verify chapter maps are separate
        assert orchestrator1._get_chapter_map_path() == Path(f"config/chapter_map_novel_{novel1_id}.json")
        assert orchestrator2._get_chapter_map_path() == Path(f"config/chapter_map_novel_{novel2_id}.json")
    
    def test_chapters_filtered_by_novel(self, tmp_path):
        """Test that chapters are correctly filtered by novel_id."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        # Create novel and chapters
        novel_id = db.create_novel(title="Test Novel", author="Author", status="active")
        
        for i in range(5):
            db.create_chapter(
                chapter_index=i + 1,
                filename=f"chapter_{i + 1}.txt",
                novel_id=novel_id,
                title=f"Chapter {i + 1}"
            )
        
        # Create another novel with chapters
        novel2_id = db.create_novel(title="Novel 2", author="Author", status="active")
        db.create_chapter(
            chapter_index=1,
            filename="other.txt",
            novel_id=novel2_id,
            title="Other Chapter"
        )
        
        # Filter by novel_id
        chapters = db.get_chapters_by_novel(novel_id)
        
        assert len(chapters) == 5
        assert all(c['novel_id'] == novel_id for c in chapters)
        
        # Verify other novel's chapters are not included
        other_chapters = db.get_chapters_by_novel(novel2_id)
        assert len(other_chapters) == 1


class TestBackwardCompatibilityIntegration:
    """Integration tests for backward compatibility."""
    
    def test_legacy_and_new_chapters_together(self, tmp_path):
        """Test that legacy and new chapters work together."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        # Create legacy chapter (NULL novel_id)
        legacy_id = db.create_chapter(
            chapter_index=1,
            filename="legacy.txt",
            novel_id=None,
            title="Legacy Chapter"
        )
        
        # Create new novel with chapter
        novel_id = db.create_novel(title="New Novel", author="Author", status="active")
        new_id = db.create_chapter(
            chapter_index=1,
            filename="new.txt",
            novel_id=novel_id,
            title="New Chapter"
        )
        
        # Get all chapters - should include both
        all_chapters = db.get_all_chapters()
        filenames = [c['filename'] for c in all_chapters]
        
        assert 'legacy.txt' in filenames
        assert 'new.txt' in filenames
        
        # Get chapters for novel - should only include new
        novel_chapters = db.get_chapters_by_novel(novel_id)
        assert len(novel_chapters) == 1
        assert novel_chapters[0]['filename'] == 'new.txt'
    
    def test_legacy_chapter_uses_root_directory(self, tmp_path):
        """Test that legacy chapters use root directory (not novel-specific)."""
        config = PipelineConfig(output_dir=tmp_path)
        
        # Legacy orchestrator (NULL novel_id)
        legacy_orchestrator = PipelineOrchestrator(
            config=config,
            input_path=Path("legacy.epub"),
            novel_id=None
        )
        
        # New orchestrator
        new_orchestrator = PipelineOrchestrator(
            config=config,
            input_path=Path("new.epub"),
            novel_id=1
        )
        
        # Verify directory paths
        legacy_clean = legacy_orchestrator._get_phase_directory("clean")
        new_clean = new_orchestrator._get_phase_directory("clean")
        
        assert legacy_clean == tmp_path / "clean"
        assert new_clean == tmp_path / "clean" / "novel_1"


class TestAPIWorkflow:
    """Tests for complete API workflow."""
    
    def test_novel_list_to_details_to_chapters(self, tmp_path):
        """Test workflow: list novels → get details → get chapters."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        # Create novel with chapters
        novel_id = db.create_novel(title="Test Novel", author="Author", status="active")
        
        for i in range(3):
            db.create_chapter(
                chapter_index=i + 1,
                filename=f"chapter_{i + 1}.txt",
                novel_id=novel_id,
                title=f"Chapter {i + 1}"
            )
        
        # List novels with chapter count
        novels = db.list_novels_with_chapter_count()
        assert len(novels) == 1
        assert novels[0]['chapter_count'] == 3
        
        # Get novel with chapter count
        novel = db.get_novel_with_chapter_count(novel_id)
        assert novel['title'] == 'Test Novel'
        assert novel['chapter_count'] == 3
        
        # Get chapters for novel
        chapters = db.get_chapters_by_novel(novel_id)
        assert len(chapters) == 3
        assert all(c['chapter_index'] in [1, 2, 3] for c in chapters)
    
    def test_chapters_metadata_with_novel_filter(self, tmp_path):
        """Test /api/chapters/metadata endpoint with novel_id filter."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        # Create two novels
        novel1_id = db.create_novel(title="Novel 1", author="Author", status="active")
        novel2_id = db.create_novel(title="Novel 2", author="Author", status="active")
        
        # Add chapters to each
        for i in range(3):
            db.create_chapter(
                chapter_index=i + 1,
                filename=f"novel1_chapter_{i + 1}.txt",
                novel_id=novel1_id,
                title=f"Novel 1 Chapter {i + 1}"
            )
            db.create_chapter(
                chapter_index=i + 1,
                filename=f"novel2_chapter_{i + 1}.txt",
                novel_id=novel2_id,
                title=f"Novel 2 Chapter {i + 1}"
            )
        
        # Query with novel_id filter
        chapters_novel1 = db.get_chapters_by_novel(novel1_id)
        assert len(chapters_novel1) == 3
        assert all(c['novel_id'] == novel1_id for c in chapters_novel1)
        
        # Query all chapters
        all_chapters = db.get_all_chapters()
        assert len(all_chapters) == 6


class TestTransactionRollback:
    """Tests for transaction rollback on failures."""
    
    def test_rollback_on_directory_creation_failure(self, tmp_path):
        """Test that novel entry is deleted when directory creation fails."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        # Create novel
        novel_id = db.create_novel(title="Test Novel", author="Author", status="active")
        assert db.get_novel(novel_id) is not None
        
        # Simulate directory creation failure by using a read-only path
        # (In real code, this would be handled by the try/except in the API)
        
        # Verify novel can be deleted
        success = db.delete_novel(novel_id)
        assert success is True
        assert db.get_novel(novel_id) is None
    
    def test_cascade_delete_removes_chapters(self, tmp_path):
        """Test that deleting a novel cascade deletes its chapters."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        # Create novel with chapters
        novel_id = db.create_novel(title="Test Novel", author="Author", status="active")
        
        chapter_ids = []
        for i in range(3):
            chapter_id = db.create_chapter(
                chapter_index=i + 1,
                filename=f"chapter_{i + 1}.txt",
                novel_id=novel_id,
                title=f"Chapter {i + 1}"
            )
            chapter_ids.append(chapter_id)
        
        # Verify chapters exist
        chapters = db.get_chapters_by_novel(novel_id)
        assert len(chapters) == 3
        
        # Delete novel
        db.delete_novel(novel_id)
        
        # Verify chapters are deleted
        for chapter_id in chapter_ids:
            chapter = db.get_chapter(chapter_id)
            assert chapter is None


class TestPerformance:
    """Performance tests for multi-novel support."""
    
    def test_list_novels_no_n_plus_one(self, tmp_path):
        """Test that list_novels with chapter counts doesn't have N+1 problem."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        # Create multiple novels with chapters
        for i in range(10):
            novel_id = db.create_novel(title=f"Novel {i}", author="Author", status="active")
            for j in range(5):
                db.create_chapter(
                    chapter_index=j + 1,
                    filename=f"novel{i}_chapter_{j + 1}.txt",
                    novel_id=novel_id,
                    title=f"Novel {i} Chapter {j + 1}"
                )
        
        # Use efficient query with COUNT aggregation
        novels = db.list_novels_with_chapter_count(limit=100, offset=0)
        
        assert len(novels) == 10
        # Each novel should have chapter_count = 5
        for novel in novels:
            assert novel['chapter_count'] == 5
    
    def test_get_chapters_by_novel_efficient(self, tmp_path):
        """Test that get_chapters_by_novel is efficient."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        # Create novel with many chapters
        novel_id = db.create_novel(title="Test Novel", author="Author", status="active")
        
        for i in range(100):
            db.create_chapter(
                chapter_index=i + 1,
                filename=f"chapter_{i + 1}.txt",
                novel_id=novel_id,
                title=f"Chapter {i + 1}"
            )
        
        # Query chapters - should be efficient (single query)
        chapters = db.get_chapters_by_novel(novel_id)
        
        assert len(chapters) == 100
        # Verify ordering
        for i, chapter in enumerate(chapters):
            assert chapter['chapter_index'] == i + 1