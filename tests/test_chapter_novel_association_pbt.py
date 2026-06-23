"""
Property-based tests for chapter-novel association.

These tests validate universal correctness properties that should hold
across all valid executions of the multi-novel library management system.

Property 9: Chapter-Novel Association
Validates: Requirements 2.4
"""

import pytest
import tempfile
from pathlib import Path
from hypothesis import given, strategies as st, settings, HealthCheck

from babel.data.db import DatabaseManager


# Strategy for generating novel titles
@st.composite
def novel_title_strategy(draw):
    """Generate a valid novel title."""
    title = draw(st.text(
        min_size=1,
        max_size=500,
        alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0d\x0e\x0f'
        )
    ))
    return title


# Strategy for generating chapter indices
@st.composite
def chapter_index_strategy(draw):
    """Generate a valid chapter index."""
    return draw(st.integers(min_value=1, max_value=1000))


# Strategy for generating chapter filenames
@st.composite
def chapter_filename_strategy(draw):
    """Generate a valid chapter filename."""
    prefix = draw(st.text(min_size=1, max_size=20, alphabet=st.ascii_letters))
    chapter_num = draw(st.integers(min_value=1, max_value=1000))
    return f"{prefix}_{chapter_num:03d}.txt"


# Strategy for generating chapter titles
@st.composite
def chapter_title_strategy(draw):
    """Generate a valid chapter title."""
    title = draw(st.text(
        min_size=1,
        max_size=200,
        alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0d\x0e\x0f'
        )
    ))
    return title


# Strategy for generating chapter counts
chapter_count_strategy = st.integers(min_value=1, max_value=50)


@settings(max_examples=15, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    novel_title=novel_title_strategy(),
    chapter_count=chapter_count_strategy
)
def test_property_9_chapter_novel_association(novel_title, chapter_count):
    """
    Feature: cli-sqlite-migration, Property 9: Chapter-Novel Association
    
    For any novel created in the database, when chapters are created with
    the novel_id parameter, all chapters should be correctly associated
    with that novel_id and can be queried by novel_id.
    
    Validates: Requirements 2.4
    """
    # Create a fresh database for this test using a temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_babel.db"
        db = DatabaseManager(db_path)
        
        try:
            # Create a novel
            novel_id = db.create_novel(title=novel_title)
            
            # Verify novel was created
            assert novel_id is not None, "Novel should be created with a valid ID"
            assert novel_id > 0, "Novel ID should be a positive integer"
            
            # Create chapters with the novel_id
            created_chapters = []
            for i in range(chapter_count):
                chapter_id = db.create_chapter(
                    novel_id=novel_id,
                    chapter_index=i + 1,
                    filename=f"chapter_{i + 1:03d}.txt",
                    title=f"Chapter {i + 1}"
                )
                created_chapters.append({
                    'id': chapter_id,
                    'chapter_index': i + 1,
                    'filename': f"chapter_{i + 1:03d}.txt",
                    'title': f"Chapter {i + 1}"
                })
            
            # Verify all chapters were created
            assert len(created_chapters) == chapter_count, (
                f"Expected {chapter_count} chapters to be created, got {len(created_chapters)}"
            )
            
            # Query chapters by novel_id
            chapters = db.get_chapters_by_novel(novel_id)
            
            # Verify correct number of chapters returned
            assert len(chapters) == chapter_count, (
                f"Expected {chapter_count} chapters for novel {novel_id}, got {len(chapters)}"
            )
            
            # Verify each chapter is correctly associated with the novel
            for i, chapter in enumerate(chapters):
                assert chapter['novel_id'] == novel_id, (
                    f"Chapter {chapter['id']} should be associated with novel {novel_id}, "
                    f"but has novel_id={chapter['novel_id']}"
                )
            
            # Verify chapters are ordered by chapter_index
            for i in range(len(chapters) - 1):
                assert chapters[i]['chapter_index'] <= chapters[i + 1]['chapter_index'], (
                    "Chapters should be ordered by chapter_index"
                )
            
            # Verify each created chapter can be retrieved individually
            for created_chapter in created_chapters:
                chapter = db.get_chapter(created_chapter['id'])
                assert chapter is not None, f"Chapter {created_chapter['id']} should exist"
                assert chapter['novel_id'] == novel_id, (
                    f"Chapter {created_chapter['id']} should be associated with novel {novel_id}"
                )
                assert chapter['chapter_index'] == created_chapter['chapter_index'], (
                    f"Chapter {created_chapter['id']} should have correct chapter_index"
                )
                assert chapter['filename'] == created_chapter['filename'], (
                    f"Chapter {created_chapter['id']} should have correct filename"
                )
        
        finally:
            db.close()


