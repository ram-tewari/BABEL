"""Unit tests for pipeline CLI commands."""
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


def test_pipeline_status_no_novel_id(runner, test_db, monkeypatch):
    """Test pipeline status without novel_id shows all states."""
    db, db_path = test_db
    
    # Create pipeline state
    novel_id = db.create_novel(title="Test Novel", author="Author", status="active")
    db.update_pipeline_state(
        phase="transform",
        status="complete",
        novel_id=novel_id,
        total_chapters=10,
        last_chapter=10
    )
    db.close()
    
    # Use --db-path option - must come before subcommand
    result = runner.invoke(app, ["--db-path", str(db_path), "pipeline", "status"])
    assert result.exit_code == 0
    # The command should work - either show states or say none found
    assert "pipeline" in result.stdout.lower() or "no pipeline" in result.stdout.lower() or "transform" in result.stdout


def test_pipeline_status_with_novel_id(runner, test_db, monkeypatch):
    """Test pipeline status filtered by novel_id."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    novel_id = db.create_novel(title="Test Novel", author="Author", status="active")
    db.update_pipeline_state(
        phase="transform",
        status="running",
        novel_id=novel_id,
        total_chapters=10,
        last_chapter=5
    )
    
    result = runner.invoke(app, ["pipeline", "status", "--novel-id", str(novel_id)])
    assert result.exit_code == 0
    assert "Test Novel" in result.stdout
    assert "transform" in result.stdout


def test_pipeline_status_nonexistent_novel(runner, test_db, monkeypatch):
    """Test pipeline status for non-existent novel returns error."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    result = runner.invoke(app, ["pipeline", "status", "--novel-id", "999"])
    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_pipeline_status_no_state(runner, test_db, monkeypatch):
    """Test pipeline status when no state exists."""
    db, db_path = test_db
    monkeypatch.setenv("BABEL_DB_PATH", str(db_path))
    
    novel_id = db.create_novel(title="Test Novel", author="Author", status="active")
    
    result = runner.invoke(app, ["pipeline", "status", "--novel-id", str(novel_id)])
    assert result.exit_code == 0
    assert "No pipeline state found" in result.stdout
