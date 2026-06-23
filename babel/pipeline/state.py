"""
Pipeline state management for BABEL.

This module provides classes for tracking pipeline execution state,
chapter status, and job progress.
"""

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any
import json
import threading


class ChapterStatus(str, Enum):
    """Chapter processing status."""
    RAW = "raw"
    CLEAN = "clean"
    JSON = "json"
    HTML = "html"
    FAILED = "failed"
    RENDER_FAILED = "render_failed"


class ChapterState:
    """State for a single chapter."""

    def __init__(
        self,
        index: int,
        filename: str,
        title: str,
        status: ChapterStatus = ChapterStatus.RAW,
        error_message: Optional[str] = None,
        last_updated: Optional[datetime] = None
    ):
        self.index = index
        self.filename = filename
        self.title = title
        self.status = status
        self.error_message = error_message
        self.last_updated = last_updated or datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'index': self.index,
            'filename': self.filename,
            'title': self.title,
            'status': self.status.value,
            'error_message': self.error_message,
            'last_updated': self.last_updated.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChapterState':
        """Create from dictionary."""
        return cls(
            index=data['index'],
            filename=data['filename'],
            title=data['title'],
            status=ChapterStatus(data['status']),
            error_message=data.get('error_message'),
            last_updated=datetime.fromisoformat(data['last_updated'])
        )


class JobState:
    """Complete job state including all chapters."""

    def __init__(
        self,
        input_file: str,
        chapters: List[ChapterState],
        novel_id: Optional[int] = None,
        started_at: Optional[datetime] = None,
        last_updated: Optional[datetime] = None
    ):
        self.input_file = input_file
        self.chapters = chapters
        self.novel_id = novel_id  # Track which novel this job belongs to
        self.started_at = started_at or datetime.now(timezone.utc)
        self.last_updated = last_updated or datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'input_file': self.input_file,
            'novel_id': self.novel_id,
            'chapters': [c.to_dict() for c in self.chapters],
            'started_at': self.started_at.isoformat(),
            'last_updated': self.last_updated.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobState':
        """Create from dictionary."""
        return cls(
            input_file=data['input_file'],
            novel_id=data.get('novel_id'),
            chapters=[ChapterState.from_dict(c) for c in data['chapters']],
            started_at=datetime.fromisoformat(data['started_at']),
            last_updated=datetime.fromisoformat(data['last_updated'])
        )


class JobStateManager:
    """
    Manages job state persistence and chapter status updates.
    
    Thread-safe implementation that persists state immediately after
    each update.
    """

    def __init__(self, state_file: Path, novel_id: Optional[int] = None):
        """
        Initialize state manager.
        
        Args:
            state_file: Path to the state file
            novel_id: Optional novel ID to associate with this job
        """
        self.state_file = Path(state_file)
        self.novel_id = novel_id
        self._lock = threading.Lock()
        self._state: Optional[JobState] = None

    @property
    def state(self) -> Optional[JobState]:
        """Get current state."""
        return self._state

    def initialize(
        self,
        input_file: str,
        chapters: List[Dict[str, Any]]
    ) -> JobState:
        """
        Initialize a new job state.
        
        Args:
            input_file: Path to input file
            chapters: List of chapter metadata dictionaries
            
        Returns:
            Initialized JobState
        """
        with self._lock:
            chapter_states = [
                ChapterState(
                    index=c['index'],
                    filename=c['filename'],
                    title=c['title']
                )
                for c in chapters
            ]
            
            self._state = JobState(
                input_file=input_file,
                chapters=chapter_states,
                novel_id=self.novel_id
            )
            
            self._persist()
            return self._state

    def load(self) -> Optional[JobState]:
        """
        Load state from disk.
        
        Returns:
            Loaded JobState or None if file doesn't exist or is invalid
        """
        with self._lock:
            if not self.state_file.exists():
                return None
            
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._state = JobState.from_dict(data)
                return self._state
            except (json.JSONDecodeError, KeyError, TypeError):
                return None

    def update_chapter(
        self,
        chapter_index: int,
        status: ChapterStatus,
        error_message: Optional[str] = None
    ) -> None:
        """
        Update chapter status.
        
        Args:
            chapter_index: Index of chapter to update
            status: New status
            error_message: Optional error message
            
        Raises:
            ValueError: If chapter_index is invalid
        """
        with self._lock:
            if self._state is None:
                raise ValueError("State not initialized")
            
            if chapter_index < 0 or chapter_index >= len(self._state.chapters):
                raise ValueError(f"Invalid chapter index: {chapter_index}")
            
            chapter = self._state.chapters[chapter_index]
            chapter.status = status
            chapter.error_message = error_message
            chapter.last_updated = datetime.now(timezone.utc)
            self._state.last_updated = chapter.last_updated
            
            self._persist()

    def should_skip_chapter(
        self,
        chapter_index: int,
        target_status: ChapterStatus
    ) -> bool:
        """
        Check if chapter should be skipped for current phase.
        
        Args:
            chapter_index: Index of chapter
            target_status: Status we're trying to achieve
            
        Returns:
            True if chapter should be skipped
        """
        with self._lock:
            if self._state is None:
                return False
            
            if chapter_index < 0 or chapter_index >= len(self._state.chapters):
                return False
            
            chapter = self._state.chapters[chapter_index]
            
            # Never skip failed chapters (need explicit --retry-failed)
            if chapter.status in (ChapterStatus.FAILED, ChapterStatus.RENDER_FAILED):
                return False
            
            # Skip if already at or past target status
            status_order = [
                ChapterStatus.RAW,
                ChapterStatus.CLEAN,
                ChapterStatus.JSON,
                ChapterStatus.HTML
            ]
            
            current_pos = status_order.index(chapter.status)
            target_pos = status_order.index(target_status)
            
            return current_pos >= target_pos

    def get_chapters_for_phase(self, phase: int) -> List[ChapterState]:
        """
        Get chapters that need processing for a specific phase.
        
        Args:
            phase: Phase number (0=sanitize, 1=transform, 2=render)
            
        Returns:
            List of chapters needing processing
            
        Raises:
            ValueError: If phase is invalid
        """
        with self._lock:
            if self._state is None:
                return []
            
            if phase == 0:
                target = ChapterStatus.CLEAN
            elif phase == 1:
                target = ChapterStatus.JSON
            elif phase == 2:
                target = ChapterStatus.HTML
            else:
                raise ValueError(f"Invalid phase: {phase}")
            
            return [
                c for c in self._state.chapters
                if not self.should_skip_chapter(c.index, target)
            ]

    def _persist(self) -> None:
        """Persist state to disk."""
        if self._state is None:
            return
        
        # Ensure directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self._state.to_dict(), f, indent=2, ensure_ascii=False)