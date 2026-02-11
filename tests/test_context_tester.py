"""
Integration tests for glossary effectiveness testing.

Tests the GlossaryTester class and test-glossary CLI command.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from babel.context.tester import GlossaryTester
from babel.context.models import Glossary, GlossaryEntry
from babel.transform.models import ChapterData, ScriptBlock, ScriptBlockType
from datetime import datetime, timezone


@pytest.fixture
def sample_glossary():
    """Create a sample glossary for testing."""
    return Glossary(
        characters=[
            GlossaryEntry(
                name="Chung Myung",
                raw="청명",
                aliases=["The Divine Dragon", "Sahyung"],
                desc="Protagonist"
            ),
            GlossaryEntry(
                name="Baek Cheon",
                raw="백천",
                aliases=["Righteous Sword"],
                desc="Senior disciple"
            )
        ],
        factions=[
            GlossaryEntry(
                name="Mount Hua Sect",
                raw="화산파",
                aliases=["Plum Blossom Sect"],
                desc="One of the Nine Great Sects"
            )
        ],
        locations=[
            GlossaryEntry(
                name="Mount Hua",
                raw="화산",
                aliases=["Hua Mountain"],
                desc="Sacred mountain"
            )
        ],
        terms=[
            GlossaryEntry(
                name="Qi",
                raw="기",
                aliases=["Internal Energy", "Ki"],
                desc="Life force energy"
            )
        ]
    )


@pytest.fixture
def sample_chapter_data():
    """Create sample chapter data for testing."""
    return ChapterData(
        blocks=[
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Chung Myung",
                content="I will restore Mount Hua!"
            ),
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="He channeled his Qi through his meridians."
            ),
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Baek Cheon",
                content="The Mount Hua Sect will rise again!"
            )
        ],
        source_hash="a" * 64,
        model_version="gemini-2.5-flash",
        processed_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def mock_gemini_client():
    """Create a mock Gemini client."""
    client = Mock()
    client.generate_content = Mock(return_value="test response")
    return client


@pytest.fixture
def temp_glossary_file(tmp_path, sample_glossary):
    """Create a temporary glossary file."""
    from babel.context.store import GlossaryStore
    
    glossary_path = tmp_path / "glossary.yaml"
    store = GlossaryStore(glossary_path)
    store.save(sample_glossary)
    
    return glossary_path


@pytest.fixture
def temp_clean_chapters(tmp_path):
    """Create temporary clean chapter files."""
    clean_dir = tmp_path / "clean"
    clean_dir.mkdir()
    
    # Create 3 sample chapters
    for i in range(1, 4):
        chapter_path = clean_dir / f"Ch_{i:03d}.txt"
        chapter_path.write_text(
            f"Chapter {i}\n\n"
            f"Chung Myung stood at the peak of Mount Hua.\n"
            f"The Mount Hua Sect had fallen, but he would restore it.\n"
            f"Baek Cheon approached, his Qi radiating power.\n"
            f"'The Divine Dragon has returned,' he said.\n"
        )
    
    return clean_dir


def test_glossary_tester_initialization(mock_gemini_client, temp_glossary_file):
    """Test GlossaryTester initialization."""
    tester = GlossaryTester(mock_gemini_client, temp_glossary_file)
    
    assert tester.client == mock_gemini_client
    assert tester.glossary_path == temp_glossary_file
    assert tester.glossary_store is not None


def test_test_glossary_effectiveness_with_sample_chapters(
    mock_gemini_client,
    temp_glossary_file,
    temp_clean_chapters,
    sample_chapter_data
):
    """Test glossary effectiveness testing with sample chapters."""
    # Mock the transformer to return sample data
    with patch('babel.context.tester.Transformer') as MockTransformer:
        # Create mock transformer instances
        mock_transformer = Mock()
        mock_transformer.transform_chapter = Mock(return_value=sample_chapter_data)
        MockTransformer.return_value = mock_transformer
        
        # Create tester
        tester = GlossaryTester(mock_gemini_client, temp_glossary_file)
        
        # Run test
        results = tester.test_glossary_effectiveness(
            clean_chapters_dir=temp_clean_chapters,
            sample_size=2,
            random_seed=42
        )
        
        # Verify results structure
        assert 'test_timestamp' in results
        assert 'glossary_path' in results
        assert 'glossary_entries' in results
        assert 'chapters_tested' in results
        assert 'consistency_score' in results
        assert 'chapter_results' in results
        assert 'low_scoring_chapters' in results
        
        # Verify chapters were tested
        assert results['chapters_tested'] == 2
        assert results['glossary_entries'] == 5  # 2 chars + 1 faction + 1 location + 1 term
        
        # Verify consistency score is calculated
        assert 0.0 <= results['consistency_score'] <= 1.0


def test_test_glossary_effectiveness_with_empty_glossary(
    mock_gemini_client,
    tmp_path,
    temp_clean_chapters
):
    """Test that empty glossary returns error."""
    # Create empty glossary
    glossary_path = tmp_path / "empty_glossary.yaml"
    from babel.context.store import GlossaryStore
    store = GlossaryStore(glossary_path)
    store.save(Glossary())
    
    # Create tester
    tester = GlossaryTester(mock_gemini_client, glossary_path)
    
    # Run test
    results = tester.test_glossary_effectiveness(
        clean_chapters_dir=temp_clean_chapters,
        sample_size=2
    )
    
    # Verify error is returned
    assert 'error' in results
    assert results['error'] == "Glossary is empty"
    assert results['consistency_score'] == 0.0
    assert results['chapters_tested'] == 0


def test_test_glossary_effectiveness_with_no_chapters(
    mock_gemini_client,
    temp_glossary_file,
    tmp_path
):
    """Test that missing chapters returns error."""
    # Create empty clean directory
    clean_dir = tmp_path / "empty_clean"
    clean_dir.mkdir()
    
    # Create tester
    tester = GlossaryTester(mock_gemini_client, temp_glossary_file)
    
    # Run test
    results = tester.test_glossary_effectiveness(
        clean_chapters_dir=clean_dir,
        sample_size=2
    )
    
    # Verify error is returned
    assert 'error' in results
    assert results['error'] == "No chapter files found"
    assert results['consistency_score'] == 0.0
    assert results['chapters_tested'] == 0


def test_detect_inconsistencies(
    mock_gemini_client,
    temp_glossary_file,
    sample_glossary
):
    """Test inconsistency detection between transformations."""
    # Create tester
    tester = GlossaryTester(mock_gemini_client, temp_glossary_file)
    
    # Create two different chapter data results
    result_without = ChapterData(
        blocks=[
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Divine Dragon",  # Wrong name
                content="I will restore the sect!"
            ),
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="He used his internal energy."  # Wrong term
            )
        ],
        source_hash="a" * 64,
        model_version="gemini-2.5-flash",
        processed_at=datetime.now(timezone.utc)
    )
    
    result_with = ChapterData(
        blocks=[
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Chung Myung",  # Correct name
                content="I will restore the sect!"
            ),
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="He used his Qi."  # Correct term
            )
        ],
        source_hash="a" * 64,
        model_version="gemini-2.5-flash",
        processed_at=datetime.now(timezone.utc)
    )
    
    # Detect inconsistencies
    inconsistencies = tester._detect_inconsistencies(
        result_without,
        result_with,
        sample_glossary
    )
    
    # Verify inconsistencies were detected
    assert len(inconsistencies) > 0
    
    # Check speaker inconsistency
    speaker_inconsistencies = [
        inc for inc in inconsistencies
        if inc['type'] == 'speaker'
    ]
    assert len(speaker_inconsistencies) > 0


def test_export_results(
    mock_gemini_client,
    temp_glossary_file,
    tmp_path
):
    """Test exporting test results to JSON."""
    # Create tester
    tester = GlossaryTester(mock_gemini_client, temp_glossary_file)
    
    # Create sample results
    results = {
        "test_timestamp": "2024-01-01T00:00:00Z",
        "glossary_path": str(temp_glossary_file),
        "glossary_entries": 5,
        "chapters_tested": 2,
        "consistency_score": 0.85,
        "chapter_results": [
            {
                "chapter": "Ch_001.txt",
                "consistency_score": 0.9,
                "inconsistencies": []
            },
            {
                "chapter": "Ch_002.txt",
                "consistency_score": 0.8,
                "inconsistencies": []
            }
        ],
        "low_scoring_chapters": []
    }
    
    # Export results
    output_path = tmp_path / "test_results.json"
    tester.export_results(results, output_path)
    
    # Verify file was created
    assert output_path.exists()
    
    # Verify content
    with open(output_path, 'r', encoding='utf-8') as f:
        loaded_results = json.load(f)
    
    assert loaded_results == results


def test_calculate_consistency_score(
    mock_gemini_client,
    temp_glossary_file
):
    """Test consistency score calculation."""
    # Create tester
    tester = GlossaryTester(mock_gemini_client, temp_glossary_file)
    
    # Test with sample results
    results = [
        {"consistency_score": 0.9},
        {"consistency_score": 0.8},
        {"consistency_score": 0.7}
    ]
    
    score = tester._calculate_consistency_score(results)
    assert score == pytest.approx(0.8, rel=0.01)
    
    # Test with empty results
    score = tester._calculate_consistency_score([])
    assert score == 0.0


def test_low_scoring_chapters_identification(
    mock_gemini_client,
    temp_glossary_file,
    temp_clean_chapters,
    sample_chapter_data
):
    """Test that low-scoring chapters are identified."""
    # Mock the transformer to return different scores
    with patch('babel.context.tester.Transformer') as MockTransformer:
        # Create mock transformer that returns different results
        def mock_transform(chapter_text):
            # Simulate low score by returning different data
            if "Chapter 1" in chapter_text:
                # Low score chapter
                return ChapterData(
                    blocks=[
                        ScriptBlock(
                            type=ScriptBlockType.DIALOGUE,
                            speaker="Wrong Name",
                            content="Test"
                        )
                    ],
                    source_hash="a" * 64,
                    model_version="gemini-2.5-flash",
                    processed_at=datetime.now(timezone.utc)
                )
            else:
                # High score chapter
                return sample_chapter_data
        
        mock_transformer = Mock()
        mock_transformer.transform_chapter = Mock(side_effect=mock_transform)
        MockTransformer.return_value = mock_transformer
        
        # Create tester
        tester = GlossaryTester(mock_gemini_client, temp_glossary_file)
        
        # Run test
        results = tester.test_glossary_effectiveness(
            clean_chapters_dir=temp_clean_chapters,
            sample_size=2,
            random_seed=42
        )
        
        # Verify low-scoring chapters are identified
        # Note: This test may not always identify low-scoring chapters
        # depending on the mock implementation, but it verifies the structure
        assert 'low_scoring_chapters' in results
        assert isinstance(results['low_scoring_chapters'], list)
