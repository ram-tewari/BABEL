"""Tests for render CLI commands with novel support."""
import pytest
from typer.testing import CliRunner
from pathlib import Path
import os
import tempfile
import shutil
import json


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


@pytest.fixture
def temp_dirs(tmp_path):
    """Create temporary directories for testing."""
    json_dir = tmp_path / "json"
    json_dir.mkdir()
    render_dir = tmp_path / "render"
    render_dir.mkdir()
    return json_dir, render_dir


@pytest.fixture
def sample_chapter_data():
    """Create sample chapter data for testing."""
    return {
        "blocks": [
            {
                "type": "system_notification",
                "content": "[Chapter 1: Test Chapter]"
            },
            {
                "type": "dialogue",
                "speaker": "Alice",
                "content": "Hello, world!",
                "tone": "cheerful"
            }
        ],
        "source_hash": "a" * 64,
        "model_version": "gemini-2.5-flash",
        "processed_at": "2026-02-03T10:00:00+00:00"
    }


class TestRenderCommandsRegistration:
    """Test that render commands are properly registered."""

    def test_render_command_exists(self, cli_runner_with_db):
        """Test that the 'render' command is registered."""
        runner, app = cli_runner_with_db
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "render" in result.output.lower()

    def test_render_batch_command_exists(self, cli_runner_with_db):
        """Test that the 'render batch' command is registered."""
        runner, app = cli_runner_with_db
        result = runner.invoke(app, ["render", "--help"])
        assert result.exit_code == 0
        assert "batch" in result.output.lower()

    def test_render_batch_has_novel_id_option(self, cli_runner_with_db):
        """Test that 'render batch' has --novel-id option."""
        runner, app = cli_runner_with_db
        result = runner.invoke(app, ["render", "batch", "--help"])
        assert result.exit_code == 0
        assert "--novel-id" in result.output


