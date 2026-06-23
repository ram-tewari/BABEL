"""
Unit tests for the legacy chapters migration script.

These tests validate:
- Migration script creates legacy novel correctly
- Migration script associates chapters with legacy novel
- Migration script is idempotent
- Migration script preserves existing novels and chapters

Requirements: 8.2, 8.5
"""

import tempfile
from pathlib import Path

import pytest

from babel.data.db import DatabaseManager
from babel.data.migrations.migrations_004_legacy_chapters_migration import (
    run_migration,
    check_migration_status,
    get_legacy_novel_id,
    get_legacy_chapters,
    associate_chapters_with_legacy_novel,
    create_legacy_novel,
    LEGACY_NOVEL_TITLE
)


class TestLegacyMigration:
    """Unit tests for legacy chapters migration script."""
    
    def test_migration_creates_legacy_novel(self, tmp_path):
        """Test that migration creates the legacy novel if it doesn't exist."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        try:
            # Run migration
            result = run_migration(db_path)
            
            # Verify legacy novel was created
            assert result["legacy_novel_id"] is not None
            assert result["legacy_novel_id"] > 0
            assert result["legacy_novel_title"] == "Infinite Mage"
            assert result["is_new"] is True
            assert result["chapters_associated"] == 0
            
            # Verify novel exists in database
            novel = db.get_novel(result["legacy_novel_id"])
            assert novel is not None
            assert novel["title"] == "Infinite Mage"
            
        finally:
            db.close()
    
    def test_migration_associates_legacy_chapters(self, tmp_path):
        """Test that migration associates chapters with NULL novel_id to legacy novel."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        try:
            # Create chapters with NULL novel_id
            chapter_ids = []
            for i in range(5):
                chapter_id = db.create_chapter(
                    novel_id=None,
                    chapter_index=i + 1,
                    filename=f"chapter_{i + 1}.txt",
                    title=f"Chapter {i + 1}"
                )
                chapter_ids.append(chapter_id)
            
            # Verify chapters have NULL novel_id
            for chapter_id in chapter_ids:
                chapter = db.get_chapter(chapter_id)
                assert chapter["novel_id"] is None
            
            # Run migration
            result = run_migration(db_path)
            
            # Verify chapters are associated
            assert result["chapters_associated"] == 5
            assert result["is_new"] is True
            
            # Verify each chapter now has the legacy novel_id
            for chapter_id in chapter_ids:
                chapter = db.get_chapter(chapter_id)
                assert chapter["novel_id"] == result["legacy_novel_id"]
            
        finally:
            db.close()
    
    def test_migration_idempotent(self, tmp_path):
        """Test that running migration multiple times is idempotent."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        try:
            # Create some legacy chapters
            for i in range(3):
                db.create_chapter(
                    novel_id=None,
                    chapter_index=i + 1,
                    filename=f"chapter_{i + 1}.txt"
                )
            
            # Run migration first time
            result1 = run_migration(db_path)
            legacy_novel_id_1 = result1["legacy_novel_id"]
            
            # Run migration second time
            result2 = run_migration(db_path)
            legacy_novel_id_2 = result2["legacy_novel_id"]
            
            # Verify same novel ID
            assert legacy_novel_id_1 == legacy_novel_id_2
            assert result1["is_new"] is True
            assert result2["is_new"] is False  # Second run should not create new novel
            
            # Verify chapters are still correctly associated
            chapters = db.get_chapters_by_novel(legacy_novel_id_1)
            assert len(chapters) == 3
            
        finally:
            db.close()
    
    def test_migration_preserves_existing_novels(self, tmp_path):
        """Test that migration preserves existing novels and their chapters."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        try:
            # Create an existing novel
            existing_novel_id = db.create_novel(
                title="Existing Novel",
                author="Existing Author"
            )
            
            # Create chapters for existing novel
            existing_chapter_ids = []
            for i in range(3):
                chapter_id = db.create_chapter(
                    novel_id=existing_novel_id,
                    chapter_index=i + 1,
                    filename=f"existing_chapter_{i + 1}.txt"
                )
                existing_chapter_ids.append(chapter_id)
            
            # Create some legacy chapters
            legacy_chapter_ids = []
            for i in range(2):
                chapter_id = db.create_chapter(
                    novel_id=None,
                    chapter_index=i + 1,
                    filename=f"legacy_chapter_{i + 1}.txt"
                )
                legacy_chapter_ids.append(chapter_id)
            
            # Run migration
            result = run_migration(db_path)
            
            # Verify existing novel still exists
            existing_novel = db.get_novel(existing_novel_id)
            assert existing_novel is not None
            assert existing_novel["title"] == "Existing Novel"
            
            # Verify existing novel's chapters are unchanged
            existing_chapters = db.get_chapters_by_novel(existing_novel_id)
            assert len(existing_chapters) == 3
            for chapter in existing_chapters:
                assert chapter["novel_id"] == existing_novel_id
            
            # Verify legacy chapters are now associated with legacy novel
            legacy_chapters = db.get_chapters_by_novel(result["legacy_novel_id"])
            assert len(legacy_chapters) == 2
            
            # Verify legacy novel is different from existing novel
            assert result["legacy_novel_id"] != existing_novel_id
            
        finally:
            db.close()
    
    def test_migration_handles_empty_database(self, tmp_path):
        """Test that migration works correctly on empty database."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        try:
            # Run migration on empty database
            result = run_migration(db_path)
            
            # Verify legacy novel was created
            assert result["legacy_novel_id"] is not None
            assert result["chapters_associated"] == 0
            assert result["is_new"] is True
            
            # Verify no chapters exist
            all_chapters = db.get_all_chapters()
            assert len(all_chapters) == 0
            
        finally:
            db.close()
    
    def test_migration_with_mixed_chapters(self, tmp_path):
        """Test migration with mix of associated and unassociated chapters."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        try:
            # Create two novels
            novel1_id = db.create_novel(title="Novel 1", author="Author")
            novel2_id = db.create_novel(title="Novel 2", author="Author")
            
            # Create chapters for novel 1
            for i in range(2):
                db.create_chapter(
                    novel_id=novel1_id,
                    chapter_index=i + 1,
                    filename=f"novel1_chapter_{i + 1}.txt"
                )
            
            # Create chapters for novel 2
            for i in range(2):
                db.create_chapter(
                    novel_id=novel2_id,
                    chapter_index=i + 1,
                    filename=f"novel2_chapter_{i + 1}.txt"
                )
            
            # Create legacy chapters (NULL novel_id)
            for i in range(3):
                db.create_chapter(
                    novel_id=None,
                    chapter_index=i + 1,
                    filename=f"legacy_chapter_{i + 1}.txt"
                )
            
            # Run migration
            result = run_migration(db_path)
            
            # Verify only legacy chapters were associated
            assert result["chapters_associated"] == 3
            
            # Verify novel 1 chapters unchanged
            novel1_chapters = db.get_chapters_by_novel(novel1_id)
            assert len(novel1_chapters) == 2
            
            # Verify novel 2 chapters unchanged
            novel2_chapters = db.get_chapters_by_novel(novel2_id)
            assert len(novel2_chapters) == 2
            
            # Verify legacy novel has only the legacy chapters
            legacy_chapters = db.get_chapters_by_novel(result["legacy_novel_id"])
            assert len(legacy_chapters) == 3
            
        finally:
            db.close()
    
    def test_check_migration_status(self, tmp_path):
        """Test the migration status check function."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        try:
            # Initially, no legacy novel exists
            status = check_migration_status(db_path)
            assert status["legacy_novel_exists"] is False
            assert status["legacy_novel_id"] is None
            assert status["unassociated_chapters"] == 0
            assert status["migration_needed"] is True
            
            # Create some legacy chapters
            for i in range(3):
                db.create_chapter(
                    novel_id=None,
                    chapter_index=i + 1,
                    filename=f"chapter_{i + 1}.txt"
                )
            
            # Status should show unassociated chapters
            status = check_migration_status(db_path)
            assert status["unassociated_chapters"] == 3
            assert status["migration_needed"] is True
            
            # Run migration
            run_migration(db_path)
            
            # Status should show migration complete
            status = check_migration_status(db_path)
            assert status["legacy_novel_exists"] is True
            assert status["legacy_novel_id"] is not None
            assert status["unassociated_chapters"] == 0
            assert status["migration_needed"] is False
            
        finally:
            db.close()
    
    def test_get_legacy_novel_id(self, tmp_path):
        """Test the get_legacy_novel_id function."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        try:
            # Initially, no legacy novel
            novel_id = get_legacy_novel_id(db_path)
            assert novel_id is None
            
            # Create legacy novel
            legacy_id = create_legacy_novel(db_path)
            
            # Now should return the ID
            novel_id = get_legacy_novel_id(db_path)
            assert novel_id == legacy_id
            
        finally:
            db.close()
    
    def test_get_legacy_chapters(self, tmp_path):
        """Test the get_legacy_chapters function."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        try:
            # Initially, no chapters
            chapters = get_legacy_chapters(db_path)
            assert len(chapters) == 0
            
            # Create some legacy chapters
            for i in range(3):
                db.create_chapter(
                    novel_id=None,
                    chapter_index=i + 1,
                    filename=f"chapter_{i + 1}.txt",
                    title=f"Chapter {i + 1}"
                )
            
            # Create a chapter with a novel
            novel_id = db.create_novel(title="Novel", author="Author")
            db.create_chapter(
                novel_id=novel_id,
                chapter_index=1,
                filename="associated.txt"
            )
            
            # Should only return legacy chapters
            chapters = get_legacy_chapters(db_path)
            assert len(chapters) == 3
            
        finally:
            db.close()
    
    def test_associate_chapters_with_legacy_novel(self, tmp_path):
        """Test the associate_chapters_with_legacy_novel function."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        try:
            # Create legacy novel
            legacy_id = create_legacy_novel(db_path)
            
            # Create legacy chapters
            chapter_ids = []
            for i in range(3):
                chapter_id = db.create_chapter(
                    novel_id=None,
                    chapter_index=i + 1,
                    filename=f"chapter_{i + 1}.txt"
                )
                chapter_ids.append(chapter_id)
            
            # Associate chapters
            count = associate_chapters_with_legacy_novel(db_path, legacy_id)
            assert count == 3
            
            # Verify chapters are associated
            for chapter_id in chapter_ids:
                chapter = db.get_chapter(chapter_id)
                assert chapter["novel_id"] == legacy_id
            
        finally:
            db.close()


