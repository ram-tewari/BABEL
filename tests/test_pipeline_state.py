"""
Unit tests for the pipeline state manager.

These tests validate specific examples and edge cases for state management.
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from babel.pipeline.state import (
    ChapterStatus,
    ChapterState,
    JobState,
    JobStateManager
)


class TestChapterStatus:
    """Test ChapterStatus enum."""
    
    def test_status_values(self):
        """Test that all status values are defined correctly."""
        assert ChapterStatus.RAW.value == "raw"
        assert ChapterStatus.CLEAN.value == "clean"
        assert ChapterStatus.JSON.value == "json"
        assert ChapterStatus.HTML.value == "html"
        assert ChapterStatus.FAILED.value == "failed"
        assert ChapterStatus.RENDER_FAILED.value == "render_failed"


class TestChapterState:
    """Test ChapterState model."""
    
    def test_create_chapter_state(self):
        """Test creating a chapter state."""
        state = ChapterState(
            index=0,
            filename="Ch_001.txt",
            title="Chapter 1"
        )
        
        assert state.index == 0
        assert state.filename == "Ch_001.txt"
        assert state.title == "Chapter 1"
        assert state.status == ChapterStatus.RAW
        assert state.error_message is None
        assert isinstance(state.last_updated, datetime)
    
    def test_chapter_state_with_error(self):
        """Test creating a chapter state with error message."""
        state = ChapterState(
            index=0,
            filename="Ch_001.txt",
            title="Chapter 1",
            status=ChapterStatus.FAILED,
            error_message="API timeout"
        )
        
        assert state.status == ChapterStatus.FAILED
        assert state.error_message == "API timeout"


class TestJobState:
    """Test JobState model."""
    
    def test_create_job_state(self):
        """Test creating a job state."""
        chapters = [
            ChapterState(index=0, filename="Ch_001.txt", title="Chapter 1"),
            ChapterState(index=1, filename="Ch_002.txt", title="Chapter 2")
        ]
        
        state = JobState(
            input_file="test.epub",
            chapters=chapters
        )
        
        assert state.input_file == "test.epub"
        assert len(state.chapters) == 2
        assert isinstance(state.started_at, datetime)
        assert isinstance(state.last_updated, datetime)


class TestJobStateManager:
    """Test JobStateManager class."""
    
    def test_initialize_new_state(self):
        """Test initializing a new job state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "job_status.json"
            manager = JobStateManager(state_file)
            
            chapters = [
                {'index': 0, 'filename': 'Ch_001.txt', 'title': 'Chapter 1'},
                {'index': 1, 'filename': 'Ch_002.txt', 'title': 'Chapter 2'}
            ]
            
            state = manager.initialize("test.epub", chapters)
            
            assert state.input_file == "test.epub"
            assert len(state.chapters) == 2
            assert state.chapters[0].status == ChapterStatus.RAW
            assert state.chapters[1].status == ChapterStatus.RAW
            
            # Verify state file was created
            assert state_file.exists()
    
    def test_load_existing_state(self):
        """Test loading existing state from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "job_status.json"
            
            # Create initial state
            manager1 = JobStateManager(state_file)
            chapters = [
                {'index': 0, 'filename': 'Ch_001.txt', 'title': 'Chapter 1'}
            ]
            manager1.initialize("test.epub", chapters)
            manager1.update_chapter(0, ChapterStatus.CLEAN)
            
            # Load state in new manager
            manager2 = JobStateManager(state_file)
            loaded_state = manager2.load()
            
            assert loaded_state is not None
            assert loaded_state.input_file == "test.epub"
            assert len(loaded_state.chapters) == 1
            assert loaded_state.chapters[0].status == ChapterStatus.CLEAN
    
    def test_load_nonexistent_state(self):
        """Test loading state when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "nonexistent.json"
            manager = JobStateManager(state_file)
            
            loaded_state = manager.load()
            
            assert loaded_state is None
    
    def test_load_corrupted_state(self):
        """Test loading corrupted state file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "job_status.json"
            
            # Write invalid JSON
            with open(state_file, 'w') as f:
                f.write("{ invalid json }")
            
            manager = JobStateManager(state_file)
            loaded_state = manager.load()
            
            assert loaded_state is None
    
    def test_update_chapter_status(self):
        """Test updating chapter status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "job_status.json"
            manager = JobStateManager(state_file)
            
            chapters = [
                {'index': 0, 'filename': 'Ch_001.txt', 'title': 'Chapter 1'}
            ]
            manager.initialize("test.epub", chapters)
            
            # Update chapter status
            manager.update_chapter(0, ChapterStatus.JSON)
            
            assert manager.state.chapters[0].status == ChapterStatus.JSON
            
            # Verify state was persisted
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            assert data['chapters'][0]['status'] == 'json'
    
    def test_update_chapter_with_error(self):
        """Test updating chapter status with error message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "job_status.json"
            manager = JobStateManager(state_file)
            
            chapters = [
                {'index': 0, 'filename': 'Ch_001.txt', 'title': 'Chapter 1'}
            ]
            manager.initialize("test.epub", chapters)
            
            # Update chapter with error
            manager.update_chapter(0, ChapterStatus.FAILED, "API timeout")
            
            assert manager.state.chapters[0].status == ChapterStatus.FAILED
            assert manager.state.chapters[0].error_message == "API timeout"
    
    def test_update_invalid_chapter_index(self):
        """Test updating chapter with invalid index."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "job_status.json"
            manager = JobStateManager(state_file)
            
            chapters = [
                {'index': 0, 'filename': 'Ch_001.txt', 'title': 'Chapter 1'}
            ]
            manager.initialize("test.epub", chapters)
            
            # Try to update invalid index
            with pytest.raises(ValueError, match="Invalid chapter index"):
                manager.update_chapter(10, ChapterStatus.JSON)
    
    def test_should_skip_chapter_already_complete(self):
        """Test skipping already-processed chapters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "job_status.json"
            manager = JobStateManager(state_file)
            
            chapters = [
                {'index': 0, 'filename': 'Ch_001.txt', 'title': 'Chapter 1'}
            ]
            manager.initialize("test.epub", chapters)
            
            # Mark chapter as JSON
            manager.update_chapter(0, ChapterStatus.JSON)
            
            # Should skip for JSON phase
            assert manager.should_skip_chapter(0, ChapterStatus.JSON)
            
            # Should also skip for earlier phases
            assert manager.should_skip_chapter(0, ChapterStatus.CLEAN)
            
            # Should not skip for later phases
            assert not manager.should_skip_chapter(0, ChapterStatus.HTML)
    
    def test_should_not_skip_failed_chapters(self):
        """Test that failed chapters are not skipped by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "job_status.json"
            manager = JobStateManager(state_file)
            
            chapters = [
                {'index': 0, 'filename': 'Ch_001.txt', 'title': 'Chapter 1'}
            ]
            manager.initialize("test.epub", chapters)
            
            # Mark chapter as FAILED
            manager.update_chapter(0, ChapterStatus.FAILED)
            
            # Should not skip (needs explicit --retry-failed flag)
            assert not manager.should_skip_chapter(0, ChapterStatus.JSON)
            
            # Mark chapter as RENDER_FAILED
            manager.update_chapter(0, ChapterStatus.RENDER_FAILED)
            
            # Should not skip
            assert not manager.should_skip_chapter(0, ChapterStatus.HTML)
    
    def test_get_chapters_for_phase_0(self):
        """Test getting chapters for Phase 0 (sanitization)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "job_status.json"
            manager = JobStateManager(state_file)
            
            chapters = [
                {'index': 0, 'filename': 'Ch_001.txt', 'title': 'Chapter 1'},
                {'index': 1, 'filename': 'Ch_002.txt', 'title': 'Chapter 2'}
            ]
            manager.initialize("test.epub", chapters)
            
            # All chapters should be RAW initially
            phase_0_chapters = manager.get_chapters_for_phase(0)
            assert len(phase_0_chapters) == 2
            
            # Mark one chapter as CLEAN
            manager.update_chapter(0, ChapterStatus.CLEAN)
            
            # Only one chapter should need Phase 0
            phase_0_chapters = manager.get_chapters_for_phase(0)
            assert len(phase_0_chapters) == 1
            assert phase_0_chapters[0].index == 1
    
    def test_get_chapters_for_phase_1(self):
        """Test getting chapters for Phase 1 (transformation)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "job_status.json"
            manager = JobStateManager(state_file)
            
            chapters = [
                {'index': 0, 'filename': 'Ch_001.txt', 'title': 'Chapter 1'},
                {'index': 1, 'filename': 'Ch_002.txt', 'title': 'Chapter 2'}
            ]
            manager.initialize("test.epub", chapters)
            
            # Mark chapters as CLEAN
            manager.update_chapter(0, ChapterStatus.CLEAN)
            manager.update_chapter(1, ChapterStatus.CLEAN)
            
            # Both chapters should need Phase 1
            phase_1_chapters = manager.get_chapters_for_phase(1)
            assert len(phase_1_chapters) == 2
            
            # Mark one chapter as JSON
            manager.update_chapter(0, ChapterStatus.JSON)
            
            # Only one chapter should need Phase 1
            phase_1_chapters = manager.get_chapters_for_phase(1)
            assert len(phase_1_chapters) == 1
            assert phase_1_chapters[0].index == 1
    
    def test_get_chapters_for_phase_2(self):
        """Test getting chapters for Phase 2 (rendering)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "job_status.json"
            manager = JobStateManager(state_file)
            
            chapters = [
                {'index': 0, 'filename': 'Ch_001.txt', 'title': 'Chapter 1'},
                {'index': 1, 'filename': 'Ch_002.txt', 'title': 'Chapter 2'}
            ]
            manager.initialize("test.epub", chapters)
            
            # Mark chapters as JSON
            manager.update_chapter(0, ChapterStatus.JSON)
            manager.update_chapter(1, ChapterStatus.JSON)
            
            # Both chapters should need Phase 2
            phase_2_chapters = manager.get_chapters_for_phase(2)
            assert len(phase_2_chapters) == 2
            
            # Mark one chapter as HTML
            manager.update_chapter(0, ChapterStatus.HTML)
            
            # Only one chapter should need Phase 2
            phase_2_chapters = manager.get_chapters_for_phase(2)
            assert len(phase_2_chapters) == 1
            assert phase_2_chapters[0].index == 1
    
    def test_get_chapters_for_invalid_phase(self):
        """Test getting chapters for invalid phase."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "job_status.json"
            manager = JobStateManager(state_file)
            
            chapters = [
                {'index': 0, 'filename': 'Ch_001.txt', 'title': 'Chapter 1'}
            ]
            manager.initialize("test.epub", chapters)
            
            # Try to get chapters for invalid phase
            with pytest.raises(ValueError, match="Invalid phase"):
                manager.get_chapters_for_phase(99)
    
    def test_state_persistence_immediate(self):
        """Test that state is persisted immediately after updates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "job_status.json"
            manager = JobStateManager(state_file)
            
            chapters = [
                {'index': 0, 'filename': 'Ch_001.txt', 'title': 'Chapter 1'}
            ]
            manager.initialize("test.epub", chapters)
            
            # Get initial modification time
            initial_mtime = state_file.stat().st_mtime
            
            # Small delay to ensure different timestamp
            import time
            time.sleep(0.01)
            
            # Update chapter
            manager.update_chapter(0, ChapterStatus.CLEAN)
            
            # Verify file was modified
            new_mtime = state_file.stat().st_mtime
            assert new_mtime > initial_mtime
            
            # Verify content is correct
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            assert data['chapters'][0]['status'] == 'clean'
