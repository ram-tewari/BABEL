"""Unit tests for chapter management CLI commands."""
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


def test_chapters_list_empty(runner, test_db, monkeypatch):
    """Test listing chapters when database is empty."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    result = runner.invoke(app, ["chapters", "list"])
    assert result.exit_code == 0
    assert "No chapters found" in result.stdout


def test_chapters_list_with_novel_id(runner, test_db, monkeypatch):
    """Test listing chapters filtered by novel_id."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    # Create novel and chapters
    novel_id = db.create_novel(title="Test Novel", author="Author", status="active")
    db.create_chapter(
        novel_id=novel_id,
        chapter_index=1,
        filename="chapter_1.txt",
        title="Chapter 1"
    )
    db.create_chapter(
        novel_id=novel_id,
        chapter_index=2,
        filename="chapter_2.txt",
        title="Chapter 2"
    )
    
    result = runner.invoke(app, ["chapters", "list", "--novel-id", str(novel_id)])
    assert result.exit_code == 0
    assert "Chapter 1" in result.stdout
    assert "Chapter 2" in result.stdout


def test_chapters_list_without_novel_id(runner, test_db, monkeypatch):
    """Test listing all chapters including legacy."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    # Create novel chapter
    novel_id = db.create_novel(title="Test Novel", author="Author", status="active")
    db.create_chapter(
        novel_id=novel_id,
        chapter_index=1,
        filename="chapter_1.txt",
        title="Chapter 1"
    )
    
    # Create legacy chapter
    db.create_chapter(
        novel_id=None,
        chapter_index=1,
        filename="legacy.txt",
        title="Legacy Chapter"
    )
    
    result = runner.invoke(app, ["chapters", "list"])
    assert result.exit_code == 0
    assert "Chapter 1" in result.stdout
    assert "Legacy Chapter" in result.stdout
    assert "Legacy" in result.stdout  # Novel ID column should show "Legacy"


def test_chapters_list_empty_novel(runner, test_db, monkeypatch):
    """Test listing chapters for novel with no chapters."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    novel_id = db.create_novel(title="Empty Novel", author="Author", status="active")
    
    result = runner.invoke(app, ["chapters", "list", "--novel-id", str(novel_id)])
    assert result.exit_code == 0
    assert "has no chapters" in result.stdout


def test_chapters_list_nonexistent_novel(runner, test_db, monkeypatch):
    """Test listing chapters for non-existent novel returns error."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    result = runner.invoke(app, ["chapters", "list", "--novel-id", "999"])
    assert result.exit_code == 1
    assert "not found" in result.stdout
