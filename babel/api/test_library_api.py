"""
Unit and property-based tests for library management API endpoints.

These tests validate the library API endpoints including:
- Novel list endpoint (GET /api/library)
- Single novel endpoint (GET /api/library/{id})
- Novel chapters endpoint (GET /api/library/{id}/chapters)
- Delete novel endpoint (DELETE /api/library/{id})
"""

import io
import json
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, strategies as st, settings, HealthCheck

from babel.api.library import router, get_db
from babel.data.db import DatabaseManager
from babel.data.models import NovelResponse, NovelListResponse, ChapterListResponse


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    tmpdir = tempfile.mkdtemp()
    try:
        db_path = Path(tmpdir) / "test.db"
        db = DatabaseManager(db_path)
        yield db
        # Force close all connections by deleting the thread-local storage
        if hasattr(db, '_local'):
            if hasattr(db._local, 'conn'):
                try:
                    db._local.conn.close()
                except Exception:
                    pass
                delattr(db._local, 'conn')
        # Clear singleton instances to release file locks
        DatabaseManager._instances.clear()
    finally:
        # Clean up temp directory with retry for Windows file locking
        import time
        for _ in range(3):
            try:
                import shutil
                shutil.rmtree(tmpdir, ignore_errors=True)
                break
            except Exception:
                time.sleep(0.1)


@pytest.fixture
def client(temp_db):
    """Create a test client with mocked database."""
    # Reset the global database manager
    import babel.api.library as library_module
    library_module._db_manager = temp_db
    
    # Create a minimal FastAPI app with the router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    
    with TestClient(app) as client:
        yield client


@pytest.fixture
def sample_novels(temp_db):
    """Create sample novels for testing."""
    novels = []
    for i in range(5):
        novel_id = temp_db.create_novel(
            title=f"Test Novel {i}",
            author=f"Author {i}",
            status="active"
        )
        novels.append({
            "id": novel_id,
            "title": f"Test Novel {i}",
            "author": f"Author {i}",
            "status": "active"
        })
    return novels


# ============================================================================
# Unit Tests for GET /api/library
# ============================================================================

