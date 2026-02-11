"""
Unit tests for DatabaseManager.

Tests thread-safety, transactions, and CRUD operations.
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
        
        assert 'pipeline_state' in tables
        assert 'chapter_status' in tables
        assert 'rate_limit_state' in tables
    
    def test_indexes_created(self, temp_db):
        """Test that indexes are created."""
        with temp_db.transaction() as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' 
                ORDER BY name
            """)
            indexes = [row[0] for row in cursor.fetchall()]
        
        assert 'idx_pipeline_novel' in indexes
        assert 'idx_chapter_novel_phase' in indexes
        assert 'idx_chapter_status' in indexes
        assert 'idx_rate_limit_provider' in indexes


class TestTransactionHandling:
    """Test transaction commit and rollback."""
    
    def test_transaction_commit(self, temp_db):
        """Test that transactions commit successfully."""
        with temp_db.transaction() as conn:
            conn.execute("""
                INSERT INTO pipeline_state (novel_id, phase, status)
                VALUES ('test', 'transform', 'running')
            """)
        
        # Verify data persisted
        state = temp_db.get_pipeline_state('test', 'transform')
        assert state is not None
        assert state['status'] == 'running'
    
    def test_transaction_rollback(self, temp_db):
        """Test that transactions rollback on error."""
        try:
            with temp_db.transaction() as conn:
                conn.execute("""
                    INSERT INTO pipeline_state (novel_id, phase, status)
                    VALUES ('test_rollback', 'transform', 'running')
                """)
                # Force an error
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Verify data was not persisted
        state = temp_db.get_pipeline_state('test_rollback', 'transform')
        assert state is None


class TestPipelineStateOperations:
    """Test pipeline state CRUD operations."""
    
    def test_update_pipeline_state(self, temp_db):
        """Test updating pipeline state."""
        temp_db.update_pipeline_state(
            novel_id='test',
            phase='transform',
            status='running',
            last_chapter=5,
            total_chapters=100
        )
        
        state = temp_db.get_pipeline_state('test', 'transform')
        assert state['novel_id'] == 'test'
        assert state['phase'] == 'transform'
        assert state['status'] == 'running'
        assert state['last_chapter'] == 5
        assert state['total_chapters'] == 100
    
    def test_update_pipeline_state_with_error(self, temp_db):
        """Test updating pipeline state with error message."""
        temp_db.update_pipeline_state(
            novel_id='test',
            phase='transform',
            status='failed',
            error_message='API timeout'
        )
        
        state = temp_db.get_pipeline_state('test', 'transform')
        assert state['status'] == 'failed'
        assert state['error_message'] == 'API timeout'
    
    def test_get_nonexistent_pipeline_state(self, temp_db):
        """Test getting nonexistent pipeline state returns None."""
        state = temp_db.get_pipeline_state('nonexistent', 'transform')
        assert state is None