class TestRenderBatchWithNovelId:
    """Test the 'babel render batch' command with --novel-id option."""

    @pytest.mark.xfail(reason="Chapter class not implemented in babel.render.models")
    def test_render_batch_with_novel_id(self, cli_runner_with_db, temp_db, sample_novel, temp_dirs, sample_chapter_data):
        """Test rendering chapters for a specific novel using --novel-id."""
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db.db_path)
        novel_id = sample_novel

        json_dir, render_dir = temp_dirs

        # Create chapters in the database for the novel
        for i in range(1, 4):
            db.create_chapter(
                novel_id=novel_id,
                chapter_index=i,
                filename=f"chapter_{i:03d}.json",
                title=f"Chapter {i}"
            )
            # Create JSON files in the novel-specific directory
            novel_json_dir = json_dir / f"novel_{novel_id}"
            novel_json_dir.mkdir(exist_ok=True)
            json_path = novel_json_dir / f"chapter_{i:03d}.json"
            chapter_data = sample_chapter_data.copy()
            chapter_data["blocks"][0]["content"] = f"[Chapter {i}: Test Chapter]"
            json_path.write_text(json.dumps(chapter_data), encoding="utf-8")

        runner, app = cli_runner_with_db

        # Run render batch with --novel-id
        result = runner.invoke(app, [
            "render", "batch",
            str(json_dir / f"novel_{novel_id}"),
            "--output", str(render_dir / f"novel_{novel_id}"),
            "--novel-id", str(novel_id)
        ])

        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Check that HTML files were created in novel-specific directory
        for i in range(1, 4):
            output_path = render_dir / f"novel_{novel_id}" / f"chapter_{i:03d}.html"
            assert output_path.exists(), f"Expected {output_path} to exist"

    @pytest.mark.xfail(reason="Chapter class not implemented in babel.render.models")
    def test_render_batch_novel_specific_directory_paths(self, cli_runner_with_db, temp_db, sample_novel, temp_dirs, sample_chapter_data):
        """Test that render uses novel-specific directory paths."""
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db.db_path)
        novel_id = sample_novel

        json_dir, render_dir = temp_dirs

        # Create chapters in the database
        db.create_chapter(
            novel_id=novel_id,
            chapter_index=1,
            filename="chapter_001.json",
            title="Chapter 1"
        )

        # Create JSON file in novel-specific directory
        novel_json_dir = json_dir / f"novel_{novel_id}"
        novel_json_dir.mkdir(exist_ok=True)
        json_path = novel_json_dir / "chapter_001.json"
        json_path.write_text(json.dumps(sample_chapter_data), encoding="utf-8")

        runner, app = cli_runner_with_db

        # Run render batch with --novel-id
        result = runner.invoke(app, [
            "render", "batch",
            str(json_dir / f"novel_{novel_id}"),
            "--output", str(render_dir),
            "--novel-id", str(novel_id)
        ])

        assert result.exit_code == 0

        # Verify output is in novel-specific directory
        output_path = render_dir / f"novel_{novel_id}" / "chapter_001.html"
        assert output_path.exists()

    @pytest.mark.xfail(reason="Chapter class not implemented in babel.render.models")
    def test_render_batch_updates_pipeline_state(self, cli_runner_with_db, temp_db, sample_novel, temp_dirs, sample_chapter_data):
        """Test that render batch updates pipeline state with novel_id."""
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db.db_path)
        novel_id = sample_novel

        json_dir, render_dir = temp_dirs

        # Create a chapter in the database
        db.create_chapter(
            novel_id=novel_id,
            chapter_index=1,
            filename="chapter_001.json",
            title="Chapter 1"
        )

        # Create JSON file
        novel_json_dir = json_dir / f"novel_{novel_id}"
        novel_json_dir.mkdir(exist_ok=True)
        json_path = novel_json_dir / "chapter_001.json"
        json_path.write_text(json.dumps(sample_chapter_data), encoding="utf-8")

        runner, app = cli_runner_with_db

        # Run render batch with --novel-id
        result = runner.invoke(app, [
            "render", "batch",
            str(json_dir / f"novel_{novel_id}"),
            "--output", str(render_dir / f"novel_{novel_id}"),
            "--novel-id", str(novel_id)
        ])

        assert result.exit_code == 0

        # Verify pipeline state was updated
        states = db.get_pipeline_states_by_novel(novel_id)
        render_state = next((s for s in states if s["phase"] == "render"), None)
        assert render_state is not None, "Pipeline state for 'render' phase should exist"
        assert render_state["novel_id"] == novel_id

    @pytest.mark.xfail(reason="Chapter class not implemented in babel.render.models")
    def test_render_batch_generates_novel_specific_chapter_map(self, cli_runner_with_db, temp_db, sample_novel, temp_dirs, sample_chapter_data):
        """Test that render batch generates novel-specific chapter map."""
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db.db_path)
        novel_id = sample_novel

        json_dir, render_dir = temp_dirs

        # Create chapters in the database
        for i in range(1, 4):
            db.create_chapter(
                novel_id=novel_id,
                chapter_index=i,
                filename=f"chapter_{i:03d}.json",
                title=f"Chapter {i}"
            )

        # Create JSON files
        novel_json_dir = json_dir / f"novel_{novel_id}"
        novel_json_dir.mkdir(exist_ok=True)
        for i in range(1, 4):
            json_path = novel_json_dir / f"chapter_{i:03d}.json"
            chapter_data = sample_chapter_data.copy()
            chapter_data["blocks"][0]["content"] = f"[Chapter {i}: Test Chapter]"
            json_path.write_text(json.dumps(chapter_data), encoding="utf-8")

        runner, app = cli_runner_with_db

        # Run render batch with --novel-id
        result = runner.invoke(app, [
            "render", "batch",
            str(json_dir / f"novel_{novel_id}"),
            "--output", str(render_dir / f"novel_{novel_id}"),
            "--novel-id", str(novel_id)
        ])

        assert result.exit_code == 0

        # Verify novel-specific chapter map was created
        chapter_map_path = Path("config") / f"chapter_map_novel_{novel_id}.json"
        assert chapter_map_path.exists() or (render_dir / f"novel_{novel_id}" / "chapter_map.json").exists()


