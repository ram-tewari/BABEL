"""
Database layer for BABEL multi-novel library management.

This module provides the DatabaseManager class for thread-safe SQLite database
operations with support for novels, chapters, and pipeline state tracking.
"""

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional


class DatabaseManager:
    """
    Thread-safe singleton database manager for BABEL.
    
    Provides CRUD operations for novels, chapters, and pipeline state.
    Uses thread-local connections for concurrent access.
    """
    
    _instances: Dict[Path, 'DatabaseManager'] = {}
    _lock = threading.Lock()
    
    def __new__(cls, db_path: Path = Path("data/babel.db")):
        """
        Create or return existing singleton instance.
        
        Args:
            db_path: Path to the SQLite database file.
            
        Returns:
            DatabaseManager: Singleton instance for the given path.
        """
        db_path = Path(db_path).resolve()
        with cls._lock:
            if db_path not in cls._instances:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instances[db_path] = instance
            return cls._instances[db_path]
    
    def __init__(self, db_path: Path = Path("data/babel.db")):
        """
        Initialize database and create schema if needed.
        
        Args:
            db_path: Path to the SQLite database file.
        """
        if self._initialized:
            return
        
        self.db_path = Path(db_path).resolve()
        self._local = threading.local()
        self._initialized = True
        self._create_tables()
    
    @property
    def connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False
            )
            self._local.conn.row_factory = sqlite3.Row
            # Enable foreign key support for cascade delete
            self._local.conn.execute("PRAGMA foreign_keys = ON")
        return self._local.conn
    
    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for database transactions.
        
        Automatically commits on success, rolls back on exception.
        
        Yields:
            sqlite3.Connection: The database connection.
        """
        conn = self.connection
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def _create_tables(self) -> None:
        """Create database schema if it doesn't exist."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            
            # Novels table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS novels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    author TEXT,
                    cover_url TEXT,
                    synopsis TEXT,
                    tags TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Chapters table (extended with novel_id for backward compatibility)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chapters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER,
                    chapter_index INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
                )
            """)
            
            # Pipeline state table (extended with novel_id)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER,
                    phase TEXT NOT NULL,
                    status TEXT NOT NULL,
                    last_chapter INTEGER,
                    total_chapters INTEGER,
                    error_message TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE,
                    UNIQUE(novel_id, phase)
                )
            """)
            
            # Indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chapters_novel
                ON chapters(novel_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pipeline_novel
                ON pipeline_state(novel_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_novels_updated
                ON novels(updated_at DESC)
            """)
    
    # Novel operations
    
    def create_novel(
        self,
        title: str,
        author: Optional[str] = None,
        cover_url: Optional[str] = None,
        status: str = "active"
    ) -> int:
        """
        Create a new novel entry and return novel_id.
        
        Args:
            title: Novel title.
            author: Novel author (optional).
            cover_url: Cover image URL (optional).
            status: Novel status (default: 'active').
            
        Returns:
            int: The ID of the newly created novel.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO novels (title, author, cover_url, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (title, author, cover_url, status, now, now)
            )
            return cursor.lastrowid
    
    def get_novel(self, novel_id: int) -> Optional[Dict[str, Any]]:
        """
        Get novel by ID.
        
        Args:
            novel_id: The novel ID to retrieve.
            
        Returns:
            Optional[Dict]: Novel data or None if not found.
        """
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM novels WHERE id = ?", (novel_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def get_novel_with_chapter_count(self, novel_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a novel by ID with chapter count.
        
        Uses SQL COUNT aggregation to avoid N+1 query.
        
        Args:
            novel_id: The novel ID to retrieve.
            
        Returns:
            Dict: Novel data with chapter_count, or None if not found.
        """
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT n.*, COUNT(c.id) as chapter_count
            FROM novels n
            LEFT JOIN chapters c ON n.id = c.novel_id
            WHERE n.id = ?
            GROUP BY n.id
            """,
            (novel_id,)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def list_novels(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List all novels sorted by updated_at descending.
        
        Args:
            limit: Maximum number of novels to return.
            offset: Number of novels to skip.
            
        Returns:
            List[Dict]: List of novel data dictionaries.
        """
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT * FROM novels
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def list_novels_with_chapter_count(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List all novels with chapter counts using SQL COUNT aggregation.
        
        Uses a single query with LEFT JOIN to avoid N+1 query problem.
        
        Args:
            limit: Maximum number of novels to return.
            offset: Number of novels to skip.
            
        Returns:
            List[Dict]: List of novel data with chapter_count included.
        """
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT n.*, COUNT(c.id) as chapter_count
            FROM novels n
            LEFT JOIN chapters c ON n.id = c.novel_id
            GROUP BY n.id
            ORDER BY n.updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def update_novel(
        self,
        novel_id: int,
        **kwargs: Any
    ) -> bool:
        """
        Update novel metadata.
        
        Args:
            novel_id: The novel ID to update.
            **kwargs: Fields to update (title, author, cover_url, status, etc.).
            
        Returns:
            bool: True if update was successful.
        """
        if not kwargs:
            return False
        
        allowed_fields = {
            'title', 'author', 'cover_url', 'synopsis', 'tags', 'status'
        }
        update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not update_fields:
            return False
        
        # Add updated_at timestamp
        update_fields['updated_at'] = 'CURRENT_TIMESTAMP'
        
        with self.transaction() as conn:
            cursor = conn.cursor()
            set_clause = ', '.join([f"{k} = ?" for k in update_fields.keys()])
            values = list(update_fields.values()) + [novel_id]
            
            cursor.execute(
                f"UPDATE novels SET {set_clause} WHERE id = ?",
                values
            )
            return cursor.rowcount > 0
    
    def count_novels(self) -> int:
        """
        Count total number of novels.
        
        Returns:
            int: Total count of novels in the database.
        """
        cursor = self.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM novels")
        return cursor.fetchone()[0]
    
    def get_pipeline_states_by_novel(self, novel_id: int) -> List[Dict[str, Any]]:
        """
        Get all pipeline state records for a novel.
        
        Args:
            novel_id: The novel ID to get states for.
            
        Returns:
            List[Dict]: List of pipeline state records.
        """
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT * FROM pipeline_state
            WHERE novel_id = ?
            ORDER BY phase
            """,
            (novel_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def delete_novel(self, novel_id: int) -> bool:
        """
        Delete novel and cascade delete chapters.
        
        Args:
            novel_id: The novel ID to delete.
            
        Returns:
            bool: True if deletion was successful.
        """
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM novels WHERE id = ?", (novel_id,))
            return cursor.rowcount > 0
    
    # Chapter operations
    
    def create_chapter(
        self,
        chapter_index: int,
        filename: str,
        novel_id: Optional[int] = None,
        title: Optional[str] = None
    ) -> int:
        """
        Create a new chapter entry.
        
        Args:
            chapter_index: The chapter number/index.
            filename: The source filename.
            novel_id: Associated novel ID (optional for backward compatibility).
            title: Chapter title (optional).
            
        Returns:
            int: The ID of the newly created chapter.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chapters (novel_id, chapter_index, filename, title, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (novel_id, chapter_index, filename, title, now)
            )
            return cursor.lastrowid
    
    def get_chapter(self, chapter_id: int) -> Optional[Dict[str, Any]]:
        """
        Get chapter by ID.
        
        Args:
            chapter_id: The chapter ID to retrieve.
            
        Returns:
            Optional[Dict]: Chapter data or None if not found.
        """
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def get_chapters_by_novel(self, novel_id: int) -> List[Dict[str, Any]]:
        """
        Get all chapters for a novel.
        
        Args:
            novel_id: The novel ID.
            
        Returns:
            List[Dict]: List of chapter data dictionaries.
        """
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT * FROM chapters
            WHERE novel_id = ?
            ORDER BY chapter_index ASC
            """,
            (novel_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def get_all_chapters(self) -> List[Dict[str, Any]]:
        """
        Get all chapters (including those with NULL novel_id for legacy support).
        
        Returns:
            List[Dict]: List of all chapter data dictionaries.
        """
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT * FROM chapters
            ORDER BY chapter_index ASC
            """
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def update_chapter_novel(
        self,
        chapter_id: int,
        novel_id: Optional[int]
    ) -> bool:
        """
        Associate a chapter with a novel.
        
        Args:
            chapter_id: The chapter ID to update.
            novel_id: The novel ID to associate (None for backward compatibility).
            
        Returns:
            bool: True if update was successful.
        """
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE chapters SET novel_id = ? WHERE id = ?",
                (novel_id, chapter_id)
            )
            return cursor.rowcount > 0
    
    def update_chapter(
        self,
        chapter_id: int,
        **kwargs: Any
    ) -> bool:
        """
        Update chapter metadata.
        
        Args:
            chapter_id: The chapter ID to update.
            **kwargs: Fields to update (chapter_index, filename, title, etc.).
            
        Returns:
            bool: True if update was successful.
        """
        if not kwargs:
            return False
        
        allowed_fields = {'chapter_index', 'filename', 'title'}
        update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not update_fields:
            return False
        
        with self.transaction() as conn:
            cursor = conn.cursor()
            set_clause = ', '.join([f"{k} = ?" for k in update_fields.keys()])
            values = list(update_fields.values()) + [chapter_id]
            
            cursor.execute(
                f"UPDATE chapters SET {set_clause} WHERE id = ?",
                values
            )
            return cursor.rowcount > 0
    
    def delete_chapter(self, chapter_id: int) -> bool:
        """
        Delete a chapter.
        
        Args:
            chapter_id: The chapter ID to delete.
            
        Returns:
            bool: True if deletion was successful.
        """
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chapters WHERE id = ?", (chapter_id,))
            return cursor.rowcount > 0
    
    # Pipeline state operations
    
    def update_pipeline_state(
        self,
        phase: str,
        status: str,
        novel_id: Optional[int] = None,
        last_chapter: Optional[int] = None,
        total_chapters: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> int:
        """
        Update or create pipeline state for a phase.
        
        Args:
            phase: Pipeline phase (sanitize, transform, render).
            status: Phase status (pending, running, complete, failed).
            novel_id: Associated novel ID (optional for legacy).
            last_chapter: Last processed chapter number.
            total_chapters: Total chapters to process.
            error_message: Error message if failed.
            
        Returns:
            int: The ID of the updated or created pipeline state.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction() as conn:
            cursor = conn.cursor()
            
            # Check if exists
            cursor.execute(
                """
                SELECT id FROM pipeline_state
                WHERE novel_id IS ? AND phase IS ?
                """,
                (novel_id, phase)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing
                cursor.execute(
                    """
                    UPDATE pipeline_state
                    SET status = ?, last_chapter = ?, total_chapters = ?,
                        error_message = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status, last_chapter, total_chapters, error_message, now, existing['id'])
                )
                return existing['id']
            else:
                # Insert new
                cursor.execute(
                    """
                    INSERT INTO pipeline_state
                    (novel_id, phase, status, last_chapter, total_chapters, error_message, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (novel_id, phase, status, last_chapter, total_chapters, error_message, now)
                )
                return cursor.lastrowid
    
    def get_pipeline_state(
        self,
        phase: str,
        novel_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get pipeline state for a phase.
        
        Args:
            phase: Pipeline phase.
            novel_id: Novel ID (optional for legacy).
            
        Returns:
            Optional[Dict]: Pipeline state data or None if not found.
        """
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT * FROM pipeline_state
            WHERE novel_id IS ? AND phase = ?
            """,
            (novel_id, phase)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def get_all_pipeline_states(
        self,
        novel_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all pipeline states for a novel.
        
        Args:
            novel_id: Novel ID (optional for legacy).
            
        Returns:
            List[Dict]: List of pipeline state data dictionaries.
        """
        cursor = self.connection.cursor()
        if novel_id is not None:
            cursor.execute(
                """
                SELECT * FROM pipeline_state
                WHERE novel_id = ?
                ORDER BY phase
                """,
                (novel_id,)
            )
        else:
            cursor.execute(
                """
                SELECT * FROM pipeline_state
                WHERE novel_id IS NULL
                ORDER BY phase
                """
            )
        return [dict(row) for row in cursor.fetchall()]
    
    def delete_pipeline_state(
        self,
        phase: str,
        novel_id: Optional[int] = None
    ) -> bool:
        """
        Delete pipeline state for a phase.
        
        Args:
            phase: Pipeline phase.
            novel_id: Novel ID (optional for legacy).
            
        Returns:
            bool: True if deletion was successful.
        """
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM pipeline_state
                WHERE novel_id IS ? AND phase = ?
                """,
                (novel_id, phase)
            )
            return cursor.rowcount > 0
    
    def close(self) -> None:
        """Close the thread-local database connection."""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            del self._local.conn