class TestChapterStatusOperations:
    """Test chapter status CRUD operations."""
    
    def test_update_chapter_status(self, temp_db):
        """Test updating chapter status."""
        temp_db.update_chapter_status(
            novel_id='test',
            chapter_index=1,
            filename='Ch_001.txt',
            phase='transform',
            status='complete'
        )
        
        status = temp_db.get_chapter_status('test', 1, 'transform')
        assert status['chapter_index'] == 1
        assert status['filename'] == 'Ch_001.txt'
        assert status['phase'] == 'transform'
        assert status['status'] == 'complete'
        assert status['processed_at'] is not None
    
    def test_update_chapter_status_with_error(self, temp_db):
        """Test updating chapter status with error."""
        temp_db.update_chapter_status(
            novel_id='test',
            chapter_index=1,
            filename='Ch_001.txt',
            phase='transform',
            status='failed',
            error_message='JSON validation failed'
        )
        
        status = temp_db.get_chapter_status('test', 1, 'transform')
        assert status['status'] == 'failed'
        assert status['error_message'] == 'JSON validation failed'
    
    def test_get_pending_chapters(self, temp_db):
        """Test getting pending chapters."""
        # Add multiple chapters
        for i in range(1, 6):
            temp_db.update_chapter_status(
                novel_id='test',
                chapter_index=i,
                filename=f'Ch_{i:03d}.txt',
                phase='transform',
                status='pending' if i % 2 == 0 else 'complete'
            )
        
        pending = temp_db.get_pending_chapters('test', 'transform')
        assert len(pending) == 2  # Chapters 2 and 4
        assert pending[0]['chapter_index'] == 2
        assert pending[1]['chapter_index'] == 4
    
    def test_get_all_chapters(self, temp_db):
        """Test getting all chapters."""
        # Use unique novel_id to avoid conflicts with other tests
        for i in range(1, 4):
            temp_db.update_chapter_status(
                novel_id='test_all',
                chapter_index=i,
                filename=f'Ch_{i:03d}.txt',
                phase='transform',
                status='complete'
            )
        
        chapters = temp_db.get_all_chapters('test_all', 'transform')
        assert len(chapters) == 3
        assert chapters[0]['chapter_index'] == 1
        assert chapters[2]['chapter_index'] == 3


class TestRateLimitOperations:
    """Test rate limit state operations."""
    
    def test_update_rate_limit(self, temp_db):
        """Test updating rate limit state."""
        window_start = datetime.now(timezone.utc)
        temp_db.update_rate_limit(
            provider='groq',
            key_index=1,
            requests_made=50,
            window_start=window_start
        )
        
        state = temp_db.get_rate_limit('groq', 1)
        assert state['provider'] == 'groq'
        assert state['key_index'] == 1
        assert state['requests_made'] == 50
    
    def test_get_nonexistent_rate_limit(self, temp_db):
        """Test getting nonexistent rate limit returns None."""
        state = temp_db.get_rate_limit('nonexistent', 999)
        assert state is None


class TestConcurrentAccess:
    """Test thread-safe concurrent access."""
    
    def test_concurrent_writes(self, temp_db):
        """Test concurrent writes from multiple threads."""
        errors = []
        
        def write_chapter(chapter_index):
            try:
                temp_db.update_chapter_status(
                    novel_id='test',
                    chapter_index=chapter_index,
                    filename=f'Ch_{chapter_index:03d}.txt',
                    phase='transform',
                    status='complete'
                )
            except Exception as e:
                errors.append(e)
        
        # Create 10 threads writing simultaneously
        threads = []
        for i in range(1, 11):
            thread = threading.Thread(target=write_chapter, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Verify no errors
        assert len(errors) == 0
        
        # Verify all chapters written
        chapters = temp_db.get_all_chapters('test', 'transform')
        assert len(chapters) == 10
    
    def test_concurrent_reads_and_writes(self, temp_db):
        """Test concurrent reads and writes."""
        # Pre-populate some data
        for i in range(1, 6):
            temp_db.update_chapter_status(
                novel_id='test',
                chapter_index=i,
                filename=f'Ch_{i:03d}.txt',
                phase='transform',
                status='pending'
            )
        
        errors = []
        read_results = []
        
        def read_chapters():
            try:
                chapters = temp_db.get_all_chapters('test', 'transform')
                read_results.append(len(chapters))
            except Exception as e:
                errors.append(e)
        
        def write_chapter(chapter_index):
            try:
                temp_db.update_chapter_status(
                    novel_id='test',
                    chapter_index=chapter_index,
                    filename=f'Ch_{chapter_index:03d}.txt',
                    phase='transform',
                    status='complete'
                )
            except Exception as e:
                errors.append(e)
        
        # Mix of read and write threads
        threads = []
        for i in range(10):
            if i % 2 == 0:
                thread = threading.Thread(target=read_chapters)
            else:
                thread = threading.Thread(target=write_chapter, args=(i + 10,))
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