class TestRenderBatchLegacy:
    """Test backward compatibility for render batch without novel_id."""

    @pytest.mark.xfail(reason="Chapter class not implemented in babel.render.models")
    def test_render_batch_without_novel_id_uses_root_directory(self, cli_runner_with_db, temp_db, temp_dirs, sample_chapter_data):
        """Test that render batch without --novel-id uses root directories (backward compatibility)."""
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db.db_path)

        json_dir, render_dir = temp_dirs

        # Create legacy chapters (no novel_id)
        for i in range(1, 4):
            db.create_chapter(
                novel_id=None,
                chapter_index=i,
                filename=f"legacy_chapter_{i:03d}.json",
                title=f"Legacy Chapter {i}"
            )

        # Create JSON files in root directory
        for i in range(1, 4):
            json_path = json_dir / f"legacy_chapter_{i:03d}.json"
            chapter_data = sample_chapter_data.copy()
            chapter_data["blocks"][0]["content"] = f"[Legacy Chapter {i}]"
            json_path.write_text(json.dumps(chapter_data), encoding="utf-8")

        runner, app = cli_runner_with_db

        # Run render batch WITHOUT --novel-id
        result = runner.invoke(app, [
            "render", "batch",
            str(json_dir),
            "--output", str(render_dir)
        ])

        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Check that HTML files were created in root directory
        for i in range(1, 4):
            output_path = render_dir / f"legacy_chapter_{i:03d}.html"
            assert output_path.exists(), f"Expected {output_path} to exist"

    @pytest.mark.xfail(reason="Chapter class not implemented in babel.render.models")
    def test_render_batch_legacy_uses_chapter_map_json(self, cli_runner_with_db, temp_db, temp_dirs, sample_chapter_data):
        """Test that legacy render uses chapter_map.json (not novel-specific)."""
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db.db_path)

        json_dir, render_dir = temp_dirs

        # Create a legacy chapter
        db.create_chapter(
            novel_id=None,
            chapter_index=1,
            filename="legacy_chapter.json",
            title="Legacy Chapter"
        )

        # Create JSON file
        json_path = json_dir / "legacy_chapter.json"
        json_path.write_text(json.dumps(sample_chapter_data), encoding="utf-8")

        runner, app = cli_runner_with_db

        # Run render batch without --novel-id
        result = runner.invoke(app, [
            "render", "batch",
            str(json_dir),
            "--output", str(render_dir)
        ])

        assert result.exit_code == 0

        # Verify legacy chapter_map.json is used (not novel-specific)
        legacy_map_path = Path("config") / "chapter_map.json"
        assert legacy_map_path.exists() or (render_dir / "chapter_map.json").exists()

    @pytest.mark.xfail(reason="Chapter class not implemented in babel.render.models")
    def test_render_batch_legacy_updates_null_pipeline_state(self, cli_runner_with_db, temp_db, temp_dirs, sample_chapter_data):
        """Test that legacy render updates pipeline state with NULL novel_id."""
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db.db_path)

        json_dir, render_dir = temp_dirs

        # Create a legacy chapter
        db.create_chapter(
            novel_id=None,
            chapter_index=1,
            filename="legacy_chapter.json",
            title="Legacy Chapter"
        )

        # Create JSON file
        json_path = json_dir / "legacy_chapter.json"
        json_path.write_text(json.dumps(sample_chapter_data), encoding="utf-8")

        runner, app = cli_runner_with_db

        # Run render batch without --novel-id
        result = runner.invoke(app, [
            "render", "batch",
            str(json_dir),
            "--output", str(render_dir)
        ])

        assert result.exit_code == 0

        # Verify pipeline state was updated with NULL novel_id
        states = db.get_all_pipeline_states(novel_id=None)
        render_state = next((s for s in states if s["phase"] == "render"), None)
        assert render_state is not None
        assert render_state["novel_id"] is None


