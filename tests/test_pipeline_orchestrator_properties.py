"""
Property-based tests for Pipeline Orchestrator.

These tests validate universal correctness properties that should hold
across all valid executions of the orchestrator.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from pathlib import Path
import tempfile
import json
import time
from unittest.mock import Mock, patch, MagicMock
from babel.pipeline.orchestrator import PipelineOrchestrator, PipelineConfig
from babel.pipeline.state import JobStateManager, ChapterStatus
from babel.pipeline.rate_limiter import RateLimiter
from babel.pipeline.reporter import Reporter, ChangelogUpdater, IssueReporter


@settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    num_chapters=st.integers(min_value=3, max_value=10),
    fail_indices=st.lists(st.integers(min_value=0, max_value=9), min_size=1, max_size=3)
)
def test_property_4_fail_soft_chapter_handling(num_chapters, fail_indices):
    """
    Feature: automation-pipeline, Property 4: Fail-Soft Chapter Handling
    
    For any chapter that fails during Phase 1 or Phase 2, the Pipeline should
    mark the chapter status as FAILED (or RENDER_FAILED), log the error, and
    continue processing the next chapter without halting execution.
    
    Validates: Requirements 4.1, 4.2, 4.3, 4.5
    """
    # Ensure fail_indices are within range
    fail_indices = [idx % num_chapters for idx in fail_indices]
    fail_indices = list(set(fail_indices))  # Remove duplicates
    
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
        
        # Create state manager
        state_file = temp_path / "job_status.json"
        state_manager = JobStateManager(state_file)
        
        # Initialize state with test chapters
        chapters = [
            {
                'index': i,
                'filename': f'chapter_{i:03d}.txt',
                'title': f'Chapter {i + 1}'
            }
            for i in range(num_chapters)
        ]
        state_manager.initialize("test.epub", chapters)
        
        # Create rate limiter (with minimal delay for testing)
        rate_limiter = RateLimiter(min_delay_seconds=0.01)
        
        # Create reporter
        changelog_path = temp_path / "CHANGELOG.md"
        issues_path = temp_path / "ISSUES.md"
        changelog = ChangelogUpdater(changelog_path)
        issue_reporter = IssueReporter(issues_path)
        reporter = Reporter(changelog, issue_reporter)
        
        # Create orchestrator
        input_path = temp_path / "test.epub"
        input_path.touch()  # Create dummy file
        
        orchestrator = PipelineOrchestrator(
            input_path=input_path,
            config=config,
            state_manager=state_manager,
            rate_limiter=rate_limiter,
            reporter=reporter
        )
        
        # Mock Phase 0 to return test chapters
        mock_chapters = [
            Mock(index=i, filename=f'chapter_{i:03d}.txt', title=f'Chapter {i + 1}')
            for i in range(num_chapters)
        ]
        
        # Mock _process_chapter to fail for specific indices
        original_process = orchestrator._process_chapter
        
        def mock_process_chapter(chapter_entry, chapter_index):
            if chapter_index in fail_indices:
                raise Exception(f"Simulated failure for chapter {chapter_index}")
            # For successful chapters, just update state
            state_manager.update_chapter(chapter_index, ChapterStatus.HTML)
        
        # Patch methods
        with patch.object(orchestrator, '_execute_phase_0', return_value=mock_chapters):
            with patch.object(orchestrator, '_process_chapter', side_effect=mock_process_chapter):
                with patch.object(orchestrator, '_generate_omnibus'):
                    # Execute pipeline
                    try:
                        result = orchestrator.execute()
                    except SystemExit:
                        # Ignore sys.exit() calls
                        pass
        
        # Close log handlers to release file locks (Windows)
        for handler in orchestrator.logger.handlers[:]:
            handler.close()
            orchestrator.logger.removeHandler(handler)
        
        # Verify fail-soft behavior
        # 1. Pipeline should continue processing all chapters
        assert state_manager.state is not None
        assert len(state_manager.state.chapters) == num_chapters
        
        # 2. Failed chapters should be marked as FAILED
        for idx in fail_indices:
            chapter = state_manager.state.chapters[idx]
            assert chapter.status in [ChapterStatus.FAILED, ChapterStatus.RENDER_FAILED], \
                f"Chapter {idx} should be marked as FAILED, got {chapter.status}"
            assert chapter.error_message is not None, \
                f"Chapter {idx} should have error message"
        
        # 3. Successful chapters should be marked as HTML
        successful_indices = [i for i in range(num_chapters) if i not in fail_indices]
        for idx in successful_indices:
            chapter = state_manager.state.chapters[idx]
            assert chapter.status == ChapterStatus.HTML, \
                f"Chapter {idx} should be marked as HTML, got {chapter.status}"
        
        # 4. ISSUES.md should contain error reports
        if issues_path.exists():
            issues_content = issues_path.read_text()
            # Should have at least one issue logged
            assert len(issues_content) > 0, "ISSUES.md should contain error reports"


@settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    num_chapters=st.integers(min_value=5, max_value=15),
    interrupt_at=st.integers(min_value=1, max_value=10)
)
def test_property_9_state_file_integrity_on_interruption(num_chapters, interrupt_at):
    """
    Feature: automation-pipeline, Property 9: State File Integrity on Interruption
    
    For any interruption (KeyboardInterrupt or system crash), the job_status.json file
    should remain valid JSON and contain the state of all chapters processed up to the
    interruption point.
    
    Validates: Requirements 9.5
    """
    # Ensure interrupt_at is within range
    interrupt_at = min(interrupt_at, num_chapters - 1)
    
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
        
        # Create state manager
        state_file = temp_path / "job_status.json"
        state_manager = JobStateManager(state_file)
        
        # Initialize state with test chapters
        chapters = [
            {
                'index': i,
                'filename': f'chapter_{i:03d}.txt',
                'title': f'Chapter {i + 1}'
            }
            for i in range(num_chapters)
        ]
        state_manager.initialize("test.epub", chapters)
        
        # Create rate limiter (with minimal delay for testing)
        rate_limiter = RateLimiter(min_delay_seconds=0.01)
        
        # Create reporter
        changelog_path = temp_path / "CHANGELOG.md"
        issues_path = temp_path / "ISSUES.md"
        changelog = ChangelogUpdater(changelog_path)
        issue_reporter = IssueReporter(issues_path)
        reporter = Reporter(changelog, issue_reporter)
        
        # Create orchestrator
        input_path = temp_path / "test.epub"
        input_path.touch()  # Create dummy file
        
        orchestrator = PipelineOrchestrator(
            input_path=input_path,
            config=config,
            state_manager=state_manager,
            rate_limiter=rate_limiter,
            reporter=reporter
        )
        
        # Mock Phase 0 to return test chapters
        mock_chapters = [
            Mock(index=i, filename=f'chapter_{i:03d}.txt', title=f'Chapter {i + 1}')
            for i in range(num_chapters)
        ]
        
        # Mock _process_chapter to raise KeyboardInterrupt at specific index
        def mock_process_chapter(chapter_entry, chapter_index):
            if chapter_index == interrupt_at:
                raise KeyboardInterrupt("Simulated user interruption")
            # For successful chapters, just update state
            state_manager.update_chapter(chapter_index, ChapterStatus.HTML)
        
        # Patch methods
        with patch.object(orchestrator, '_execute_phase_0', return_value=mock_chapters):
            with patch.object(orchestrator, '_process_chapter', side_effect=mock_process_chapter):
                with patch.object(orchestrator, '_generate_omnibus'):
                    # Execute pipeline (should be interrupted)
                    try:
                        result = orchestrator.execute()
                    except SystemExit as e:
                        # Expected - KeyboardInterrupt causes sys.exit(130)
                        assert e.code == 130, f"Expected exit code 130, got {e.code}"
        
        # Close log handlers to release file locks (Windows)
        for handler in orchestrator.logger.handlers[:]:
            handler.close()
            orchestrator.logger.removeHandler(handler)
        
        # Verify state file integrity
        # 1. State file should exist
        assert state_file.exists(), "State file should exist after interruption"
        
        # 2. State file should be valid JSON
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
        except json.JSONDecodeError as e:
            pytest.fail(f"State file is not valid JSON: {e}")
        
        # 3. State should contain all chapters
        assert 'chapters' in state_data, "State should contain 'chapters' field"
        assert len(state_data['chapters']) == num_chapters, \
            f"State should contain {num_chapters} chapters, got {len(state_data['chapters'])}"
        
        # 4. Chapters before interruption should be marked as HTML
        for i in range(interrupt_at):
            chapter = state_data['chapters'][i]
            assert chapter['status'] == 'html', \
                f"Chapter {i} should be marked as HTML, got {chapter['status']}"
        
        # 5. Chapter at interruption point should not be HTML (interrupted before completion)
        interrupt_chapter = state_data['chapters'][interrupt_at]
        assert interrupt_chapter['status'] != 'html', \
            f"Chapter {interrupt_at} should not be HTML (interrupted), got {interrupt_chapter['status']}"
        
        # 6. Chapters after interruption should be in initial state (not processed)
        for i in range(interrupt_at + 1, num_chapters):
            chapter = state_data['chapters'][i]
            assert chapter['status'] in ['raw', 'clean'], \
                f"Chapter {i} should be raw/clean (not processed), got {chapter['status']}"


@settings(max_examples=15, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    num_chapters=st.integers(min_value=3, max_value=8)
)
def test_property_10_deterministic_processing(num_chapters):
    """
    Feature: automation-pipeline, Property 10: Deterministic Processing
    
    For any EPUB file, processing it twice should produce identical processing order
    and state updates (deterministic behavior).
    
    Note: This test validates deterministic orchestrator behavior (processing order,
    state updates). Full end-to-end determinism (identical HTML output) would require
    integration testing with real transformers/renderers.
    
    Validates: Requirements 13.1, 13.3
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
        
        # Track processing order for both runs
        processing_order_run1 = []
        processing_order_run2 = []
        
        # Run 1
        state_file_1 = temp_path / "job_status_run1.json"
        state_manager_1 = JobStateManager(state_file_1)
        
        chapters = [
            {
                'index': i,
                'filename': f'chapter_{i:03d}.txt',
                'title': f'Chapter {i + 1}'
            }
            for i in range(num_chapters)
        ]
        state_manager_1.initialize("test.epub", chapters)
        
        rate_limiter_1 = RateLimiter(min_delay_seconds=0.01)
        
        changelog_path_1 = temp_path / "CHANGELOG_run1.md"
        issues_path_1 = temp_path / "ISSUES_run1.md"
        changelog_1 = ChangelogUpdater(changelog_path_1)
        issue_reporter_1 = IssueReporter(issues_path_1)
        reporter_1 = Reporter(changelog_1, issue_reporter_1)
        
        input_path = temp_path / "test.epub"
        input_path.touch()
        
        orchestrator_1 = PipelineOrchestrator(
            input_path=input_path,
            config=config,
            state_manager=state_manager_1,
            rate_limiter=rate_limiter_1,
            reporter=reporter_1
        )
        
        mock_chapters = [
            Mock(index=i, filename=f'chapter_{i:03d}.txt', title=f'Chapter {i + 1}')
            for i in range(num_chapters)
        ]
        
        def mock_process_chapter_run1(chapter_entry, chapter_index):
            processing_order_run1.append(chapter_index)
            state_manager_1.update_chapter(chapter_index, ChapterStatus.HTML)
        
        with patch.object(orchestrator_1, '_execute_phase_0', return_value=mock_chapters):
            with patch.object(orchestrator_1, '_process_chapter', side_effect=mock_process_chapter_run1):
                with patch.object(orchestrator_1, '_generate_omnibus'):
                    try:
                        orchestrator_1.execute()
                    except SystemExit:
                        pass
        
        for handler in orchestrator_1.logger.handlers[:]:
            handler.close()
            orchestrator_1.logger.removeHandler(handler)
        
        # Run 2 (with fresh state)
        state_file_2 = temp_path / "job_status_run2.json"
        state_manager_2 = JobStateManager(state_file_2)
        state_manager_2.initialize("test.epub", chapters)
        
        rate_limiter_2 = RateLimiter(min_delay_seconds=0.01)
        
        changelog_path_2 = temp_path / "CHANGELOG_run2.md"
        issues_path_2 = temp_path / "ISSUES_run2.md"
        changelog_2 = ChangelogUpdater(changelog_path_2)
        issue_reporter_2 = IssueReporter(issues_path_2)
        reporter_2 = Reporter(changelog_2, issue_reporter_2)
        
        orchestrator_2 = PipelineOrchestrator(
            input_path=input_path,
            config=config,
            state_manager=state_manager_2,
            rate_limiter=rate_limiter_2,
            reporter=reporter_2
        )
        
        def mock_process_chapter_run2(chapter_entry, chapter_index):
            processing_order_run2.append(chapter_index)
            state_manager_2.update_chapter(chapter_index, ChapterStatus.HTML)
        
        with patch.object(orchestrator_2, '_execute_phase_0', return_value=mock_chapters):
            with patch.object(orchestrator_2, '_process_chapter', side_effect=mock_process_chapter_run2):
                with patch.object(orchestrator_2, '_generate_omnibus'):
                    try:
                        orchestrator_2.execute()
                    except SystemExit:
                        pass
        
        for handler in orchestrator_2.logger.handlers[:]:
            handler.close()
            orchestrator_2.logger.removeHandler(handler)
        
        # Verify deterministic behavior
        # 1. Processing order should be identical
        assert processing_order_run1 == processing_order_run2, \
            f"Processing order should be deterministic: {processing_order_run1} != {processing_order_run2}"
        
        # 2. Both runs should process all chapters
        assert len(processing_order_run1) == num_chapters, \
            f"Run 1 should process all {num_chapters} chapters, got {len(processing_order_run1)}"
        assert len(processing_order_run2) == num_chapters, \
            f"Run 2 should process all {num_chapters} chapters, got {len(processing_order_run2)}"
        
        # 3. Final state should be identical
        with open(state_file_1, 'r', encoding='utf-8') as f:
            state_data_1 = json.load(f)
        with open(state_file_2, 'r', encoding='utf-8') as f:
            state_data_2 = json.load(f)
        
        # Compare chapter statuses (ignore timestamps)
        for i in range(num_chapters):
            status_1 = state_data_1['chapters'][i]['status']
            status_2 = state_data_2['chapters'][i]['status']
            assert status_1 == status_2, \
                f"Chapter {i} status should be identical: {status_1} != {status_2}"


