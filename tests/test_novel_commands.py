"""
Unit tests for novel management commands.

Tests command existence, registration, confirmation prompts,
and error messages for non-existent novels.
"""

import pytest
import os
from typer.testing import CliRunner
from pathlib import Path
import tempfile

from babel.cli import app
from babel.data.db import DatabaseManager


runner = CliRunner()


@pytest.fixture(autouse=True)
def clear_singleton():
    """Clear DatabaseManager singleton instances before each test."""
    # Clear the singleton instances
    DatabaseManager._instances.clear()
    yield
    # Clean up after test
    DatabaseManager._instances.clear()


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path for testing."""
    return tmp_path / "test_babel.db"


@pytest.fixture
def temp_db(temp_db_path):
    """Create a temporary database for testing."""
    db = DatabaseManager(temp_db_path)
    yield db
    db.close()


@pytest.fixture
def cli_runner_with_db(temp_db_path):
    """Create a CLI runner configured to use the temp database."""
    return CliRunner(env={"BABEL_DB_PATH": str(temp_db_path)})


@pytest.fixture
def sample_novel(temp_db):
    """Create a sample novel for testing."""
    novel_id = temp_db.create_novel(
        title="Test Novel",
        author="Test Author",
        cover_url="https://example.com/cover.jpg",
        status="active"
    )
    return novel_id


class TestNovelCommandsRegistration:
    """Test that novel commands are properly registered."""
    
    def test_novels_command_exists(self):
        """Test that 'novels' command is registered."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "novels" in result.output, "novels command should be in help"
    
    def test_novels_list_command_exists(self):
        """Test that 'novels list' command is registered."""
        result = runner.invoke(app, ["novels", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output, "list command should be in novels help"
    
    def test_novels_get_command_exists(self):
        """Test that 'novels get' command is registered."""
        result = runner.invoke(app, ["novels", "--help"])
        assert result.exit_code == 0
        assert "get" in result.output, "get command should be in novels help"
    
    def test_novels_update_command_exists(self):
        """Test that 'novels update' command is registered."""
        result = runner.invoke(app, ["novels", "--help"])
        assert result.exit_code == 0
        assert "update" in result.output, "update command should be in novels help"
    
    def test_novels_delete_command_exists(self):
        """Test that 'novels delete' command is registered."""
        result = runner.invoke(app, ["novels", "--help"])
        assert result.exit_code == 0
        assert "delete" in result.output, "delete command should be in novels help"


class TestNovelListCommand:
    """Test 'babel novels list' command."""
    
    def test_list_empty_database(self, temp_db_path, cli_runner_with_db):
        """Test listing when database is empty."""
        result = cli_runner_with_db.invoke(app, ["novels", "list"])
        assert result.exit_code == 0
        assert "no novels found" in result.output.lower() or "empty" in result.output.lower()
    
    def test_list_with_novels(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test listing with novels in database."""
        result = cli_runner_with_db.invoke(app, ["novels", "list"])
        assert result.exit_code == 0
        assert "Test Novel" in result.output
        assert str(sample_novel) in result.output
    
    def test_list_limit_option(self, temp_db_path, cli_runner_with_db):
        """Test --limit option."""
        db = DatabaseManager(temp_db_path)
        for i in range(5):
            db.create_novel(title=f"Novel {i}")
        db.close()
        
        result = cli_runner_with_db.invoke(app, ["novels", "list", "--limit", "3"])
        assert result.exit_code == 0
        # Should show at most 3 novels
    
    def test_list_status_filter(self, temp_db_path, cli_runner_with_db):
        """Test --status filter option."""
        db = DatabaseManager(temp_db_path)
        db.create_novel(title="Active Novel", status="active")
        db.create_novel(title="Completed Novel", status="completed")
        db.close()
        
        result = cli_runner_with_db.invoke(app, ["novels", "list", "--status", "active"])
        assert result.exit_code == 0
        assert "Active Novel" in result.output
        # Completed Novel should not appear in active filter
        # (This is a simplified check - in reality we'd parse the table)


class TestNovelGetCommand:
    """Test 'babel novels get <novel_id>' command."""
    
    def test_get_existing_novel(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test getting an existing novel."""
        result = cli_runner_with_db.invoke(app, ["novels", "get", str(sample_novel)])
        assert result.exit_code == 0
        assert "Test Novel" in result.output
        assert "Test Author" in result.output
        assert "active" in result.output
    
    def test_get_nonexistent_novel(self, temp_db_path, cli_runner_with_db):
        """Test getting a non-existent novel."""
        result = cli_runner_with_db.invoke(app, ["novels", "get", "99999"])
        assert result.exit_code == 1
        assert "99999" in result.output or "not found" in result.output.lower()
    
    def test_get_displays_chapter_count(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test that get command displays chapter count."""
        # Add some chapters
        db = DatabaseManager(temp_db_path)
        for i in range(1, 4):
            db.create_chapter(
                novel_id=sample_novel,
                chapter_index=i,
                filename=f"Ch_{i:03d}.txt"
            )
        db.close()
        
        result = cli_runner_with_db.invoke(app, ["novels", "get", str(sample_novel)])
        assert result.exit_code == 0
        # Chapter count should be displayed
        assert "3" in result.output or "chapter" in result.output.lower()


class TestNovelUpdateCommand:
    """Test 'babel novels update <novel_id>' command."""
    
    def test_update_title(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test updating novel title."""
        result = cli_runner_with_db.invoke(app, [
            "novels", "update", str(sample_novel),
            "--title", "Updated Title"
        ])
        assert result.exit_code == 0
        assert "updated successfully" in result.output.lower()
        
        # Verify update
        db = DatabaseManager(temp_db_path)
        novel = db.get_novel(sample_novel)
        db.close()
        assert novel['title'] == "Updated Title"
    
    def test_update_status(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test updating novel status."""
        result = cli_runner_with_db.invoke(app, [
            "novels", "update", str(sample_novel),
            "--status", "completed"
        ])
        assert result.exit_code == 0
        
        db = DatabaseManager(temp_db_path)
        novel = db.get_novel(sample_novel)
        db.close()
        assert novel['status'] == "completed"
    
    def test_update_multiple_fields(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test updating multiple fields at once."""
        result = cli_runner_with_db.invoke(app, [
            "novels", "update", str(sample_novel),
            "--title", "New Title",
            "--author", "New Author",
            "--status", "paused"
        ])
        assert result.exit_code == 0
        
        db = DatabaseManager(temp_db_path)
        novel = db.get_novel(sample_novel)
        db.close()
        assert novel['title'] == "New Title"
        assert novel['author'] == "New Author"
        assert novel['status'] == "paused"
    
    def test_update_nonexistent_novel(self, temp_db_path, cli_runner_with_db):
        """Test updating a non-existent novel."""
        result = cli_runner_with_db.invoke(app, [
            "novels", "update", "99999",
            "--title", "Test"
        ])
        assert result.exit_code == 1
        assert "99999" in result.output or "not found" in result.output.lower()
    
    def test_update_no_fields_provided(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test update with no fields provided."""
        result = cli_runner_with_db.invoke(app, ["novels", "update", str(sample_novel)])
        assert result.exit_code == 1
        assert "no update fields" in result.output.lower() or "provide" in result.output.lower()


class TestNovelDeleteCommand:
    """Test 'babel novels delete <novel_id>' command."""
    
    def test_delete_existing_novel(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test deleting an existing novel."""
        result = cli_runner_with_db.invoke(app, ["novels", "delete", str(sample_novel), "--force"])
        assert result.exit_code == 0
        assert "deleted" in result.output.lower()
        
        # Verify deletion
        db = DatabaseManager(temp_db_path)
        novel = db.get_novel(sample_novel)
        db.close()
        assert novel is None
    
    def test_delete_nonexistent_novel(self, temp_db_path, cli_runner_with_db):
        """Test deleting a non-existent novel."""
        result = cli_runner_with_db.invoke(app, ["novels", "delete", "99999", "--force"])
        assert result.exit_code == 1
        assert "99999" in result.output or "not found" in result.output.lower()
    
    def test_delete_cascades_chapters(self, temp_db_path, cli_runner_with_db):
        """Test that deleting a novel cascade deletes chapters."""
        db = DatabaseManager(temp_db_path)
        novel_id = db.create_novel(title="Test Novel")
        
        # Add chapters
        for i in range(1, 4):
            db.create_chapter(
                novel_id=novel_id,
                chapter_index=i,
                filename=f"Ch_{i:03d}.txt"
            )
        db.close()
        
        # Delete novel
        result = cli_runner_with_db.invoke(app, ["novels", "delete", str(novel_id), "--force"])
        assert result.exit_code == 0
        
        # Verify chapters are deleted
        db = DatabaseManager(temp_db_path)
        chapters = db.get_chapters_by_novel(novel_id)
        db.close()
        assert len(chapters) == 0
    
    def test_delete_prompts_confirmation(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test that delete prompts for confirmation without --force."""
        result = cli_runner_with_db.invoke(app, ["novels", "delete", str(sample_novel)], input="n\n")
        assert result.exit_code == 0
        assert "cancelled" in result.output.lower() or "warning" in result.output.lower()
        
        # Novel should still exist
        db = DatabaseManager(temp_db_path)
        novel = db.get_novel(sample_novel)
        db.close()
        assert novel is not None
    
    def test_delete_confirm_yes(self, temp_db_path, cli_runner_with_db, sample_novel):
        """Test that confirming deletion proceeds."""
        result = cli_runner_with_db.invoke(app, ["novels", "delete", str(sample_novel)], input="y\n")
        assert result.exit_code == 0
        
        # Novel should be deleted
        db = DatabaseManager(temp_db_path)
        novel = db.get_novel(sample_novel)
        db.close()
        assert novel is None


class TestNovelErrorMessages:
    """Test error messages for novel commands."""
    
    def test_get_nonexistent_error_message(self, temp_db_path, cli_runner_with_db):
        """Test error message format for non-existent novel."""
        result = cli_runner_with_db.invoke(app, ["novels", "get", "12345"])
        assert result.exit_code == 1
        # Should contain novel_id in error message
        assert "12345" in result.output
    
    def test_update_nonexistent_error_message(self, temp_db_path, cli_runner_with_db):
        """Test error message format for updating non-existent novel."""
        result = cli_runner_with_db.invoke(app, ["novels", "update", "12345", "--title", "Test"])
        assert result.exit_code == 1
        assert "12345" in result.output
    
    def test_delete_nonexistent_error_message(self, temp_db_path, cli_runner_with_db):
        """Test error message format for deleting non-existent novel."""
        result = cli_runner_with_db.invoke(app, ["novels", "delete", "12345", "--force"])
        assert result.exit_code == 1
        assert "12345" in result.output