class TestRenderBatchErrorHandling:
    """Test error handling for render batch command."""

    @pytest.mark.xfail(reason="Chapter class not implemented in babel.render.models")
    def test_render_batch_nonexistent_novel_id(self, cli_runner_with_db, temp_db, temp_dirs):
        """Test that render batch handles non-existent novel_id gracefully."""
        runner, app = cli_runner_with_db
        json_dir, render_dir = temp_dirs

        # Run render batch with non-existent novel_id
        result = runner.invoke(app, [
            "render", "batch",
            str(json_dir),
            "--output", str(render_dir),
            "--novel-id", "99999"
        ])

        # Should fail with error about novel not found
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "99999" in result.output

    @pytest.mark.xfail(reason="Chapter class not implemented in babel.render.models")
    def test_render_batch_no_chapters_for_novel(self, cli_runner_with_db, temp_db, sample_novel, temp_dirs):
        """Test render batch when novel has no chapters."""
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db.db_path)
        novel_id = sample_novel

        json_dir, render_dir = temp_dirs

        # Create empty novel-specific directory
        novel_json_dir = json_dir / f"novel_{novel_id}"
        novel_json_dir.mkdir(exist_ok=True)

        runner, app = cli_runner_with_db

        # Run render batch with --novel-id but no chapters
        result = runner.invoke(app, [
            "render", "batch",
            str(novel_json_dir),
            "--output", str(render_dir / f"novel_{novel_id}"),
            "--novel-id", str(novel_id)
        ])

        # Should complete but report no chapters found
        assert result.exit_code == 0
        assert "no chapters" in result.output.lower() or "0" in result.output


class TestRenderBatchChapterFiltering:
    """Test chapter filtering by novel_id."""

    @pytest.mark.xfail(reason="Chapter class not implemented in babel.render.models")
    def test_render_batch_filters_by_novel_id(self, cli_runner_with_db, temp_db, temp_dirs, sample_chapter_data):
        """Test that render batch only renders chapters for the specified novel."""
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db.db_path)

        json_dir, render_dir = temp_dirs

        # Create two novels
        novel1_id = db.create_novel(title="Novel One", author="Author A", status="active")
        novel2_id = db.create_novel(title="Novel Two", author="Author B", status="active")

        # Create chapters for both novels
        for i in range(1, 4):
            # Novel 1 chapters
            db.create_chapter(
                novel_id=novel1_id,
                chapter_index=i,
                filename=f"novel1_chapter_{i:03d}.json",
                title=f"Novel 1 - Chapter {i}"
            )
            novel1_json_dir = json_dir / f"novel_{novel1_id}"
            novel1_json_dir.mkdir(exist_ok=True)
            json_path = novel1_json_dir / f"novel1_chapter_{i:03d}.json"
            chapter_data = sample_chapter_data.copy()
            chapter_data["blocks"][0]["content"] = f"[Novel 1 - Chapter {i}]"
            json_path.write_text(json.dumps(chapter_data), encoding="utf-8")

            # Novel 2 chapters
            db.create_chapter(
                novel_id=novel2_id,
                chapter_index=i,
                filename=f"novel2_chapter_{i:03d}.json",
                title=f"Novel 2 - Chapter {i}"
            )
            novel2_json_dir = json_dir / f"novel_{novel2_id}"
            novel2_json_dir.mkdir(exist_ok=True)
            json_path = novel2_json_dir / f"novel2_chapter_{i:03d}.json"
            chapter_data = sample_chapter_data.copy()
            chapter_data["blocks"][0]["content"] = f"[Novel 2 - Chapter {i}]"
            json_path.write_text(json.dumps(chapter_data), encoding="utf-8")

        runner, app = cli_runner_with_db

        # Run render batch for novel1 only
        result = runner.invoke(app, [
            "render", "batch",
            str(json_dir / f"novel_{novel1_id}"),
            "--output", str(render_dir / f"novel_{novel1_id}"),
            "--novel-id", str(novel1_id)
        ])

        assert result.exit_code == 0

        # Verify only novel1 chapters were rendered
        for i in range(1, 4):
            output_path = render_dir / f"novel_{novel1_id}" / f"novel1_chapter_{i:03d}.html"
            assert output_path.exists(), f"Expected {output_path} to exist"

            # Novel2 chapters should NOT exist in novel1's output
            novel2_in_novel1 = render_dir / f"novel_{novel1_id}" / f"novel2_chapter_{i:03d}.html"
            assert not novel2_in_novel1.exists(), f"Novel2 chapter should not be in novel1's output"


