"""
Integration tests for LLM transformation module with mock API.

These tests validate end-to-end flows including:
- Happy path processing
- Idempotency (hash-based skipping)
- Hash change detection
- Partial failure handling
- Rate limit recovery
- Glossary integration (Phase 4)
"""

import json
import hashlib
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, call
import pytest
from babel.transform.batch_processor import BatchProcessor
from babel.transform.transformer import Transformer
from babel.transform.models import ChapterData, ScriptBlock, ScriptBlockType
from babel.transform.gemini_client import RateLimitError

# Try to import Phase 4 components
try:
    from babel.context.store import GlossaryStore
    from babel.context.models import Glossary, GlossaryEntry
    CONTEXT_AVAILABLE = True
except ImportError:
    CONTEXT_AVAILABLE = False


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    clean_dir = Path(tempfile.mkdtemp())
    json_dir = Path(tempfile.mkdtemp())
    
    yield clean_dir, json_dir
    
    # Cleanup
    shutil.rmtree(clean_dir, ignore_errors=True)
    shutil.rmtree(json_dir, ignore_errors=True)


@pytest.fixture
def sample_chapter_data():
    """Create sample chapter data."""
    return ChapterData(
        blocks=[
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Character",
                content="Sample dialogue"
            ),
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="Sample action"
            )
        ],
        source_hash="a" * 64,
        model_version="gemini-1.5-flash"
    )


