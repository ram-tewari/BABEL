"""
Unit tests for ManifestGenerator class

Tests cover manifest generation, token estimation, JSON writing,
validation, and error handling scenarios.
"""

import tempfile
import json
from pathlib import Path
from datetime import datetime
import pytest
from pydantic import ValidationError

from babel.sanitize import ManifestGenerator, CleanChapter, ChapterMap, ChapterEntry


# ============================================================================
# Token Estimation Tests
# ============================================================================

def test_estimate_tokens_basic():
    """Test basic token estimation with simple text."""
    text = "This is a test string with exactly 40 chars"
    # 40 chars / 4 = 10 tokens
    tokens = ManifestGenerator._estimate_tokens(text)
    assert tokens == 10


def test_estimate_tokens_empty_string():
    """Test token estimation with empty string."""
    tokens = ManifestGenerator._estimate_tokens("")
    assert tokens == 0


def test_estimate_tokens_large_text():
    """Test token estimation with large text."""
    # 10,000 characters should estimate to 2,500 tokens
    text = "A" * 10000
    tokens = ManifestGenerator._estimate_tokens(text)
    assert tokens == 2500


def test_estimate_tokens_with_unicode():
    """Test token estimation with unicode characters."""
    # Unicode characters still count as characters
    text = "日本語" * 100  # 300 characters
    tokens = ManifestGenerator._estimate_tokens(text)
    assert tokens == 75  # 300 / 4


def test_estimate_tokens_with_whitespace():
    """Test token estimation includes whitespace."""
    text = "word " * 100  # 500 characters (including spaces)
    tokens = ManifestGenerator._estimate_tokens(text)
    assert tokens == 125  # 500 / 4


def test_estimate_tokens_rounding():
    """Test that token estimation uses integer division (floor)."""
    # 10 chars / 4 = 2.5, should floor to 2
    text = "1234567890"
    tokens = ManifestGenerator._estimate_tokens(text)
    assert tokens == 2
    
    # 15 chars / 4 = 3.75, should floor to 3
    text = "123456789012345"
    tokens = ManifestGenerator._estimate_tokens(text)
    assert tokens == 3


# ============================================================================
# Manifest Generation Tests
# ============================================================================

def test_generate_manifest_basic():
    """Test basic manifest generation with simple chapters."""
    chapters = [
        CleanChapter(
            index=0,
            title="Prologue",
            content="Prologue content here",
            token_count_est=100,
            filename="000_prologue.txt",
            volume=None,
            tags=[]
        ),
        CleanChapter(
            index=1,
            title="Chapter 1",
            content="Chapter 1 content here",
            token_count_est=150,
            filename="001_chapter_1.txt",
            volume=None,
            tags=[]
        )
    ]
    
    manifest = ManifestGenerator.generate_manifest(chapters, "test_novel.epub")
    
    # Verify manifest structure
    assert isinstance(manifest, ChapterMap)
    assert manifest.source_filename == "test_novel.epub"
    assert isinstance(manifest.processed_at, datetime)
    assert len(manifest.chapters) == 2
    
    # Verify first chapter entry
    assert manifest.chapters[0].index == 0
    assert manifest.chapters[0].filename == "000_prologue.txt"
    assert manifest.chapters[0].title == "Prologue"
    assert manifest.chapters[0].token_count_est == 100
    assert manifest.chapters[0].volume is None
    assert manifest.chapters[0].metadata == {"tags": []}
    
    # Verify second chapter entry
    assert manifest.chapters[1].index == 1
    assert manifest.chapters[1].filename == "001_chapter_1.txt"
    assert manifest.chapters[1].title == "Chapter 1"
    assert manifest.chapters[1].token_count_est == 150