@settings(max_examples=15, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    max_retries=st.integers(min_value=2, max_value=4),
    backoff_factor=st.floats(min_value=1.5, max_value=2.5)
)
def test_property_13_retry_logic_with_exponential_backoff(max_retries, backoff_factor):
    """
    Feature: automation-pipeline, Property 13: Retry Logic with Exponential Backoff
    
    For any API call that fails with a transient error (429, 503, network timeout),
    the Pipeline should retry up to the configured maximum with exponential backoff,
    and if all retries fail, mark the chapter as FAILED.
    
    Validates: Requirements 15.1, 15.4
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create config with custom retry settings
        config = PipelineConfig(
            output_dir=temp_path / "data",
            clean_dir=temp_path / "data/clean",
            json_dir=temp_path / "data/json",
            render_dir=temp_path / "data/render",
            log_file=temp_path / "babel.log",
            enable_omnibus=False,
            max_retries=max_retries,
            retry_backoff_factor=backoff_factor
        )
        
        # Create state manager
        state_file = temp_path / "job_status.json"
        state_manager = JobStateManager(state_file)
        
        chapters = [
            {
                'index': 0,
                'filename': 'chapter_001.txt',
                'title': 'Chapter 1'
            }
        ]
        state_manager.initialize("test.epub", chapters)
        
        # Create rate limiter (with minimal delay for testing)
        rate_limiter = RateLimiter(min_delay_seconds=0.01)
        
        # Create reporter
        changelog_path = temp_path / "CHANGELOG.md"
        issues_path = temp_path / "ISSUES.md"
        changelog = ChangelogUpdater(changelog_path)
        issue_reporter = IssueReporter(issues_path)
        reporter = Reporter(changelog, issue_reporter)
        
        # Create orchestrator
        input_path = temp_path / "test.epub"
        input_path.touch()
        
        orchestrator = PipelineOrchestrator(
            input_path=input_path,
            config=config,
            state_manager=state_manager,
            rate_limiter=rate_limiter,
            reporter=reporter
        )
        
        # Track retry attempts and sleep calls
        retry_attempts = []
        sleep_delays = []
        
        # Mock time.sleep to track delays
        def mock_sleep(delay):
            sleep_delays.append(delay)
            # Don't actually sleep in tests
        
        # Mock transformer that always fails with transient error
        def mock_transform_chapter(chapter_text):
            retry_attempts.append(len(retry_attempts) + 1)
            raise Exception("503 Service Unavailable")  # Transient error
        
        # Test _transform_with_retry directly
        with patch('time.sleep', side_effect=mock_sleep):
            # Also patch the rate limiter's sleep to avoid interference
            with patch.object(rate_limiter, 'wait_if_needed', return_value=None):
                with patch('babel.transform.transformer.Transformer') as MockTransformer:
                    mock_transformer_instance = Mock()
                    mock_transformer_instance.transform_chapter = mock_transform_chapter
                    MockTransformer.return_value = mock_transformer_instance
                    
                    # Call _transform_with_retry (should fail after retries)
                    try:
                        orchestrator._transform_with_retry("test chapter text", "Chapter 1")
                        assert False, "Should have raised exception after retries exhausted"
                    except Exception as e:
                        # Expected - all retries exhausted
                        assert "503" in str(e) or "Service Unavailable" in str(e) or "retries" in str(e).lower()
        
        # Close log handlers
        for handler in orchestrator.logger.handlers[:]:
            handler.close()
            orchestrator.logger.removeHandler(handler)
        
        # Verify retry logic
        # 1. Should have attempted max_retries times
        assert len(retry_attempts) == max_retries, \
            f"Should have {max_retries} retry attempts, got {len(retry_attempts)}"
        
        # 2. Should have max_retries-1 sleep calls (no sleep after last attempt)
        assert len(sleep_delays) == max_retries - 1, \
            f"Should have {max_retries - 1} sleep calls, got {len(sleep_delays)}"
        
        # 3. Delays should follow exponential backoff pattern
        # Expected delays: backoff_factor^0, backoff_factor^1, backoff_factor^2, ...
        for i, delay in enumerate(sleep_delays):
            expected_delay = backoff_factor ** i
            # Allow small tolerance for floating point
            assert abs(delay - expected_delay) < 0.01, \
                f"Retry {i+1} delay should be {expected_delay}s, got {delay}s"




