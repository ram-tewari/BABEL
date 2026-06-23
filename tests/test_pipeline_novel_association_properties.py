"""
Property-based tests for Pipeline Novel Association.

These tests validate universal correctness properties for multi-novel
pipeline processing, ensuring that chapters are correctly associated
with their novel_id and that pipeline state tracks progress separately
for each novel.

Feature: phase-7-librarian, Property 13: Pipeline Novel Association
Validates: Requirements 9.2, 9.3
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from babel.pipeline.orchestrator import PipelineOrchestrator, PipelineConfig
from babel.pipeline.state import JobStateManager, ChapterStatus, JobState
from babel.pipeline.rate_limiter import RateLimiter
from babel.pipeline.reporter import Reporter, ChangelogUpdater, IssueReporter


# ============================================================================
# Strategies for generating test data
# ============================================================================

@st.composite
def novel_id_strategy(draw):
    """Generate a valid novel_id (positive integer or None for legacy)."""
    use_none = draw(st.booleans())
    if use_none:
        return None
    return draw(st.integers(min_value=1, max_value=1000))


@st.composite
def chapter_data_strategy(draw):
    """Generate valid chapter data for pipeline processing."""
    index = draw(st.integers(min_value=0, max_value=100))
    # Filter out control characters and special characters
    title = draw(st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='<>'
        )
    ))
    filename = f"chapter_{index:03d}.txt"
    return {
        'index': index,
        'filename': filename,
        'title': title
    }


@st.composite
def chapters_list_strategy(draw):
    """Generate a list of chapters for pipeline processing."""
    count = draw(st.integers(min_value=1, max_value=20))
    chapters = []
    for i in range(count):
        chapters.append({
            'index': i,
            'filename': f"chapter_{i:03d}.txt",
            'title': f"Chapter {i + 1}"
        })
    return chapters


# ============================================================================
# Property 13: Pipeline Novel Association Tests
# ============================================================================

class TestPipelineNovelAssociation:
    """
    Property-based tests for pipeline novel association.
    
    Feature: phase-7-librarian, Property 13: Pipeline Novel Association
    Validates: Requirements 9.2, 9.3
    """
    
    @given(
        novel_id=novel_id_strategy(),
        chapters=chapters_list_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_chapter_processing_preserves_novel_id(self, novel_id, chapters):
        """
        Feature: phase-7-librarian, Property 13: Pipeline Novel Association
        
        For any chapter processed through the transformation pipeline, the output
        should be correctly associated with the specified novel_id.
        
        This test verifies that:
        1. The orchestrator correctly stores the novel_id
        2. The state manager correctly associates chapters with novel_id
        3. Progress tracking includes the correct novel_id
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create config
            config = PipelineConfig(
                output_dir=temp_path / "data",
                clean_dir=temp_path / "data/clean",
                json_dir=temp_path / "data/json",
                render_dir=temp_path / "data/render",
                log_file=temp_path / "babel.log",
                enable_omnibus=False
            )
            
            # Create state manager with novel_id
            state_file = temp_path / "job_status.json"
            state_manager = JobStateManager(state_file, novel_id=novel_id)
            
            # Initialize state with chapters
            state_manager.initialize("test.epub", chapters)
            
            # Create orchestrator with novel_id
            input_path = temp_path / "test.epub"
            input_path.touch()
            
            rate_limiter = RateLimiter(min_delay_seconds=0.01)
            
            changelog_path = temp_path / "CHANGELOG.md"
            issues_path = temp_path / "ISSUES.md"
            changelog = ChangelogUpdater(changelog_path)
            issue_reporter = IssueReporter(issues_path)
            reporter = Reporter(changelog, issue_reporter)
            
            orchestrator = PipelineOrchestrator(
                config=config,
                input_path=input_path,
                state_manager=state_manager,
                rate_limiter=rate_limiter,
                reporter=reporter,
                novel_id=novel_id
            )
            
            # Verify orchestrator has correct novel_id
            assert orchestrator.current_novel_id == novel_id, \
                f"Orchestrator novel_id should be {novel_id}, got {orchestrator.current_novel_id}"
            
            # Verify state manager has correct novel_id
            assert state_manager.novel_id == novel_id, \
                f"State manager novel_id should be {novel_id}, got {state_manager.novel_id}"
            
            # Verify state has correct novel_id
            assert state_manager.state is not None
            assert state_manager.state.novel_id == novel_id, \
                f"JobState novel_id should be {novel_id}, got {state_manager.state.novel_id}"
            
            # Close log handlers to release file locks (Windows)
            for handler in orchestrator.logger.handlers[:]:
                handler.close()
                orchestrator.logger.removeHandler(handler)
    
    @given(
        novel_ids=st.lists(
            st.one_of(st.none(), st.integers(min_value=1, max_value=100)),
            min_size=2,
            max_size=5,
            unique=True
        ),
        chapters_per_novel=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_separate_progress_tracking_per_novel(self, novel_ids, chapters_per_novel):
        """
        Feature: phase-7-librarian, Property 13: Pipeline Novel Association
        
        The Pipeline_State SHALL track progress separately for each novel_id.
        
        This test verifies that:
        1. Each novel's pipeline state is independent
        2. Progress for one novel doesn't affect another
        3. State files are separate for each novel
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create separate state managers for each novel
            state_managers = {}
            states = {}
            
            for novel_id in novel_ids:
                # Create unique state file for each novel
                state_file = temp_path / f"job_status_{id(novel_id)}.json"
                state_manager = JobStateManager(state_file, novel_id=novel_id)
                
                # Create chapters for this novel
                chapters = [
                    {
                        'index': i,
                        'filename': f"chapter_{i:03d}.txt",
                        'title': f"Chapter {i + 1}"
                    }
                    for i in range(chapters_per_novel)
                ]
                
                # Initialize state
                state_manager.initialize("test.epub", chapters)
                state_managers[novel_id] = state_manager
                states[novel_id] = state_manager.state
            
            # Verify each state has correct novel_id
            for novel_id in novel_ids:
                assert states[novel_id].novel_id == novel_id, \
                    f"State for novel {novel_id} should have novel_id {novel_id}"
            
            # Simulate processing chapters for each novel independently
            for novel_id in novel_ids:
                state = states[novel_id]
                
                # Process some chapters (not all, to test partial progress)
                chapters_to_process = len(state.chapters) // 2
                for i in range(chapters_to_process):
                    state_managers[novel_id].update_chapter(
                        i,
                        ChapterStatus.HTML
                    )
            
            # Verify progress is tracked separately
            for novel_id in novel_ids:
                state = states[novel_id]
                
                # Count completed chapters
                completed = sum(
                    1 for c in state.chapters
                    if c.status == ChapterStatus.HTML
                )
                
                # Verify that only the intended chapters were processed
                assert completed == chapters_per_novel // 2, \
                    f"Novel {novel_id} should have {chapters_per_novel // 2} completed chapters, got {completed}"
                
                # Verify remaining chapters are not processed
                remaining = sum(
                    1 for c in state.chapters
                    if c.status not in (ChapterStatus.HTML, ChapterStatus.FAILED, ChapterStatus.RENDER_FAILED)
                )
                assert remaining == chapters_per_novel - (chapters_per_novel // 2), \
                    f"Novel {novel_id} should have {chapters_per_novel - (chapters_per_novel // 2)} remaining chapters"
    
    @given(
        novel_id=st.integers(min_value=1, max_value=1000),
        chapters=chapters_list_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_progress_includes_novel_id(self, novel_id, chapters):
        """
        Feature: phase-7-librarian, Property 13: Pipeline Novel Association
        
        The pipeline progress tracking should include the novel_id in all
        progress reports.
        
        This test verifies that:
        1. get_progress() returns the correct novel_id
        2. Progress is calculated correctly
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create config
            config = PipelineConfig(
                output_dir=temp_path / "data",
                clean_dir=temp_path / "data/clean",
                json_dir=temp_path / "data/json",
                render_dir=temp_path / "data/render",
                log_file=temp_path / "babel.log",
                enable_omnibus=False
            )
            
            # Create state manager with novel_id
            state_file = temp_path / "job_status.json"
            state_manager = JobStateManager(state_file, novel_id=novel_id)
            
            # Initialize state
            state_manager.initialize("test.epub", chapters)
            
            # Create orchestrator
            input_path = temp_path / "test.epub"
            input_path.touch()
            
            rate_limiter = RateLimiter(min_delay_seconds=0.01)
            
            changelog_path = temp_path / "CHANGELOG.md"
            issues_path = temp_path / "ISSUES.md"
            changelog = ChangelogUpdater(changelog_path)
            issue_reporter = IssueReporter(issues_path)
            reporter = Reporter(changelog, issue_reporter)
            
            orchestrator = PipelineOrchestrator(
                config=config,
                input_path=input_path,
                state_manager=state_manager,
                rate_limiter=rate_limiter,
                reporter=reporter,
                novel_id=novel_id
            )
            
            # Get progress
            progress = orchestrator.get_progress()
            
            # Verify progress includes novel_id
            assert progress["novel_id"] == novel_id, \
                f"Progress should include novel_id {novel_id}, got {progress.get('novel_id')}"
            
            # Verify progress structure
            assert "status" in progress
            assert "progress" in progress
            
            # Verify progress values
            progress_info = progress["progress"]
            assert progress_info["total_chapters"] == len(chapters)
            assert progress_info["completed_chapters"] == 0  # No chapters processed yet
            assert progress_info["percentage"] == 0.0
            
            # Close log handlers to release file locks (Windows)
            for handler in orchestrator.logger.handlers[:]:
                handler.close()
                orchestrator.logger.removeHandler(handler)
    
    @given(
        novel_id=st.integers(min_value=1, max_value=1000),
        num_chapters=st.integers(min_value=1, max_value=15)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_state_serialization_preserves_novel_id(self, novel_id, num_chapters):
        """
        Feature: phase-7-librarian, Property 13: Pipeline Novel Association
        
        When pipeline state is serialized to disk and loaded back, the novel_id
        should be preserved correctly.
        
        This test verifies that:
        1. State serialization includes novel_id
        2. State deserialization restores novel_id correctly
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create state manager with novel_id
            state_file = temp_path / "job_status.json"
            state_manager = JobStateManager(state_file, novel_id=novel_id)
            
            # Create chapters
            chapters = [
                {
                    'index': i,
                    'filename': f"chapter_{i:03d}.txt",
                    'title': f"Chapter {i + 1}"
                }
                for i in range(num_chapters)
            ]
            
            # Initialize state
            state_manager.initialize("test.epub", chapters)
            
            # Process some chapters
            for i in range(num_chapters // 2):
                state_manager.update_chapter(i, ChapterStatus.HTML)
            
            # Serialize to JSON file
            state_dict = state_manager.state.to_dict()
            
            # Verify novel_id is in serialized state
            assert "novel_id" in state_dict
            assert state_dict["novel_id"] == novel_id
            
            # Create new state manager and load from file
            new_state_manager = JobStateManager(state_file, novel_id=None)
            loaded_state = new_state_manager.load()
            
            # Verify novel_id is restored
            assert loaded_state is not None
            assert loaded_state.novel_id == novel_id, \
                f"Loaded state should have novel_id {novel_id}, got {loaded_state.novel_id}"
            
            # Verify chapter states are preserved
            assert len(loaded_state.chapters) == num_chapters
            
            # Verify processed chapters have correct status
            for i in range(num_chapters // 2):
                assert loaded_state.chapters[i].status == ChapterStatus.HTML, \
                    f"Chapter {i} should have HTML status"
            
            # Verify unprocessed chapters have correct status
            for i in range(num_chapters // 2, num_chapters):
                assert loaded_state.chapters[i].status == ChapterStatus.RAW, \
                    f"Chapter {i} should have RAW status"
    
    @given(
        novel_ids=st.lists(
            st.integers(min_value=1, max_value=100),
            min_size=2,
            max_size=5,
            unique=True
        ),
        chapters_count=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_concurrent_novel_processing_isolation(self, novel_ids, chapters_count):
        """
        Feature: phase-7-librarian, Property 13: Pipeline Novel Association
        
        When processing multiple novels, each novel's state should be completely
        isolated and not interfere with other novels' state.
        
        This test verifies that:
        1. Each novel has independent state
        2. Processing one novel doesn't affect another
        3. State files are separate and correct
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create orchestrators and state managers for each novel
            orchestrators = {}
            state_managers = {}
            
            for novel_id in novel_ids:
                # Create unique config and paths for each novel
                config = PipelineConfig(
                    output_dir=temp_path / f"data_{novel_id}",
                    clean_dir=temp_path / f"data_{novel_id}/clean",
                    json_dir=temp_path / f"data_{novel_id}/json",
                    render_dir=temp_path / f"data_{novel_id}/render",
                    log_file=temp_path / f"babel_{novel_id}.log",
                    enable_omnibus=False
                )
                
                # Create state manager with novel_id
                state_file = temp_path / f"job_status_{novel_id}.json"
                state_manager = JobStateManager(state_file, novel_id=novel_id)
                
                # Create chapters
                chapters = [
                    {
                        'index': i,
                        'filename': f"chapter_{i:03d}.txt",
                        'title': f"Chapter {i + 1}"
                    }
                    for i in range(chapters_count)
                ]
                
                # Initialize state
                state_manager.initialize("test.epub", chapters)
                
                # Create orchestrator
                input_path = temp_path / f"test_{novel_id}.epub"
                input_path.touch()
                
                rate_limiter = RateLimiter(min_delay_seconds=0.01)
                
                changelog_path = temp_path / f"CHANGELOG_{novel_id}.md"
                issues_path = temp_path / f"ISSUES_{novel_id}.md"
                changelog = ChangelogUpdater(changelog_path)
                issue_reporter = IssueReporter(issues_path)
                reporter = Reporter(changelog, issue_reporter)
                
                orchestrator = PipelineOrchestrator(
                    config=config,
                    input_path=input_path,
                    state_manager=state_manager,
                    rate_limiter=rate_limiter,
                    reporter=reporter,
                    novel_id=novel_id
                )
                
                orchestrators[novel_id] = orchestrator
                state_managers[novel_id] = state_manager
            
            # Process different numbers of chapters for each novel
            # Use min to ensure we don't exceed available chapters
            for idx, novel_id in enumerate(novel_ids):
                chapters_to_process = min(idx + 1, chapters_count)  # Don't exceed available chapters
                for i in range(chapters_to_process):
                    state_managers[novel_id].update_chapter(i, ChapterStatus.HTML)
            
            # Verify each novel's state is correct and isolated
            for idx, novel_id in enumerate(novel_ids):
                state = state_managers[novel_id].state
                
                # Verify novel_id is correct
                assert state.novel_id == novel_id, \
                    f"Novel {novel_id} state should have novel_id {novel_id}"
                
                # Verify correct number of chapters processed
                expected_processed = min(idx + 1, chapters_count)
                actual_processed = sum(
                    1 for c in state.chapters
                    if c.status == ChapterStatus.HTML
                )
                assert actual_processed == expected_processed, \
                    f"Novel {novel_id} should have {expected_processed} processed chapters, got {actual_processed}"
                
                # Verify other novels are not affected
                for other_id in novel_ids:
                    if other_id != novel_id:
                        other_state = state_managers[other_id].state
                        other_processed = sum(
                            1 for c in other_state.chapters
                            if c.status == ChapterStatus.HTML
                        )
                        # Other novels should have their own processing count
                        other_expected = min(novel_ids.index(other_id) + 1, chapters_count)
                        assert other_processed == other_expected, \
                            f"Novel {other_id} should have {other_expected} processed chapters, got {other_processed}"
            
            # Clean up log handlers
            for orchestrator in orchestrators.values():
                for handler in orchestrator.logger.handlers[:]:
                    handler.close()
                    orchestrator.logger.removeHandler(handler)


# ============================================================================
# Legacy Support Tests (NULL novel_id)
# ============================================================================

class TestLegacyNovelAssociation:
    """
    Tests for backward compatibility with NULL novel_id (legacy chapters).
    
    Feature: phase-7-librarian, Property 13: Pipeline Novel Association
    Validates: Requirements 9.2, 9.3 (backward compatibility)
    """
    
    @given(
        chapters=chapters_list_strategy()
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_legacy_chapters_with_null_novel_id(self, chapters):
        """
        For chapters with NULL novel_id (legacy), the pipeline should still
        function correctly without requiring a novel_id.
        
        This test verifies that:
        1. State manager handles NULL novel_id correctly
        2. Processing works without novel_id
        3. State is preserved correctly
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create state manager with NULL novel_id (legacy mode)
            state_file = temp_path / "job_status.json"
            state_manager = JobStateManager(state_file, novel_id=None)
            
            # Initialize state
            state_manager.initialize("test.epub", chapters)
            
            # Verify state has NULL novel_id
            assert state_manager.state.novel_id is None
            assert state_manager.novel_id is None
            
            # Process some chapters
            for i in range(len(chapters) // 2):
                state_manager.update_chapter(i, ChapterStatus.HTML)
            
            # Verify processing worked correctly
            completed = sum(
                1 for c in state_manager.state.chapters
                if c.status == ChapterStatus.HTML
            )
            assert completed == len(chapters) // 2
    
    @given(
        chapters=chapters_list_strategy()
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_legacy_state_serialization(self, chapters):
        """
        Legacy state (NULL novel_id) should serialize and deserialize correctly.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create state manager with NULL novel_id
            state_file = temp_path / "job_status.json"
            state_manager = JobStateManager(state_file, novel_id=None)
            
            # Initialize state
            state_manager.initialize("test.epub", chapters)
            
            # Serialize
            state_dict = state_manager.state.to_dict()
            
            # Verify novel_id is None in serialized form
            assert state_dict["novel_id"] is None
            
            # Deserialize
            new_state_manager = JobStateManager(state_file, novel_id=None)
            loaded_state = new_state_manager.load()
            
            # Verify novel_id is still None
            assert loaded_state.novel_id is None