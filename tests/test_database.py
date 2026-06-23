"""
Unit tests for DatabaseManager.

Tests thread-safety, transactions, and CRUD operations for the
multi-novel library management system.
"""

import pytest
import threading
import time
from pathlib import Path
from datetime import datetime, timezone
from babel.data.db import DatabaseManager


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test_babel.db"
    db = DatabaseManager(db_path)
    yield db
    db.close()


@pytest.fixture
def sample_novel(temp_db):
    """Create a sample novel for testing."""
    novel_id = temp_db.create_novel(
        title="Test Novel",
        author="Test Author",
        cover_url="https://example.com/cover.jpg",
        status="active"
    )
    return novel_id


class TestDatabaseInitialization:
    """Test database initialization and schema creation."""
    
    def test_database_file_created(self, temp_db):
        """Test that database file is created."""
        assert temp_db.db_path.exists()
    
    def test_tables_created(self, temp_db):
        """Test that all tables are created."""
        with temp_db.transaction() as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                ORDER BY name
            """)
            tables = [row[0] for row in cursor.fetchall()]
        
        assert 'novels' in tables
        assert 'chapters' in tables
        assert 'pipeline_state' in tables
    
    def test_indexes_created(self, temp_db):
        """Test that indexes are created."""
        with temp_db.transaction() as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' 
                ORDER BY name
            """)
            indexes = [row[0] for row in cursor.fetchall()]
        
        assert 'idx_chapters_novel' in indexes
        assert 'idx_pipeline_novel' in indexes
        assert 'idx_novels_updated' in indexes


class TestNovelOperations:
    """Test novel CRUD operations."""
    
    def test_create_novel(self, temp_db):
        """Test creating a novel."""
        novel_id = temp_db.create_novel(
            title="Test Novel",
            author="Test Author",
            cover_url="https://example.com/cover.jpg",
            status="active"
        )
        
        assert novel_id is not None
        assert novel_id > 0
    
    def test_create_novel_minimal(self, temp_db):
        """Test creating a novel with minimal fields."""
        novel_id = temp_db.create_novel(title="Minimal Novel")
        
        assert novel_id is not None
        novel = temp_db.get_novel(novel_id)
        assert novel['title'] == "Minimal Novel"
        assert novel['author'] is None
        assert novel['status'] == "active"
    
    def test_get_novel(self, temp_db, sample_novel):
        """Test getting a novel by ID."""
        novel = temp_db.get_novel(sample_novel)
        
        assert novel is not None
        assert novel['id'] == sample_novel
        assert novel['title'] == "Test Novel"
        assert novel['author'] == "Test Author"
    
    def test_get_nonexistent_novel(self, temp_db):
        """Test getting nonexistent novel returns None."""
        novel = temp_db.get_novel(99999)
        assert novel is None
    
    def test_list_novels(self, temp_db):
        """Test listing novels sorted by updated_at descending."""
        # Create multiple novels
        temp_db.create_novel(title="Novel 1")
        time.sleep(0.01)  # Ensure different timestamps
        temp_db.create_novel(title="Novel 2")
        time.sleep(0.01)
        temp_db.create_novel(title="Novel 3")
        
        novels = temp_db.list_novels()
        
        assert len(novels) >= 3
        # Should be sorted by updated_at descending (newest first)
        assert novels[0]['title'] == "Novel 3"
        assert novels[1]['title'] == "Novel 2"
        assert novels[2]['title'] == "Novel 1"
    
    def test_list_novels_with_limit(self, temp_db):
        """Test listing novels with limit."""
        for i in range(5):
            temp_db.create_novel(title=f"Novel {i}")
        
        novels = temp_db.list_novels(limit=3)
        
        assert len(novels) == 3
    
    def test_list_novels_with_offset(self, temp_db):
        """Test listing novels with offset."""
        for i in range(5):
            temp_db.create_novel(title=f"Novel {i}")
        
        novels = temp_db.list_novels(limit=3, offset=2)
        
        assert len(novels) == 3
        # Should skip the first 2 (newest) novels
        assert novels[0]['title'] == "Novel 2"
    
    def test_update_novel(self, temp_db, sample_novel):
        """Test updating novel metadata."""
        result = temp_db.update_novel(
            sample_novel,
            title="Updated Title",
            status="completed"
        )
        
        assert result is True
        novel = temp_db.get_novel(sample_novel)
        assert novel['title'] == "Updated Title"
        assert novel['status'] == "completed"
    
    def test_update_novel_partial(self, temp_db, sample_novel):
        """Test partial novel update."""
        temp_db.update_novel(sample_novel, author="New Author")
        
        novel = temp_db.get_novel(sample_novel)
        assert novel['author'] == "New Author"
        assert novel['title'] == "Test Novel"  # Unchanged
    
    def test_delete_novel(self, temp_db, sample_novel):
        """Test deleting a novel."""
        result = temp_db.delete_novel(sample_novel)
        
        assert result is True
        novel = temp_db.get_novel(sample_novel)
        assert novel is None


