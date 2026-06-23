"""
Unit tests for backward compatibility with legacy chapters (NULL novel_id).
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from babel.pipeline.orchestrator import PipelineOrchestrator
from babel.pipeline.core import PipelineConfig
from babel.data.db import DatabaseManager


class TestNullNovelIdDirectoryManagement:
    """Tests for backward compatibility with NULL novel_id."""
    
    def test_phase_directory_returns_root_for_null_novel_id(self, tmp_path):
        """Test that NULL novel_id returns root phase directory."""
        mock_config = MagicMock(spec=PipelineConfig)
        mock_config.output_dir = tmp_path
        mock_config.log_file = None
        
        orchestrator = PipelineOrchestrator(
            config=mock_config,
            input_path=Path("test.epub"),
            novel_id=None
        )
        
        clean_dir = orchestrator._get_phase_directory("clean")
        assert clean_dir == tmp_path / "clean"
        
        json_dir = orchestrator._get_phase_directory("json")
        assert json_dir == tmp_path / "json"
        
        render_dir = orchestrator._get_phase_directory("render")
        assert render_dir == tmp_path / "render"
    
    def test_chapter_map_path_returns_legacy_for_null_novel_id(self):
        """Test that NULL novel_id returns legacy chapter_map.json."""
        mock_config = MagicMock(spec=PipelineConfig)
        mock_config.output_dir = Path("data")
        mock_config.log_file = None
        
        orchestrator = PipelineOrchestrator(
            config=mock_config,
            input_path=Path("test.epub"),
            novel_id=None
        )
        
        chapter_map_path = orchestrator._get_chapter_map_path()
        assert chapter_map_path == Path("config/chapter_map.json")
    
    def test_initialize_directories_creates_root_for_null_novel_id(self, tmp_path):
        """Test that NULL novel_id creates root directories (no subdirectory)."""
        mock_config = MagicMock(spec=PipelineConfig)
        mock_config.output_dir = tmp_path
        mock_config.log_file = None
        
        orchestrator = PipelineOrchestrator(
            config=mock_config,
            input_path=Path("test.epub"),
            novel_id=None
        )
        
        orchestrator.initialize_directories()
        
        # Should create root directories
        assert (tmp_path / "clean").exists()
        assert (tmp_path / "json").exists()
        assert (tmp_path / "render").exists()
        
        # Should NOT create novel subdirectories
        assert not (tmp_path / "clean" / "novel_None").exists()
        assert not (tmp_path / "json" / "novel_None").exists()
        assert not (tmp_path / "render" / "novel_None").exists()


class TestLegacyChapterQueries:
    """Tests for database queries with legacy chapters (NULL novel_id)."""
    
    def test_get_all_chapters_includes_null_novel_id(self, tmp_path):
        """Test that get_all_chapters returns chapters with NULL novel_id."""
        # This test requires a real database
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        # Create a chapter with NULL novel_id (legacy)
        chapter_id = db.create_chapter(
            chapter_index=1,
            filename="legacy_chapter.txt",
            novel_id=None,  # Legacy chapter
            title="Legacy Chapter 1"
        )
        
        # Create a chapter with a novel_id (new)
        novel_id = db.create_novel(title="Test Novel", author="Test Author", status="active")
        chapter_id2 = db.create_chapter(
            chapter_index=1,
            filename="new_chapter.txt",
            novel_id=novel_id,
            title="New Chapter 1"
        )
        
        # Get all chapters
        all_chapters = db.get_all_chapters()
        
        # Should include both chapters
        assert len(all_chapters) >= 2
        
        # Find our chapters
        legacy_chapters = [c for c in all_chapters if c.get("novel_id") is None]
        new_chapters = [c for c in all_chapters if c.get("novel_id") is not None]
        
        assert len(legacy_chapters) >= 1
        assert len(new_chapters) >= 1
        
        # Verify legacy chapter is included
        legacy_found = any(c["filename"] == "legacy_chapter.txt" for c in all_chapters)
        assert legacy_found
    
    def test_get_chapters_by_novel_excludes_null_novel_id(self, tmp_path):
        """Test that get_chapters_by_novel only returns chapters for specific novel."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        # Create a chapter with NULL novel_id (legacy)
        db.create_chapter(
            chapter_index=1,
            filename="legacy_chapter.txt",
            novel_id=None,
            title="Legacy Chapter 1"
        )
        
        # Create a novel and chapter
        novel_id = db.create_novel(title="Test Novel", author="Test Author", status="active")
        db.create_chapter(
            chapter_index=1,
            filename="new_chapter.txt",
            novel_id=novel_id,
            title="New Chapter 1"
        )
        
        # Get chapters for the novel
        novel_chapters = db.get_chapters_by_novel(novel_id)
        
        # Should only include the new chapter
        assert len(novel_chapters) == 1
        assert novel_chapters[0]["filename"] == "new_chapter.txt"
        assert novel_chapters[0]["novel_id"] == novel_id