def test_integration_happy_path_3_chapters(temp_dirs, sample_chapter_data):
    """
    Integration Test: Happy Path - 3 chapters processed successfully.
    
    Validates: Requirements 3.6, 5.3
    """
    clean_dir, json_dir = temp_dirs
    
    # Setup chapter map with 3 chapters
    chapter_map = {
        "chapters": [
            {"index": 0, "filename": "ch_001.txt", "title": "Chapter 1"},
            {"index": 1, "filename": "ch_002.txt", "title": "Chapter 2"},
            {"index": 2, "filename": "ch_003.txt", "title": "Chapter 3"}
        ]
    }
    
    manifest_path = clean_dir / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(chapter_map, f)
    
    # Create source files
    for i in range(1, 4):
        source_path = clean_dir / f"ch_00{i}.txt"
        with open(source_path, 'w', encoding='utf-8') as f:
            f.write(f"Chapter {i} content")
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        
        # Mock transformer to return successful data
        processor.transformer = Mock()
        processor.transformer.transform_chapter = Mock(return_value=sample_chapter_data)
        
        # Process all chapters
        processed, skipped, failed = processor.process_all_chapters()
        
        # Verify results
        assert processed == 3, "All 3 chapters should be processed"
        assert skipped == 0, "No chapters should be skipped"
        assert failed == 0, "No chapters should fail"
        
        # Verify transformer was called 3 times
        assert processor.transformer.transform_chapter.call_count == 3
        
        # Verify output files exist
        for i in range(1, 4):
            output_path = json_dir / f"ch_00{i}.json"
            assert output_path.exists(), f"Output file should exist for chapter {i}"
            
            # Verify JSON is valid
            with open(output_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                assert "blocks" in data
                assert "source_hash" in data


def test_integration_idempotency_skip_with_hash_match(temp_dirs, sample_chapter_data):
    """
    Integration Test: Idempotency - re-run on existing output should skip with hash match.
    
    Validates: Requirements 5.3, 5.4
    """
    clean_dir, json_dir = temp_dirs
    
    # Setup chapter map
    chapter_map = {
        "chapters": [
            {"index": 0, "filename": "ch_001.txt", "title": "Chapter 1"}
        ]
    }
    
    manifest_path = clean_dir / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(chapter_map, f)
    
    # Create source file
    source_text = "Chapter 1 content"
    source_hash = hashlib.sha256(source_text.encode('utf-8')).hexdigest()
    source_path = clean_dir / "ch_001.txt"
    with open(source_path, 'w', encoding='utf-8') as f:
        f.write(source_text)
    
    # Create existing output with matching hash
    existing_data = sample_chapter_data.model_copy(update={"source_hash": source_hash})
    output_path = json_dir / "ch_001.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(existing_data.model_dump_json(indent=2))
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        
        # Mock transformer
        processor.transformer = Mock()
        processor.transformer.transform_chapter = Mock(return_value=sample_chapter_data)
        
        # Process (should skip due to hash match)
        processed, skipped, failed = processor.process_all_chapters()
        
        # Verify results
        assert processed == 0, "No chapters should be processed"
        assert skipped == 1, "Chapter should be skipped (hash match)"
        assert failed == 0, "No chapters should fail"
        
        # Verify transformer was NOT called
        processor.transformer.transform_chapter.assert_not_called()


def test_integration_hash_change_triggers_reprocessing(temp_dirs, sample_chapter_data):
    """
    Integration Test: Hash change - modify source, verify reprocessing.
    
    Validates: Requirements 5.4, 5.5
    """
    clean_dir, json_dir = temp_dirs
    
    # Setup chapter map
    chapter_map = {
        "chapters": [
            {"index": 0, "filename": "ch_001.txt", "title": "Chapter 1"}
        ]
    }
    
    manifest_path = clean_dir / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(chapter_map, f)
    
    # Create source file with NEW content
    new_source_text = "Chapter 1 MODIFIED content"
    new_source_hash = hashlib.sha256(new_source_text.encode('utf-8')).hexdigest()
    source_path = clean_dir / "ch_001.txt"
    with open(source_path, 'w', encoding='utf-8') as f:
        f.write(new_source_text)
    
    # Create existing output with OLD hash
    old_hash = "b" * 64
    existing_data = sample_chapter_data.model_copy(update={"source_hash": old_hash})
    output_path = json_dir / "ch_001.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(existing_data.model_dump_json(indent=2))
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        
        # Mock transformer to return new data with new hash
        new_data = sample_chapter_data.model_copy(update={"source_hash": new_source_hash})
        processor.transformer = Mock()
        processor.transformer.transform_chapter = Mock(return_value=new_data)
        
        # Process (should reprocess due to hash mismatch)
        processed, skipped, failed = processor.process_all_chapters()
        
        # Verify results
        assert processed == 1, "Chapter should be reprocessed"
        assert skipped == 0, "No chapters should be skipped"
        assert failed == 0, "No chapters should fail"
        
        # Verify transformer WAS called
        processor.transformer.transform_chapter.assert_called_once()
        
        # Verify output file has new hash
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert data["source_hash"] == new_source_hash


def test_integration_partial_failure_2_succeed_1_fails(temp_dirs, sample_chapter_data):
    """
    Integration Test: Partial failure - 2 succeed, 1 fails (verify placeholder written).
    
    Validates: Requirements 5.5, 12.1, 12.4
    """
    clean_dir, json_dir = temp_dirs
    
    # Setup chapter map with 3 chapters
    chapter_map = {
        "chapters": [
            {"index": 0, "filename": "ch_001.txt", "title": "Chapter 1"},
            {"index": 1, "filename": "ch_002.txt", "title": "Chapter 2"},
            {"index": 2, "filename": "ch_003.txt", "title": "Chapter 3"}
        ]
    }
    
    manifest_path = clean_dir / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(chapter_map, f)
    
    # Create source files
    for i in range(1, 4):
        source_path = clean_dir / f"ch_00{i}.txt"
        with open(source_path, 'w', encoding='utf-8') as f:
            f.write(f"Chapter {i} content")
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        
        # Mock transformer to succeed for ch1 and ch3, fail for ch2
        def mock_transform(text):
            if "Chapter 2" in text:
                return None  # Failure
            return sample_chapter_data
        
        processor.transformer = Mock()
        processor.transformer.transform_chapter = Mock(side_effect=mock_transform)
        
        # Process all chapters
        processed, skipped, failed = processor.process_all_chapters()
        
        # Verify results
        assert processed == 2, "2 chapters should succeed"
        assert skipped == 0, "No chapters should be skipped"
        assert failed == 1, "1 chapter should fail"
        
        # Verify placeholder was written for failed chapter
        placeholder_path = json_dir / "ch_002.json"
        assert placeholder_path.exists(), "Placeholder should be written for failed chapter"
        
        with open(placeholder_path, 'r', encoding='utf-8') as f:
            placeholder_data = json.load(f)
            
            # Verify placeholder structure
            assert placeholder_data["model_version"] == "gemini-1.5-flash-failed"
            assert len(placeholder_data["blocks"]) == 2
            assert placeholder_data["blocks"][0]["type"] == "system_notification"
            assert "Transformation Failed" in placeholder_data["blocks"][0]["content"]
            assert placeholder_data["blocks"][1]["type"] == "action"
            assert "Chapter 2 content" in placeholder_data["blocks"][1]["content"]


def test_integration_rate_limit_recovery(temp_dirs, sample_chapter_data):
    """
    Integration Test: Rate limit recovery - mock 429, verify retry and success.
    
    Validates: Requirements 3.6
    
    Note: Rate limit retry logic is handled by GeminiClient (with tenacity decorator).
    This test verifies that the batch processor correctly handles transformer failures
    and writes placeholder JSON when rate limits are exhausted.
    """
    clean_dir, json_dir = temp_dirs
    
    # Setup chapter map
    chapter_map = {
        "chapters": [
            {"index": 0, "filename": "ch_001.txt", "title": "Chapter 1"}
        ]
    }
    
    manifest_path = clean_dir / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(chapter_map, f)
    
    # Create source file
    source_path = clean_dir / "ch_001.txt"
    with open(source_path, 'w', encoding='utf-8') as f:
        f.write("Chapter 1 content")
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        
        # Mock transformer to return None (simulating rate limit exhaustion)
        # In real scenario, GeminiClient retries 5 times then transformer returns None
        processor.transformer = Mock()
        processor.transformer.transform_chapter = Mock(return_value=None)
        
        # Process (should write placeholder on failure)
        processed, skipped, failed = processor.process_all_chapters()
        
        # Verify failure was handled gracefully
        assert processed == 0, "No chapters should be processed"
        assert skipped == 0, "No chapters should be skipped"
        assert failed == 1, "Chapter should fail (rate limit exhausted)"
        
        # Verify placeholder was written
        placeholder_path = json_dir / "ch_001.json"
        assert placeholder_path.exists(), "Placeholder should be written for failed chapter"
        
        with open(placeholder_path, 'r', encoding='utf-8') as f:
            placeholder_data = json.load(f)
            assert placeholder_data["model_version"] == "gemini-1.5-flash-failed"


def test_integration_end_to_end_workflow(temp_dirs, sample_chapter_data):
    """
    Integration Test: Complete end-to-end workflow.
    
    Tests the full pipeline from chapter map to JSON output.
    """
    clean_dir, json_dir = temp_dirs
    
    # Setup chapter map
    chapter_map = {
        "chapters": [
            {"index": 0, "filename": "prologue.txt", "title": "Prologue"},
            {"index": 1, "filename": "ch_001.txt", "title": "Chapter 1: The Beginning"},
            {"index": 2, "filename": "epilogue.txt", "title": "Epilogue"}
        ]
    }
    
    manifest_path = clean_dir / "chapter_map.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(chapter_map, f)
    
    # Create source files with different content
    chapters_content = {
        "prologue.txt": "This is the prologue text.",
        "ch_001.txt": "Chapter 1 begins here with exciting content.",
        "epilogue.txt": "The story concludes in the epilogue."
    }
    
    for filename, content in chapters_content.items():
        source_path = clean_dir / filename
        with open(source_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    with patch('babel.transform.batch_processor.GeminiClient'):
        processor = BatchProcessor(clean_dir, json_dir)
        
        # Mock transformer to return data with correct hash
        def mock_transform(text):
            source_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
            return sample_chapter_data.model_copy(update={"source_hash": source_hash})
        
        processor.transformer = Mock()
        processor.transformer.transform_chapter = Mock(side_effect=mock_transform)
        
        # First run - process all
        processed, skipped, failed = processor.process_all_chapters()
        assert processed == 3
        assert skipped == 0
        assert failed == 0
        
        # Verify all output files exist
        assert (json_dir / "prologue.json").exists()
        assert (json_dir / "ch_001.json").exists()
        assert (json_dir / "epilogue.json").exists()
        
        # Second run - should skip all (idempotency)
        processor.transformer.transform_chapter.reset_mock()
        processed, skipped, failed = processor.process_all_chapters()
        assert processed == 0
        assert skipped == 3
        assert failed == 0
        
        # Transformer should not be called on second run
        processor.transformer.transform_chapter.assert_not_called()



# ============================================================================
# Phase 4 Integration Tests (Glossary Context Injection)
# ============================================================================

@pytest.mark.skipif(not CONTEXT_AVAILABLE, reason="Phase 4 (Context) not available")
def test_integration_transformation_with_glossary():
    """
    Integration Test: Transformation with glossary present.
    
    Validates: Requirements 3.1, 3.2
    
    Verifies that:
    1. Transformer loads glossary successfully
    2. Glossary context is injected into system prompt
    3. Transformation completes successfully with glossary
    """
    # Create temporary glossary file
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        glossary_path = temp_path / "glossary.yaml"
        
        # Create sample glossary
        glossary = Glossary(
            characters=[
                GlossaryEntry(
                    name="Chung Myung",
                    raw="청명|Chung Myung",
                    aliases=["The Divine Dragon", "Sahyung"],
                    desc="Protagonist. Former Divine Dragon, reincarnated."
                ),
                GlossaryEntry(
                    name="Baek Cheon",
                    raw="백천|Baek Cheon",
                    aliases=["Righteous Sword"],
                    desc="Senior disciple of Mount Hua Sect."
                )
            ],
            factions=[
                GlossaryEntry(
                    name="Mount Hua Sect",
                    raw="화산파|Mount Hua Sect",
                    aliases=["Plum Blossom Sect"],
                    desc="One of the Nine Great Sects."
                )
            ],
            locations=[
                GlossaryEntry(
                    name="Mount Hua",
                    raw="화산|Mount Hua",
                    aliases=["Hua Mountain"],
                    desc="Sacred mountain where Mount Hua Sect is located."
                )
            ],
            terms=[
                GlossaryEntry(
                    name="Qi",
                    raw="기|Qi",
                    aliases=["Internal Energy", "Ki"],
                    desc="Life force energy used in martial arts."
                )
            ]
        )
        
        # Save glossary
        store = GlossaryStore(glossary_path)
        store.save(glossary)
        
        # Create mock Gemini client
        mock_client = Mock()
        mock_response = json.dumps({
            "blocks": [
                {
                    "type": "dialogue",
                    "speaker": "Chung Myung",
                    "content": "I am the Divine Dragon!"
                },
                {
                    "type": "action",
                    "content": "He stood at Mount Hua."
                }
            ]
        })
        mock_client.generate_content = Mock(return_value=mock_response)
        
        # Create transformer with glossary
        transformer = Transformer(mock_client, glossary_path=glossary_path)
        
        # Verify glossary was loaded
        assert transformer.glossary_store is not None, "Glossary store should be initialized"
        assert transformer.context_injector is not None, "Context injector should be initialized"
        
        # Transform a chapter
        chapter_text = "Chung Myung stood at Mount Hua, channeling his Qi."
        result = transformer.transform_chapter(chapter_text)
        
        # Verify transformation succeeded
        assert result is not None, "Transformation should succeed"
        assert len(result.blocks) == 2, "Should have 2 blocks"
        
        # Verify API was called with glossary context
        mock_client.generate_content.assert_called_once()
        prompt_used = mock_client.generate_content.call_args[0][0]
        
        # Verify glossary section is in prompt
        assert "## NARRATIVE CONTEXT & GLOSSARY" in prompt_used, \
            "Glossary section should be in prompt"
        assert "Chung Myung" in prompt_used, \
            "Character name should be in prompt"
        assert "Mount Hua Sect" in prompt_used, \
            "Faction name should be in prompt"
        assert "Mount Hua" in prompt_used, \
            "Location name should be in prompt"
        assert "Qi" in prompt_used, \
            "Term should be in prompt"
        assert "CRITICAL" in prompt_used, \
            "Critical instruction should be in prompt"


@pytest.mark.skipif(not CONTEXT_AVAILABLE, reason="Phase 4 (Context) not available")
def test_integration_transformation_without_glossary_graceful_degradation():
    """
    Integration Test: Transformation without glossary (graceful degradation).
    
    Validates: Requirements 3.1, 3.2
    
    Verifies that:
    1. Transformer handles missing glossary gracefully
    2. Transformation proceeds without context injection
    3. No errors are raised
    """
    # Create temporary directory without glossary file
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        glossary_path = temp_path / "glossary.yaml"  # Does not exist
        
        # Create mock Gemini client
        mock_client = Mock()
        mock_response = json.dumps({
            "blocks": [
                {
                    "type": "dialogue",
                    "speaker": "Character",
                    "content": "Hello world!"
                }
            ]
        })
        mock_client.generate_content = Mock(return_value=mock_response)
        
        # Create transformer with non-existent glossary path
        transformer = Transformer(mock_client, glossary_path=glossary_path)
        
        # Verify glossary components are initialized but empty
        assert transformer.glossary_store is not None, "Glossary store should be initialized"
        assert transformer.context_injector is not None, "Context injector should be initialized"
        
        # Transform a chapter
        chapter_text = "A character speaks."
        result = transformer.transform_chapter(chapter_text)
        
        # Verify transformation succeeded without glossary
        assert result is not None, "Transformation should succeed without glossary"
        assert len(result.blocks) == 1, "Should have 1 block"
        
        # Verify API was called
        mock_client.generate_content.assert_called_once()
        prompt_used = mock_client.generate_content.call_args[0][0]
        
        # Verify NO glossary section in prompt (empty glossary)
        # The injector should not add the section if glossary is empty
        assert "## NARRATIVE CONTEXT & GLOSSARY" not in prompt_used, \
            "Glossary section should NOT be in prompt when glossary is empty"


@pytest.mark.skipif(not CONTEXT_AVAILABLE, reason="Phase 4 (Context) not available")
def test_integration_glossary_context_appears_in_system_prompt():
    """
    Integration Test: Verify glossary context appears in system prompt.
    
    Validates: Requirements 3.1, 3.2
    
    Verifies the exact format and content of glossary injection.
    """
    # Create temporary glossary file
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        glossary_path = temp_path / "glossary.yaml"
        
        # Create minimal glossary
        glossary = Glossary(
            characters=[
                GlossaryEntry(
                    name="Test Character",
                    raw="테스트|Test Character",
                    aliases=["TC", "Tester"],
                    desc="A test character for validation."
                )
            ],
            factions=[],
            locations=[],
            terms=[]
        )
        
        # Save glossary
        store = GlossaryStore(glossary_path)
        store.save(glossary)
        
        # Create mock Gemini client
        mock_client = Mock()
        mock_response = json.dumps({
            "blocks": [{"type": "action", "content": "Test"}]
        })
        mock_client.generate_content = Mock(return_value=mock_response)
        
        # Create transformer with glossary
        transformer = Transformer(mock_client, glossary_path=glossary_path)
        
        # Transform a chapter
        chapter_text = "Test Character appears."
        result = transformer.transform_chapter(chapter_text)
        
        # Get the prompt that was used
        prompt_used = mock_client.generate_content.call_args[0][0]
        
        # Verify glossary section structure
        assert "## NARRATIVE CONTEXT & GLOSSARY" in prompt_used
        assert "**CRITICAL**" in prompt_used
        assert "You MUST adhere to the following naming conventions" in prompt_used
        
        # Verify character entry format
        assert "### Characters" in prompt_used
        assert "- **Test Character**" in prompt_used
        assert "(테스트|Test Character)" in prompt_used
        assert "Aliases: TC, Tester" in prompt_used
        assert "Context: A test character for validation." in prompt_used
        
        # Verify reminder at end
        assert "**REMINDER**" in prompt_used
        assert "Use these exact names and terms" in prompt_used


@pytest.mark.skipif(not CONTEXT_AVAILABLE, reason="Phase 4 (Context) not available")
def test_integration_glossary_loading_logs_entry_count():
    """
    Integration Test: Verify glossary loading logs entry count.
    
    Validates: Requirement 3.9
    
    Verifies that the transformer logs the number of glossary entries loaded.
    """
    # Create temporary glossary file
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        glossary_path = temp_path / "glossary.yaml"
        
        # Create glossary with known counts
        glossary = Glossary(
            characters=[
                GlossaryEntry(name="Char1", raw="C1"),
                GlossaryEntry(name="Char2", raw="C2")
            ],
            factions=[
                GlossaryEntry(name="Faction1", raw="F1")
            ],
            locations=[
                GlossaryEntry(name="Loc1", raw="L1"),
                GlossaryEntry(name="Loc2", raw="L2"),
                GlossaryEntry(name="Loc3", raw="L3")
            ],
            terms=[
                GlossaryEntry(name="Term1", raw="T1")
            ]
        )
        
        # Save glossary
        store = GlossaryStore(glossary_path)
        store.save(glossary)
        
        # Create mock Gemini client
        mock_client = Mock()
        
        # Capture log output
        import logging
        with patch('babel.transform.transformer.logger') as mock_logger:
            # Create transformer (this should log glossary loading)
            transformer = Transformer(mock_client, glossary_path=glossary_path)
            
            # Verify logging was called with entry counts
            # Should log: "Glossary loaded: 7 entries (2 characters, 1 factions, 3 locations, 1 terms)"
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            
            # Find the glossary loading log
            glossary_log = None
            for log_call in log_calls:
                if "Glossary loaded" in log_call:
                    glossary_log = log_call
                    break
            
            assert glossary_log is not None, "Should log glossary loading"
            assert "7 entries" in glossary_log, "Should log total entry count"
            assert "2 characters" in glossary_log, "Should log character count"
            assert "1 factions" in glossary_log, "Should log faction count"
            assert "3 locations" in glossary_log, "Should log location count"
            assert "1 terms" in glossary_log, "Should log term count"