class TestChapterOperations:
    """Test chapter CRUD operations."""
    
    def test_create_chapter(self, temp_db, sample_novel):
        """Test creating a chapter."""
        chapter_id = temp_db.create_chapter(
            novel_id=sample_novel,
            chapter_index=1,
            filename="Ch_001.txt",
            title="Chapter 1"
        )
        
        assert chapter_id is not None
        assert chapter_id > 0
    
    def test_create_chapter_without_novel(self, temp_db):
        """Test creating a chapter without novel_id (backward compatibility)."""
        chapter_id = temp_db.create_chapter(
            novel_id=None,
            chapter_index=1,
            filename="Ch_001.txt"
        )
        
        assert chapter_id is not None
        chapter = temp_db.get_chapter(chapter_id)
        assert chapter['novel_id'] is None
    
    def test_get_chapter(self, temp_db, sample_novel):
        """Test getting a chapter by ID."""
        chapter_id = temp_db.create_chapter(
            novel_id=sample_novel,
            chapter_index=1,
            filename="Ch_001.txt"
        )
        
        chapter = temp_db.get_chapter(chapter_id)
        
        assert chapter is not None
        assert chapter['id'] == chapter_id
        assert chapter['novel_id'] == sample_novel
        assert chapter['chapter_index'] == 1
    
    def test_get_chapters_by_novel(self, temp_db, sample_novel):
        """Test getting all chapters for a novel."""
        # Create multiple chapters
        for i in range(1, 6):
            temp_db.create_chapter(
                novel_id=sample_novel,
                chapter_index=i,
                filename=f"Ch_{i:03d}.txt",
                title=f"Chapter {i}"
            )
        
        chapters = temp_db.get_chapters_by_novel(sample_novel)
        
        assert len(chapters) == 5
        # Should be sorted by chapter_index ascending
        assert chapters[0]['chapter_index'] == 1
        assert chapters[4]['chapter_index'] == 5
    
    def test_get_all_chapters(self, temp_db, sample_novel):
        """Test getting all chapters including legacy ones."""
        # Create chapters with and without novel_id
        temp_db.create_chapter(novel_id=sample_novel, chapter_index=1, filename="Ch_001.txt")
        temp_db.create_chapter(novel_id=None, chapter_index=1, filename="Legacy_001.txt")
        
        chapters = temp_db.get_all_chapters()
        
        assert len(chapters) >= 2
    
    def test_update_chapter_novel(self, temp_db, sample_novel):
        """Test associating a chapter with a novel."""
        chapter_id = temp_db.create_chapter(
            novel_id=None,
            chapter_index=1,
            filename="Ch_001.txt"
        )
        
        result = temp_db.update_chapter_novel(chapter_id, sample_novel)
        
        assert result is True
        chapter = temp_db.get_chapter(chapter_id)
        assert chapter['novel_id'] == sample_novel
    
    def test_update_chapter(self, temp_db, sample_novel):
        """Test updating chapter metadata."""
        chapter_id = temp_db.create_chapter(
            novel_id=sample_novel,
            chapter_index=1,
            filename="Ch_001.txt"
        )
        
        result = temp_db.update_chapter(
            chapter_id,
            title="Updated Chapter Title"
        )
        
        assert result is True
        chapter = temp_db.get_chapter(chapter_id)
        assert chapter['title'] == "Updated Chapter Title"
    
    def test_delete_chapter(self, temp_db, sample_novel):
        """Test deleting a chapter."""
        chapter_id = temp_db.create_chapter(
            novel_id=sample_novel,
            chapter_index=1,
            filename="Ch_001.txt"
        )
        
        result = temp_db.delete_chapter(chapter_id)
        
        assert result is True
        chapter = temp_db.get_chapter(chapter_id)
        assert chapter is None