def test_generate_manifest_with_volumes():
    """Test manifest generation with volume information."""
    chapters = [
        CleanChapter(
            index=0,
            title="Chapter 1",
            content="Content",
            token_count_est=100,
            filename="000_chapter_1.txt",
            volume="Volume 1",
            tags=[]
        ),
        CleanChapter(
            index=1,
            title="Chapter 2",
            content="Content",
            token_count_est=100,
            filename="001_chapter_2.txt",
            volume="Volume 1",
            tags=[]
        ),
        CleanChapter(
            index=2,
            title="Chapter 3",
            content="Content",
            token_count_est=100,
            filename="002_chapter_3.txt",
            volume="Volume 2",
            tags=[]
        )
    ]
    
    manifest = ManifestGenerator.generate_manifest(chapters, "test.epub")
    
    assert manifest.chapters[0].volume == "Volume 1"
    assert manifest.chapters[1].volume == "Volume 1"
    assert manifest.chapters[2].volume == "Volume 2"


def test_generate_manifest_with_tags():
    """Test manifest generation with content tags."""
    chapters = [
        CleanChapter(
            index=0,
            title="Chapter 1",
            content="Content",
            token_count_est=100,
            filename="000_chapter_1.txt",
            volume=None,
            tags=["litrpg", "stat_sheet"]
        ),
        CleanChapter(
            index=1,
            title="Chapter 2",
            content="Short",
            token_count_est=50,
            filename="001_chapter_2.txt",
            volume=None,
            tags=["short_chapter"]
        )
    ]
    
    manifest = ManifestGenerator.generate_manifest(chapters, "test.txt")
    
    assert manifest.chapters[0].metadata == {"tags": ["litrpg", "stat_sheet"]}
    assert manifest.chapters[1].metadata == {"tags": ["short_chapter"]}


def test_generate_manifest_empty_chapters():
    """Test manifest generation with empty chapter list."""
    chapters = []
    
    manifest = ManifestGenerator.generate_manifest(chapters, "empty.txt")
    
    assert isinstance(manifest, ChapterMap)
    assert manifest.source_filename == "empty.txt"
    assert len(manifest.chapters) == 0


def test_generate_manifest_single_chapter():
    """Test manifest generation with single chapter."""
    chapters = [
        CleanChapter(
            index=0,
            title="Only Chapter",
            content="Content",
            token_count_est=200,
            filename="000_only_chapter.txt",
            volume=None,
            tags=[]
        )
    ]
    
    manifest = ManifestGenerator.generate_manifest(chapters, "single.txt")
    
    assert len(manifest.chapters) == 1
    assert manifest.chapters[0].title == "Only Chapter"


def test_generate_manifest_preserves_order():
    """Test that manifest preserves chapter order."""
    chapters = [
        CleanChapter(index=i, title=f"Chapter {i}", content="Content",
                    token_count_est=100, filename=f"{i:03d}_chapter_{i}.txt",
                    volume=None, tags=[])
        for i in range(10)
    ]
    
    manifest = ManifestGenerator.generate_manifest(chapters, "test.epub")
    
    # Verify order is preserved
    for i, entry in enumerate(manifest.chapters):
        assert entry.index == i
        assert entry.title == f"Chapter {i}"


def test_generate_manifest_with_complex_metadata():
    """Test manifest generation with complex chapter metadata."""
    chapters = [
        CleanChapter(
            index=0,
            title="Chapter 1: The Beginning",
            content="A" * 4000,  # 1000 tokens
            token_count_est=1000,
            filename="000_chapter_1_the_beginning.txt",
            volume="Book 1: The Awakening",
            tags=["litrpg", "stat_sheet", "short_chapter"]
        )
    ]
    
    manifest = ManifestGenerator.generate_manifest(chapters, "complex_novel.epub")
    
    entry = manifest.chapters[0]
    assert entry.title == "Chapter 1: The Beginning"
    assert entry.volume == "Book 1: The Awakening"
    assert len(entry.metadata["tags"]) == 3
    assert "litrpg" in entry.metadata["tags"]


# ============================================================================
# Manifest Writing Tests
# ============================================================================

