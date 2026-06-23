"""
Property-based tests for database layer operations.

These tests validate universal correctness properties for multi-novel
database operations, ensuring that novel creation, chapter filtering,
and cascade deletion work correctly across all valid inputs.

Feature: multi-novel-ingestion-support
Validates: Properties 2, 4, 5
"""

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, HealthCheck, strategies as st

from babel.data.db import DatabaseManager


# ============================================================================
# Strategies for generating test data
# ============================================================================

@st.composite
def novel_title_strategy(draw):
    """Generate a valid novel title."""
    return draw(st.text(min_size=1, max_size=200))


@st.composite
def author_name_strategy(draw):
    """Generate a valid author name (can be None)."""
    use_none = draw(st.booleans())
    if use_none:
        return None
    return draw(st.text(min_size=1, max_size=100))


@st.composite
def chapter_data_strategy(draw):
    """Generate valid chapter data."""
    index = draw(st.integers(min_value=0, max_value=1000))
    # Filter out control characters and special characters
    title = draw(st.text(
        min_size=1,
        max_size=200,
        alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='<>'
        )
    ))
    filename = f"chapter_{index:04d}.txt"
    return {
        'index': index,
        'filename': filename,
        'title': title
    }


@st.composite
def novel_with_chapters_strategy(draw):
    """Generate a novel with associated chapters."""
    num_chapters = draw(st.integers(min_value=1, max_value=20))
    title = draw(st.text(min_size=1, max_size=200))
    author = draw(author_name_strategy())
    
    chapters = []
    for i in range(num_chapters):
        chapters.append({
            'index': i,
            'filename': f"chapter_{i:04d}.txt",
            'title': f"Chapter {i + 1}"
        })
    
    return {
        'title': title,
        'author': author,
        'chapters': chapters
    }


# ============================================================================
# Property 2: Novel Creation Returns ID
# ============================================================================