class TestCascadeDeletion:
    """Test cascade deletion of chapters when novel is deleted."""
    
    def test_delete_novel_cascades_chapters(self, temp_db):
        """Test that deleting a novel deletes all associated chapters."""
        novel_id = temp_db.create_novel(title="Test Novel")
        
        # Create chapters
        for i in range(1, 6):
            temp_db.create_chapter(
                novel_id=novel_id,
                chapter_index=i,
                filename=f"Ch_{i:03d}.txt"
            )
        
        # Verify chapters exist
        chapters = temp_db.get_chapters_by_novel(novel_id)
        assert len(chapters) == 5
        
        # Delete novel
        temp_db.delete_novel(novel_id)
        
        # Verify chapters are deleted
        chapters = temp_db.get_chapters_by_novel(novel_id)
        assert len(chapters) == 0
    
    def test_delete_novel_preserves_legacy_chapters(self, temp_db):
        """Test that deleting a novel doesn't affect chapters with NULL novel_id."""
        # Create a novel and chapters
        novel_id = temp_db.create_novel(title="Test Novel")
        temp_db.create_chapter(novel_id=novel_id, chapter_index=1, filename="Ch_001.txt")
        
        # Create legacy chapters (no novel_id)
        legacy_id = temp_db.create_chapter(novel_id=None, chapter_index=1, filename="Legacy_001.txt")
        
        # Delete novel
        temp_db.delete_novel(novel_id)
        
        # Verify legacy chapter still exists
        legacy_chapter = temp_db.get_chapter(legacy_id)
        assert legacy_chapter is not None


