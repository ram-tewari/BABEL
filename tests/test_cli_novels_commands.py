"""Unit tests for novel management CLI commands."""
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
def test_db(tmp_path):
    """Create a temporary test database."""
    db_path = tmp_path / "test.db"
    db = DatabaseManager(db_path)
    yield db, db_path
    db.close()


def test_novels_list_empty(runner, test_db, monkeypatch):
    """Test listing novels when database is empty."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    result = runner.invoke(app, ["novels", "list"])
    assert result.exit_code == 0
    assert "No novels found" in result.stdout


def test_novels_list_with_data(runner, test_db, monkeypatch):
    """Test listing novels with data."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    # Create test novel
    novel_id = db.create_novel(
        title="Test Novel",
        author="Test Author",
        status="active"
    )
    
    result = runner.invoke(app, ["novels", "list"])
    assert result.exit_code == 0
    assert "Test Novel" in result.stdout
    assert "Test Author" in result.stdout


def test_novels_get_existing(runner, test_db, monkeypatch):
    """Test getting an existing novel."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    novel_id = db.create_novel(
        title="Test Novel",
        author="Test Author",
        status="active"
    )
    
    result = runner.invoke(app, ["novels", "get", str(novel_id)])
    assert result.exit_code == 0
    assert "Test Novel" in result.stdout
    assert "Test Author" in result.stdout


def test_novels_get_nonexistent(runner, test_db, monkeypatch):
    """Test getting a non-existent novel returns error."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    result = runner.invoke(app, ["novels", "get", "999"])
    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_novels_update(runner, test_db, monkeypatch):
    """Test updating novel metadata."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    novel_id = db.create_novel(
        title="Original Title",
        author="Original Author",
        status="active"
    )
    
    result = runner.invoke(app, [
        "novels", "update", str(novel_id),
        "--title", "Updated Title",
        "--status", "completed"
    ])
    assert result.exit_code == 0
    assert "updated successfully" in result.stdout
    
    # Verify update
    novel = db.get_novel(novel_id)
    assert novel['title'] == "Updated Title"
    assert novel['status'] == "completed"


def test_novels_update_no_fields(runner, test_db, monkeypatch):
    """Test updating novel without fields returns error."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    novel_id = db.create_novel(
        title="Test Novel",
        author="Test Author",
        status="active"
    )
    
    result = runner.invoke(app, ["novels", "update", str(novel_id)])
    assert result.exit_code == 1
    assert "No update fields provided" in result.stdout


def test_novels_delete_with_confirmation(runner, test_db, monkeypatch):
    """Test deleting novel with force flag."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    novel_id = db.create_novel(
        title="Test Novel",
        author="Test Author",
        status="active"
    )
    
    result = runner.invoke(app, ["novels", "delete", str(novel_id), "--force"])
    assert result.exit_code == 0
    assert "deleted successfully" in result.stdout
    
    # Verify deletion
    novel = db.get_novel(novel_id)
    assert novel is None


def test_novels_delete_nonexistent(runner, test_db, monkeypatch):
    """Test deleting non-existent novel returns error."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    result = runner.invoke(app, ["novels", "delete", "999", "--force"])
    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_novels_list_with_status_filter(runner, test_db, monkeypatch):
    """Test filtering novels by status."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    # Create novels with different statuses
    db.create_novel(title="Active Novel", author="Author", status="active")
    db.create_novel(title="Completed Novel", author="Author", status="completed")
    
    result = runner.invoke(app, ["novels", "list", "--status", "active"])
    assert result.exit_code == 0
    assert "Active Novel" in result.stdout
    assert "Completed Novel" not in result.stdout
