"""Integration tests for CLI SQLite migration."""
import pytest
from pathlib import Path
from typer.testing import CliRunner
from babel.cli import app
from babel.data.db import DatabaseManager


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def test_env(tmp_path, monkeypatch):
    """Create test environment with database and directories."""
    db_path = tmp_path / "test.db"
    db = DatabaseManager(db_path)
    
    # Create directory structure
    (tmp_path / "data" / "clean").mkdir(parents=True)
    (tmp_path / "data" / "json").mkdir(parents=True)
    (tmp_path / "data" / "render").mkdir(parents=True)
    
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    monkeypatch.chdir(tmp_path)
    
    yield db, db_path, tmp_path
    db.close()


def test_end_to_end_novel_workflow(runner, test_env):
    """Test complete workflow: create novel, add chapters, process, delete."""
    db, db_path, tmp_path = test_env
    
    # Step 1: Create novel
    novel_id = db.create_novel(
        title="Integration Test Novel",
        author="Test Author",
        status="active"
    )
    
    # Step 2: Add chapters
    for i in range(1, 4):
        db.create_chapter(
            novel_id=novel_id,
            chapter_index=i,
            filename=f"chapter_{i}.txt",
            title=f"Chapter {i}"
        )
    
    # Step 3: List novels
    result = runner.invoke(app, ["novels", "list"])
    assert result.exit_code == 0
    assert "Integration Test" in result.stdout or "Test Author" in result.stdout
    
    # Step 4: List chapters
    result = runner.invoke(app, ["chapters", "list", "--novel-id", str(novel_id)])
    assert result.exit_code == 0
    assert "Chapter 1" in result.stdout
    assert "Chapter 2" in result.stdout
    assert "Chapter 3" in result.stdout
    
    # Step 5: Check pipeline status
    result = runner.invoke(app, ["pipeline", "status", "--novel-id", str(novel_id)])
    assert result.exit_code == 0
    
    # Step 6: Update novel
    result = runner.invoke(app, [
        "novels", "update", str(novel_id),
        "--status", "completed"
    ])
    assert result.exit_code == 0
    
    # Step 7: Delete novel
    result = runner.invoke(app, ["novels", "delete", str(novel_id), "--force"])
    assert result.exit_code == 0
    
    # Step 8: Verify deletion
    result = runner.invoke(app, ["novels", "get", str(novel_id)])
    assert result.exit_code == 1


def test_multi_novel_isolation(runner, test_env):
    """Test that processing one novel doesn't affect others."""
    db, db_path, tmp_path = test_env
    
    # Create two novels
    novel1_id = db.create_novel(title="Novel 1", author="Author 1", status="active")
    novel2_id = db.create_novel(title="Novel 2", author="Author 2", status="active")
    
    # Add chapters to both
    db.create_chapter(novel_id=novel1_id, chapter_index=1, filename="n1_ch1.txt", title="N1 Ch1")
    db.create_chapter(novel_id=novel2_id, chapter_index=1, filename="n2_ch1.txt", title="N2 Ch1")
    
    # Update pipeline state for novel 1
    db.update_pipeline_state(
        phase="transform",
        status="complete",
        novel_id=novel1_id,
        total_chapters=1,
        last_chapter=1
    )
    
    # Check novel 1 status
    result = runner.invoke(app, ["pipeline", "status", "--novel-id", str(novel1_id)])
    assert result.exit_code == 0
    assert "complete" in result.stdout
    
    # Check novel 2 status (should have no state)
    result = runner.invoke(app, ["pipeline", "status", "--novel-id", str(novel2_id)])
    assert result.exit_code == 0
    assert "No pipeline state" in result.stdout


def test_legacy_chapter_support(runner, test_env):
    """Test backward compatibility with legacy chapters."""
    db, db_path, tmp_path = test_env
    
    # Create legacy chapter (no novel_id)
    db.create_chapter(
        novel_id=None,
        chapter_index=1,
        filename="legacy.txt",
        title="Legacy Chapter"
    )
    
    # Create novel chapter
    novel_id = db.create_novel(title="New Novel", author="Author", status="active")
    db.create_chapter(
        novel_id=novel_id,
        chapter_index=1,
        filename="new.txt",
        title="New Chapter"
    )
    
    # List all chapters
    result = runner.invoke(app, ["chapters", "list"])
    assert result.exit_code == 0
    assert "Legacy Chapter" in result.stdout
    assert "New Chapter" in result.stdout
    assert "Legacy" in result.stdout  # Novel ID column


def test_database_path_configuration(runner, tmp_path, monkeypatch):
    """Test database path configuration via environment variable."""
    custom_db_path = tmp_path / "custom" / "babel.db"
    custom_db_path.parent.mkdir(parents=True)
    
    monkeypatch.setenv("BABEL_DB_PATH", str(custom_db_path))
    
    # Create novel (should create database at custom path)
    db = DatabaseManager(custom_db_path)
    novel_id = db.create_novel(title="Test", author="Author", status="active")
    db.close()
    
    # Verify database was created at custom path
    assert custom_db_path.exists()
    
    # Verify CLI can read from custom path
    result = runner.invoke(app, ["novels", "list"])
    assert result.exit_code == 0
    assert "Test" in result.stdout


def test_cascade_deletion(runner, test_env):
    """Test that deleting novel cascades to chapters and pipeline state."""
    db, db_path, tmp_path = test_env
    
    # Create novel with chapters and pipeline state
    novel_id = db.create_novel(title="Test Novel", author="Author", status="active")
    chapter_id = db.create_chapter(
        novel_id=novel_id,
        chapter_index=1,
        filename="ch1.txt",
        title="Chapter 1"
    )
    db.update_pipeline_state(
        phase="transform",
        status="complete",
        novel_id=novel_id,
        total_chapters=1,
        last_chapter=1
    )
    
    # Delete novel
    result = runner.invoke(app, ["novels", "delete", str(novel_id), "--force"])
    assert result.exit_code == 0
    
    # Verify cascade deletion
    assert db.get_novel(novel_id) is None
    assert db.get_chapter(chapter_id) is None
    assert len(db.get_pipeline_states_by_novel(novel_id)) == 0


def test_db_check_detects_orphaned_chapters(runner, test_env):
    """Test that db-check detects orphaned chapters."""
    db, db_path, tmp_path = test_env
    
    # Create chapter with invalid novel_id (disable FK temporarily)
    conn = db.connection
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        "INSERT INTO chapters (novel_id, chapter_index, filename, title) VALUES (?, ?, ?, ?)",
        (999, 1, "orphan.txt", "Orphaned Chapter")
    )
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")
    db.close()
    
    result = runner.invoke(app, ["--db-path", str(db_path), "util", "db-check"])
    assert result.exit_code == 1
    assert "Orphaned Chapters" in result.stdout


def test_novel_specific_directory_paths(runner, test_env):
    """Test that novel-specific directories are used correctly."""
    db, db_path, tmp_path = test_env
    
    novel_id = db.create_novel(title="Test Novel", author="Author", status="active")
    
    # Create novel-specific directories
    clean_dir = tmp_path / "data" / "clean" / f"novel_{novel_id}"
    json_dir = tmp_path / "data" / "json" / f"novel_{novel_id}"
    render_dir = tmp_path / "data" / "render" / f"novel_{novel_id}"
    
    clean_dir.mkdir(parents=True)
    json_dir.mkdir(parents=True)
    render_dir.mkdir(parents=True)
    
    # Verify directories exist
    assert clean_dir.exists()
    assert json_dir.exists()
    assert render_dir.exists()
