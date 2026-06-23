"""
Unit tests for pipeline locking mechanism.

Tests concurrent processing prevention functionality.
"""

import os
import sys
import time
import tempfile
import threading
from pathlib import Path
from datetime import datetime, timezone

import pytest

# Add babel to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from babel.pipeline.locking import PipelineLock, PipelineLockError, LockInfo


class TestPipelineLock:
    """Test cases for PipelineLock class."""
    
    @pytest.fixture
    def temp_lock_dir(self):
        """Create a temporary directory for lock files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def lock(self, temp_lock_dir):
        """Create a PipelineLock instance with temp directory."""
        return PipelineLock(lock_dir=temp_lock_dir)
    
    def test_acquire_lock_creates_lock_file(self, lock, temp_lock_dir):
        """Test that acquiring a lock creates a lock file."""
        novel_id = 123
        lock_info = lock.acquire(novel_id)
        
        # Lock file should exist
        lock_file = temp_lock_dir / f"pipeline_lock_{novel_id}.lock"
        assert lock_file.exists()
        
        # Lock info should be correct
        assert lock_info.novel_id == novel_id
        assert lock_info.process_id == os.getpid()
        assert isinstance(lock_info.acquired_at, datetime)
    
    def test_release_lock_removes_lock_file(self, lock, temp_lock_dir):
        """Test that releasing a lock removes the lock file."""
        novel_id = 456
        lock.acquire(novel_id)
        
        # Lock file should exist
        lock_file = temp_lock_dir / f"pipeline_lock_{novel_id}.lock"
        assert lock_file.exists()
        
        # Release lock
        result = lock.release(novel_id)
        assert result is True
        
        # Lock file should be removed
        assert not lock_file.exists()
    
    def test_is_locked_returns_true_when_locked(self, lock, temp_lock_dir):
        """Test that is_locked returns True when lock exists."""
        novel_id = 789
        lock.acquire(novel_id)
        
        assert lock.is_locked(novel_id) is True
    
    def test_is_locked_returns_false_when_not_locked(self, lock):
        """Test that is_locked returns False when no lock exists."""
        novel_id = 999
        
        assert lock.is_locked(novel_id) is False
    
    def test_duplicate_lock_raises_error(self, lock):
        """Test that acquiring a lock for the same novel raises PipelineLockError."""
        novel_id = 111
        
        # First acquire should succeed
        lock.acquire(novel_id)
        
        # Second acquire should raise error
        with pytest.raises(PipelineLockError) as exc_info:
            lock.acquire(novel_id)
        
        assert "currently being processed" in str(exc_info.value)
    
    def test_release_nonexistent_lock_returns_false(self, lock):
        """Test that releasing a nonexistent lock returns False."""
        result = lock.release(99999)
        assert result is False
    
    def test_get_lock_info_returns_correct_info(self, lock):
        """Test that get_lock_info returns correct lock information."""
        novel_id = 222
        lock.acquire(novel_id)
        
        lock_info = lock.get_lock_info(novel_id)
        
        assert lock_info is not None
        assert lock_info.novel_id == novel_id
        assert lock_info.process_id == os.getpid()
        assert isinstance(lock_info.acquired_at, datetime)
    
    def test_get_lock_info_returns_none_for_nonexistent(self, lock):
        """Test that get_lock_info returns None for nonexistent lock."""
        lock_info = lock.get_lock_info(88888)
        assert lock_info is None
    
    def test_concurrent_acquire_from_same_process(self, lock):
        """Test that concurrent acquire from same process raises error."""
        novel_id = 333
        errors = []
        
        def try_acquire():
            try:
                lock.acquire(novel_id)
            except PipelineLockError as e:
                errors.append(e)
        
        # First acquire
        lock.acquire(novel_id)
        
        # Try concurrent acquire
        threads = [threading.Thread(target=try_acquire) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All concurrent attempts should have raised errors
        assert len(errors) == 3
        for error in errors:
            assert isinstance(error, PipelineLockError)
    
    def test_lock_with_timeout(self, lock):
        """Test that timeout parameter works correctly."""
        novel_id = 444
        
        # First acquire with no timeout
        lock.acquire(novel_id)
        
        # Second acquire with timeout should raise error
        with pytest.raises(PipelineLockError):
            lock.acquire(novel_id, timeout=0.5)
    
    def test_cleanup_stale_locks(self, lock, temp_lock_dir):
        """Test that cleanup_all_locks removes stale locks."""
        novel_id = 555
        lock.acquire(novel_id)
        
        # Simulate stale lock by removing the process
        # (In real scenario, the process would have terminated)
        lock_file = temp_lock_dir / f"pipeline_lock_{novel_id}.lock"
        
        # Manually create a stale lock with non-existent PID
        with open(lock_file, 'w') as f:
            f.write(f"{999999999}|{datetime.now(timezone.utc).isoformat()}")
        
        # Cleanup should remove the stale lock
        count = lock.cleanup_all_locks()
        assert count >= 1
        
        # Lock should no longer exist
        assert not lock.is_locked(novel_id)
    
    def test_lock_info_dataclass(self):
        """Test LockInfo dataclass creation."""
        now = datetime.now(timezone.utc)
        lock_info = LockInfo(
            novel_id=1,
            acquired_at=now,
            process_id=1234,
            lock_file=Path("/test/lock.lock")
        )
        
        assert lock_info.novel_id == 1
        assert lock_info.acquired_at == now
        assert lock_info.process_id == 1234
        assert str(lock_info.lock_file) == "/test/lock.lock"
    
    def test_lock_acquire_release_cycle(self, lock, temp_lock_dir):
        """Test complete acquire-release cycle."""
        novel_id = 666
        
        # Acquire
        lock_info = lock.acquire(novel_id)
        assert lock.is_locked(novel_id)
        assert lock.get_lock_info(novel_id) is not None
        
        # Release
        result = lock.release(novel_id)
        assert result is True
        assert not lock.is_locked(novel_id)
        assert lock.get_lock_info(novel_id) is None
        
        # Should be able to acquire again
        lock_info2 = lock.acquire(novel_id)
        assert lock_info2.novel_id == novel_id
        
        # Cleanup
        lock.release(novel_id)
    
    def test_multiple_novels_independent_locks(self, lock, temp_lock_dir):
        """Test that locks for different novels are independent."""
        novel_ids = [100, 200, 300]
        
        # Acquire locks for all novels
        for novel_id in novel_ids:
            lock.acquire(novel_id)
            assert lock.is_locked(novel_id)
        
        # All should be locked
        for novel_id in novel_ids:
            assert lock.is_locked(novel_id)
        
        # Release one
        lock.release(novel_ids[1])
        assert not lock.is_locked(novel_ids[1])
        
        # Others should still be locked
        assert lock.is_locked(novel_ids[0])
        assert lock.is_locked(novel_ids[2])
        
        # Cleanup
        for novel_id in novel_ids:
            lock.release(novel_id)


class TestPipelineLockEdgeCases:
    """Test edge cases for PipelineLock."""
    
    @pytest.fixture
    def temp_lock_dir(self):
        """Create a temporary directory for lock files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def lock(self, temp_lock_dir):
        """Create a PipelineLock instance with temp directory."""
        return PipelineLock(lock_dir=temp_lock_dir)
    
    def test_lock_nonexistent_novel_returns_false_for_is_locked(self, lock):
        """Test is_locked for novel that never had a lock."""
        assert lock.is_locked(12345) is False
    
    def test_get_lock_info_for_never_locked_novel(self, lock):
        """Test get_lock_info for novel that never had a lock."""
        assert lock.get_lock_info(54321) is None
    
    def test_lock_file_creation_with_custom_directory(self, temp_lock_dir):
        """Test lock file creation in custom directory."""
        custom_dir = temp_lock_dir / "custom" / "path"
        lock = PipelineLock(lock_dir=custom_dir)
        
        novel_id = 777
        lock_info = lock.acquire(novel_id)
        
        expected_lock_file = custom_dir / f"pipeline_lock_{novel_id}.lock"
        assert expected_lock_file.exists()
        assert lock_info.lock_file == expected_lock_file
        
        # Cleanup
        lock.release(novel_id)
    
    def test_concurrent_thread_lock_contention(self, temp_lock_dir):
        """Test lock behavior under concurrent thread contention."""
        lock = PipelineLock(lock_dir=temp_lock_dir)
        novel_id = 888
        
        # First thread acquires lock
        acquired_by_first = threading.Event()
        first_thread = threading.Thread(target=lambda: (
            lock.acquire(novel_id),
            acquired_by_first.set()
        ))
        first_thread.start()
        acquired_by_first.wait()
        
        # Other threads should fail to acquire
        errors = []
        success = []
        
        def try_acquire():
            try:
                lock.acquire(novel_id)
                success.append(True)
            except PipelineLockError:
                errors.append(True)
        
        threads = [threading.Thread(target=try_acquire) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All concurrent attempts should have failed
        assert len(errors) == 5
        assert len(success) == 0
        
        # First thread releases
        lock.release(novel_id)
        
        # Now another thread should be able to acquire
        lock.acquire(novel_id)
        lock.release(novel_id)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])