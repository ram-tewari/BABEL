"""
Tests for database layer operations.
"""

import pytest
import tempfile
from pathlib import Path
from babel.data.db import DatabaseManager


@pytest.fixture
def db_manager():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_babel.db"
        db = DatabaseManager(db_path)
        yield db
        db.close()


class TestPipelineStateOperations:
    """Tests for pipeline state CRUD operations."""
    
    def test_update_pipeline_state_creates_new_state(self, db_manager):
        """Test that update_pipeline_state creates a new state entry."""
        novel_id = db_manager.create_novel(title="Test Novel")
        
        result = db_manager.update_pipeline_state(
            novel_id=novel_id,
            phase="sanitize",
            status="running",
            last_chapter=0,
            total_chapters=10
        )
        
        assert result is not None
        assert result > 0
    
    def test_update_pipeline_state_updates_existing_state(self, db_manager):
        """Test that update_pipeline_state updates an existing state entry."""
        novel_id = db_manager.create_novel(title="Test Novel")
        
        # Create initial state
        state_id = db_manager.update_pipeline_state(
            novel_id=novel_id,
            phase="sanitize",
            status="running",
            last_chapter=0,
            total_chapters=10
        )
        
        # Update the state
        updated_id = db_manager.update_pipeline_state(
            novel_id=novel_id,
            phase="sanitize",
            status="complete",
            last_chapter=10,
            total_chapters=10
        )
        
        assert updated_id == state_id
        
        # Verify the update
        state = db_manager.get_pipeline_state(novel_id=novel_id, phase="sanitize")
        assert state is not None
        assert state["status"] == "complete"
        assert state["last_chapter"] == 10
    
    def test_update_pipeline_state_with_error_message(self, db_manager):
        """Test that update_pipeline_state stores error messages."""
        novel_id = db_manager.create_novel(title="Test Novel")
        
        db_manager.update_pipeline_state(
            novel_id=novel_id,
            phase="sanitize",
            status="failed",
            error_message="Failed to parse EPUB file"
        )
        
        state = db_manager.get_pipeline_state(novel_id=novel_id, phase="sanitize")
        assert state is not None
        assert state["status"] == "failed"
        assert state["error_message"] == "Failed to parse EPUB file"
    
    def test_get_pipeline_state_returns_state(self, db_manager):
        """Test that get_pipeline_state returns the correct state."""
        novel_id = db_manager.create_novel(title="Test Novel")
        
        db_manager.update_pipeline_state(
            novel_id=novel_id,
            phase="transform",
            status="running",
            last_chapter=5,
            total_chapters=20
        )
        
        state = db_manager.get_pipeline_state(novel_id=novel_id, phase="transform")
        
        assert state is not None
        assert state["novel_id"] == novel_id
        assert state["phase"] == "transform"
        assert state["status"] == "running"
        assert state["last_chapter"] == 5
        assert state["total_chapters"] == 20
    
    def test_get_pipeline_state_returns_none_for_missing(self, db_manager):
        """Test that get_pipeline_state returns None for non-existent state."""
        novel_id = db_manager.create_novel(title="Test Novel")
        
        state = db_manager.get_pipeline_state(novel_id=novel_id, phase="nonexistent")
        
        assert state is None
    
    def test_pipeline_state_legacy_support_null_novel_id(self, db_manager):
        """Test pipeline state operations with NULL novel_id for backward compatibility."""
        # Create pipeline state without novel_id (legacy mode)
        state_id = db_manager.update_pipeline_state(
            novel_id=None,
            phase="sanitize",
            status="complete",
            last_chapter=10,
            total_chapters=10
        )
        
        assert state_id is not None
        assert state_id > 0
        
        # Retrieve the state
        state = db_manager.get_pipeline_state(novel_id=None, phase="sanitize")
        
        assert state is not None
        assert state["novel_id"] is None
        assert state["phase"] == "sanitize"
        assert state["status"] == "complete"
    
    def test_pipeline_state_multiple_phases(self, db_manager):
        """Test that multiple pipeline phases can be tracked independently."""
        novel_id = db_manager.create_novel(title="Test Novel")
        
        # Create states for different phases
        db_manager.update_pipeline_state(novel_id=novel_id, phase="sanitize", status="complete", last_chapter=10, total_chapters=10)
        db_manager.update_pipeline_state(novel_id=novel_id, phase="transform", status="running", last_chapter=5, total_chapters=10)
        db_manager.update_pipeline_state(novel_id=novel_id, phase="render", status="pending")
        
        # Verify each phase has correct state
        sanitize_state = db_manager.get_pipeline_state(novel_id=novel_id, phase="sanitize")
        transform_state = db_manager.get_pipeline_state(novel_id=novel_id, phase="transform")
        render_state = db_manager.get_pipeline_state(novel_id=novel_id, phase="render")
        
        assert sanitize_state["status"] == "complete"
        assert transform_state["status"] == "running"
        assert render_state["status"] == "pending"
    
    def test_pipeline_state_unique_constraint(self, db_manager):
        """Test that each (novel_id, phase) combination is unique."""
        novel_id = db_manager.create_novel(title="Test Novel")
        
        # Create initial state
        state_id1 = db_manager.update_pipeline_state(
            novel_id=novel_id,
            phase="sanitize",
            status="pending"
        )
        
        # Update same phase - should not create new row
        state_id2 = db_manager.update_pipeline_state(
            novel_id=novel_id,
            phase="sanitize",
            status="running"
        )
        
        assert state_id1 == state_id2
        
        # Verify only one state exists for this phase
        all_states = db_manager.get_all_pipeline_states(novel_id=novel_id)
        phase_states = [s for s in all_states if s["phase"] == "sanitize"]
        assert len(phase_states) == 1