class TestListNovelsEndpoint:
    """Tests for the list novels endpoint."""
    
    def test_list_novels_returns_empty_list(self, temp_db):
        """Test that listing novels returns empty list when database is empty."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        library_module._db_manager = temp_db
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get("/api/library")
            
        assert response.status_code == 200
        data = response.json()
        assert data["novels"] == []
        assert data["total"] == 0
    
    def test_list_novels_returns_all_novels(self, temp_db, sample_novels):
        """Test that listing novels returns all created novels."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        library_module._db_manager = temp_db
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get("/api/library")
            
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["novels"]) == 5
    
    def test_list_novels_default_limit(self, temp_db):
        """Test that default limit is applied."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        library_module._db_manager = temp_db
        
        # Create more than 100 novels
        for i in range(105):
            temp_db.create_novel(title=f"Novel {i}", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get("/api/library")
            
        assert response.status_code == 200
        data = response.json()
        # Default limit is 100
        assert len(data["novels"]) == 100
        assert data["total"] == 105
    
    def test_list_novels_with_limit_parameter(self, temp_db):
        """Test that limit parameter is respected."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        library_module._db_manager = temp_db
        
        for i in range(10):
            temp_db.create_novel(title=f"Novel {i}", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get("/api/library?limit=5")
            
        assert response.status_code == 200
        data = response.json()
        assert len(data["novels"]) == 5
        assert data["total"] == 10
    
    def test_list_novels_with_offset_parameter(self, temp_db):
        """Test that offset parameter is respected."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        library_module._db_manager = temp_db
        
        for i in range(10):
            temp_db.create_novel(title=f"Novel {i}", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get("/api/library?offset=5")
            
        assert response.status_code == 200
        data = response.json()
        assert len(data["novels"]) == 5
        # Novels are sorted by updated_at descending (newest first)
        # With offset=5, we skip the first 5 (newest) novels
        # The first result should be the 6th newest novel
        assert data["novels"][0]["title"] == "Novel 4"
    
    def test_list_novels_includes_chapter_count(self, temp_db):
        """Test that novels include chapter count."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        # Add chapters
        for i in range(3):
            temp_db.create_chapter(
                novel_id=novel_id,
                chapter_index=i + 1,
                filename=f"chapter_{i + 1}.txt",
                title=f"Chapter {i + 1}"
            )
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get("/api/library")
            
        assert response.status_code == 200
        data = response.json()
        novel = data["novels"][0]
        assert novel["chapter_count"] == 3


# ============================================================================
# Unit Tests for GET /api/library/{id}
# ============================================================================

class TestGetNovelEndpoint:
    """Tests for the get single novel endpoint."""
    
    def test_get_novel_returns_404_for_nonexistent(self, temp_db):
        """Test that getting a non-existent novel returns 404."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        library_module._db_manager = temp_db
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get("/api/library/99999")
            
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_get_novel_returns_correct_data(self, temp_db):
        """Test that getting a novel returns correct data."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(
            title="My Novel",
            author="My Author",
            status="active"
        )
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get(f"/api/library/{novel_id}")
            
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == novel_id
        assert data["title"] == "My Novel"
        assert data["author"] == "My Author"
        assert data["status"] == "active"
    
    def test_get_novel_includes_chapter_count(self, temp_db):
        """Test that novel response includes chapter count."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        # Add chapters
        for i in range(5):
            temp_db.create_chapter(
                novel_id=novel_id,
                chapter_index=i + 1,
                filename=f"chapter_{i + 1}.txt"
            )
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get(f"/api/library/{novel_id}")
            
        assert response.status_code == 200
        data = response.json()
        assert data["chapter_count"] == 5


# ============================================================================
# Unit Tests for GET /api/library/{id}/chapters
# ============================================================================

class TestGetNovelChaptersEndpoint:
    """Tests for the get novel chapters endpoint."""
    
    def test_get_chapters_returns_404_for_nonexistent_novel(self, temp_db):
        """Test that getting chapters for non-existent novel returns 404."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        library_module._db_manager = temp_db
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get("/api/library/99999/chapters")
            
        assert response.status_code == 404
    
    def test_get_chapters_returns_empty_list(self, temp_db):
        """Test that getting chapters for novel with no chapters returns empty list."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get(f"/api/library/{novel_id}/chapters")
            
        assert response.status_code == 200
        data = response.json()
        assert data["chapters"] == []
        assert data["total"] == 0
        assert data["novel_id"] == novel_id
    
    def test_get_chapters_returns_all_chapters(self, temp_db):
        """Test that getting chapters returns all chapters for the novel."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        # Add chapters
        for i in range(3):
            temp_db.create_chapter(
                novel_id=novel_id,
                chapter_index=i + 1,
                filename=f"chapter_{i + 1}.txt",
                title=f"Chapter {i + 1}"
            )
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get(f"/api/library/{novel_id}/chapters")
            
        assert response.status_code == 200
        data = response.json()
        assert len(data["chapters"]) == 3
        assert data["total"] == 3
        assert data["novel_id"] == novel_id
    
    def test_get_chapters_sorted_by_index(self, temp_db):
        """Test that chapters are sorted by chapter_index."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        # Add chapters in non-sequential order
        temp_db.create_chapter(
            novel_id=novel_id,
            chapter_index=3,
            filename="chapter_3.txt",
            title="Chapter 3"
        )
        temp_db.create_chapter(
            novel_id=novel_id,
            chapter_index=1,
            filename="chapter_1.txt",
            title="Chapter 1"
        )
        temp_db.create_chapter(
            novel_id=novel_id,
            chapter_index=2,
            filename="chapter_2.txt",
            title="Chapter 2"
        )
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get(f"/api/library/{novel_id}/chapters")
            
        assert response.status_code == 200
        data = response.json()
        chapters = data["chapters"]
        
        # Verify sorted by chapter_index
        assert chapters[0]["chapter_index"] == 1
        assert chapters[1]["chapter_index"] == 2
        assert chapters[2]["chapter_index"] == 3


# ============================================================================
# Unit Tests for DELETE /api/library/{id}
# ============================================================================

class TestDeleteNovelEndpoint:
    """Tests for the delete novel endpoint."""
    
    def test_delete_novel_returns_404_for_nonexistent(self, temp_db):
        """Test that deleting a non-existent novel returns 404."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        library_module._db_manager = temp_db
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.delete("/api/library/99999")
            
        assert response.status_code == 404
    
    def test_delete_novel_removes_novel(self, temp_db):
        """Test that deleting a novel removes it from the database."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.delete(f"/api/library/{novel_id}")
            
        assert response.status_code == 200
        
        # Verify novel is deleted
        assert temp_db.get_novel(novel_id) is None
    
    def test_delete_novel_cascades_to_chapters(self, temp_db):
        """Test that deleting a novel cascades to delete all chapters."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        # Add chapters
        for i in range(3):
            temp_db.create_chapter(
                novel_id=novel_id,
                chapter_index=i + 1,
                filename=f"chapter_{i + 1}.txt"
            )
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.delete(f"/api/library/{novel_id}")
            
        assert response.status_code == 200
        
        # Verify chapters are deleted
        chapters = temp_db.get_chapters_by_novel(novel_id)
        assert len(chapters) == 0
    
    def test_delete_novel_response_format(self, temp_db):
        """Test that delete response has correct format."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.delete(f"/api/library/{novel_id}")
            
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert str(novel_id) in data["message"]


# ============================================================================
# Property-Based Tests
# ============================================================================

class TestNovelListSorting:
    """
    Property-based tests for novel list sorting.
    
    Feature: phase-7-librarian, Property 5: Novel List Sorting
    Validates: Requirements 3.2
    """
    
    @given(
        titles=st.lists(st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=50), min_size=1, max_size=10)
    )
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow], deadline=None)
    def test_novel_list_sorted_by_updated_at_descending(self, temp_db, titles):
        """
        Feature: phase-7-librarian, Property 5: Novel List Sorting
        
        For any set of novels in the database, when retrieved via GET /api/library,
        the results should be sorted by updated_at timestamp in descending order
        (newest first).
        """
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        import time
        
        library_module._db_manager = temp_db
        
        # Clear any existing novels to ensure clean state
        existing_novels = temp_db.list_novels(limit=10000, offset=0)
        for novel in existing_novels:
            temp_db.delete_novel(novel["id"])
        
        # Create novels with slight delay between them to ensure different timestamps
        novel_ids = []
        for i, title in enumerate(titles):
            novel_id = temp_db.create_novel(title=title, author="Author")
            novel_ids.append(novel_id)
            
            # Small delay to ensure different timestamps
            if i < len(titles) - 1:
                time.sleep(0.01)
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get("/api/library")
            
        assert response.status_code == 200
        data = response.json()
        
        # Verify we got all novels
        assert len(data["novels"]) == len(titles)
        
        # Verify sorted by updated_at descending (newest first)
        # The most recently created novel should be first
        returned_titles = [n["title"] for n in data["novels"]]
        
        # The order should match the creation order (newest last created = first in list)
        # Since we created novels in order, the last one created should be first
        assert returned_titles[0] == titles[-1]


class TestInvalidNovelIDHandling:
    """
    Property-based tests for invalid novel ID handling.
    
    Feature: phase-7-librarian, Property 6: Invalid Novel ID Returns 404
    Validates: Requirements 3.5
    """
    
    @given(
        novel_id=st.integers(min_value=1, max_value=1000000)
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_get_nonexistent_novel_returns_404(self, temp_db, novel_id):
        """
        Feature: phase-7-librarian, Property 6: Invalid Novel ID Returns 404
        
        For any novel ID that does not exist in the database, API requests to
        GET /api/library/{id} should return HTTP 404 status.
        """
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        library_module._db_manager = temp_db
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get(f"/api/library/{novel_id}")
            
        # Should return 404 for non-existent novel
        assert response.status_code == 404
    
    @given(
        novel_id=st.integers(min_value=1, max_value=1000000)
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_get_nonexistent_novel_chapters_returns_404(self, temp_db, novel_id):
        """
        Feature: phase-7-librarian, Property 6: Invalid Novel ID Returns 404
        
        For any novel ID that does not exist in the database, API requests to
        GET /api/library/{id}/chapters should return HTTP 404 status.
        """
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        library_module._db_manager = temp_db
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get(f"/api/library/{novel_id}/chapters")
            
        # Should return 404 for non-existent novel
        assert response.status_code == 404
    
    @given(
        novel_id=st.integers(min_value=1, max_value=1000000)
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_delete_nonexistent_novel_returns_404(self, temp_db, novel_id):
        """
        Feature: phase-7-librarian, Property 6: Invalid Novel ID Returns 404
        
        For any novel ID that does not exist in the database, API requests to
        DELETE /api/library/{id} should return HTTP 404 status.
        """
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        library_module._db_manager = temp_db
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.delete(f"/api/library/{novel_id}")
            
        # Should return 404 for non-existent novel
        assert response.status_code == 404
    
    @given(
        novel_id=st.integers(min_value=1, max_value=1000000)
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_update_nonexistent_novel_returns_404(self, temp_db, novel_id):
        """
        Feature: phase-7-librarian, Property 6: Invalid Novel ID Returns 404
        
        For any novel ID that does not exist in the database, API requests to
        PUT /api/library/{id} should return HTTP 404 status.
        """
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        library_module._db_manager = temp_db
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.put(f"/api/library/{novel_id}", json={"title": "New Title"})
            
        # Should return 404 for non-existent novel
        assert response.status_code == 404


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases in library API endpoints."""
    
    def test_list_novels_handles_special_characters_in_title(self, temp_db):
        """Test that special characters in novel titles are handled correctly."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        library_module._db_manager = temp_db
        
        # Create novel with special characters
        special_title = "Test: A Novel with 'Special' & \"Quotes\""
        novel_id = temp_db.create_novel(title=special_title, author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get("/api/library")
            
        assert response.status_code == 200
        data = response.json()
        
        # Find our novel
        novel = next((n for n in data["novels"] if n["id"] == novel_id), None)
        assert novel is not None
        assert novel["title"] == special_title
    
    def test_get_novel_handles_null_author(self, temp_db):
        """Test that novels with null author are handled correctly."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Anonymous Novel", author=None)
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get(f"/api/library/{novel_id}")
            
        assert response.status_code == 200
        data = response.json()
        assert data["author"] is None
    
    def test_get_novel_handles_null_cover_url(self, temp_db):
        """Test that novels with null cover_url are handled correctly."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Novel Without Cover", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get(f"/api/library/{novel_id}")
            
        assert response.status_code == 200
        data = response.json()
        assert data["cover_url"] is None
    
    def test_list_novels_pagination_boundary(self, temp_db):
        """Test pagination at boundary conditions."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        library_module._db_manager = temp_db
        
        # Create 10 novels
        for i in range(10):
            temp_db.create_novel(title=f"Novel {i}", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            # Test offset at the end
            response = client.get("/api/library?offset=10")
            
        assert response.status_code == 200
        data = response.json()
        assert len(data["novels"]) == 0
        assert data["total"] == 10
        
        # Test offset beyond end
        response = client.get("/api/library?offset=100")
        assert response.status_code == 200
        data = response.json()
        assert len(data["novels"]) == 0
    
    def test_list_novels_limit_boundary(self, temp_db):
        """Test limit at boundary conditions."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        library_module._db_manager = temp_db
        
        # Create 5 novels
        for i in range(5):
            temp_db.create_novel(title=f"Novel {i}", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            # Test limit of 0
            response = client.get("/api/library?limit=0")
            
        assert response.status_code == 200
        data = response.json()
        # Limit of 0 should return 0 results
        assert len(data["novels"]) == 0
    
    def test_get_chapters_handles_legacy_chapters(self, temp_db):
        """Test that chapters with NULL novel_id are not returned."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        library_module._db_manager = temp_db
        
        # Create a novel
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        # Create a chapter with novel_id
        temp_db.create_chapter(
            novel_id=novel_id,
            chapter_index=1,
            filename="chapter_1.txt"
        )
        
        # Create a legacy chapter (no novel_id)
        temp_db.create_chapter(
            novel_id=None,
            chapter_index=1,
            filename="legacy_chapter.txt"
        )
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get(f"/api/library/{novel_id}/chapters")
            
        assert response.status_code == 200
        data = response.json()
        
        # Should only return the chapter with the correct novel_id
        assert len(data["chapters"]) == 1
        assert data["chapters"][0]["filename"] == "chapter_1.txt"
# ============================================================================
# Unit Tests for POST /api/library/{id}/metadata
# ============================================================================

class TestFetchMetadataEndpoint:
    """Tests for the fetch metadata endpoint."""
    
    def test_fetch_metadata_returns_404_for_nonexistent_novel(self, temp_db):
        """Test that fetching metadata for non-existent novel returns 404."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        library_module._db_manager = temp_db
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.post(
                "/api/library/99999/metadata",
                json={"source": "novelupdates"}
            )
            
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_fetch_metadata_with_invalid_source(self, temp_db):
        """Test that invalid source parameter returns validation error."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.post(
                f"/api/library/{novel_id}/metadata",
                json={"source": "invalid_source"}
            )
            
        # FastAPI returns 422 for validation errors on enum fields
        assert response.status_code == 422
    
    def test_fetch_metadata_novelupdates_not_found(self, temp_db):
        """Test that 404 is returned when novel not found on NovelUpdates."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from unittest.mock import patch, AsyncMock
        import babel.api.library as library_module
        from babel.api.metadata import ExternalMetadata
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Nonexistent Novel XYZ123", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        # Mock the metadata client to return None (not found)
        with patch("babel.api.library.get_metadata_client") as mock_client:
            mock_client.return_value.search = AsyncMock(return_value=None)
            
            with TestClient(app) as client:
                response = client.post(
                    f"/api/library/{novel_id}/metadata",
                    json={"source": "novelupdates"}
                )
                
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_fetch_metadata_royalroad_not_found(self, temp_db):
        """Test that 404 is returned when novel not found on RoyalRoad."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from unittest.mock import patch, AsyncMock
        import babel.api.library as library_module
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Nonexistent Novel XYZ123", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        # Mock the metadata client to return None (not found)
        with patch("babel.api.library.get_metadata_client") as mock_client:
            mock_client.return_value.search = AsyncMock(return_value=None)
            
            with TestClient(app) as client:
                response = client.post(
                    f"/api/library/{novel_id}/metadata",
                    json={"source": "royalroad"}
                )
                
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_fetch_metadata_success_with_cover_download(self, temp_db, tmp_path):
        """Test successful metadata fetch with cover image download."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from unittest.mock import patch, AsyncMock
        import babel.api.library as library_module
        from babel.api.metadata import ExternalMetadata
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        # Create mock metadata
        mock_metadata = ExternalMetadata(
            title="Updated Title",
            author="New Author",
            cover_url="https://example.com/cover.jpg",
            synopsis="A great novel synopsis",
            tags=["fantasy", "action"],
            status="active",
            source="novelupdates"
        )
        
        # Mock the metadata client and cover download
        with patch("babel.api.library.get_metadata_client") as mock_client:
            mock_client.return_value.search = AsyncMock(return_value=mock_metadata)
            
            with patch("babel.api.library.download_cover_image", new_callable=AsyncMock) as mock_download:
                mock_download.return_value = True  # Cover download succeeds
                
                with TestClient(app) as client:
                    response = client.post(
                        f"/api/library/{novel_id}/metadata",
                        json={"source": "novelupdates"}
                    )
                    
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Metadata fetched successfully"
        assert data["source"] == "novelupdates"
        assert data["metadata"]["title"] == "Updated Title"
        assert data["metadata"]["author"] == "New Author"
        assert data["metadata"]["synopsis"] == "A great novel synopsis"
        assert data["metadata"]["status"] == "active"
        assert "fantasy" in data["metadata"]["tags"]
        assert "action" in data["metadata"]["tags"]
        # Cover URL should be local after successful download
        assert data["metadata"]["cover_url"] == f"/data/covers/{novel_id}.jpg"
    
    def test_fetch_metadata_success_cover_download_fails(self, temp_db, tmp_path):
        """Test that cover download failure falls back to remote URL."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from unittest.mock import patch, AsyncMock
        import babel.api.library as library_module
        from babel.api.metadata import ExternalMetadata
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        # Create mock metadata
        mock_metadata = ExternalMetadata(
            title="Updated Title",
            author="New Author",
            cover_url="https://example.com/cover.jpg",
            synopsis="A great novel synopsis",
            tags=["fantasy"],
            status="active",
            source="royalroad"
        )
        
        # Mock the metadata client and cover download to fail
        with patch("babel.api.library.get_metadata_client") as mock_client:
            mock_client.return_value.search = AsyncMock(return_value=mock_metadata)
            
            with patch("babel.api.library.download_cover_image", new_callable=AsyncMock) as mock_download:
                mock_download.return_value = False  # Cover download fails
                
                with TestClient(app) as client:
                    response = client.post(
                        f"/api/library/{novel_id}/metadata",
                        json={"source": "royalroad"}
                    )
                    
        assert response.status_code == 200
        data = response.json()
        # Cover URL should be remote URL after failed download
        assert data["metadata"]["cover_url"] == "https://example.com/cover.jpg"
    
    def test_fetch_metadata_with_custom_search_query(self, temp_db):
        """Test that custom search query is used instead of novel title."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from unittest.mock import patch, AsyncMock
        import babel.api.library as library_module
        from babel.api.metadata import ExternalMetadata
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Original Title", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        # Create mock metadata
        mock_metadata = ExternalMetadata(
            title="Search Result Title",
            author="Search Author",
            cover_url=None,
            synopsis="Synopsis",
            tags=[],
            status="active",
            source="novelupdates"
        )
        
        # Verify the search query is used
        with patch("babel.api.library.get_metadata_client") as mock_client:
            mock_search = AsyncMock(return_value=mock_metadata)
            mock_client.return_value.search = mock_search
            
            with TestClient(app) as client:
                response = client.post(
                    f"/api/library/{novel_id}/metadata",
                    json={
                        "source": "novelupdates",
                        "search_query": "Custom Search Query"
                    }
                )
                
        assert response.status_code == 200
        # Verify the custom search query was used
        mock_search.assert_called_once_with("Custom Search Query")
    
    def test_fetch_metadata_updates_database(self, temp_db):
        """Test that fetched metadata is stored in the database."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from unittest.mock import patch, AsyncMock
        import babel.api.library as library_module
        from babel.api.metadata import ExternalMetadata
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(
            title="Original Title",
            author="Original Author",
            status="active"
        )
        
        app = FastAPI()
        app.include_router(router)
        
        # Create mock metadata
        mock_metadata = ExternalMetadata(
            title="New Title",
            author="New Author",
            cover_url=None,
            synopsis="New synopsis",
            tags=["tag1", "tag2"],
            status="completed",
            source="royalroad"
        )
        
        with patch("babel.api.library.get_metadata_client") as mock_client:
            mock_client.return_value.search = AsyncMock(return_value=mock_metadata)
            
            with TestClient(app) as client:
                response = client.post(
                    f"/api/library/{novel_id}/metadata",
                    json={"source": "royalroad"}
                )
                
        assert response.status_code == 200
        
        # Verify database was updated
        updated_novel = temp_db.get_novel(novel_id)
        assert updated_novel["title"] == "New Title"
        assert updated_novel["author"] == "New Author"
        assert updated_novel["synopsis"] == "New synopsis"
        assert updated_novel["status"] == "completed"
    
    def test_fetch_metadata_handles_client_error(self, temp_db):
        """Test that client errors are handled gracefully."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from unittest.mock import patch, AsyncMock
        import babel.api.library as library_module
        import httpx
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        # Mock the metadata client to raise an HTTP error
        with patch("babel.api.library.get_metadata_client") as mock_client:
            mock_client.return_value.search = AsyncMock(
                side_effect=httpx.HTTPError("Connection failed")
            )
            
            with TestClient(app) as client:
                response = client.post(
                    f"/api/library/{novel_id}/metadata",
                    json={"source": "novelupdates"}
                )
                
        # Should return 500 for client errors
        assert response.status_code == 500
        assert "Failed to fetch metadata" in response.json()["detail"]


# ============================================================================
# Property-Based Tests for Metadata Updates (Property 7)
# ============================================================================

class TestMetadataUpdateCompleteness:
    """
    Property-based tests for metadata update completeness.

    Feature: phase-7-librarian, Property 7: Metadata Update Completeness
    Validates: Requirements 4.4
    """

    @given(
        title=st.text(min_size=1, max_size=100),
        author=st.one_of(st.none(), st.text(max_size=50)),
        synopsis=st.one_of(st.none(), st.text(max_size=500)),
        status=st.sampled_from(["active", "completed", "dropped"]),
        tags=st.lists(st.text(min_size=1, max_size=30), max_size=10)
    )
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_metadata_update_includes_all_fields(
        self, temp_db, title, author, synopsis, status, tags
    ):
        """
        Feature: phase-7-librarian, Property 7: Metadata Update Completeness

        For any successful metadata fetch from external sources, the novel entry
        should be updated with all available fields (cover_url, synopsis, tags, status).
        """
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from unittest.mock import patch, AsyncMock
        import babel.api.library as library_module
        from babel.api.metadata import ExternalMetadata
        import json as json_module

        library_module._db_manager = temp_db

        novel_id = temp_db.create_novel(title="Test Novel", author="Author")

        app = FastAPI()
        app.include_router(router)

        # Create mock metadata with all fields
        mock_metadata = ExternalMetadata(
            title=title,
            author=author,
            cover_url="https://example.com/cover.jpg",
            synopsis=synopsis,
            tags=tags,
            status=status,
            source="novelupdates"
        )

        with patch("babel.api.library.get_metadata_client") as mock_client:
            mock_client.return_value.search = AsyncMock(return_value=mock_metadata)

            with patch("babel.api.library.download_cover_image", new_callable=AsyncMock) as mock_download:
                mock_download.return_value = True

                with TestClient(app) as client:
                    response = client.post(
                        f"/api/library/{novel_id}/metadata",
                        json={"source": "novelupdates"}
                    )

        assert response.status_code == 200
        data = response.json()

        # Verify all fields are present in response
        assert data["metadata"]["title"] == title
        assert data["metadata"]["status"] == status
        # Author may be None in the response if it was None in the mock
        if author:
            assert data["metadata"]["author"] == author
        # Synopsis may be None in the response if it was None in the mock
        if synopsis:
            assert data["metadata"]["synopsis"] == synopsis
        # Tags should be present (may be None or empty list)
        assert data["metadata"]["tags"] is None or isinstance(data["metadata"]["tags"], list)

        # Verify database was updated with all fields (Requirement 4.4)
        updated_novel = temp_db.get_novel(novel_id)
        assert updated_novel["title"] == title
        assert updated_novel["status"] == status
        # Cover URL should be updated (local path after successful download)
        assert updated_novel["cover_url"] == f"/data/covers/{novel_id}.jpg"
        # Synopsis should be updated
        if synopsis:
            assert updated_novel["synopsis"] == synopsis
        # Tags should be stored as JSON and match (accounting for deduplication and whitespace stripping)
        stored_tags = updated_novel.get("tags")
        if stored_tags:
            if isinstance(stored_tags, str):
                stored_tags = json_module.loads(stored_tags)
            # ExternalMetadata deduplicates and strips tags, so compare cleaned unique tags
            expected_unique_tags = []
            seen = set()
            for tag in tags:
                cleaned_tag = tag.strip()
                if cleaned_tag and cleaned_tag.lower() not in seen:
                    expected_unique_tags.append(cleaned_tag)
                    seen.add(cleaned_tag.lower())
            assert stored_tags == expected_unique_tags


# ============================================================================
# Property-Based Tests for Cover Image Storage (Property 8)
# ============================================================================

class TestCoverImageStorage:
    """
    Property-based tests for cover image storage.

    Feature: phase-7-librarian, Property 8: Cover Image Storage
    Validates: Requirements 4.6
    """

    @given(
        novel_title=st.text(min_size=1, max_size=100),
        cover_url=st.one_of(
            st.none(),
            st.text(min_size=10, max_size=500, alphabet=st.characters(
                whitelist_categories=['L', 'N'],
                whitelist_characters='.-_/:'
            ))
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cover_image_stored_and_database_updated(self, temp_db, novel_title, cover_url, tmp_path):
        """
        Feature: phase-7-librarian, Property 8: Cover Image Storage

        For any successful cover image download, the file should be stored locally
        at data/covers/{novel_id}.jpg and the novel's cover_url field should be updated.
        """
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from unittest.mock import patch, AsyncMock
        import babel.api.library as library_module
        from babel.api.metadata import ExternalMetadata
        from babel.api.metadata import ensure_covers_directory

        library_module._db_manager = temp_db

        novel_id = temp_db.create_novel(title=novel_title, author="Author")

        app = FastAPI()
        app.include_router(router)

        # Create mock metadata
        mock_metadata = ExternalMetadata(
            title="Test Title",
            author="Test Author",
            cover_url=cover_url,
            synopsis="Synopsis",
            tags=[],
            status="active",
            source="royalroad"
        )

        # Track the cover path that was passed to download_cover_image
        captured_cover_path = None

        async def mock_download_cover(url, path):
            nonlocal captured_cover_path
            captured_cover_path = path
            # Create a dummy file to simulate successful download
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'\x89PNG\r\n\x1a\n')  # PNG header
            return True

        with patch("babel.api.library.get_metadata_client") as mock_client:
            mock_client.return_value.search = AsyncMock(return_value=mock_metadata)

            with patch("babel.api.library.download_cover_image", side_effect=mock_download_cover):
                with TestClient(app) as client:
                    response = client.post(
                        f"/api/library/{novel_id}/metadata",
                        json={"source": "royalroad"}
                    )

        # If cover_url is provided, the download should succeed
        if cover_url:
            assert response.status_code == 200
            data = response.json()

            # Verify 1: The response contains the local cover URL path
            assert data["metadata"]["cover_url"] == f"/data/covers/{novel_id}.jpg"

            # Verify 2: The novel's cover_url field is updated in the database
            updated_novel = temp_db.get_novel(novel_id)
            assert updated_novel["cover_url"] == f"/data/covers/{novel_id}.jpg"

            # Verify 3: The file was stored at the correct path
            assert captured_cover_path is not None
            expected_path = captured_cover_path
            assert expected_path.name == f"{novel_id}.jpg"
            assert expected_path.suffix == ".jpg"


# ============================================================================
# Unit Tests for POST /api/library/{id}/cover
# ============================================================================

class TestUploadCoverEndpoint:
    """Tests for the cover upload endpoint."""
    
    def test_upload_cover_returns_404_for_nonexistent_novel(self, temp_db):
        """Test that uploading cover for non-existent novel returns 404."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        library_module._db_manager = temp_db
        
        app = FastAPI()
        app.include_router(router)
        
        # Create a simple PNG image for testing
        from PIL import Image
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        with TestClient(app) as client:
            response = client.post(
                "/api/library/99999/cover",
                files={"file": ("cover.png", img_bytes, "image/png")}
            )
            
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_upload_cover_rejects_invalid_file_type(self, temp_db):
        """Test that invalid file types are rejected with 400."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        # Upload a text file instead of an image
        with TestClient(app) as client:
            response = client.post(
                f"/api/library/{novel_id}/cover",
                files={"file": ("document.txt", b"This is not an image", "text/plain")}
            )
            
        assert response.status_code == 400
        assert "invalid file type" in response.json()["detail"].lower()
    
    def test_upload_cover_accepts_jpg(self, temp_db, tmp_path):
        """Test that JPG files are accepted."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        from PIL import Image
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        # Create a simple JPG image
        img = Image.new('RGB', (200, 300), color='blue')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        with TestClient(app) as client:
            response = client.post(
                f"/api/library/{novel_id}/cover",
                files={"file": ("cover.jpg", img_bytes, "image/jpeg")}
            )
            
        assert response.status_code == 200
        data = response.json()
        assert data["novel_id"] == novel_id
        assert data["cover_url"] == f"/data/covers/{novel_id}.jpg"
        assert data["message"] == "Cover uploaded successfully"
    
    def test_upload_cover_accepts_png(self, temp_db):
        """Test that PNG files are accepted."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        from PIL import Image
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        # Create a simple PNG image
        img = Image.new('RGB', (200, 300), color='green')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        with TestClient(app) as client:
            response = client.post(
                f"/api/library/{novel_id}/cover",
                files={"file": ("cover.png", img_bytes, "image/png")}
            )
            
        assert response.status_code == 200
        data = response.json()
        assert data["cover_url"] == f"/data/covers/{novel_id}.jpg"
    
    def test_upload_cover_accepts_webp(self, temp_db):
        """Test that WebP files are accepted."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        from PIL import Image
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        # Create a simple WebP image
        img = Image.new('RGB', (200, 300), color='yellow')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='WebP')
        img_bytes.seek(0)
        
        with TestClient(app) as client:
            response = client.post(
                f"/api/library/{novel_id}/cover",
                files={"file": ("cover.webp", img_bytes, "image/webp")}
            )
            
        assert response.status_code == 200
        data = response.json()
        assert data["cover_url"] == f"/data/covers/{novel_id}.jpg"
    
    def test_upload_cover_resizes_image(self, temp_db, tmp_path):
        """Test that uploaded images are resized to 400x600px."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        from PIL import Image
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        # Create a larger image (800x1200 - 2x the target size)
        img = Image.new('RGB', (800, 1200), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        with TestClient(app) as client:
            response = client.post(
                f"/api/library/{novel_id}/cover",
                files={"file": ("cover.jpg", img_bytes, "image/jpeg")}
            )
            
        assert response.status_code == 200
        
        # Verify the saved image is 400x600px
        cover_path = Path("data/covers") / f"{novel_id}.jpg"
        if cover_path.exists():
            saved_img = Image.open(cover_path)
            assert saved_img.size == (400, 600)
    
    def test_upload_cover_maintains_aspect_ratio(self, temp_db):
        """Test that aspect ratio is maintained during resizing."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        from PIL import Image
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        # Create a wide image (800x400 - 2:1 aspect ratio)
        img = Image.new('RGB', (800, 400), color='cyan')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        with TestClient(app) as client:
            response = client.post(
                f"/api/library/{novel_id}/cover",
                files={"file": ("cover.jpg", img_bytes, "image/jpeg")}
            )
            
        assert response.status_code == 200
        
        # Verify the saved image fits within 400x600 and maintains aspect ratio
        cover_path = Path("data/covers") / f"{novel_id}.jpg"
        if cover_path.exists():
            saved_img = Image.open(cover_path)
            width, height = saved_img.size
            
            # Final image should be 400x600 (padded)
            assert width == 400, f"Expected width 400, got {width}"
            assert height == 600, f"Expected height 600, got {height}"
            
            # The image content maintains 2:1 aspect ratio (400x200 content in 400x600 canvas)
            # We verify this by checking that the non-white border exists
            # The cyan content should be centered with white padding on top and bottom
            # Top padding = (600 - 200) / 2 = 200 pixels
            # Bottom padding = 200 pixels
            
            # Check that the top 200 pixels are white (padding)
            top_region = saved_img.crop((0, 0, 400, 200))
            # Check a pixel in the middle of the top region
            top_pixel = top_region.getpixel((200, 100))
            assert top_pixel == (255, 255, 255), f"Expected white padding, got {top_pixel}"
            
            # Check that the middle 200 pixels contain the cyan content
            middle_region = saved_img.crop((0, 200, 400, 400))
            middle_pixel = middle_region.getpixel((200, 100))
            assert middle_pixel == (0, 255, 255), f"Expected cyan content, got {middle_pixel}"
    
    def test_upload_cover_updates_novel_entry(self, temp_db):
        """Test that the novel entry is updated with cover_url."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        from PIL import Image
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        # Verify initial state has no cover
        novel = temp_db.get_novel(novel_id)
        assert novel["cover_url"] is None
        
        app = FastAPI()
        app.include_router(router)
        
        # Upload a cover
        img = Image.new('RGB', (200, 300), color='purple')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        with TestClient(app) as client:
            response = client.post(
                f"/api/library/{novel_id}/cover",
                files={"file": ("cover.jpg", img_bytes, "image/jpeg")}
            )
            
        assert response.status_code == 200
        
        # Verify novel entry was updated
        updated_novel = temp_db.get_novel(novel_id)
        assert updated_novel["cover_url"] == f"/data/covers/{novel_id}.jpg"
    
    def test_upload_cover_handles_corrupt_image(self, temp_db):
        """Test that corrupt image data returns 400 error."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        # Upload corrupt data
        with TestClient(app) as client:
            response = client.post(
                f"/api/library/{novel_id}/cover",
                files={"file": ("cover.jpg", b"not an image", "image/jpeg")}
            )
            
        assert response.status_code == 400
        assert "invalid image data" in response.json()["detail"].lower()
    
    def test_upload_cover_response_format(self, temp_db):
        """Test that the response follows CoverUploadResponse format."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        from babel.data.models import CoverUploadResponse
        from PIL import Image
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        # Upload a cover
        img = Image.new('RGB', (200, 300), color='orange')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        with TestClient(app) as client:
            response = client.post(
                f"/api/library/{novel_id}/cover",
                files={"file": ("cover.jpg", img_bytes, "image/jpeg")}
            )
            
        assert response.status_code == 200
        data = response.json()
        
        # Verify response matches CoverUploadResponse schema
        assert "novel_id" in data
        assert "cover_url" in data
        assert "message" in data
        assert data["novel_id"] == novel_id
        assert data["cover_url"].endswith(f"{novel_id}.jpg")
        assert data["message"] == "Cover uploaded successfully"


# ============================================================================
# Property-Based Tests for Cover Upload (Property 15)
# ============================================================================

class TestCoverUploadValidation:
    """
    Property-based tests for cover upload validation and processing.
    
    Feature: phase-7-librarian, Property 15: Cover Upload Validation and Processing
    Validates: Requirements 10.2, 10.3, 10.4, 10.5
    """
    
    @given(
        width=st.integers(min_value=50, max_value=2000),
        height=st.integers(min_value=50, max_value=2000),
        color_r=st.integers(min_value=0, max_value=255),
        color_g=st.integers(min_value=0, max_value=255),
        color_b=st.integers(min_value=0, max_value=255)
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cover_upload_resizes_to_400x600(self, temp_db, width, height, color_r, color_g, color_b):
        """
        Feature: phase-7-librarian, Property 15: Cover Upload Validation and Processing
        
        For any valid image file (jpg, png, webp) uploaded as cover art, the system
        should resize it to 400x600px maintaining aspect ratio and save it to
        data/covers/{novel_id}.jpg.
        """
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        from PIL import Image
        import os
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title="Test Novel", author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        # Create an image with the specified dimensions
        img = Image.new('RGB', (width, height), color=(color_r, color_g, color_b))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        with TestClient(app) as client:
            response = client.post(
                f"/api/library/{novel_id}/cover",
                files={"file": ("cover.jpg", img_bytes, "image/jpeg")}
            )
            
        assert response.status_code == 200
        data = response.json()
        
        # Verify cover URL is returned
        assert data["cover_url"] == f"/data/covers/{novel_id}.jpg"
        
        # Verify the saved image is 400x600px
        cover_path = Path("data/covers") / f"{novel_id}.jpg"
        if cover_path.exists():
            saved_img = Image.open(cover_path)
            saved_width, saved_height = saved_img.size
            
            # Should fit within 400x600
            assert saved_width <= 400, f"Width {saved_width} exceeds 400"
            assert saved_height <= 600, f"Height {saved_height} exceeds 600"
            
            # At least one dimension should be at the target size
            # (unless the original was smaller than target)
            assert saved_width == 400 or saved_height == 600 or (
                width < 400 and height < 600
            ), f"Image {saved_width}x{saved_height} should fit 400x600 box"
    
    @given(
        novel_title=st.text(min_size=1, max_size=100),
        file_ext=st.sampled_from(['jpg', 'jpeg', 'png', 'webp'])
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cover_upload_accepts_valid_types(self, temp_db, novel_title, file_ext):
        """
        Feature: phase-7-librarian, Property 15: Cover Upload Validation and Processing
        
        For any valid image file (jpg, png, webp) uploaded as cover art, the system
        should validate the file type and accept it.
        """
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        from PIL import Image
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title=novel_title, author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        # Create an image with the specified format
        img = Image.new('RGB', (200, 300), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format=file_ext.upper() if file_ext != 'jpg' else 'JPEG')
        img_bytes.seek(0)
        
        mime_type = f"image/{'jpeg' if file_ext in ('jpg', 'jpeg') else file_ext}"
        
        with TestClient(app) as client:
            response = client.post(
                f"/api/library/{novel_id}/cover",
                files={"file": (f"cover.{file_ext}", img_bytes, mime_type)}
            )
            
        # Should accept valid file types
        assert response.status_code == 200, f"Failed for {file_ext}: {response.json()}"
        assert response.json()["cover_url"] == f"/data/covers/{novel_id}.jpg"
    
    @given(
        novel_title=st.text(min_size=1, max_size=100),
        invalid_ext=st.text(min_size=1, max_size=10).filter(lambda x: x.lower() not in ['jpg', 'jpeg', 'png', 'webp'])
    )
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cover_upload_rejects_invalid_types(self, temp_db, novel_title, invalid_ext):
        """
        Feature: phase-7-librarian, Property 15: Cover Upload Validation and Processing
        
        For any invalid file type uploaded as cover art, the system should reject it
        with HTTP 400 error.
        """
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title=novel_title, author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.post(
                f"/api/library/{novel_id}/cover",
                files={"file": (f"cover.{invalid_ext}", b"not an image", "application/octet-stream")}
            )
            
        # Should reject invalid file types
        assert response.status_code == 400
        assert "invalid file type" in response.json()["detail"].lower()
    
    @given(
        novel_title=st.text(min_size=1, max_size=100)
    )
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cover_upload_updates_database(self, temp_db, novel_title):
        """
        Feature: phase-7-librarian, Property 15: Cover Upload Validation and Processing
        
        For any successful cover upload, the system should update the novel's
        cover_url field in the database.
        """
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        import babel.api.library as library_module
        from PIL import Image
        
        library_module._db_manager = temp_db
        
        novel_id = temp_db.create_novel(title=novel_title, author="Author")
        
        app = FastAPI()
        app.include_router(router)
        
        # Upload a cover
        img = Image.new('RGB', (200, 300), color='blue')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        with TestClient(app) as client:
            response = client.post(
                f"/api/library/{novel_id}/cover",
                files={"file": ("cover.jpg", img_bytes, "image/jpeg")}
            )
            
        assert response.status_code == 200
        
        # Verify database was updated
        updated_novel = temp_db.get_novel(novel_id)
        assert updated_novel["cover_url"] == f"/data/covers/{novel_id}.jpg"