def test_write_manifest_basic():
    """Test basic manifest writing to JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        # Create a simple manifest
        chapters = [
            CleanChapter(
                index=0,
                title="Test Chapter",
                content="Content",
                token_count_est=100,
                filename="000_test_chapter.txt",
                volume=None,
                tags=[]
            )
        ]
        
        manifest = ManifestGenerator.generate_manifest(chapters, "test.epub")
        
        # Write manifest
        ManifestGenerator.write_manifest(manifest, output_dir)
        
        # Verify file was created
        manifest_path = output_dir / "chapter_map.json"
        assert manifest_path.exists()
        
        # Verify content
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert data["source_filename"] == "test.epub"
        assert "processed_at" in data
        assert len(data["chapters"]) == 1
        assert data["chapters"][0]["title"] == "Test Chapter"


def test_write_manifest_creates_directory():
    """Test that write_manifest creates output directory if needed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "new_directory"
        
        # Directory should not exist yet
        assert not output_dir.exists()
        
        # Create and write manifest
        chapters = [
            CleanChapter(
                index=0, title="Test", content="Content",
                token_count_est=100, filename="000_test.txt",
                volume=None, tags=[]
            )
        ]
        manifest = ManifestGenerator.generate_manifest(chapters, "test.txt")
        
        ManifestGenerator.write_manifest(manifest, output_dir)
        
        # Directory should be created
        assert output_dir.exists()
        assert (output_dir / "chapter_map.json").exists()


def test_write_manifest_json_formatting():
    """Test that manifest JSON is formatted with 2-space indentation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        chapters = [
            CleanChapter(
                index=0, title="Test", content="Content",
                token_count_est=100, filename="000_test.txt",
                volume=None, tags=[]
            )
        ]
        manifest = ManifestGenerator.generate_manifest(chapters, "test.txt")
        
        ManifestGenerator.write_manifest(manifest, output_dir)
        
        # Read raw file content
        manifest_path = output_dir / "chapter_map.json"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verify 2-space indentation (check for "  " at start of lines)
        lines = content.split('\n')
        # Should have lines with 2-space indentation
        assert any(line.startswith('  ') for line in lines)
        # Should NOT have lines with 4-space indentation at top level
        # (but nested objects might have 4 spaces)


def test_write_manifest_overwrites_existing():
    """Test that write_manifest overwrites existing manifest file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        manifest_path = output_dir / "chapter_map.json"
        
        # Create initial manifest
        with open(manifest_path, 'w') as f:
            json.dump({"old": "data"}, f)
        
        # Write new manifest
        chapters = [
            CleanChapter(
                index=0, title="New", content="Content",
                token_count_est=100, filename="000_new.txt",
                volume=None, tags=[]
            )
        ]
        manifest = ManifestGenerator.generate_manifest(chapters, "new.txt")
        
        ManifestGenerator.write_manifest(manifest, output_dir)
        
        # Verify old data is replaced
        with open(manifest_path, 'r') as f:
            data = json.load(f)
        
        assert "old" not in data
        assert data["source_filename"] == "new.txt"


