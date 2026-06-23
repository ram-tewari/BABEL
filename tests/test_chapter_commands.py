"""Tests for chapter management CLI commands."""
import pytest
from typer.testing import CliRunner
from pathlib import Path
import os


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test_babel.db"


@pytest.fixture
def temp_db(temp_db_path):
    """Create a temporary database with schema."""
    from babel.data.db import DatabaseManager
    DatabaseManager._instances = {}
    DatabaseManager._singletons = {}
    db = DatabaseManager(temp_db_path)
    db._create_tables()
    return db


@pytest.fixture
def cli_runner_with_db(temp_db_path):
    """Create a CLI runner with a temporary database."""
    from babel.data.db import DatabaseManager
    DatabaseManager._instances = {}
    DatabaseManager._singletons = {}
    os.environ["BABEL_DB_PATH"] = str(temp_db_path)
    from babel.cli import app
    runner = CliRunner()
    yield runner, app
    if "BABEL_DB_PATH" in os.environ:
        del os.environ["BABEL_DB_PATH"]
    DatabaseManager._instances = {}
    DatabaseManager._singletons = {}


@pytest.fixture
def sample_novel(temp_db):
    """Create a sample novel in the database."""
    novel_id = temp_db.create_novel(
        title="Test Novel",
        author="Test Author",
        status="active"
    )
    return novel_id