@settings(max_examples=15, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    novel_title=novel_title_strategy(),
    chapter_count=chapter_count_strategy
)
def test_property_9_chapter_novel_foreign_key_relationship(novel_title, chapter_count):
    """
    Feature: cli-sqlite-migration, Property 9: Chapter-Novel Association
    
    For any chapters created with a novel_id, the foreign key relationship
    should be maintained such that querying the novel returns all associated
    chapters and the chapter count is accurate.
    
    Validates: Requirements 2.4
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_babel.db"
        db = DatabaseManager(db_path)
        
        try:
            # Create a novel
            novel_id = db.create_novel(title=novel_title)
            
            # Create chapters with the novel_id
            for i in range(chapter_count):
                db.create_chapter(
                    novel_id=novel_id,
                    chapter_index=i + 1,
                    filename=f"ch_{i + 1:03d}.txt",
                    title=f"Chapter {i + 1}: Test Title"
                )
            
            # Verify novel exists and has correct chapter count
            novel = db.get_novel_with_chapter_count(novel_id)
            assert novel is not None, f"Novel {novel_id} should exist"
            assert novel['chapter_count'] == chapter_count, (
                f"Novel {novel_id} should have {chapter_count} chapters, "
                f"got {novel['chapter_count']}"
            )
            
            # Verify the novel's chapters can be filtered by novel_id
            all_chapters = db.get_all_chapters()
            novel_chapters = [ch for ch in all_chapters if ch['novel_id'] == novel_id]
            
            assert len(novel_chapters) == chapter_count, (
                f"Filtering all chapters by novel_id {novel_id} should return "
                f"{chapter_count} chapters, got {len(novel_chapters)}"
            )
            
            # Verify no chapters from other novels are included
            other_novel_chapters = [ch for ch in all_chapters if ch['novel_id'] != novel_id]
            for chapter in other_novel_chapters:
                assert chapter['novel_id'] != novel_id, (
                    f"Chapter {chapter['id']} should not be associated with novel {novel_id}"
                )
        
        finally:
            db.close()


@settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    novel_title=novel_title_strategy(),
    chapter_count=chapter_count_strategy
)
def test_property_9_chapter_query_by_novel_id(novel_title, chapter_count):
    """
    Feature: cli-sqlite-migration, Property 9: Chapter-Novel Association
    
    For any set of novels with chapters, querying chapters by novel_id should
    return only chapters associated with that specific novel, and no chapters
    from other novels should be included in the results.
    
    Validates: Requirements 2.4
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_babel.db"
        db = DatabaseManager(db_path)
        
        try:
            # Create multiple novels
            novel_ids = []
            for i in range(3):
                novel_id = db.create_novel(title=f"{novel_title} - Book {i + 1}")
                novel_ids.append(novel_id)
                
                # Create chapters for each novel
                for j in range(chapter_count):
                    db.create_chapter(
                        novel_id=novel_id,
                        chapter_index=j + 1,
                        filename=f"novel{i + 1}_ch_{j + 1:03d}.txt",
                        title=f"Book {i + 1}, Chapter {j + 1}"
                    )
            
            # For each novel, verify querying by novel_id returns only its chapters
            for i, novel_id in enumerate(novel_ids):
                chapters = db.get_chapters_by_novel(novel_id)
                
                # Verify correct count
                assert len(chapters) == chapter_count, (
                    f"Novel {novel_id} should have {chapter_count} chapters, "
                    f"got {len(chapters)}"
                )
                
                # Verify all chapters belong to this novel
                for chapter in chapters:
                    assert chapter['novel_id'] == novel_id, (
                        f"Chapter {chapter['id']} should belong to novel {novel_id}, "
                        f"but has novel_id={chapter['novel_id']}"
                    )
                    # Verify chapter filename contains novel identifier
                    assert f"novel{i + 1}" in chapter['filename'], (
                        f"Chapter {chapter['id']} filename should contain novel identifier"
                    )
            
            # Verify that chapters from one novel are not in another novel's results
            chapters_novel_1 = db.get_chapters_by_novel(novel_ids[0])
            chapters_novel_2 = db.get_chapters_by_novel(novel_ids[1])
            
            chapter_ids_novel_1 = {ch['id'] for ch in chapters_novel_1}
            chapter_ids_novel_2 = {ch['id'] for ch in chapters_novel_2}
            
            # Ensure no overlap between novels
            assert len(chapter_ids_novel_1.intersection(chapter_ids_novel_2)) == 0, (
                "Chapters from different novels should not overlap"
            )
        
        finally:
            db.close()