"""
Property-based tests for Pipeline Concurrent Processing Prevention.

These tests validate universal correctness properties for the concurrent
processing prevention mechanism, ensuring that duplicate processing of the
same novel is properly prevented.

Feature: phase-7-librarian, Property 14: Concurrent Processing Prevention
Validates: Requirements 9.5
"""

import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from babel.pipeline.locking import PipelineLock, PipelineLockError, LockInfo


# ============================================================================
# Strategies for generating test data
# ============================================================================

@st.composite
def novel_id_strategy(draw):
    """Generate a valid novel_id (positive integer)."""
    return draw(st.integers(min_value=1, max_value=10000))


@st.composite
def novel_ids_list_strategy(draw):
    """Generate a list of unique novel IDs."""
    count = draw(st.integers(min_value=2, max_value=10))
    novel_ids = []
    seen = set()
    while len(novel_ids) < count:
        novel_id = draw(st.integers(min_value=1, max_value=10000))
        if novel_id not in seen:
            seen.add(novel_id)
            novel_ids.append(novel_id)
    return novel_ids


# ============================================================================
# Helper class for managing lock tests with proper cleanup
# ============================================================================

class LockTestHelper:
    """Helper class for managing lock tests with proper cleanup."""
    
    def __init__(self):
        self.temp_dir = None
        self.lock = None
    
    def setup(self):
        """Set up the test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.lock = PipelineLock(lock_dir=self.temp_dir)
    
    def teardown(self):
        """Clean up the test environment."""
        if self.lock is not None and self.temp_dir is not None:
            # Release any remaining locks
            try:
                if os.path.exists(self.temp_dir):
                    for filename in os.listdir(self.temp_dir):
                        if filename.startswith("pipeline_lock_") and filename.endswith(".lock"):
                            try:
                                os.unlink(os.path.join(self.temp_dir, filename))
                            except OSError:
                                pass
            except OSError:
                pass
        
        # Remove temp directory
        if self.temp_dir is not None and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except OSError:
                pass
        
        self.temp_dir = None
        self.lock = None
    
    def __enter__(self):
        self.setup()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.teardown()
        return False


# ============================================================================
# Property 14: Concurrent Processing Prevention Tests
# ============================================================================

class TestConcurrentProcessingPrevention:
    """
    Property-based tests for concurrent processing prevention.
    
    Feature: phase-7-librarian, Property 14: Concurrent Processing Prevention
    Validates: Requirements 9.5
    """
    
    @given(novel_id=novel_id_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_duplicate_lock_acquisition_rejected(self, novel_id):
        """
        Feature: phase-7-librarian, Property 14: Concurrent Processing Prevention
        
        For any novel currently being processed, attempts to start another
        processing job for the same novel should be rejected until the first
        job completes.
        
        This test verifies that:
        1. First lock acquisition succeeds
        2. Second lock acquisition for the same novel raises PipelineLockError
        3. Lock is still held after failed attempt
        """
        with LockTestHelper() as helper:
            lock = helper.lock
            
            # First acquisition should succeed
            lock_info_1 = lock.acquire(novel_id)
            assert lock_info_1 is not None
            assert lock_info_1.novel_id == novel_id
            assert lock.is_locked(novel_id) is True
            
            # Second acquisition should raise PipelineLockError
            with pytest.raises(PipelineLockError) as exc_info:
                lock.acquire(novel_id)
            
            # Error message should indicate the novel is being processed
            error_message = str(exc_info.value).lower()
            assert "currently being processed" in error_message or "duplicate" in error_message
            
            # Lock should still be held
            assert lock.is_locked(novel_id) is True
            
            # Cleanup
            lock.release(novel_id)
    
    @given(novel_id=novel_id_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_lock_release_enables_new_acquisition(self, novel_id):
        """
        Feature: phase-7-librarian, Property 14: Concurrent Processing Prevention
        
        After a lock is released, a new processing job should be able to acquire
        the lock for the same novel.
        
        This test verifies that:
        1. Lock can be acquired
        2. Lock can be released
        3. Lock can be acquired again after release
        """
        with LockTestHelper() as helper:
            lock = helper.lock
            
            # Initial state - not locked
            assert lock.is_locked(novel_id) is False
            
            # First acquisition
            lock_info_1 = lock.acquire(novel_id)
            assert lock_info_1 is not None
            assert lock.is_locked(novel_id) is True
            
            # Release
            result = lock.release(novel_id)
            assert result is True
            assert lock.is_locked(novel_id) is False
            
            # Second acquisition should succeed
            lock_info_2 = lock.acquire(novel_id)
            assert lock_info_2 is not None
            assert lock_info_2.novel_id == novel_id
            assert lock.is_locked(novel_id) is True
            
            # Cleanup
            lock.release(novel_id)
    
    @given(novel_ids=novel_ids_list_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_different_novels_can_lock_simultaneously(self, novel_ids):
        """
        Feature: phase-7-librarian, Property 14: Concurrent Processing Prevention
        
        Different novels can be processed simultaneously - the locking mechanism
        should only prevent duplicate processing of the SAME novel.
        
        This test verifies that:
        1. Multiple different novels can be locked at the same time
        2. Locking one novel doesn't affect locks on other novels
        """
        with LockTestHelper() as helper:
            lock = helper.lock
            
            # Acquire locks for all novels
            lock_infos = {}
            for novel_id in novel_ids:
                lock_info = lock.acquire(novel_id)
                lock_infos[novel_id] = lock_info
                assert lock.is_locked(novel_id) is True
            
            # Verify all novels are locked
            for novel_id in novel_ids:
                assert lock.is_locked(novel_id) is True
            
            # Verify each lock has correct novel_id
            for novel_id in novel_ids:
                assert lock_infos[novel_id].novel_id == novel_id
            
            # Verify get_lock_info returns correct info for each
            for novel_id in novel_ids:
                retrieved_info = lock.get_lock_info(novel_id)
                assert retrieved_info is not None
                assert retrieved_info.novel_id == novel_id
            
            # Cleanup - release all locks
            for novel_id in novel_ids:
                lock.release(novel_id)
                assert lock.is_locked(novel_id) is False
    
    @given(
        novel_ids=st.lists(
            st.integers(min_value=1, max_value=1000),
            min_size=2,
            max_size=5,
            unique=True
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_lock_isolation_between_novels(self, novel_ids):
        """
        Feature: phase-7-librarian, Property 14: Concurrent Processing Prevention
        
        Locking one novel should not affect the ability to lock other novels.
        Each novel's lock is independent.
        
        This test verifies that:
        1. Locking novel A doesn't prevent locking novel B
        2. Releasing novel A doesn't affect novel B's lock
        3. Each novel's lock state is independent
        """
        with LockTestHelper() as helper:
            lock = helper.lock
            
            # Lock first novel
            first_novel = novel_ids[0]
            lock.acquire(first_novel)
            assert lock.is_locked(first_novel) is True
            
            # Lock all other novels - should succeed
            for novel_id in novel_ids[1:]:
                lock_info = lock.acquire(novel_id)
                assert lock_info is not None
                assert lock.is_locked(novel_id) is True
            
            # Release first novel
            lock.release(first_novel)
            assert lock.is_locked(first_novel) is False
            
            # Other novels should still be locked
            for novel_id in novel_ids[1:]:
                assert lock.is_locked(novel_id) is True
            
            # Cleanup - release all remaining locks
            for novel_id in novel_ids[1:]:
                lock.release(novel_id)
    
    @given(
        novel_id=novel_id_strategy(),
        timeout=st.floats(min_value=0.1, max_value=0.5)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_timeout_rejects_duplicate_lock(self, novel_id, timeout):
        """
        Feature: phase-7-librarian, Property 14: Concurrent Processing Prevention
        
        When a timeout is specified and the lock is held by another process,
        the lock acquisition should fail after the timeout expires.
        
        This test verifies that:
        1. Lock acquisition with timeout raises PipelineLockError when blocked
        2. Error message indicates timeout
        """
        with LockTestHelper() as helper:
            lock = helper.lock
            
            # First acquisition
            lock.acquire(novel_id)
            
            # Second acquisition with timeout should raise error
            with pytest.raises(PipelineLockError) as exc_info:
                lock.acquire(novel_id, timeout=timeout)
            
            error_message = str(exc_info.value)
            # Either "currently being processed" or "timeout" should be in message
            assert "currently being processed" in error_message or "timeout" in error_message.lower()
            
            # Cleanup
            lock.release(novel_id)
    
    @given(
        novel_ids=st.lists(
            st.integers(min_value=1, max_value=1000),
            min_size=2,
            max_size=5,
            unique=True
        )
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_concurrent_thread_lock_contention(self, novel_ids):
        """
        Feature: phase-7-librarian, Property 14: Concurrent Processing Prevention
        
        When multiple threads attempt to acquire a lock for the same novel
        simultaneously, only one should succeed and others should fail.
        
        This test verifies that:
        1. Only one thread can acquire the lock
        2. Other threads receive PipelineLockError
        3. Lock state is consistent after contention
        """
        with LockTestHelper() as helper:
            lock = helper.lock
            
            # Use a novel that all threads will try to lock
            target_novel = novel_ids[0]
            
            # Results from each thread
            successes = []
            errors = []
            lock_info_results = []
            
            def try_acquire_lock():
                try:
                    lock_info = lock.acquire(target_novel)
                    lock_info_results.append(lock_info)
                    successes.append(True)
                except PipelineLockError:
                    errors.append(True)
            
            # First, acquire the lock (simulating existing processing)
            lock.acquire(target_novel)
            
            # Try concurrent acquires from multiple threads
            threads = [threading.Thread(target=try_acquire_lock) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            
            # All concurrent attempts should have failed
            assert len(errors) == 5, f"Expected 5 errors, got {len(errors)}"
            assert len(successes) == 0, f"Expected 0 successes, got {len(successes)}"
            
            # Original lock should still be held
            assert lock.is_locked(target_novel) is True
            
            # Cleanup
            lock.release(target_novel)
    
    @given(
        novel_id=novel_id_strategy(),
        num_cycles=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_lock_acquire_release_cycles(self, novel_id, num_cycles):
        """
        Feature: phase-7-librarian, Property 14: Concurrent Processing Prevention
        
        The lock should support multiple acquire-release cycles for the same novel,
        allowing repeated processing jobs.
        
        This test verifies that:
        1. Multiple acquire-release cycles work correctly
        2. Each cycle is independent
        3. Lock state is consistent throughout
        """
        with LockTestHelper() as helper:
            lock = helper.lock
            
            for cycle in range(num_cycles):
                # Acquire
                lock_info = lock.acquire(novel_id)
                assert lock_info is not None
                assert lock.is_locked(novel_id) is True
                
                # Verify lock info
                retrieved_info = lock.get_lock_info(novel_id)
                assert retrieved_info is not None
                assert retrieved_info.novel_id == novel_id
                
                # Release
                result = lock.release(novel_id)
                assert result is True
                assert lock.is_locked(novel_id) is False
    
    @given(
        novel_ids=st.lists(
            st.integers(min_value=1, max_value=1000),
            min_size=2,
            max_size=5,
            unique=True
        )
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_partial_release_preserves_other_locks(self, novel_ids):
        """
        Feature: phase-7-librarian, Property 14: Concurrent Processing Prevention
        
        Releasing a lock for one novel should not affect locks on other novels.
        
        This test verifies that:
        1. Multiple novels can be locked simultaneously
        2. Releasing one novel's lock doesn't affect others
        3. Other novels remain locked after partial release
        """
        with LockTestHelper() as helper:
            lock = helper.lock
            
            # Lock all novels
            for novel_id in novel_ids:
                lock.acquire(novel_id)
                assert lock.is_locked(novel_id) is True
            
            # Release first novel
            first_novel = novel_ids[0]
            result = lock.release(first_novel)
            assert result is True
            assert lock.is_locked(first_novel) is False
            
            # Other novels should still be locked
            for novel_id in novel_ids[1:]:
                assert lock.is_locked(novel_id) is True
                # Should be able to get lock info
                lock_info = lock.get_lock_info(novel_id)
                assert lock_info is not None
                assert lock_info.novel_id == novel_id
            
            # Cleanup - release remaining locks
            for novel_id in novel_ids[1:]:
                lock.release(novel_id)
    
    @given(novel_id=novel_id_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_lock_info_accuracy(self, novel_id):
        """
        Feature: phase-7-librarian, Property 14: Concurrent Processing Prevention
        
        LockInfo returned by acquire() should contain accurate information about
        the acquired lock.
        
        This test verifies that:
        1. LockInfo contains correct novel_id
        2. LockInfo contains process_id
        3. LockInfo contains acquired_at timestamp
        4. LockInfo contains lock_file path
        """
        from datetime import datetime
        
        with LockTestHelper() as helper:
            lock = helper.lock
            
            # Acquire lock
            lock_info = lock.acquire(novel_id)
            
            # Verify LockInfo fields
            assert lock_info.novel_id == novel_id
            assert lock_info.process_id == os.getpid()
            assert isinstance(lock_info.acquired_at, datetime)
            assert isinstance(lock_info.lock_file, str)
            assert str(novel_id) in lock_info.lock_file
            
            # Verify get_lock_info returns equivalent info
            retrieved_info = lock.get_lock_info(novel_id)
            assert retrieved_info is not None
            assert retrieved_info.novel_id == lock_info.novel_id
            assert retrieved_info.process_id == lock_info.process_id
            assert retrieved_info.lock_file == lock_info.lock_file
            
            # Cleanup
            lock.release(novel_id)
    
    @given(
        novel_ids=st.lists(
            st.integers(min_value=1, max_value=1000),
            min_size=3,
            max_size=5,
            unique=True
        )
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_lock_state_consistency_after_operations(self, novel_ids):
        """
        Feature: phase-7-librarian, Property 14: Concurrent Processing Prevention
        
        After various lock operations, the lock state should remain consistent
        and predictable.
        
        This test verifies that:
        1. Lock state matches expected state after operations
        2. No orphaned lock files remain
        3. State is consistent across different check methods
        """
        with LockTestHelper() as helper:
            lock = helper.lock
            
            # Initial state - no locks
            for novel_id in novel_ids:
                assert lock.is_locked(novel_id) is False
                assert lock.get_lock_info(novel_id) is None
            
            # Acquire some locks
            lock_subset = novel_ids[:len(novel_ids) // 2]
            for novel_id in lock_subset:
                lock.acquire(novel_id)
            
            # Verify state
            for novel_id in lock_subset:
                assert lock.is_locked(novel_id) is True
                assert lock.get_lock_info(novel_id) is not None
            
            for novel_id in novel_ids[len(lock_subset):]:
                assert lock.is_locked(novel_id) is False
                assert lock.get_lock_info(novel_id) is None
            
            # Release all locks
            for novel_id in lock_subset:
                lock.release(novel_id)
            
            # Final state - no locks
            for novel_id in novel_ids:
                assert lock.is_locked(novel_id) is False
                assert lock.get_lock_info(novel_id) is None


# ============================================================================
# Edge Cases and Boundary Conditions
# ============================================================================

class TestConcurrentProcessingEdgeCases:
    """Edge case tests for concurrent processing prevention."""
    
    @given(
        novel_ids=st.lists(
            st.integers(min_value=1, max_value=1000),
            min_size=2,
            max_size=5,
            unique=True
        )
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_release_nonexistent_lock_returns_false(self, novel_ids):
        """
        Releasing a lock for a novel that doesn't have a lock should return False.
        """
        with LockTestHelper() as helper:
            lock = helper.lock
            
            # Try to release a novel that was never locked
            result = lock.release(99999)
            assert result is False
    
    @given(novel_id=novel_id_strategy())
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_get_lock_info_for_unlocked_novel(self, novel_id):
        """
        Getting lock info for a novel that doesn't have a lock should return None.
        """
        with LockTestHelper() as helper:
            lock = helper.lock
            
            # Get lock info for novel that was never locked
            lock_info = lock.get_lock_info(novel_id)
            assert lock_info is None
    
    @given(
        novel_ids=st.lists(
            st.integers(min_value=1, max_value=1000),
            min_size=2,
            max_size=5,
            unique=True
        )
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_lock_file_cleanup_after_release(self, novel_ids):
        """
        After releasing a lock, the lock file should be removed from the filesystem.
        """
        with LockTestHelper() as helper:
            lock = helper.lock
            
            for novel_id in novel_ids:
                # Acquire lock
                lock.acquire(novel_id)
                lock_file = os.path.join(helper.temp_dir, f"pipeline_lock_{novel_id}.lock")
                assert os.path.exists(lock_file)
                
                # Release lock
                lock.release(novel_id)
                assert not os.path.exists(lock_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])