class TestPipelineStateOperations:
    """Test pipeline state CRUD operations."""
    
    def test_update_pipeline_state(self, temp_db, sample_novel):
        """Test updating pipeline state."""
        state_id = temp_db.update_pipeline_state(
            novel_id=sample_novel,
            phase='sanitize',
            status='running',
            last_chapter=5,
            total_chapters=100
        )
        
        assert state_id is not None
        state = temp_db.get_pipeline_state('sanitize', sample_novel)
        assert state['novel_id'] == sample_novel
        assert state['phase'] == 'sanitize'
        assert state['status'] == 'running'
        assert state['last_chapter'] == 5
        assert state['total_chapters'] == 100
    
    def test_update_pipeline_state_legacy(self, temp_db):
        """Test updating pipeline state without novel_id (legacy)."""
        state_id = temp_db.update_pipeline_state(
            novel_id=None,
            phase='transform',
            status='complete'
        )
        
        assert state_id is not None
        state = temp_db.get_pipeline_state('transform', None)
        assert state['novel_id'] is None
        assert state['status'] == 'complete'
    
    def test_update_pipeline_state_with_error(self, temp_db, sample_novel):
        """Test updating pipeline state with error message."""
        temp_db.update_pipeline_state(
            novel_id=sample_novel,
            phase='render',
            status='failed',
            error_message='Template not found'
        )
        
        state = temp_db.get_pipeline_state('render', sample_novel)
        assert state['status'] == 'failed'
        assert state['error_message'] == 'Template not found'
    
    def test_update_pipeline_state_idempotent(self, temp_db, sample_novel):
        """Test that updating pipeline state is idempotent."""
        state_id1 = temp_db.update_pipeline_state(
            novel_id=sample_novel,
            phase='sanitize',
            status='running'
        )
        state_id2 = temp_db.update_pipeline_state(
            novel_id=sample_novel,
            phase='sanitize',
            status='complete'
        )
        
        # Should return the same ID
        assert state_id1 == state_id2
        
        # Status should be updated
        state = temp_db.get_pipeline_state('sanitize', sample_novel)
        assert state['status'] == 'complete'
    
    def test_get_nonexistent_pipeline_state(self, temp_db):
        """Test getting nonexistent pipeline state returns None."""
        state = temp_db.get_pipeline_state('nonexistent', 999)
        assert state is None
    
    def test_get_all_pipeline_states(self, temp_db, sample_novel):
        """Test getting all pipeline states for a novel."""
        temp_db.update_pipeline_state(novel_id=sample_novel, phase='sanitize', status='complete')
        temp_db.update_pipeline_state(novel_id=sample_novel, phase='transform', status='running')
        temp_db.update_pipeline_state(novel_id=sample_novel, phase='render', status='pending')
        
        states = temp_db.get_all_pipeline_states(sample_novel)
        
        assert len(states) == 3
        phases = [s['phase'] for s in states]
        assert 'sanitize' in phases
        assert 'transform' in phases
        assert 'render' in phases
    
    def test_delete_pipeline_state(self, temp_db, sample_novel):
        """Test deleting pipeline state."""
        temp_db.update_pipeline_state(novel_id=sample_novel, phase='sanitize', status='complete')
        
        result = temp_db.delete_pipeline_state('sanitize', sample_novel)
        
        assert result is True
        state = temp_db.get_pipeline_state('sanitize', sample_novel)
        assert state is None


class TestTransactionHandling:
    """Test transaction commit and rollback."""
    
    def test_transaction_commit(self, temp_db):
        """Test that transactions commit successfully."""
        with temp_db.transaction() as conn:
            conn.execute("""
                INSERT INTO novels (title, author)
                VALUES ('Transaction Test', 'Test Author')
            """)
        
        # Verify data persisted
        novels = temp_db.list_novels()
        titles = [n['title'] for n in novels]
        assert 'Transaction Test' in titles
    
    def test_transaction_rollback(self, temp_db):
        """Test that transactions rollback on error."""
        try:
            with temp_db.transaction() as conn:
                conn.execute("""
                    INSERT INTO novels (title, author)
                    VALUES ('Rollback Test', 'Test Author')
                """)
                # Force an error
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Verify data was not persisted
        novels = temp_db.list_novels()
        titles = [n['title'] for n in novels]
        assert 'Rollback Test' not in titles


