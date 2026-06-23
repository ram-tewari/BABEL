"""Unit tests for utility CLI commands."""
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


def test_db_info_empty(runner, test_db, monkeypatch):
    """Test db-info command with empty database."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    result = runner.invoke(app, ["util", "db-info"])
    assert result.exit_code == 0
    assert "Database Information" in result.stdout
    assert "Total Novels" in result.stdout
    assert "Total Chapters" in result.stdout


def test_db_info_with_data(runner, test_db, monkeypatch):
    """Test db-info command with data."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    # Create test data
    novel_id = db.create_novel(title="Test Novel", author="Author", status="active")
    db.create_chapter(novel_id=novel_id, chapter_index=1, filename="ch1.txt", title="Chapter 1")
    db.create_chapter(novel_id=None, chapter_index=1, filename="legacy.txt", title="Legacy")
    
    result = runner.invoke(app, ["util", "db-info"])
    assert result.exit_code == 0
    assert "Total Novels" in result.stdout
    assert "1" in result.stdout  # 1 novel
    assert "2" in result.stdout  # 2 chapters
    assert "Legacy Chapters" in result.stdout


def test_db_check_clean(runner, test_db, monkeypatch):
    """Test db-check with clean database."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    result = runner.invoke(app, ["util", "db-check"])
    assert result.exit_code == 0
    assert "No integrity issues found" in result.stdout


def test_db_check_with_issues(runner, test_db, monkeypatch, tmp_path):
    """Test db-check detects missing files."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    # Create chapter with missing file
    novel_id = db.create_novel(title="Test Novel", author="Author", status="active")
    db.create_chapter(
        novel_id=novel_id,
        chapter_index=1,
        filename="missing.txt",
        title="Missing Chapter"
    )
    
    result = runner.invoke(app, ["util", "db-check"])
    assert result.exit_code == 1
    assert "Issues Found" in result.stdout
    assert "Missing Files" in result.stdout


def test_db_vacuum(runner, test_db, monkeypatch):
    """Test db-vacuum command."""
    db, db_path = test_db
    db.close()  # Close the database before vacuum
    
    result = runner.invoke(app, ["--db-path", str(db_path), "util", "db-vacuum"])
    if result.exit_code != 0:
        print(f"Error: {result.stdout}")
        if result.exception:
            print(f"Exception: {result.exception}")
    assert result.exit_code == 0
    assert "Database Optimization" in result.stdout
    assert "optimized successfully" in result.stdout