class TestNovelOperations:
    """Tests for novel CRUD operations."""
    
    def test_create_novel(self, db_manager):
        """Test creating a novel."""
        novel_id = db_manager.create_novel(
            title="Test Novel",
            author="Test Author"
        )
        
        assert novel_id is not None
        assert novel_id > 0
        
        novel = db_manager.get_novel(novel_id)
        assert novel is not None
        assert novel["title"] == "Test Novel"
        assert novel["author"] == "Test Author"
    
    def test_get_novel_not_found(self, db_manager):
        """Test getting a non-existent novel."""
        novel = db_manager.get_novel(99999)
        assert novel is None
    
    def test_list_novels(self, db_manager):
        """Test listing novels."""
        # Create multiple novels
        id1 = db_manager.create_novel(title="Novel 1")
        id2 = db_manager.create_novel(title="Novel 2")
        id3 = db_manager.create_novel(title="Novel 3")
        
        novels = db_manager.list_novels(limit=10, offset=0)
        
        assert len(novels) == 3
        # Should be sorted by updated_at descending
        assert novels[0]["title"] == "Novel 3"
        assert novels[2]["title"] == "Novel 1"
    
    def test_update_novel(self, db_manager):
        """Test updating a novel."""
        novel_id = db_manager.create_novel(title="Original Title")
        
        result = db_manager.update_novel(novel_id, title="Updated Title")
        
        assert result is True
        
        novel = db_manager.get_novel(novel_id)
        assert novel["title"] == "Updated Title"
    
    def test_delete_novel(self, db_manager):
        """Test deleting a novel."""
        novel_id = db_manager.create_novel(title="To Delete")
        
        result = db_manager.delete_novel(novel_id)
        
        assert result is True
        assert db_manager.get_novel(novel_id) is None


class TestChapterOperations:
    """Tests for chapter CRUD operations."""
    
    def test_create_chapter(self, db_manager):
        """Test creating a chapter."""
        novel_id = db_manager.create_novel(title="Test Novel")
        
        chapter_id = db_manager.create_chapter(
            novel_id=novel_id,
            chapter_index=1,
            filename="chapter_01.txt",
            title="Chapter 1"
        )
        
        assert chapter_id is not None
        assert chapter_id > 0
    
    def test_get_chapters_by_novel(self, db_manager):
        """Test getting chapters for a novel."""
        novel_id = db_manager.create_novel(title="Test Novel")
        
        # Create multiple chapters
        for i in range(1, 6):
            db_manager.create_chapter(
                novel_id=novel_id,
                chapter_index=i,
                filename=f"chapter_{i:02d}.txt"
            )
        
        chapters = db_manager.get_chapters_by_novel(novel_id)
        
        assert len(chapters) == 5
        # Should be ordered by chapter_index
        assert chapters[0]["chapter_index"] == 1
        assert chapters[4]["chapter_index"] == 5
    
    def test_update_chapter_novel(self, db_manager):
        """Test associating a chapter with a novel."""
        # Create chapter without novel_id
        chapter_id = db_manager.create_chapter(
            novel_id=None,
            chapter_index=1,
            filename="orphan_chapter.txt"
        )
        
        # Create novel and associate
        novel_id = db_manager.create_novel(title="New Novel")
        
        result = db_manager.update_chapter_novel(chapter_id, novel_id)
        
        assert result is True
        
        chapter = db_manager.get_chapter(chapter_id)
        assert chapter["novel_id"] == novel_id