class TestConcurrentAccess:
    """Test thread-safe concurrent access."""
    
    def test_concurrent_novel_creation(self, temp_db):
        """Test concurrent novel creation from multiple threads."""
        errors = []
        novel_ids = []
        
        def create_novel(index):
            try:
                novel_id = temp_db.create_novel(title=f"Concurrent Novel {index}")
                novel_ids.append(novel_id)
            except Exception as e:
                errors.append(e)
        
        # Create 10 threads creating novels simultaneously
        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_novel, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Verify no errors
        assert len(errors) == 0
        
        # Verify all novels created
        assert len(novel_ids) == 10
    
    def test_concurrent_chapter_creation(self, temp_db, sample_novel):
        """Test concurrent chapter creation from multiple threads."""
        errors = []
        chapter_ids = []
        
        def create_chapter(chapter_index):
            try:
                chapter_id = temp_db.create_chapter(
                    novel_id=sample_novel,
                    chapter_index=chapter_index,
                    filename=f"Ch_{chapter_index:03d}.txt"
                )
                chapter_ids.append(chapter_id)
            except Exception as e:
                errors.append(e)
        
        # Create 10 threads creating chapters simultaneously
        threads = []
        for i in range(1, 11):
            thread = threading.Thread(target=create_chapter, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Verify no errors
        assert len(errors) == 0
        
        # Verify all chapters created
        assert len(chapter_ids) == 10
        
        # Verify chapters are retrievable
        chapters = temp_db.get_chapters_by_novel(sample_novel)
        assert len(chapters) == 10
    
    def test_concurrent_reads_and_writes(self, temp_db, sample_novel):
        """Test concurrent reads and writes."""
        # Pre-populate some chapters
        for i in range(1, 6):
            temp_db.create_chapter(
                novel_id=sample_novel,
                chapter_index=i,
                filename=f"Ch_{i:03d}.txt"
            )
        
        errors = []
        read_results = []
        
        def read_chapters():
            try:
                chapters = temp_db.get_chapters_by_novel(sample_novel)
                read_results.append(len(chapters))
            except Exception as e:
                errors.append(e)
        
        def write_chapter(chapter_index):
            try:
                temp_db.create_chapter(
                    novel_id=sample_novel,
                    chapter_index=chapter_index + 10,
                    filename=f"Ch_{chapter_index + 10:03d}.txt"
                )
            except Exception as e:
                errors.append(e)
        
        # Mix of read and write threads
        threads = []
        for i in range(10):
            if i % 2 == 0:
                thread = threading.Thread(target=read_chapters)
            else:
                thread = threading.Thread(target=write_chapter, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify no errors
        assert len(errors) == 0
        assert len(read_results) > 0


class TestSingletonPattern:
    """Test singleton pattern for DatabaseManager."""
    
    def test_singleton_same_instance(self, tmp_path):
        """Test that multiple calls return same instance."""
        db_path = tmp_path / "test_singleton.db"
        db1 = DatabaseManager(db_path)
        db2 = DatabaseManager(db_path)
        
        assert db1 is db2
    
    def test_singleton_thread_local_connections(self, tmp_path):
        """Test that each thread gets its own connection."""
        db_path = tmp_path / "test_thread_local.db"
        db = DatabaseManager(db_path)
        
        connections = []
        
        def get_connection():
            connections.append(id(db.connection))
        
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=get_connection)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Each thread should have different connection
        assert len(set(connections)) == 3


class TestBackwardCompatibility:
    """Test backward compatibility with NULL novel_id."""
    
    def test_legacy_chapters_work(self, temp_db):
        """Test that chapters with NULL novel_id work correctly."""
        # Create legacy chapters (no novel_id)
        for i in range(1, 4):
            temp_db.create_chapter(
                novel_id=None,
                chapter_index=i,
                filename=f"Legacy_Ch_{i:03d}.txt"
            )
        
        # Get all chapters
        all_chapters = temp_db.get_all_chapters()
        legacy_chapters = [c for c in all_chapters if c['novel_id'] is None]
        
        assert len(legacy_chapters) == 3
        assert legacy_chapters[0]['filename'] == "Legacy_Ch_001.txt"
    
    def test_legacy_pipeline_state_work(self, temp_db):
        """Test that pipeline state without novel_id works correctly."""
        temp_db.update_pipeline_state(
            novel_id=None,
            phase='sanitize',
            status='complete'
        )
        
        state = temp_db.get_pipeline_state('sanitize', None)
        assert state is not None
        assert state['novel_id'] is None
        assert state['status'] == 'complete'
    
    def test_associate_legacy_chapter_with_novel(self, temp_db, sample_novel):
        """Test associating a legacy chapter with a novel."""
        chapter_id = temp_db.create_chapter(
            novel_id=None,
            chapter_index=1,
            filename="Legacy_001.txt"
        )
        
        # Associate with novel
        temp_db.update_chapter_novel(chapter_id, sample_novel)
        
        # Verify association
        chapter = temp_db.get_chapter(chapter_id)
        assert chapter['novel_id'] == sample_novel
        
        # Verify chapter appears in novel's chapter list
        chapters = temp_db.get_chapters_by_novel(sample_novel)
        assert len(chapters) == 1