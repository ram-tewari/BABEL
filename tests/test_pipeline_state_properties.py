"""
Property-based tests for the pipeline state manager.

These tests validate universal correctness properties that should hold
across all valid executions of the state management system.
"""

import json
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from babel.pipeline.state import (
    ChapterStatus,
    ChapterState,
    JobState,
    JobStateManager
)


# Strategy for generating chapter metadata
@st.composite
def chapter_metadata(draw):
    """Generate valid chapter metadata."""
    index = draw(st.integers(min_value=0, max_value=100))
    filename = f"Ch_{index:03d}.txt"
    # Filter out surrogate characters and control characters that can't be encoded in UTF-8
    title = draw(st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(
            blacklist_categories=('Cs',),  # Surrogate characters
            blacklist_characters='\x00\n\r'
        )
    ))
    return {
        'index': index,
        'filename': filename,
        'title': title
    }


# Strategy for generating lists of chapter metadata
chapters_list = st.lists(
    chapter_metadata(),
    min_size=1,
    max_size=20,
    unique_by=lambda x: x['index']
).map(lambda chapters: sorted(chapters, key=lambda x: x['index']))


# Strategy for generating chapter status transitions
status_transitions = st.sampled_from([
    (ChapterStatus.RAW, ChapterStatus.CLEAN),
    (ChapterStatus.CLEAN, ChapterStatus.JSON),
    (ChapterStatus.JSON, ChapterStatus.HTML),
    (ChapterStatus.RAW, ChapterStatus.FAILED),
    (ChapterStatus.JSON, ChapterStatus.RENDER_FAILED)
])


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    chapters=chapters_list,
    transitions=st.lists(
        st.tuples(st.integers(min_value=0, max_value=19), status_transitions),
        min_size=1,
        max_size=10
    )
)
def test_property_1_state_transition_consistency(chapters, transitions):
    """
    Feature: automation-pipeline, Property 1: State Transition Consistency
    
    For any chapter that completes a phase successfully, the State_Manager
    should update the chapter status to the corresponding state (CLEAN for
    Phase 0, JSON for Phase 1, HTML for Phase 2) and persist the state to
    disk immediately.
    
    Validates: Requirements 2.2, 2.3, 2.4, 2.7
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "job_status.json"
        manager = JobStateManager(state_file)
        
        # Initialize state
        manager.initialize("test.epub", chapters)
        
        # Verify initial state is persisted
        assert state_file.exists(), "State file should be created on initialization"
        
        # Apply transitions
        for chapter_idx, (from_status, to_status) in transitions:
            # Ensure chapter index is valid
            if chapter_idx >= len(chapters):
                continue
            
            # Update chapter status
            manager.update_chapter(chapter_idx, to_status)
            
            # Verify state is persisted immediately
            assert state_file.exists(), "State file should exist after update"
            
            # Load state from disk and verify
            with open(state_file, 'r', encoding='utf-8') as f:
                persisted_data = json.load(f)
            
            # Verify the chapter status was updated
            persisted_chapter = persisted_data['chapters'][chapter_idx]
            assert persisted_chapter['status'] == to_status.value, (
                f"Chapter {chapter_idx} status should be {to_status.value}, "
                f"got {persisted_chapter['status']}"
            )
            
            # Verify last_updated was updated
            assert 'last_updated' in persisted_chapter, (
                "Chapter should have last_updated timestamp"
            )
            
            # Verify the state file is valid JSON
            try:
                JobState(**persisted_data)
            except Exception as e:
                pytest.fail(f"Persisted state is not valid: {e}")



@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    chapters=chapters_list,
    completed_status=st.sampled_from([
        ChapterStatus.CLEAN,
        ChapterStatus.JSON,
        ChapterStatus.HTML
    ])
)
def test_property_2_resume_by_default_behavior(chapters, completed_status):
    """
    Feature: automation-pipeline, Property 2: Resume-by-Default Behavior
    
    For any chapter that is already in the target state for the current phase,
    the Pipeline should skip reprocessing that chapter unless the `--retry-failed`
    flag is explicitly provided.
    
    Validates: Requirements 2.5, 13.2
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "job_status.json"
        manager = JobStateManager(state_file)
        
        # Initialize state
        manager.initialize("test.epub", chapters)
        
        # Mark some chapters as completed
        for i, chapter in enumerate(chapters):
            if i % 2 == 0:  # Mark every other chapter as completed
                manager.update_chapter(i, completed_status)
        
        # Verify that completed chapters should be skipped
        for i, chapter in enumerate(chapters):
            if i % 2 == 0:
                # These chapters are completed, should be skipped
                assert manager.should_skip_chapter(i, completed_status), (
                    f"Chapter {i} with status {completed_status} should be skipped "
                    f"when target status is {completed_status}"
                )
                
                # Should also be skipped for earlier phases
                if completed_status == ChapterStatus.HTML:
                    assert manager.should_skip_chapter(i, ChapterStatus.JSON), (
                        f"Chapter {i} with status HTML should be skipped for JSON phase"
                    )
                    assert manager.should_skip_chapter(i, ChapterStatus.CLEAN), (
                        f"Chapter {i} with status HTML should be skipped for CLEAN phase"
                    )
                elif completed_status == ChapterStatus.JSON:
                    assert manager.should_skip_chapter(i, ChapterStatus.CLEAN), (
                        f"Chapter {i} with status JSON should be skipped for CLEAN phase"
                    )
            else:
                # These chapters are not completed, should not be skipped
                assert not manager.should_skip_chapter(i, completed_status), (
                    f"Chapter {i} with status RAW should not be skipped "
                    f"when target status is {completed_status}"
                )
        
        # Verify that FAILED chapters are not skipped (they need explicit retry)
        if len(chapters) > 0:
            manager.update_chapter(0, ChapterStatus.FAILED)
            assert not manager.should_skip_chapter(0, ChapterStatus.JSON), (
                "FAILED chapters should not be skipped (need explicit --retry-failed flag)"
            )
            
            manager.update_chapter(0, ChapterStatus.RENDER_FAILED)
            assert not manager.should_skip_chapter(0, ChapterStatus.HTML), (
                "RENDER_FAILED chapters should not be skipped (need explicit --retry-failed flag)"
            )
