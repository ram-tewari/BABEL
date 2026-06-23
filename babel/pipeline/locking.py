"""
Pipeline locking mechanism for concurrent processing prevention.

This module provides file-based locking to prevent duplicate processing
of the same novel concurrently.
"""

import os
import time
import errno
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class LockInfo:
    """Information about an active lock."""
    novel_id: int
    acquired_at: datetime
    process_id: int
    lock_file: str  # Use string instead of Path


class PipelineLockError(Exception):
    """Exception raised when lock acquisition fails."""
    pass


class PipelineLock:
    """
    File-based lock manager for preventing concurrent pipeline processing.
    
    Uses file-based locking with PID tracking to ensure only one pipeline
    can process a given novel at a time. Automatically detects and cleans
    up stale locks from terminated processes.
    
    Attributes:
        lock_dir: Directory where lock files are stored
    """
    
    def __init__(self, lock_dir: Path = Path("data/locks")):
        """
        Initialize the lock manager.
        
        Args:
            lock_dir: Directory for storing lock files (created if not exists)
        """
        self.lock_dir = str(lock_dir)
        os.makedirs(self.lock_dir, exist_ok=True)
    
    def _get_lock_file(self, novel_id: int) -> str:
        """
        Get the lock file path for a novel.
        
        Args:
            novel_id: The novel ID
            
        Returns:
            Path to the lock file as string
        """
        return os.path.join(self.lock_dir, f"pipeline_lock_{novel_id}.lock")
    
    def acquire(self, novel_id: int, timeout: float = 0.0) -> LockInfo:
        """
        Acquire a lock for a novel.
        
        Prevents duplicate processing of the same novel concurrently.
        
        Args:
            novel_id: The novel ID to lock
            timeout: Maximum time to wait for lock acquisition (0 for non-blocking)
            
        Returns:
            LockInfo with lock details
            
        Raises:
            PipelineLockError: If lock cannot be acquired within timeout
        """
        lock_file = self._get_lock_file(novel_id)
        current_pid = os.getpid()
        now = datetime.now(timezone.utc).isoformat()
        lock_content = f"{current_pid}|{now}"
        
        start_time = time.time()
        
        while True:
            try:
                # Try to create the lock file exclusively
                # Use 'x' mode which fails if file exists
                with open(lock_file, 'x') as f:
                    f.write(lock_content)
                
                # Lock acquired successfully
                return LockInfo(
                    novel_id=novel_id,
                    acquired_at=datetime.now(timezone.utc),
                    process_id=current_pid,
                    lock_file=lock_file
                )
                
            except FileExistsError:
                # Lock file exists, check if it's stale
                if self._is_stale_lock(novel_id):
                    # Stale lock - remove it and retry
                    self._remove_lock(novel_id)
                    continue
                
                if timeout <= 0:
                    raise PipelineLockError(
                        f"Novel {novel_id} is currently being processed. "
                        "Duplicate processing is not allowed."
                    )
                
                # Wait and retry
                time.sleep(0.1)
                
                if timeout > 0 and (time.time() - start_time) >= timeout:
                    raise PipelineLockError(
                        f"Timeout waiting for lock on novel {novel_id}. "
                        "Another process may be processing this novel."
                    )
                
            except OSError as e:
                raise PipelineLockError(f"Failed to acquire lock: {e}")
    
    def release(self, novel_id: int) -> bool:
        """
        Release a lock for a novel.
        
        Args:
            novel_id: The novel ID to unlock
            
        Returns:
            True if lock was released, False if no lock existed
        """
        lock_file = self._get_lock_file(novel_id)
        
        try:
            if os.path.exists(lock_file):
                # Verify we own the lock before releasing
                if self._is_our_lock(novel_id):
                    os.unlink(lock_file)
                    return True
            return False
        except OSError:
            return False
    
    def is_locked(self, novel_id: int) -> bool:
        """
        Check if a novel is currently locked.
        
        Args:
            novel_id: The novel ID to check
            
        Returns:
            True if the novel is locked, False otherwise
        """
        lock_file = self._get_lock_file(novel_id)
        
        if not os.path.exists(lock_file):
            return False
        
        # Check if the lock is stale
        if self._is_stale_lock(novel_id):
            self._remove_lock(novel_id)
            return False
        
        return True
    
    def get_lock_info(self, novel_id: int) -> Optional[LockInfo]:
        """
        Get information about an active lock.
        
        Args:
            novel_id: The novel ID
            
        Returns:
            LockInfo if lock exists and is valid, None otherwise
        """
        lock_file = self._get_lock_file(novel_id)
        
        if not os.path.exists(lock_file):
            return None
        
        if self._is_stale_lock(novel_id):
            self._remove_lock(novel_id)
            return None
        
        try:
            with open(lock_file, 'r') as f:
                content = f.read().strip()
                if '|' in content:
                    parts = content.split('|', 1)
                    return LockInfo(
                        novel_id=novel_id,
                        acquired_at=datetime.fromisoformat(parts[1]),
                        process_id=int(parts[0]),
                        lock_file=lock_file
                    )
        except (ValueError, OSError):
            pass
        
        return None
    
    def _is_stale_lock(self, novel_id: int) -> bool:
        """
        Check if a lock is stale (process no longer running).
        
        Args:
            novel_id: The novel ID
            
        Returns:
            True if lock is stale, False otherwise
        """
        lock_file = self._get_lock_file(novel_id)
        
        if not os.path.exists(lock_file):
            return False
        
        try:
            with open(lock_file, 'r') as f:
                content = f.read().strip()
                if '|' in content:
                    parts = content.split('|', 1)
                    pid = int(parts[0])
                    
                    # Check if process is still running
                    try:
                        os.kill(pid, 0)  # Signal 0 doesn't kill, just checks existence
                        return False  # Process is running
                    except OSError as e:
                        if e.errno == errno.ESRCH:
                            return True  # Process doesn't exist
                        elif e.errno == errno.EPERM:
                            return False  # Process exists but we can't kill it
        except (ValueError, OSError):
            pass
        
        return True
    
    def _is_our_lock(self, novel_id: int) -> bool:
        """
        Check if we own the lock for a novel.
        
        Args:
            novel_id: The novel ID
            
        Returns:
            True if we own the lock, False otherwise
        """
        lock_info = self.get_lock_info(novel_id)
        return lock_info is not None and lock_info.process_id == os.getpid()
    
    def _remove_lock(self, novel_id: int) -> bool:
        """
        Remove a stale lock file.
        
        Args:
            novel_id: The novel ID
            
        Returns:
            True if removed, False otherwise
        """
        lock_file = self._get_lock_file(novel_id)
        
        try:
            if os.path.exists(lock_file):
                os.unlink(lock_file)
                return True
        except OSError:
            pass
        
        return False
    
    def cleanup_all_locks(self) -> int:
        """
        Remove all stale locks.
        
        Returns:
            Number of locks removed
        """
        count = 0
        
        if os.path.exists(self.lock_dir):
            for filename in os.listdir(self.lock_dir):
                if filename.startswith("pipeline_lock_") and filename.endswith(".lock"):
                    novel_id_str = filename.replace("pipeline_lock_", "").replace(".lock", "")
                    try:
                        novel_id = int(novel_id_str)
                        if self._is_stale_lock(novel_id):
                            self._remove_lock(novel_id)
                            count += 1
                    except ValueError:
                        # Invalid lock file name, remove it
                        try:
                            file_path = os.path.join(self.lock_dir, filename)
                            os.unlink(file_path)
                            count += 1
                        except OSError:
                            pass
        
        return count