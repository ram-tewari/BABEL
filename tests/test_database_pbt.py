"""
Property-based tests for database cascade deletion and data integrity.

These tests validate universal correctness properties that should hold
across all valid executions of the multi-novel library management system.
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
    # Filter out surrogate characters and control characters
    title = draw(st.text(
        min_size=1,
        max_size=500,
        alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0d\x0e\x0f'  # Exclude control chars including form feed
        )
    ))
    return title


# Strategy for generating chapter counts
chapter_count_strategy = st.integers(min_value=1, max_value=150)


@settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    novel_title=novel_title_strategy(),
    chapter_count=chapter_count_strategy
)
def test_property_1_cascade_deletion_integrity(novel_title, chapter_count):
    """
    Feature: phase-7-librarian, Property 1: Cascade Deletion Integrity
    
    For any novel with associated chapters, when the novel is deleted
    from the database, all associated chapters should be automatically
    deleted, leaving no orphaned records.
    
    Validates: Requirements 1.3, 3.7
    """
    # Create a fresh database for this test using a temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_babel.db"
        db = DatabaseManager(db_path)
        
        try:
            # Create novel
            novel_id = db.create_novel(title=novel_title)
            
            # Create chapters with the novel_id
            chapter_ids = []
            for i in range(chapter_count):
                chapter_id = db.create_chapter(
                    novel_id=novel_id,
                    chapter_index=i + 1,
                    filename=f"Ch_{i + 1:03d}.txt",
                    title=f"Chapter {i + 1}"
                )
                chapter_ids.append(chapter_id)
            
            # Verify chapters exist
            chapters_before = db.get_chapters_by_novel(novel_id)
            assert len(chapters_before) == chapter_count, (
                f"Expected {chapter_count} chapters before deletion, found {len(chapters_before)}"
            )
            
            # Verify each chapter exists
            for chapter_id in chapter_ids:
                chapter = db.get_chapter(chapter_id)
                assert chapter is not None, f"Chapter {chapter_id} should exist before deletion"
                assert chapter['novel_id'] == novel_id, (
                    f"Chapter {chapter_id} should be associated with novel {novel_id}"
                )
            
            # Delete the novel
            result = db.delete_novel(novel_id)
            assert result is True, f"Deleting novel {novel_id} should return True"
            
            # Verify novel is deleted
            novel = db.get_novel(novel_id)
            assert novel is None, f"Novel {novel_id} should be deleted"
            
            # Verify all chapters are cascade deleted
            chapters_after = db.get_chapters_by_novel(novel_id)
            assert len(chapters_after) == 0, (
                f"Expected 0 chapters after deletion, found {len(chapters_after)}"
            )
            
            # Verify each chapter is deleted
            for chapter_id in chapter_ids:
                chapter = db.get_chapter(chapter_id)
                assert chapter is None, f"Chapter {chapter_id} should be deleted after novel deletion"
        
        finally:
            db.close()


@settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    novel_title=novel_title_strategy(),
    chapter_count=chapter_count_strategy
)
def test_property_1_cascade_deletion_preserves_legacy_chapters(novel_title, chapter_count):
    """
    Feature: phase-7-librarian, Property 1: Cascade Deletion Integrity
    
    For any novel with associated chapters, when the novel is deleted,
    chapters with NULL novel_id (legacy chapters) should NOT be affected
    by the cascade deletion.
    
    Validates: Requirements 1.3, 3.7, 1.5 (backward compatibility)
    """
    # Create a fresh database for this test using a temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_babel.db"
        db = DatabaseManager(db_path)
        
        try:
            # Create novel
            novel_id = db.create_novel(title=novel_title)
            
            # Create chapters with the novel_id
            for i in range(chapter_count):
                db.create_chapter(
                    novel_id=novel_id,
                    chapter_index=i + 1,
                    filename=f"Ch_{i + 1:03d}.txt"
                )
            
            # Create legacy chapters (no novel_id)
            legacy_chapter_ids = []
            for i in range(chapter_count):
                chapter_id = db.create_chapter(
                    novel_id=None,
                    chapter_index=i + 1,
                    filename=f"Legacy_Ch_{i + 1:03d}.txt"
                )
                legacy_chapter_ids.append(chapter_id)
            
            # Verify all chapters exist
            all_chapters = db.get_all_chapters()
            assert len(all_chapters) == 2 * chapter_count, (
                f"Expected {2 * chapter_count} chapters before deletion, found {len(all_chapters)}"
            )
            
            # Delete the novel
            db.delete_novel(novel_id)
            
            # Verify novel is deleted
            novel = db.get_novel(novel_id)
            assert novel is None
            
            # Verify novel's chapters are deleted
            chapters_after = db.get_chapters_by_novel(novel_id)
            assert len(chapters_after) == 0
            
            # Verify legacy chapters still exist
            all_chapters_after = db.get_all_chapters()
            assert len(all_chapters_after) == chapter_count, (
                f"Expected {chapter_count} legacy chapters after deletion, "
                f"found {len(all_chapters_after)}"
            )
            
            # Verify each legacy chapter still exists
            for chapter_id in legacy_chapter_ids:
                chapter = db.get_chapter(chapter_id)
                assert chapter is not None, f"Legacy chapter {chapter_id} should still exist"
                assert chapter['novel_id'] is None, (
                    f"Legacy chapter {chapter_id} should still have NULL novel_id"
                )
        
        finally:
            db.close()


@settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    novel_title=novel_title_strategy(),
    chapter_count=chapter_count_strategy
)
def test_property_1_cascade_deletion_pipeline_state(novel_title, chapter_count):
    """
    Feature: phase-7-librarian, Property 1: Cascade Deletion Integrity
    
    For any novel with associated pipeline states, when the novel is deleted,
    all associated pipeline states should be automatically deleted along with
    the chapters, leaving no orphaned records.
    
    Validates: Requirements 1.3, 3.7, 1.6
    """
    # Create a fresh database for this test using a temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_babel.db"
        db = DatabaseManager(db_path)
        
        try:
            # Create novel
            novel_id = db.create_novel(title=novel_title)
            
            # Create chapters
            for i in range(chapter_count):
                db.create_chapter(
                    novel_id=novel_id,
                    chapter_index=i + 1,
                    filename=f"Ch_{i + 1:03d}.txt"
                )
            
            # Create pipeline states for the novel
            phases = ['sanitize', 'transform', 'render']
            for phase in phases:
                db.update_pipeline_state(
                    novel_id=novel_id,
                    phase=phase,
                    status='complete',
                    last_chapter=chapter_count,
                    total_chapters=chapter_count
                )
            
            # Verify pipeline states exist
            pipeline_states = db.get_all_pipeline_states(novel_id)
            assert len(pipeline_states) == len(phases), (
                f"Expected {len(phases)} pipeline states before deletion, "
                f"found {len(pipeline_states)}"
            )
            
            # Delete the novel
            db.delete_novel(novel_id)
            
            # Verify novel is deleted
            novel = db.get_novel(novel_id)
            assert novel is None
            
            # Verify chapters are deleted
            chapters_after = db.get_chapters_by_novel(novel_id)
            assert len(chapters_after) == 0
            
            # Verify pipeline states are cascade deleted
            pipeline_states_after = db.get_all_pipeline_states(novel_id)
            assert len(pipeline_states_after) == 0, (
                f"Expected 0 pipeline states after deletion, "
                f"found {len(pipeline_states_after)}"
            )
        
        finally:
            db.close()


@settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    novel_title=novel_title_strategy(),
    chapter_count=chapter_count_strategy
)
def test_property_1_cascade_deletion_multiple_novels(novel_title, chapter_count):
    """
    Feature: phase-7-librarian, Property 1: Cascade Deletion Integrity
    
    For any set of novels with chapters, when one novel is deleted,
    only that novel's chapters should be deleted. Other novels and
    their chapters should remain unaffected.
    
    Validates: Requirements 1.3, 3.7
    """
    # Create a fresh database for this test using a temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_babel.db"
        db = DatabaseManager(db_path)
        
        try:
            # Create first novel
            novel_id_1 = db.create_novel(title=f"First {novel_title}")
            
            # Create chapters for first novel
            chapter_ids_1 = []
            for i in range(chapter_count):
                chapter_id = db.create_chapter(
                    novel_id=novel_id_1,
                    chapter_index=i + 1,
                    filename=f"Novel1_Ch_{i + 1:03d}.txt"
                )
                chapter_ids_1.append(chapter_id)
            
            # Create second novel
            novel_id_2 = db.create_novel(title=f"Second {novel_title}")
            
            # Create chapters for second novel
            chapter_ids_2 = []
            for i in range(chapter_count):
                chapter_id = db.create_chapter(
                    novel_id=novel_id_2,
                    chapter_index=i + 1,
                    filename=f"Novel2_Ch_{i + 1:03d}.txt"
                )
                chapter_ids_2.append(chapter_id)
            
            # Verify both novels and their chapters exist
            novel_1 = db.get_novel(novel_id_1)
            novel_2 = db.get_novel(novel_id_2)
            chapters_1 = db.get_chapters_by_novel(novel_id_1)
            chapters_2 = db.get_chapters_by_novel(novel_id_2)
            
            assert novel_1 is not None
            assert novel_2 is not None
            assert len(chapters_1) == chapter_count
            assert len(chapters_2) == chapter_count
            
            # Delete first novel
            db.delete_novel(novel_id_1)
            
            # Verify first novel is deleted
            novel_1_after = db.get_novel(novel_id_1)
            assert novel_1_after is None
            
            # Verify first novel's chapters are deleted
            chapters_1_after = db.get_chapters_by_novel(novel_id_1)
            assert len(chapters_1_after) == 0
            
            # Verify second novel still exists
            novel_2_after = db.get_novel(novel_id_2)
            assert novel_2_after is not None
            assert novel_2_after['title'] == f"Second {novel_title}"
            
            # Verify second novel's chapters still exist
            chapters_2_after = db.get_chapters_by_novel(novel_id_2)
            assert len(chapters_2_after) == chapter_count
            
            # Verify each chapter of second novel still exists
            for chapter_id in chapter_ids_2:
                chapter = db.get_chapter(chapter_id)
                assert chapter is not None, f"Chapter {chapter_id} should still exist"
                assert chapter['novel_id'] == novel_id_2, (
                    f"Chapter {chapter_id} should still be associated with novel {novel_id_2}"
                )
        
        finally:
            db.close()