def test_write_manifest_with_unicode():
    """Test writing manifest with unicode characters."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        chapters = [
            CleanChapter(
                index=0,
                title="Chapter 1: 日本語タイトル",
                content="Content with unicode",
                token_count_est=100,
                filename="000_chapter_1.txt",
                volume="Volume 1: 第一巻",
                tags=[]
            )
        ]
        
        manifest = ManifestGenerator.generate_manifest(chapters, "unicode_novel.epub")
        ManifestGenerator.write_manifest(manifest, output_dir)
        
        # Read and verify unicode is preserved
        manifest_path = output_dir / "chapter_map.json"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert "日本語タイトル" in data["chapters"][0]["title"]
        assert "第一巻" in data["chapters"][0]["volume"]


def test_write_manifest_with_multiple_chapters():
    """Test writing manifest with multiple chapters."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        # Create 10 chapters
        chapters = [
            CleanChapter(
                index=i,
                title=f"Chapter {i+1}",
                content="Content",
                token_count_est=100 + i * 10,
                filename=f"{i:03d}_chapter_{i+1}.txt",
                volume=f"Volume {(i // 3) + 1}",
                tags=["litrpg"] if i % 2 == 0 else []
            )
            for i in range(10)
        ]
        
        manifest = ManifestGenerator.generate_manifest(chapters, "multi_chapter.epub")
        ManifestGenerator.write_manifest(manifest, output_dir)
        
        # Verify all chapters are in manifest
        manifest_path = output_dir / "chapter_map.json"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert len(data["chapters"]) == 10
        
        # Verify each chapter
        for i, chapter_data in enumerate(data["chapters"]):
            assert chapter_data["index"] == i
            assert chapter_data["title"] == f"Chapter {i+1}"
            assert chapter_data["token_count_est"] == 100 + i * 10


def test_write_manifest_timestamp_format():
    """Test that processed_at timestamp is in ISO 8601 format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        chapters = [
            CleanChapter(
                index=0, title="Test", content="Content",
                token_count_est=100, filename="000_test.txt",
                volume=None, tags=[]
            )
        ]
        
        manifest = ManifestGenerator.generate_manifest(chapters, "test.txt")
        ManifestGenerator.write_manifest(manifest, output_dir)
        
        # Read manifest
        manifest_path = output_dir / "chapter_map.json"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Verify timestamp format (ISO 8601)
        timestamp = data["processed_at"]
        assert isinstance(timestamp, str)
        # Should be parseable as ISO format
        parsed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        assert isinstance(parsed, datetime)


def test_write_manifest_all_required_fields():
    """Test that manifest includes all required fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        chapters = [
            CleanChapter(
                index=0,
                title="Test Chapter",
                content="Content",
                token_count_est=100,
                filename="000_test_chapter.txt",
                volume="Volume 1",
                tags=["litrpg"]
            )
        ]
        
        manifest = ManifestGenerator.generate_manifest(chapters, "test.epub")
        ManifestGenerator.write_manifest(manifest, output_dir)
        
        # Read and verify all required fields
        manifest_path = output_dir / "chapter_map.json"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Top-level fields
        assert "source_filename" in data
        assert "processed_at" in data
        assert "chapters" in data
        
        # Chapter entry fields
        chapter = data["chapters"][0]
        assert "index" in chapter
        assert "filename" in chapter
        assert "title" in chapter
        assert "token_count_est" in chapter
        assert "volume" in chapter
        assert "metadata" in chapter
        assert "tags" in chapter["metadata"]


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_write_manifest_invalid_path():
    """Test that write_manifest raises IOError for invalid paths."""
    # Try to write to an invalid path
    invalid_path = Path("\0invalid")
    
    chapters = [
        CleanChapter(
            index=0, title="Test", content="Content",
            token_count_est=100, filename="000_test.txt",
            volume=None, tags=[]
        )
    ]
    manifest = ManifestGenerator.generate_manifest(chapters, "test.txt")
    
    with pytest.raises(IOError) as exc_info:
        ManifestGenerator.write_manifest(manifest, invalid_path)
    
    assert "Cannot create output directory" in str(exc_info.value)


def test_write_manifest_readonly_directory():
    """Test that write_manifest raises IOError for read-only directory."""
    import sys
    import os
    
    # Skip on Windows as read-only directories behave differently
    if sys.platform == "win32":
        pytest.skip("Read-only directory test not applicable on Windows")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        # Make directory read-only
        os.chmod(output_dir, 0o444)
        
        try:
            chapters = [
                CleanChapter(
                    index=0, title="Test", content="Content",
                    token_count_est=100, filename="000_test.txt",
                    volume=None, tags=[]
                )
            ]
            manifest = ManifestGenerator.generate_manifest(chapters, "test.txt")
            
            # Should raise IOError
            with pytest.raises(IOError) as exc_info:
                ManifestGenerator.write_manifest(manifest, output_dir)
            
            assert "Cannot write manifest file" in str(exc_info.value)
        
        finally:
            # Restore permissions for cleanup
            os.chmod(output_dir, 0o755)