class TestNovelCreationReturnsID:
    """
    Property-based tests for Property 2: Novel Creation Returns ID.
    
    For any novel creation request with a valid title, the API should create
    a database entry with status "active" and return the novel_id in the response.
    
    Validates: Requirements 1.2, 1.3, 1.5
    """
    
    @given(
        title=novel_title_strategy(),
        author=author_name_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_novel_creation_returns_valid_id(self, title, author):
        """
        For any valid title and optional author, creating a novel should return
        a positive integer novel_id.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                novel_id = db.create_novel(title=title, author=author)
                
                # Property: novel_id should be a positive integer
                assert novel_id is not None
                assert isinstance(novel_id, int)
                assert novel_id > 0
            finally:
                db.close()
    
    @given(
        title=novel_title_strategy(),
        author=author_name_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_novel_has_active_status(self, title, author):
        """
        For any novel creation, the created novel should have status "active".
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                novel_id = db.create_novel(title=title, author=author)
                
                # Retrieve the novel and verify status
                novel = db.get_novel(novel_id)
                assert novel is not None
                assert novel["status"] == "active"
            finally:
                db.close()
    
    @given(
        title=novel_title_strategy(),
        author=author_name_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_novel_can_be_retrieved_by_id(self, title, author):
        """
        For any created novel, it should be retrievable by its novel_id.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                novel_id = db.create_novel(title=title, author=author)
                
                # Retrieve the novel
                novel = db.get_novel(novel_id)
                
                # Property: novel should exist and have correct title
                assert novel is not None
                assert novel["id"] == novel_id
                assert novel["title"] == title
                assert novel["author"] == author
            finally:
                db.close()
    
    @given(
        titles=st.lists(novel_title_strategy(), min_size=1, max_size=10, unique=True)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_multiple_novels_have_unique_ids(self, titles):
        """
        Creating multiple novels should return unique novel_ids.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                novel_ids = []
                for title in titles:
                    novel_id = db.create_novel(title=title)
                    novel_ids.append(novel_id)
                
                # Property: all novel_ids should be unique
                assert len(novel_ids) == len(set(novel_ids))
                
                # All novels should be retrievable
                for novel_id in novel_ids:
                    novel = db.get_novel(novel_id)
                    assert novel is not None
            finally:
                db.close()


# ============================================================================
# Property 4: Chapter Query Filtering
# ============================================================================

class TestChapterQueryFiltering:
    """
    Property-based tests for Property 4: Chapter Query Filtering.
    
    For any novel_id, querying chapters by that novel_id should return only
    chapters where the chapter's novel_id matches the query parameter, and
    no chapters from other novels.
    
    Validates: Requirements 2.3, 5.2, 9.1
    """
    
    @given(
        novels=st.lists(novel_with_chapters_strategy(), min_size=2, max_size=5)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_query_returns_only_matching_chapters(self, novels):
        """
        For any set of novels with chapters, querying by novel_id should return
        only chapters belonging to that novel.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                novel_ids = []
                for novel_data in novels:
                    novel_id = db.create_novel(
                        title=novel_data['title'],
                        author=novel_data['author']
                    )
                    novel_ids.append(novel_id)
                    
                    # Create chapters for this novel
                    for chapter in novel_data['chapters']:
                        db.create_chapter(
                            novel_id=novel_id,
                            chapter_index=chapter['index'],
                            filename=chapter['filename'],
                            title=chapter['title']
                        )
                
                # For each novel, verify query returns only its chapters
                for idx, novel_id in enumerate(novel_ids):
                    chapters = db.get_chapters_by_novel(novel_id)
                    
                    # Property: all returned chapters should have matching novel_id
                    for chapter in chapters:
                        assert chapter['novel_id'] == novel_id
                    
                    # Property: number of chapters should match
                    expected_count = len(novels[idx]['chapters'])
                    assert len(chapters) == expected_count
            finally:
                db.close()
    
    @given(
        novels=st.lists(novel_with_chapters_strategy(), min_size=2, max_size=5)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_chapters_are_not_mixed_between_novels(self, novels):
        """
        Chapters from different novels should not appear in each other's queries.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                novel_data_map = {}
                for novel_data in novels:
                    novel_id = db.create_novel(
                        title=novel_data['title'],
                        author=novel_data['author']
                    )
                    novel_data_map[novel_id] = novel_data
                    
                    # Create chapters for this novel
                    for chapter in novel_data['chapters']:
                        db.create_chapter(
                            novel_id=novel_id,
                            chapter_index=chapter['index'],
                            filename=chapter['filename'],
                            title=chapter['title']
                        )
                
                # For each novel, verify chapters don't include other novels' chapters
                for novel_id in novel_data_map:
                    chapters = db.get_chapters_by_novel(novel_id)
                    
                    # Property: all returned chapters should have matching novel_id
                    for chapter in chapters:
                        assert chapter['novel_id'] == novel_id, \
                            f"Chapter with filename {chapter['filename']} has novel_id {chapter['novel_id']}, expected {novel_id}"
            finally:
                db.close()
    
    @given(
        novels=st.lists(novel_with_chapters_strategy(), min_size=1, max_size=5)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_get_all_chapters_includes_all_novels(self, novels):
        """
        get_all_chapters should return chapters from all novels.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                total_chapters = 0
                for novel_data in novels:
                    novel_id = db.create_novel(
                        title=novel_data['title'],
                        author=novel_data['author']
                    )
                    
                    # Create chapters for this novel
                    for chapter in novel_data['chapters']:
                        db.create_chapter(
                            novel_id=novel_id,
                            chapter_index=chapter['index'],
                            filename=chapter['filename'],
                            title=chapter['title']
                        )
                        total_chapters += 1
                
                # get_all_chapters should return all chapters
                all_chapters = db.get_all_chapters()
                assert len(all_chapters) == total_chapters
            finally:
                db.close()
    
    @given(
        novels=st.lists(novel_with_chapters_strategy(), min_size=2, max_size=5)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_chapters_ordered_by_index(self, novels):
        """
        Chapters returned by get_chapters_by_novel should be ordered by chapter_index.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                for novel_data in novels:
                    novel_id = db.create_novel(
                        title=novel_data['title'],
                        author=novel_data['author']
                    )
                    
                    # Create chapters for this novel
                    for chapter in novel_data['chapters']:
                        db.create_chapter(
                            novel_id=novel_id,
                            chapter_index=chapter['index'],
                            filename=chapter['filename'],
                            title=chapter['title']
                        )
                    
                    # Verify chapters are ordered by index
                    chapters = db.get_chapters_by_novel(novel_id)
                    indices = [c['chapter_index'] for c in chapters]
                    assert indices == sorted(indices), \
                        f"Chapters should be ordered by chapter_index, got {indices}"
            finally:
                db.close()


# ============================================================================
# Property 5: Cascade Deletion Integrity
# ============================================================================

class TestCascadeDeletionIntegrity:
    """
    Property-based tests for Property 5: Cascade Deletion Integrity.
    
    For any novel with associated chapters and pipeline state records, deleting
    the novel should result in all associated chapters and pipeline state records
    being deleted from the database.
    
    Validates: Requirements 2.4, 5.5
    """
    
    @given(
        novel_data=novel_with_chapters_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_delete_novel_removes_chapters(self, novel_data):
        """
        Deleting a novel should remove all its associated chapters.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                # Create novel with chapters
                novel_id = db.create_novel(
                    title=novel_data['title'],
                    author=novel_data['author']
                )
                
                # Create chapters
                chapter_ids = []
                for chapter in novel_data['chapters']:
                    chapter_id = db.create_chapter(
                        novel_id=novel_id,
                        chapter_index=chapter['index'],
                        filename=chapter['filename'],
                        title=chapter['title']
                    )
                    chapter_ids.append(chapter_id)
                
                # Verify chapters exist
                chapters_before = db.get_chapters_by_novel(novel_id)
                assert len(chapters_before) == len(novel_data['chapters'])
                
                # Delete novel
                result = db.delete_novel(novel_id)
                assert result is True
                
                # Verify novel is deleted
                novel = db.get_novel(novel_id)
                assert novel is None
                
                # Verify chapters are cascade deleted
                chapters_after = db.get_chapters_by_novel(novel_id)
                assert len(chapters_after) == 0
            finally:
                db.close()
    
    @given(
        novel_data=novel_with_chapters_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_delete_novel_removes_pipeline_state(self, novel_data):
        """
        Deleting a novel should remove all its associated pipeline state records.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                # Create novel with chapters
                novel_id = db.create_novel(
                    title=novel_data['title'],
                    author=novel_data['author']
                )
                
                # Create pipeline states for multiple phases
                phases = ['sanitize', 'transform', 'render']
                for phase in phases:
                    db.update_pipeline_state(
                        novel_id=novel_id,
                        phase=phase,
                        status='complete',
                        last_chapter=10,
                        total_chapters=10
                    )
                
                # Verify pipeline states exist
                states_before = db.get_all_pipeline_states(novel_id)
                assert len(states_before) == len(phases)
                
                # Delete novel
                result = db.delete_novel(novel_id)
                assert result is True
                
                # Verify pipeline states are cascade deleted
                states_after = db.get_all_pipeline_states(novel_id)
                assert len(states_after) == 0
            finally:
                db.close()
    
    @given(
        novels=st.lists(novel_with_chapters_strategy(), min_size=2, max_size=5)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_delete_one_novel_does_not_affect_others(self, novels):
        """
        Deleting one novel should not affect chapters or pipeline states of other novels.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                novel_ids = []
                all_chapters = {}
                all_states = {}
                
                # Create novels with chapters and pipeline states
                for novel_data in novels:
                    novel_id = db.create_novel(
                        title=novel_data['title'],
                        author=novel_data['author']
                    )
                    novel_ids.append(novel_id)
                    
                    # Create chapters
                    for chapter in novel_data['chapters']:
                        db.create_chapter(
                            novel_id=novel_id,
                            chapter_index=chapter['index'],
                            filename=chapter['filename'],
                            title=chapter['title']
                        )
                    
                    # Create pipeline states
                    for phase in ['sanitize', 'transform']:
                        db.update_pipeline_state(
                            novel_id=novel_id,
                            phase=phase,
                            status='running'
                        )
                    
                    # Store counts for verification
                    all_chapters[novel_id] = len(novel_data['chapters'])
                    all_states[novel_id] = 2  # 2 phases
                
                # Delete the first novel
                novel_to_delete = novel_ids[0]
                db.delete_novel(novel_to_delete)
                
                # Verify other novels are unaffected
                for idx, novel_id in enumerate(novel_ids):
                    if novel_id == novel_to_delete:
                        continue
                    
                    # Verify novel still exists
                    novel = db.get_novel(novel_id)
                    assert novel is not None
                    
                    # Verify chapters still exist
                    chapters = db.get_chapters_by_novel(novel_id)
                    assert len(chapters) == all_chapters[novel_id]
                    
                    # Verify pipeline states still exist
                    states = db.get_all_pipeline_states(novel_id)
                    assert len(states) == all_states[novel_id]
            finally:
                db.close()
    
    @given(
        novel_data=novel_with_chapters_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_cascade_delete_preserves_legacy_data(self, novel_data):
        """
        Deleting a novel should not affect legacy chapters with NULL novel_id.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                # Create legacy chapters (NULL novel_id)
                legacy_chapters = []
                for i in range(3):
                    chapter_id = db.create_chapter(
                        novel_id=None,
                        chapter_index=i,
                        filename=f"legacy_chapter_{i:04d}.txt",
                        title=f"Legacy Chapter {i + 1}"
                    )
                    legacy_chapters.append(chapter_id)
                
                # Create novel with chapters
                novel_id = db.create_novel(
                    title=novel_data['title'],
                    author=novel_data['author']
                )
                
                for chapter in novel_data['chapters']:
                    db.create_chapter(
                        novel_id=novel_id,
                        chapter_index=chapter['index'],
                        filename=chapter['filename'],
                        title=chapter['title']
                    )
                
                # Verify legacy chapters exist
                all_chapters = db.get_all_chapters()
                legacy_count_before = sum(1 for c in all_chapters if c['novel_id'] is None)
                assert legacy_count_before == 3
                
                # Delete novel
                db.delete_novel(novel_id)
                
                # Verify legacy chapters still exist
                all_chapters_after = db.get_all_chapters()
                legacy_count_after = sum(1 for c in all_chapters_after if c['novel_id'] is None)
                assert legacy_count_after == 3
                
                # Verify novel chapters are deleted
                novel_chapters = [c for c in all_chapters_after if c['novel_id'] is not None]
                assert len(novel_chapters) == 0
            finally:
                db.close()
    
    @given(
        novel_data=novel_with_chapters_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_delete_nonexistent_novel_returns_false(self, novel_data):
        """
        Deleting a non-existent novel should return False.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                # Try to delete a novel that doesn't exist
                result = db.delete_novel(99999)
                assert result is False
            finally:
                db.close()

# ============================================================================
# Property 10: Transaction Atomicity for Novel Creation
# ============================================================================

class TestTransactionAtomicity:
    """
    Property-based tests for Property 10: Transaction Atomicity for Novel Creation.
    
    For any novel creation operation, if directory creation fails after database
    insert, the database transaction should be rolled back and no partial state
    should remain. All database operations should be atomic.
    
    Validates: Requirements 2.5, 20.1, 20.2
    """
    
    @given(
        title=novel_title_strategy(),
        author=author_name_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_transaction_rollback_on_exception(self, title, author):
        """
        For any novel creation, if an exception occurs during the transaction,
        the database should be rolled back to its previous state.
        
        This tests that the transaction context manager properly rolls back
        changes when an exception is raised.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                # Get initial count
                initial_count = db.count_novels()
                
                # Simulate an operation that fails after database insert
                try:
                    with db.transaction() as conn:
                        cursor = conn.cursor()
                        # Insert a novel
                        now = "2024-01-01T00:00:00+00:00"
                        cursor.execute(
                            """
                            INSERT INTO novels (title, author, cover_url, status, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (title, author, None, "active", now, now)
                        )
                        novel_id = cursor.lastrowid
                        
                        # Simulate a failure (e.g., directory creation fails)
                        raise RuntimeError("Simulated directory creation failure")
                except RuntimeError:
                    pass  # Expected exception
                
                # Verify no novel was created (transaction was rolled back)
                final_count = db.count_novels()
                assert final_count == initial_count, \
                    f"Transaction was not rolled back: count changed from {initial_count} to {final_count}"
            finally:
                db.close()
    
    @given(
        title=novel_title_strategy(),
        author=author_name_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_successful_transaction_commits(self, title, author):
        """
        For any novel creation, if no exception occurs, the transaction should
        commit and the novel should be retrievable.
        
        This tests that the transaction context manager properly commits
        changes when no exception is raised.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                # Get initial count
                initial_count = db.count_novels()
                
                # Create a novel successfully
                novel_id = db.create_novel(title=title, author=author)
                
                # Verify novel was created
                final_count = db.count_novels()
                assert final_count == initial_count + 1, \
                    f"Transaction was not committed: count should be {initial_count + 1}, got {final_count}"
                
                # Verify novel is retrievable
                novel = db.get_novel(novel_id)
                assert novel is not None
                assert novel["title"] == title
                assert novel["author"] == author
            finally:
                db.close()
    
    @given(
        novels=st.lists(novel_with_chapters_strategy(), min_size=1, max_size=5)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_chapter_creation_rollback_on_failure(self, novels):
        """
        For any chapter creation, if an exception occurs during the transaction,
        the database should be rolled back to its previous state.
        
        This tests that chapter creation is atomic and failures don't leave
        partial state.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                # Create a novel first
                novel_data = novels[0]
                novel_id = db.create_novel(
                    title=novel_data['title'],
                    author=novel_data['author']
                )
                
                # Get initial chapter count
                initial_chapters = db.get_chapters_by_novel(novel_id)
                initial_count = len(initial_chapters)
                
                # Try to create chapters but fail partway through
                chapters_to_create = novel_data['chapters']
                fail_at_index = len(chapters_to_create) // 2  # Fail at middle point
                
                try:
                    with db.transaction() as conn:
                        cursor = conn.cursor()
                        for idx, chapter in enumerate(chapters_to_create):
                            # Insert chapter
                            now = "2024-01-01T00:00:00+00:00"
                            cursor.execute(
                                """
                                INSERT INTO chapters (novel_id, chapter_index, filename, title, created_at)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (novel_id, chapter['index'], chapter['filename'], chapter['title'], now)
                            )
                            
                            # Simulate failure at the middle chapter
                            if idx == fail_at_index:
                                raise RuntimeError("Simulated processing failure")
                except RuntimeError:
                    pass  # Expected exception
                
                # Verify no chapters were created (transaction was rolled back)
                final_chapters = db.get_chapters_by_novel(novel_id)
                assert len(final_chapters) == initial_count, \
                    f"Transaction was not rolled back: chapter count changed from {initial_count} to {len(final_chapters)}"
            finally:
                db.close()
    
    @given(
        novel_data=novel_with_chapters_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_nested_transaction_rollback(self, novel_data):
        """
        For any nested operations, if an inner transaction fails, all changes
        in that transaction should be rolled back.
        
        This tests that nested transactions are properly isolated and
        roll back independently.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                # Create a novel
                novel_id = db.create_novel(
                    title=novel_data['title'],
                    author=novel_data['author']
                )
                
                # Get initial count
                initial_chapters = db.get_chapters_by_novel(novel_id)
                initial_count = len(initial_chapters)
                
                # Try to create chapters in a nested operation that fails
                try:
                    with db.transaction() as conn:
                        cursor = conn.cursor()
                        # Create some chapters
                        for chapter in novel_data['chapters'][:2]:
                            now = "2024-01-01T00:00:00+00:00"
                            cursor.execute(
                                """
                                INSERT INTO chapters (novel_id, chapter_index, filename, title, created_at)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (novel_id, chapter['index'], chapter['filename'], chapter['title'], now)
                            )
                        
                        # Simulate failure
                        raise ValueError("Simulated nested operation failure")
                except ValueError:
                    pass  # Expected exception
                
                # Verify no chapters were created
                final_chapters = db.get_chapters_by_novel(novel_id)
                assert len(final_chapters) == initial_count, \
                    f"Nested transaction was not rolled back: chapter count changed from {initial_count} to {len(final_chapters)}"
            finally:
                db.close()
    
    @given(
        novels=st.lists(novel_with_chapters_strategy(), min_size=2, max_size=5)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_partial_batch_operation_rollback(self, novels):
        """
        For any batch operation that creates multiple novels, if the operation
        fails partway through, all changes should be rolled back.
        
        This tests that batch novel creation is atomic and failures don't
        leave partial state.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            db = DatabaseManager(db_path)
            
            try:
                # Get initial count
                initial_count = db.count_novels()
                
                # Try to create novels but fail partway through
                fail_at_index = len(novels) // 2
                
                try:
                    with db.transaction() as conn:
                        cursor = conn.cursor()
                        for idx, novel in enumerate(novels):
                            now = "2024-01-01T00:00:00+00:00"
                            cursor.execute(
                                """
                                INSERT INTO novels (title, author, cover_url, status, created_at, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?)
                                """,
                                (novel['title'], novel['author'], None, "active", now, now)
                            )
                            
                            # Simulate failure at the middle novel
                            if idx == fail_at_index:
                                raise RuntimeError("Simulated batch operation failure")
                except RuntimeError:
                    pass  # Expected exception
                
                # Verify no novels were created (transaction was rolled back)
                final_count = db.count_novels()
                assert final_count == initial_count, \
                    f"Batch operation was not rolled back: count changed from {initial_count} to {final_count}"
            finally:
                db.close()