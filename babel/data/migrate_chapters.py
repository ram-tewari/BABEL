#!/usr/bin/env python3
"""
Migration script to import chapter JSON files into the database.

This script:
1. Reads all chapter JSON files from data/json/ directory
2. Creates a novel entry for "Infinite Mage" if not already present
3. Parses each JSON file and creates chapter entries in the database
4. Handles errors gracefully and logs issues
5. Is idempotent - can be run multiple times safely
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, Any
import sys

from babel.data.db import DatabaseManager


def extract_chapter_index(filename: str) -> Optional[int]:
    """
    Extract chapter index from filename.
    
    Examples:
        "000_chapter_1.json" -> 1
        "001_chapter_1_encountering_magic_1.json" -> 1
        "042_chapter_42_another_genius_4.json" -> 42
    
    Args:
        filename: The JSON filename
        
    Returns:
        The chapter index as an integer, or None if parsing fails
    """
    # Match pattern: digits_chapter_NUMBER
    match = re.search(r'_chapter_(\d+)', filename)
    if match:
        return int(match.group(1))
    return None


def get_or_create_novel(db: DatabaseManager, title: str, author: str) -> int:
    """
    Get existing novel or create a new one.
    
    Args:
        db: DatabaseManager instance
        title: Novel title
        author: Novel author
        
    Returns:
        The novel ID
    """
    # Check if novel already exists
    novels = db.list_novels()
    for novel in novels:
        if novel['title'] == title:
            print(f"✓ Novel '{title}' already exists (ID: {novel['id']})")
            return novel['id']
    
    # Create new novel
    novel_id = db.create_novel(title=title, author=author)
    print(f"✓ Created novel '{title}' (ID: {novel_id})")
    return novel_id


def migrate_chapters(json_dir: Path = Path("data/json")) -> None:
    """
    Migrate all chapter JSON files to the database.
    
    Args:
        json_dir: Path to directory containing chapter JSON files
    """
    db = DatabaseManager()
    
    # Ensure json_dir exists
    if not json_dir.exists():
        print(f"✗ Error: Directory {json_dir} does not exist")
        sys.exit(1)
    
    # Get or create the novel
    novel_id = get_or_create_novel(db, "Infinite Mage", "Unknown")
    
    # Get all JSON files sorted by filename
    json_files = sorted(json_dir.glob("*.json"))
    
    if not json_files:
        print(f"✗ No JSON files found in {json_dir}")
        sys.exit(1)
    
    print(f"\nProcessing {len(json_files)} chapter files...")
    
    skipped = 0
    created = 0
    errors = 0
    
    for json_file in json_files:
        try:
            # Extract chapter index from filename
            chapter_index = extract_chapter_index(json_file.name)
            if chapter_index is None:
                print(f"⚠ Skipped {json_file.name}: Could not extract chapter index")
                skipped += 1
                continue
            
            # Check if chapter already exists
            existing_chapters = db.get_chapters_by_novel(novel_id)
            if any(ch['chapter_index'] == chapter_index for ch in existing_chapters):
                print(f"⊘ Chapter {chapter_index} already exists, skipping")
                skipped += 1
                continue
            
            # Read and parse JSON
            with open(json_file, 'r', encoding='utf-8') as f:
                chapter_data = json.load(f)
            
            # Create chapter entry
            chapter_id = db.create_chapter(
                chapter_index=chapter_index,
                filename=json_file.name,
                novel_id=novel_id,
                title=f"Chapter {chapter_index}"
            )
            
            print(f"✓ Created chapter {chapter_index} (ID: {chapter_id})")
            created += 1
            
        except json.JSONDecodeError as e:
            print(f"✗ Error parsing {json_file.name}: {e}")
            errors += 1
        except Exception as e:
            print(f"✗ Error processing {json_file.name}: {e}")
            errors += 1
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"Migration Summary:")
    print(f"  Created:  {created}")
    print(f"  Skipped:  {skipped}")
    print(f"  Errors:   {errors}")
    print(f"  Total:    {len(json_files)}")
    print(f"{'='*50}")
    
    db.close()


if __name__ == "__main__":
    migrate_chapters()