class TestChapterCommandsRegistration:
    """Test that chapter commands are properly registered."""

    def test_chapters_command_exists(self, cli_runner_with_db):
        """Test that the 'chapters' command is registered."""
        runner, app = cli_runner_with_db
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "chapters" in result.output.lower()

    def test_chapters_list_command_exists(self, cli_runner_with_db):
        """Test that the 'chapters list' command is registered."""
        runner, app = cli_runner_with_db
        result = runner.invoke(app, ["chapters", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output.lower()


class TestChapterListCommand:
    """Test the 'babel chapters list' command."""

    def test_list_empty_database(self, temp_db_path, cli_runner_with_db):
        """Test listing chapters when database is empty."""
        runner, app = cli_runner_with_db
        result = runner.invoke(app, ["chapters", "list"])
        assert result.exit_code == 0
        assert "No chapters found" in result.output

    def test_list_with_novel_id_filter(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test listing chapters with --novel-id filter."""
        runner, app = cli_runner_with_db
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db_path)
        novel_id = sample_novel
        for i in range(1, 4):
            db.create_chapter(
                novel_id=novel_id,
                chapter_index=i,
                filename=f"chapter_{i:03d}.txt",
                title=f"Chapter {i}"
            )
        
        result = runner.invoke(app, ["chapters", "list", "--novel-id", str(novel_id)])
        assert result.exit_code == 0
        assert "Test Novel" in result.output
        assert "chapter_001" in result.output
        assert "chapter_002" in result.output
        assert "chapter_003" in result.output

    def test_list_without_filter_shows_all(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test listing all chapters without --novel-id filter."""
        runner, app = cli_runner_with_db
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db_path)
        novel_id = sample_novel
        for i in range(1, 3):
            db.create_chapter(
                novel_id=novel_id,
                chapter_index=i,
                filename=f"chapter_{i:03d}.txt",
                title=f"Chapter {i}"
            )
        
        result = runner.invoke(app, ["chapters", "list"])
        assert result.exit_code == 0
        assert "All Chapters" in result.output
        assert "chapter_001" in result.output
        assert "chapter_002" in result.output

    def test_list_empty_novel(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test listing chapters for a novel with no chapters."""
        runner, app = cli_runner_with_db
        novel_id = sample_novel
        
        result = runner.invoke(app, ["chapters", "list", "--novel-id", str(novel_id)])
        assert result.exit_code == 0
        assert "no chapters" in result.output.lower()

    def test_list_nonexistent_novel(self, temp_db_path, cli_runner_with_db):
        """Test listing chapters for a non-existent novel_id."""
        runner, app = cli_runner_with_db
        result = runner.invoke(app, ["chapters", "list", "--novel-id", "999"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_list_legacy_chapters(self, temp_db_path, cli_runner_with_db):
        """Test listing legacy chapters (NULL novel_id)."""
        runner, app = cli_runner_with_db
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db_path)
        
        # Create a legacy chapter (no novel_id)
        db.create_chapter(
            novel_id=None,
            chapter_index=1,
            filename="legacy_chapter.txt",
            title="Legacy Chapter"
        )
        
        result = runner.invoke(app, ["chapters", "list"])
        assert result.exit_code == 0
        assert "Legacy" in result.output or "legacy_chapter" in result.output

    def test_list_chapter_ordering(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test that chapters are listed in ascending chapter_index order."""
        runner, app = cli_runner_with_db
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db_path)
        novel_id = sample_novel
        for i in range(1, 6):
            db.create_chapter(
                novel_id=novel_id,
                chapter_index=i,
                filename=f"chapter_{i:03d}.txt",
                title=f"Chapter {i}"
            )
        
        result = runner.invoke(app, ["chapters", "list", "--novel-id", str(novel_id)])
        assert result.exit_code == 0
        
        # Check that chapters appear in order
        output = result.output
        idx1 = output.find("chapter_001")
        idx2 = output.find("chapter_002")
        idx3 = output.find("chapter_003")
        assert idx1 < idx2 < idx3, "Chapters should appear in ascending order"


class TestChapterErrorMessages:
    """Test error messages for chapter commands."""

    def test_get_nonexistent_error_message(self, temp_db_path, cli_runner_with_db):
        """Test error message when novel_id doesn't exist."""
        runner, app = cli_runner_with_db
        result = runner.invoke(app, ["chapters", "list", "--novel-id", "999"])
        assert result.exit_code == 1
        assert "999" in result.output or "not found" in result.output.lower()


class TestChapterListPagination:
    """Test pagination for chapter list command."""

    def test_list_with_limit(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test listing chapters with --limit option."""
        runner, app = cli_runner_with_db
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db_path)
        novel_id = sample_novel
        for i in range(1, 6):
            db.create_chapter(
                novel_id=novel_id,
                chapter_index=i,
                filename=f"chapter_{i:03d}.txt",
                title=f"Chapter {i}"
            )
        
        result = runner.invoke(app, ["chapters", "list", "--novel-id", str(novel_id), "--limit", "3"])
        assert result.exit_code == 0
        # Should show only 3 chapters
        assert "chapter_001" in result.output
        assert "chapter_002" in result.output
        assert "chapter_003" in result.output
        # Should not show chapters beyond limit
        assert "chapter_004" not in result.output
        assert "chapter_005" not in result.output

    def test_list_with_offset(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test listing chapters with --offset option."""
        runner, app = cli_runner_with_db
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db_path)
        novel_id = sample_novel
        for i in range(1, 6):
            db.create_chapter(
                novel_id=novel_id,
                chapter_index=i,
                filename=f"chapter_{i:03d}.txt",
                title=f"Chapter {i}"
            )
        
        result = runner.invoke(app, ["chapters", "list", "--novel-id", str(novel_id), "--offset", "2"])
        assert result.exit_code == 0
        # Should skip first 2 chapters
        assert "chapter_001" not in result.output
        assert "chapter_002" not in result.output
        # Should show remaining chapters
        assert "chapter_003" in result.output
        assert "chapter_004" in result.output
        assert "chapter_005" in result.output

    def test_list_with_limit_and_offset(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test listing chapters with both --limit and --offset."""
        runner, app = cli_runner_with_db
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db_path)
        novel_id = sample_novel
        for i in range(1, 11):
            db.create_chapter(
                novel_id=novel_id,
                chapter_index=i,
                filename=f"chapter_{i:03d}.txt",
                title=f"Chapter {i}"
            )
        
        result = runner.invoke(app, ["chapters", "list", "--novel-id", str(novel_id), "--limit", "3", "--offset", "2"])
        assert result.exit_code == 0
        # Should show chapters 3, 4, 5
        assert "chapter_003" in result.output
        assert "chapter_004" in result.output
        assert "chapter_005" in result.output
        # Should not show chapters before or after the range
        assert "chapter_001" not in result.output
        assert "chapter_002" not in result.output
        assert "chapter_006" not in result.output


class TestChapterListTableFormatting:
    """Test table formatting for chapter list command."""

    def test_list_table_headers_with_novel_filter(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test that table has correct headers when filtering by novel."""
        runner, app = cli_runner_with_db
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db_path)
        novel_id = sample_novel
        db.create_chapter(
            novel_id=novel_id,
            chapter_index=1,
            filename="chapter_001.txt",
            title="Chapter 1"
        )
        
        result = runner.invoke(app, ["chapters", "list", "--novel-id", str(novel_id)])
        assert result.exit_code == 0
        # Should have title column
        assert "Title" in result.output
        # Should have filename column
        assert "Filename" in result.output
        # Should NOT have Novel ID column when filtering by specific novel
        assert "Novel ID" not in result.output

    def test_list_table_headers_all_chapters(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test that table has Novel ID column when listing all chapters."""
        runner, app = cli_runner_with_db
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db_path)
        novel_id = sample_novel
        db.create_chapter(
            novel_id=novel_id,
            chapter_index=1,
            filename="chapter_001.txt",
            title="Chapter 1"
        )
        
        result = runner.invoke(app, ["chapters", "list"])
        assert result.exit_code == 0
        # Should have Novel ID column when listing all chapters
        assert "Novel ID" in result.output

    def test_list_shows_chapter_count(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test that command shows chapter count in output."""
        runner, app = cli_runner_with_db
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db_path)
        novel_id = sample_novel
        for i in range(1, 4):
            db.create_chapter(
                novel_id=novel_id,
                chapter_index=i,
                filename=f"chapter_{i:03d}.txt",
                title=f"Chapter {i}"
            )
        
        result = runner.invoke(app, ["chapters", "list", "--novel-id", str(novel_id)])
        assert result.exit_code == 0
        # Should show count of chapters
        assert "3 chapters" in result.output

    def test_list_untitled_chapter_handling(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test that chapters without titles display as 'Untitled'."""
        runner, app = cli_runner_with_db
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db_path)
        novel_id = sample_novel
        db.create_chapter(
            novel_id=novel_id,
            chapter_index=1,
            filename="chapter_001.txt",
            title=None  # No title
        )
        
        result = runner.invoke(app, ["chapters", "list", "--novel-id", str(novel_id)])
        assert result.exit_code == 0
        # Should display "Untitled" for chapters without title
        assert "Untitled" in result.output


class TestChapterListMultipleNovels:
    """Test chapter list with multiple novels."""

    def test_list_multiple_novels_separate(self, temp_db_path, cli_runner_with_db):
        """Test that chapters from different novels are properly separated."""
        runner, app = cli_runner_with_db
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db_path)
        
        # Create two novels
        novel1_id = db.create_novel(title="Novel One", author="Author A", status="active")
        novel2_id = db.create_novel(title="Novel Two", author="Author B", status="active")
        
        # Add chapters to each
        for i in range(1, 4):
            db.create_chapter(
                novel_id=novel1_id,
                chapter_index=i,
                filename=f"novel1_chapter_{i}.txt",
                title=f"Novel 1 - Chapter {i}"
            )
            db.create_chapter(
                novel_id=novel2_id,
                chapter_index=i,
                filename=f"novel2_chapter_{i}.txt",
                title=f"Novel 2 - Chapter {i}"
            )
        
        # List all chapters - should show both novels
        result = runner.invoke(app, ["chapters", "list"])
        assert result.exit_code == 0
        assert "novel1_chapter_1" in result.output
        assert "novel2_chapter_1" in result.output
        
        # Filter by novel1
        result = runner.invoke(app, ["chapters", "list", "--novel-id", str(novel1_id)])
        assert result.exit_code == 0
        assert "Novel One" in result.output
        assert "novel1_chapter_1" in result.output
        # Should NOT show novel2 chapters
        assert "novel2_chapter_1" not in result.output

    def test_list_mixed_legacy_and_novel_chapters(self, temp_db_path, cli_runner_with_db):
        """Test listing both legacy chapters (NULL novel_id) and novel chapters."""
        runner, app = cli_runner_with_db
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db_path)
        
        # Create a novel with chapters
        novel_id = db.create_novel(title="Test Novel", author="Author", status="active")
        db.create_chapter(
            novel_id=novel_id,
            chapter_index=1,
            filename="novel_chapter.txt",
            title="Novel Chapter"
        )
        
        # Create a legacy chapter
        db.create_chapter(
            novel_id=None,
            chapter_index=1,
            filename="legacy_chapter.txt",
            title="Legacy Chapter"
        )
        
        # List all chapters - should show both
        result = runner.invoke(app, ["chapters", "list"])
        assert result.exit_code == 0
        assert "novel_chapter" in result.output
        assert "legacy_chapter" in result.output
        # Legacy should be marked as such
        assert "Legacy" in result.output
        
        # Filter by novel - should only show novel chapters
        result = runner.invoke(app, ["chapters", "list", "--novel-id", str(novel_id)])
        assert result.exit_code == 0
        assert "novel_chapter" in result.output
        # Should NOT show legacy chapter
        assert "legacy_chapter" not in result.output


# ============================================================================
# Property-based tests for chapter list ordering
# ============================================================================

"""Property-based tests for chapter list ordering.

Validates: Requirements 6.2
"""
import tempfile
from pathlib import Path

from hypothesis import given, settings, HealthCheck, strategies as st
from hypothesis.strategies import lists, integers
from typer.testing import CliRunner
import os
import random
import re

from babel.data.db import DatabaseManager


# ============================================================================
# Strategies for generating test data
# ============================================================================

@st.composite
def chapter_index_strategy(draw):
    """Generate a valid chapter index (non-negative integer)."""
    return draw(st.integers(min_value=0, max_value=1000))


@st.composite
def chapter_data_strategy(draw):
    """Generate valid chapter data with random index."""
    index = draw(st.integers(min_value=0, max_value=100))
    # Filter out control characters and special characters for title
    title = draw(st.text(
        min_size=1,
        max_size=100,
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
    """Generate a novel with associated chapters in random order."""
    num_chapters = draw(st.integers(min_value=1, max_value=20))
    title = draw(st.text(min_size=1, max_size=200))
    author = draw(st.text(min_size=1, max_size=100) | st.none())
    
    # Generate chapters with random indices (not necessarily sequential)
    chapters = []
    indices_used = set()
    for i in range(num_chapters):
        # Generate unique random index
        while True:
            index = draw(st.integers(min_value=0, max_value=1000))
            if index not in indices_used:
                indices_used.add(index)
                break
        
        chapters.append({
            'index': index,
            'filename': f"chapter_{index:04d}.txt",
            'title': f"Chapter {index + 1}"
        })
    
    return {
        'title': title,
        'author': author,
        'chapters': chapters
    }


# ============================================================================
# Property 3: Chapter List Ordering
# ============================================================================

class TestChapterListOrderingProperty:
    """
    Property-based tests for Property 3: Chapter List Ordering.
    
    For any set of chapters belonging to a novel, executing 
    `babel chapters list --novel-id <id>` should return chapters 
    ordered by chapter_index in ascending order.
    
    Validates: Requirements 6.2
    """
    
    @given(novels=st.lists(novel_with_chapters_strategy(), min_size=1, max_size=5))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_chapters_ordered_by_index_ascending(self, novels):
        """
        For any novel with chapters (in any order), the CLI should return
        chapters ordered by chapter_index in ascending order.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            
            # Reset DatabaseManager singletons
            DatabaseManager._instances = {}
            DatabaseManager._singletons = {}
            
            db = DatabaseManager(db_path)
            db._create_tables()
            
            try:
                # Set environment for CLI
                old_db_path = os.environ.get("BABEL_DB_PATH")
                os.environ["BABEL_DB_PATH"] = str(db_path)
                
                try:
                    from babel.cli import app
                    runner = CliRunner()
                    
                    for novel_data in novels:
                        # Create novel
                        novel_id = db.create_novel(
                            title=novel_data['title'],
                            author=novel_data['author']
                        )
                        
                        # Create chapters in random order (not sorted by index)
                        chapters = novel_data['chapters']
                        
                        # Shuffle to ensure we're not relying on insertion order
                        shuffled_chapters = chapters[:]
                        random.shuffle(shuffled_chapters)
                        
                        for chapter in shuffled_chapters:
                            db.create_chapter(
                                novel_id=novel_id,
                                chapter_index=chapter['index'],
                                filename=chapter['filename'],
                                title=chapter['title']
                            )
                        
                        # Execute CLI command
                        result = runner.invoke(app, ["chapters", "list", "--novel-id", str(novel_id)])
                        assert result.exit_code == 0, f"CLI command failed: {result.output}"
                        
                        # Extract chapter indices from output
                        output = result.output
                        
                        # Find all chapter indices in the output
                        found_indices = [int(m.group(1)) for m in re.finditer(r'chapter_(\d+)\.txt', output)]
                        
                        # Property: chapters should be in ascending order
                        assert found_indices == sorted(found_indices), \
                            f"Chapters should be ordered by chapter_index, got {found_indices}"
                        
                        # Property: all chapters should be present
                        expected_indices = sorted([c['index'] for c in chapters])
                        assert found_indices == expected_indices, \
                            f"All chapters should be present, expected {expected_indices}, got {found_indices}"
                
                finally:
                    if old_db_path is not None:
                        os.environ["BABEL_DB_PATH"] = old_db_path
                    elif "BABEL_DB_PATH" in os.environ:
                        del os.environ["BABEL_DB_PATH"]
            
            finally:
                db.close()
    
    @given(chapters=lists(
        st.integers(min_value=0, max_value=1000),
        min_size=1,
        max_size=30,
        unique=True
    ))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_ordering_consistent_across_queries(self, chapters):
        """
        For any novel with chapters, querying multiple times should always
        return chapters in the same ascending order.
        """
        if not chapters:
            return
            
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            
            # Reset DatabaseManager singletons
            DatabaseManager._instances = {}
            DatabaseManager._singletons = {}
            
            db = DatabaseManager(db_path)
            db._create_tables()
            
            try:
                # Set environment for CLI
                old_db_path = os.environ.get("BABEL_DB_PATH")
                os.environ["BABEL_DB_PATH"] = str(db_path)
                
                try:
                    from babel.cli import app
                    runner = CliRunner()
                    
                    # Create novel
                    novel_id = db.create_novel(
                        title="Test Novel for Ordering",
                        author="Test Author"
                    )
                    
                    # Create chapters with the given indices
                    for idx in chapters:
                        db.create_chapter(
                            novel_id=novel_id,
                            chapter_index=idx,
                            filename=f"chapter_{idx:04d}.txt",
                            title=f"Chapter {idx + 1}"
                        )
                    
                    # Query multiple times and verify consistent ordering
                    first_result = None
                    
                    for _ in range(3):  # Query 3 times
                        result = runner.invoke(app, ["chapters", "list", "--novel-id", str(novel_id)])
                        assert result.exit_code == 0, f"CLI command failed: {result.output}"
                        
                        # Extract chapter indices from output
                        found_indices = [int(m.group(1)) for m in re.finditer(r'chapter_(\d+)\.txt', result.output)]
                        
                        # Property: ordering should be consistent across queries
                        expected_order = sorted(chapters)
                        assert found_indices == expected_order, \
                            f"Ordering should be consistent, expected {expected_order}, got {found_indices}"
                        
                        if first_result is None:
                            first_result = found_indices
                        else:
                            assert found_indices == first_result, \
                                f"Results should be identical across queries"
                
                finally:
                    if old_db_path is not None:
                        os.environ["BABEL_DB_PATH"] = old_db_path
                    elif "BABEL_DB_PATH" in os.environ:
                        del os.environ["BABEL_DB_PATH"]
            
            finally:
                db.close()
    
    @given(
        num_chapters=st.integers(min_value=1, max_value=50),
        start_index=st.integers(min_value=-100, max_value=100),
        step=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_ordering_with_sequential_chapters(self, num_chapters, start_index, step):
        """
        For any sequential chapter indices (with various start points and steps),
        the CLI should return chapters in ascending order.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_babel.db"
            
            # Reset DatabaseManager singletons
            DatabaseManager._instances = {}
            DatabaseManager._singletons = {}
            
            db = DatabaseManager(db_path)
            db._create_tables()
            
            try:
                # Set environment for CLI
                old_db_path = os.environ.get("BABEL_DB_PATH")
                os.environ["BABEL_DB_PATH"] = str(db_path)
                
                try:
                    from babel.cli import app
                    runner = CliRunner()
                    
                    # Create novel
                    novel_id = db.create_novel(
                        title="Sequential Chapter Test",
                        author="Test Author"
                    )
                    
                    # Create chapters with sequential indices
                    chapter_indices = []
                    for i in range(num_chapters):
                        idx = start_index + (i * step)
                        chapter_indices.append(idx)
                        db.create_chapter(
                            novel_id=novel_id,
                            chapter_index=idx,
                            filename=f"chapter_{idx:04d}.txt",
                            title=f"Chapter {idx + 1}"
                        )
                    
                    # Execute CLI command
                    result = runner.invoke(app, ["chapters", "list", "--novel-id", str(novel_id)])
                    assert result.exit_code == 0, f"CLI command failed: {result.output}"
                    
                    # Extract chapter indices from output
                    found_indices = [int(m.group(1)) for m in re.finditer(r'chapter_(\d+)\.txt', result.output)]
                    
                    # Property: chapters should be in ascending order
                    expected_order = sorted(chapter_indices)
                    assert found_indices == expected_order, \
                        f"Chapters should be ordered by chapter_index, expected {expected_order}, got {found_indices}"
                    
                finally:
                    if old_db_path is not None:
                        os.environ["BABEL_DB_PATH"] = old_db_path
                    elif "BABEL_DB_PATH" in os.environ:
                        del os.environ["BABEL_DB_PATH"]
            
            finally:
                db.close()