class TestNovelIdPreservation:
    """Tests for novel_id preservation in various scenarios."""
    
    def test_novel_id_none_for_legacy_chapters(self, tmp_path):
        """Test that legacy chapters have NULL novel_id."""
        mock_config = MagicMock(spec=PipelineConfig)
        mock_config.output_dir = tmp_path
        mock_config.log_file = None
        
        orchestrator = PipelineOrchestrator(
            config=mock_config,
            input_path=Path("test.epub"),
            novel_id=None
        )
        
        # Verify novel_id is None
        assert orchestrator.novel_id is None
        assert orchestrator.current_novel_id is None
        
        # Verify directory paths don't include novel subdirectory (novel_None or novel_123)
        phase_dir = orchestrator._get_phase_directory("clean")
        phase_dir_str = str(phase_dir)
        # Check that it doesn't end with "novel_None" or contain "novel_" followed by digits
        import re
        assert not re.search(r'novel_\d+', phase_dir_str), f"Found novel_N in path: {phase_dir_str}"
        assert not phase_dir_str.endswith("novel_None"), f"Found novel_None in path: {phase_dir_str}"
    
    def test_novel_id_preserved_in_progress(self, tmp_path):
        """Test that NULL novel_id is included in progress dict."""
        mock_config = MagicMock(spec=PipelineConfig)
        mock_config.output_dir = tmp_path
        mock_config.log_file = None
        
        orchestrator = PipelineOrchestrator(
            config=mock_config,
            input_path=Path("test.epub"),
            novel_id=None
        )
        
        progress = orchestrator.get_progress()
        assert progress["novel_id"] is None


class TestMixedLegacyAndNewData:
    """Tests for handling mixed legacy and new data."""
    
    def test_legacy_and_new_chapters_coexist(self, tmp_path):
        """Test that legacy and new chapters can coexist in the database."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        # Create legacy chapter
        legacy_id = db.create_chapter(
            chapter_index=1,
            filename="legacy.txt",
            novel_id=None,
            title="Legacy Chapter"
        )
        
        # Create novel and new chapter
        novel_id = db.create_novel(title="New Novel", author="Author", status="active")
        new_id = db.create_chapter(
            chapter_index=1,
            filename="new.txt",
            novel_id=novel_id,
            title="New Chapter"
        )
        
        # Verify both exist
        legacy = db.get_chapter(legacy_id)
        new = db.get_chapter(new_id)
        
        assert legacy is not None
        assert new is not None
        assert legacy["novel_id"] is None
        assert new["novel_id"] == novel_id
        
        # Verify all chapters query returns both
        all_chapters = db.get_all_chapters()
        filenames = [c["filename"] for c in all_chapters]
        assert "legacy.txt" in filenames
        assert "new.txt" in filenames
    
    def test_delete_novel_does_not_affect_legacy(self, tmp_path):
        """Test that deleting a novel doesn't affect legacy chapters."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        # Create legacy chapter
        legacy_id = db.create_chapter(
            chapter_index=1,
            filename="legacy.txt",
            novel_id=None,
            title="Legacy Chapter"
        )
        
        # Create novel and chapter
        novel_id = db.create_novel(title="Test Novel", author="Author", status="active")
        new_id = db.create_chapter(
            chapter_index=1,
            filename="new.txt",
            novel_id=novel_id,
            title="New Chapter"
        )
        
        # Delete the novel
        db.delete_novel(novel_id)
        
        # Verify legacy chapter still exists
        legacy = db.get_chapter(legacy_id)
        assert legacy is not None
        
        # Verify new chapter is deleted
        new = db.get_chapter(new_id)
        assert new is None