"""
Unit tests for PipelineOrchestrator directory management methods.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from babel.pipeline.orchestrator import PipelineOrchestrator
from babel.pipeline.core import PipelineConfig


@pytest.fixture
def mock_config():
    """Create a mock pipeline configuration."""
    config = MagicMock(spec=PipelineConfig)
    config.output_dir = Path("data")
    config.log_file = None
    return config


class TestGetPhaseDirectory:
    """Tests for _get_phase_directory method."""
    
    def test_with_novel_id(self, mock_config):
        """Test directory path with novel_id set."""
        orchestrator = PipelineOrchestrator(
            config=mock_config,
            input_path=Path("test.epub"),
            novel_id=42
        )
        
        clean_dir = orchestrator._get_phase_directory("clean")
        assert clean_dir == Path("data/clean/novel_42")
        
        json_dir = orchestrator._get_phase_directory("json")
        assert json_dir == Path("data/json/novel_42")
        
        render_dir = orchestrator._get_phase_directory("render")
        assert render_dir == Path("data/render/novel_42")
    
    def test_without_novel_id(self, mock_config):
        """Test directory path with novel_id=None for backward compatibility."""
        orchestrator = PipelineOrchestrator(
            config=mock_config,
            input_path=Path("test.epub"),
            novel_id=None
        )
        
        clean_dir = orchestrator._get_phase_directory("clean")
        assert clean_dir == Path("data/clean")
        
        json_dir = orchestrator._get_phase_directory("json")
        assert json_dir == Path("data/json")
        
        render_dir = orchestrator._get_phase_directory("render")
        assert render_dir == Path("data/render")


class TestGetChapterMapPath:
    """Tests for _get_chapter_map_path method."""
    
    def test_with_novel_id(self, mock_config):
        """Test chapter map path with novel_id set."""
        orchestrator = PipelineOrchestrator(
            config=mock_config,
            input_path=Path("test.epub"),
            novel_id=42
        )
        
        chapter_map_path = orchestrator._get_chapter_map_path()
        assert chapter_map_path == Path("config/chapter_map_novel_42.json")
    
    def test_without_novel_id(self, mock_config):
        """Test chapter map path with novel_id=None for backward compatibility."""
        orchestrator = PipelineOrchestrator(
            config=mock_config,
            input_path=Path("test.epub"),
            novel_id=None
        )
        
        chapter_map_path = orchestrator._get_chapter_map_path()
        assert chapter_map_path == Path("config/chapter_map.json")


class TestInitializeDirectories:
    """Tests for initialize_directories method."""
    
    def test_create_directories_with_novel_id(self, mock_config, tmp_path):
        """Test directory creation with novel_id set."""
        mock_config.output_dir = tmp_path
        
        orchestrator = PipelineOrchestrator(
            config=mock_config,
            input_path=Path("test.epub"),
            novel_id=42
        )
        
        # Initialize directories
        orchestrator.initialize_directories()
        
        # Verify directories were created
        assert (tmp_path / "clean" / "novel_42").exists()
        assert (tmp_path / "json" / "novel_42").exists()
        assert (tmp_path / "render" / "novel_42").exists()
    
    def test_create_directories_without_novel_id(self, mock_config, tmp_path):
        """Test directory creation with novel_id=None."""
        mock_config.output_dir = tmp_path
        
        orchestrator = PipelineOrchestrator(
            config=mock_config,
            input_path=Path("test.epub"),
            novel_id=None
        )
        
        # Initialize directories
        orchestrator.initialize_directories()
        
        # Verify root directories were created (no novel subdirectory)
        assert (tmp_path / "clean").exists()
        assert (tmp_path / "json").exists()
        assert (tmp_path / "render").exists()
    
    def test_create_directories_idempotent(self, mock_config, tmp_path):
        """Test that initialize_directories is idempotent."""
        mock_config.output_dir = tmp_path
        
        orchestrator = PipelineOrchestrator(
            config=mock_config,
            input_path=Path("test.epub"),
            novel_id=42
        )
        
        # Initialize directories twice
        orchestrator.initialize_directories()
        orchestrator.initialize_directories()
        
        # Should not raise an error
        assert (tmp_path / "clean" / "novel_42").exists()


class TestNovelIdPreservation:
    """Tests for novel_id preservation in orchestrator."""
    
    def test_novel_id_stored_in_constructor(self, mock_config):
        """Test that novel_id is stored as instance variable."""
        orchestrator = PipelineOrchestrator(
            config=mock_config,
            input_path=Path("test.epub"),
            novel_id=42
        )
        
        assert orchestrator.novel_id == 42
        assert orchestrator.current_novel_id == 42
    
    def test_novel_id_none_for_legacy(self, mock_config):
        """Test that novel_id can be None for legacy chapters."""
        orchestrator = PipelineOrchestrator(
            config=mock_config,
            input_path=Path("test.epub"),
            novel_id=None
        )
        
        assert orchestrator.novel_id is None
        assert orchestrator.current_novel_id is None
    
    def test_novel_id_in_progress(self, mock_config):
        """Test that novel_id is included in progress dict."""
        orchestrator = PipelineOrchestrator(
            config=mock_config,
            input_path=Path("test.epub"),
            novel_id=42
        )
        
        progress = orchestrator.get_progress()
        assert progress["novel_id"] == 42
    
    def test_novel_id_none_in_progress(self, mock_config):
        """Test that None novel_id is included in progress dict."""
        orchestrator = PipelineOrchestrator(
            config=mock_config,
            input_path=Path("test.epub"),
            novel_id=None
        )
        
        progress = orchestrator.get_progress()
        assert progress["novel_id"] is None