class TestRenderBatchOutput:
    """Test render batch output quality."""

    @pytest.mark.xfail(reason="Chapter class not implemented in babel.render.models")
    def test_render_batch_html_contains_chapter_content(self, cli_runner_with_db, temp_db, sample_novel, temp_dirs, sample_chapter_data):
        """Test that rendered HTML contains the chapter content."""
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db.db_path)
        novel_id = sample_novel

        json_dir, render_dir = temp_dirs

        # Create a chapter
        db.create_chapter(
            novel_id=novel_id,
            chapter_index=1,
            filename="chapter_001.json",
            title="Chapter 1"
        )

        # Create JSON file
        novel_json_dir = json_dir / f"novel_{novel_id}"
        novel_json_dir.mkdir(exist_ok=True)
        json_path = novel_json_dir / "chapter_001.json"
        chapter_data = sample_chapter_data.copy()
        chapter_data["blocks"][0]["content"] = "[Chapter 1: The Beginning]"
        chapter_data["blocks"][1]["content"] = "Hello, world!"
        json_path.write_text(json.dumps(chapter_data), encoding="utf-8")

        runner, app = cli_runner_with_db

        result = runner.invoke(app, [
            "render", "batch",
            str(novel_json_dir),
            "--output", str(render_dir / f"novel_{novel_id}"),
            "--novel-id", str(novel_id)
        ])

        assert result.exit_code == 0

        # Check HTML content
        output_path = render_dir / f"novel_{novel_id}" / "chapter_001.html"
        html_content = output_path.read_text(encoding="utf-8")

        assert "<!DOCTYPE html>" in html_content
        assert "Hello, world!" in html_content
        assert "Alice" in html_content

    @pytest.mark.xfail(reason="Chapter class not implemented in babel.render.models")
    def test_render_batch_creates_navigation_links(self, cli_runner_with_db, temp_db, sample_novel, temp_dirs, sample_chapter_data):
        """Test that rendered HTML has navigation links between chapters."""
        from babel.data.db import DatabaseManager
        DatabaseManager._instances = {}
        DatabaseManager._singletons = {}
        db = DatabaseManager(temp_db.db_path)
        novel_id = sample_novel

        json_dir, render_dir = temp_dirs

        # Create multiple chapters
        for i in range(1, 4):
            db.create_chapter(
                novel_id=novel_id,
                chapter_index=i,
                filename=f"chapter_{i:03d}.json",
                title=f"Chapter {i}"
            )

            novel_json_dir = json_dir / f"novel_{novel_id}"
            novel_json_dir.mkdir(exist_ok=True)
            json_path = novel_json_dir / f"chapter_{i:03d}.json"
            chapter_data = sample_chapter_data.copy()
            chapter_data["blocks"][0]["content"] = f"[Chapter {i}]"
            json_path.write_text(json.dumps(chapter_data), encoding="utf-8")

        runner, app = cli_runner_with_db

        result = runner.invoke(app, [
            "render", "batch",
            str(json_dir / f"novel_{novel_id}"),
            "--output", str(render_dir / f"novel_{novel_id}"),
            "--novel-id", str(novel_id)
        ])

        assert result.exit_code == 0

        # Check middle chapter has navigation links
        middle_html = (render_dir / f"novel_{novel_id}" / "chapter_002.html").read_text(encoding="utf-8")
        assert "chapter_001.html" in middle_html  # Previous link
        assert "chapter_003.html" in middle_html  # Next link