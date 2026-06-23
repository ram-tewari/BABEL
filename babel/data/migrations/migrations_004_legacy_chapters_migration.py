"""
Migration script for backward compatibility with existing chapters.

This migration:
1. Creates a default "legacy" novel titled "Infinite Mage" if it doesn't exist
2. Associates all chapters with NULL novel_id to this legacy novel

This ensures backward compatibility with existing single-novel workflows
while enabling the new multi-novel library management system.

Requirements: 8.2
"""

import sqlite3
from pathlib import Path
from typing import Optional


LEGACY_NOVEL_TITLE = "Infinite Mage"


def get_legacy_novel_id(db_path: Path) -> Optional[int]:
    """
    Check if a legacy novel already exists and return its ID.
    
    Args:
        db_path: Path to the SQLite database file.
        
    Returns:
        Novel ID if found, None otherwise.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id FROM novels WHERE title = ?",
        (LEGACY_NOVEL_TITLE,)
    )
    row = cursor.fetchone()
    
    conn.close()
    
    if row:
        return row["id"]
    return None


def create_legacy_novel(db_path: Path) -> int:
    """
    Create the legacy novel entry.
    
    Args:
        db_path: Path to the SQLite database file.
        
    Returns:
        The ID of the newly created novel.
    """
    from datetime import datetime, timezone
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    now = datetime.now(timezone.utc).isoformat()
    
    cursor.execute(
        """
        INSERT INTO novels (title, author, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (LEGACY_NOVEL_TITLE, None, "active", now, now)
    )
    
    novel_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return novel_id


def get_legacy_chapters(db_path: Path) -> list:
    """
    Get all chapters with NULL novel_id.
    
    Args:
        db_path: Path to the SQLite database file.
        
    Returns:
        List of chapter dictionaries with NULL novel_id.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT id, chapter_index, filename, title FROM chapters
        WHERE novel_id IS NULL
        ORDER BY chapter_index ASC
        """
    )
    
    chapters = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return chapters


def associate_chapters_with_legacy_novel(db_path: Path, novel_id: int) -> int:
    """
    Associate all chapters with NULL novel_id to the legacy novel.
    
    Args:
        db_path: Path to the SQLite database file.
        novel_id: The legacy novel ID to associate chapters with.
        
    Returns:
        Number of chapters updated.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE chapters SET novel_id = ? WHERE novel_id IS NULL",
        (novel_id,)
    )
    
    updated_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    return updated_count


def run_migration(db_path: Path = Path("data/babel.db")) -> dict:
    """
    Run the legacy chapters migration.
    
    This migration ensures backward compatibility by:
    1. Creating a legacy novel titled "Infinite Mage" if needed
    2. Associating all existing chapters (with NULL novel_id) to this novel
    
    Args:
        db_path: Path to the SQLite database file.
        
    Returns:
        Dictionary with migration results:
        - legacy_novel_id: ID of the legacy novel (existing or newly created)
        - chapters_associated: Number of chapters associated with the legacy novel
        - is_new: True if a new legacy novel was created
    """
    db_path = Path(db_path)
    
    # Check if legacy novel already exists
    legacy_novel_id = get_legacy_novel_id(db_path)
    
    is_new = False
    if legacy_novel_id is None:
        # Create the legacy novel
        legacy_novel_id = create_legacy_novel(db_path)
        is_new = True
    
    # Get and associate chapters with NULL novel_id
    chapters = get_legacy_chapters(db_path)
    chapters_associated = associate_chapters_with_legacy_novel(db_path, legacy_novel_id)
    
    return {
        "legacy_novel_id": legacy_novel_id,
        "chapters_associated": chapters_associated,
        "is_new": is_new,
        "legacy_novel_title": LEGACY_NOVEL_TITLE
    }


def check_migration_status(db_path: Path = Path("data/babel.db")) -> dict:
    """
    Check the status of the legacy chapters migration.
    
    Args:
        db_path: Path to the SQLite database file.
        
    Returns:
        Dictionary with migration status:
        - legacy_novel_exists: Whether the legacy novel exists
        - legacy_novel_id: ID of the legacy novel if it exists
        - unassociated_chapters: Number of chapters still with NULL novel_id
        - migration_needed: True if migration should be run
    """
    db_path = Path(db_path)
    
    legacy_novel_id = get_legacy_novel_id(db_path)
    chapters = get_legacy_chapters(db_path)
    
    return {
        "legacy_novel_exists": legacy_novel_id is not None,
        "legacy_novel_id": legacy_novel_id,
        "unassociated_chapters": len(chapters),
        "migration_needed": len(chapters) > 0 or legacy_novel_id is None
    }


if __name__ == "__main__":
    import sys
    
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/babel.db")
    
    print(f"Running legacy chapters migration on: {db_path}")
    print()
    
    # Check current status
    status = check_migration_status(db_path)
    print(f"Current status:")
    print(f"  Legacy novel exists: {status['legacy_novel_exists']}")
    print(f"  Unassociated chapters: {status['unassociated_chapters']}")
    print(f"  Migration needed: {status['migration_needed']}")
    print()
    
    if status["migration_needed"]:
        # Run migration
        result = run_migration(db_path)
        print(f"Migration results:")
        print(f"  Legacy novel ID: {result['legacy_novel_id']}")
        print(f"  Legacy novel title: {result['legacy_novel_title']}")
        print(f"  New novel created: {result['is_new']}")
        print(f"  Chapters associated: {result['chapters_associated']}")
    else:
        print("Migration not needed - all chapters are already associated.")