# ============================================================================
# Integration Tests
# ============================================================================

def test_generate_and_write_manifest_integration():
    """Test complete workflow: generate and write manifest."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        # Create realistic chapters
        chapters = [
            CleanChapter(
                index=0,
                title="Prologue: The Awakening",
                content="A" * 2000,
                token_count_est=500,
                filename="000_prologue_the_awakening.txt",
                volume=None,
                tags=[]
            ),
            CleanChapter(
                index=1,
                title="Chapter 1: First Steps",
                content="B" * 4000,
                token_count_est=1000,
                filename="001_chapter_1_first_steps.txt",
                volume="Volume 1",
                tags=["litrpg"]
            ),
            CleanChapter(
                index=2,
                title="Chapter 2: Status Window",
                content="C" * 3000,
                token_count_est=750,
                filename="002_chapter_2_status_window.txt",
                volume="Volume 1",
                tags=["litrpg", "stat_sheet"]
            )
        ]
        
        # Generate manifest
        manifest = ManifestGenerator.generate_manifest(chapters, "test_novel.epub")
        
        # Write manifest
        ManifestGenerator.write_manifest(manifest, output_dir)
        
        # Verify file exists and is valid JSON
        manifest_path = output_dir / "chapter_map.json"
        assert manifest_path.exists()
        
        # Read and validate structure
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Validate top-level structure
        assert data["source_filename"] == "test_novel.epub"
        assert len(data["chapters"]) == 3
        
        # Validate each chapter
        assert data["chapters"][0]["title"] == "Prologue: The Awakening"
        assert data["chapters"][0]["token_count_est"] == 500
        assert data["chapters"][0]["volume"] is None
        
        assert data["chapters"][1]["title"] == "Chapter 1: First Steps"
        assert data["chapters"][1]["volume"] == "Volume 1"
        assert "litrpg" in data["chapters"][1]["metadata"]["tags"]
        
        assert data["chapters"][2]["title"] == "Chapter 2: Status Window"
        assert len(data["chapters"][2]["metadata"]["tags"]) == 2


def test_manifest_round_trip():
    """Test that manifest can be written and read back correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        # Create original chapters
        original_chapters = [
            CleanChapter(
                index=i,
                title=f"Chapter {i+1}",
                content="Content" * 100,
                token_count_est=100 + i * 50,
                filename=f"{i:03d}_chapter_{i+1}.txt",
                volume=f"Volume {(i // 5) + 1}" if i >= 5 else None,
                tags=["litrpg"] if i % 3 == 0 else []
            )
            for i in range(10)
        ]
        
        # Generate and write manifest
        original_manifest = ManifestGenerator.generate_manifest(
            original_chapters, "round_trip_test.epub"
        )
        ManifestGenerator.write_manifest(original_manifest, output_dir)
        
        # Read manifest back
        manifest_path = output_dir / "chapter_map.json"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Reconstruct ChapterMap from JSON
        reconstructed_manifest = ChapterMap(**data)
        
        # Verify all data matches
        assert reconstructed_manifest.source_filename == original_manifest.source_filename
        assert len(reconstructed_manifest.chapters) == len(original_manifest.chapters)
        
        for orig, recon in zip(original_manifest.chapters, reconstructed_manifest.chapters):
            assert orig.index == recon.index
            assert orig.filename == recon.filename
            assert orig.title == recon.title
            assert orig.token_count_est == recon.token_count_est
            assert orig.volume == recon.volume
            assert orig.metadata == recon.metadata