class TestLegacyChapterAPICompatibility:
    """Unit tests for legacy chapter API compatibility."""
    
    def test_legacy_chapter_accessible_via_api(self, tmp_path):
        """Test that legacy chapters are accessible via the API after migration."""
        from babel.data.migrations.migrations_004_legacy_chapters_migration import run_migration
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        try:
            # Create legacy chapters
            chapter_ids = []
            for i in range(3):
                chapter_id = db.create_chapter(
                    novel_id=None,
                    chapter_index=i + 1,
                    filename=f"chapter_{i + 1}.txt",
                    title=f"Chapter {i + 1}"
                )
                chapter_ids.append(chapter_id)
            
            # Run migration
            result = run_migration(db_path)
            legacy_novel_id = result["legacy_novel_id"]
            
            # Set up test client
            library_module._db_manager = db
            
            app = FastAPI()
            app.include_router(library_module.router)
            
            with TestClient(app) as client:
                # Test accessing chapter via new URL pattern
                for chapter_id in chapter_ids:
                    response = client.get(f"/api/library/{legacy_novel_id}/chapter/{chapter_id}")
                    assert response.status_code == 200
                    data = response.json()
                    assert data["id"] == chapter_id
                    assert data["novel_id"] == legacy_novel_id
                    assert data["chapter_index"] == chapter_id  # chapter_index matches order created
        
        finally:
            db.close()
    
    def test_chapter_from_wrong_novel_returns_404(self, tmp_path):
        """Test that accessing a chapter from the wrong novel returns 404."""
        from babel.data.migrations.migrations_004_legacy_chapters_migration import run_migration
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        try:
            # Create legacy chapters
            chapter_id = db.create_chapter(
                novel_id=None,
                chapter_index=1,
                filename="chapter_1.txt"
            )
            
            # Run migration
            result = run_migration(db_path)
            legacy_novel_id = result["legacy_novel_id"]
            
            # Create another novel
            other_novel_id = db.create_novel(title="Other Novel", author="Author")
            
            # Set up test client
            library_module._db_manager = db
            
            app = FastAPI()
            app.include_router(library_module.router)
            
            with TestClient(app) as client:
                # Accessing legacy chapter via wrong novel should return 404
                response = client.get(f"/api/library/{other_novel_id}/chapter/{chapter_id}")
                assert response.status_code == 404
        
        finally:
            db.close()
    
    def test_nonexistent_chapter_returns_404(self, tmp_path):
        """Test that accessing a non-existent chapter returns 404."""
        from babel.data.migrations.migrations_004_legacy_chapters_migration import run_migration
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        try:
            # Run migration
            result = run_migration(db_path)
            legacy_novel_id = result["legacy_novel_id"]
            
            # Set up test client
            library_module._db_manager = db
            
            app = FastAPI()
            app.include_router(library_module.router)
            
            with TestClient(app) as client:
                # Accessing non-existent chapter should return 404
                response = client.get(f"/api/library/{legacy_novel_id}/chapter/99999")
                assert response.status_code == 404
        
        finally:
            db.close()
    
    def test_nonexistent_novel_returns_404(self, tmp_path):
        """Test that accessing chapters from a non-existent novel returns 404."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        
        try:
            # Set up test client
            library_module._db_manager = db
            
            app = FastAPI()
            app.include_router(library_module.router)
            
            with TestClient(app) as client:
                # Accessing chapters from non-existent novel should return 404
                response = client.get("/api/library/99999/chapters")
                assert response.status_code == 404
                
                # Single chapter access should also return 404
                response = client.get("/api/library/99999/chapter/1")
                assert response.status_code == 404
        
        finally:
            db.close()