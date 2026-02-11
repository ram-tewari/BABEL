"""
Property-based tests for the pipeline reporter module.

These tests validate universal correctness properties that should hold
across all valid inputs and execution scenarios.
"""

import logging
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from babel.pipeline.reporter import ChangelogEntry, ChangelogUpdater, IssueReporter


# Strategy for generating valid ChangelogEntry objects
@st.composite
def changelog_entry_strategy(draw):
    """Generate valid ChangelogEntry objects."""
    status = draw(st.sampled_from(["Success", "Aborted", "Failed"]))
    chapters_processed = draw(st.integers(min_value=0, max_value=1000))
    chapters_failed = draw(st.integers(min_value=0, max_value=100))
    execution_time = draw(st.floats(min_value=0.0, max_value=10000.0))
    
    # Generate printable ASCII text for input_file (avoid control characters)
    input_file = draw(st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),  # Printable ASCII
        min_size=1,
        max_size=100
    ))
    
    entry = ChangelogEntry(
        timestamp=datetime.now(timezone.utc),
        status=status,
        input_file=input_file,
        chapters_processed=chapters_processed,
        chapters_failed=chapters_failed,
        execution_time=execution_time,
        error_message=draw(st.one_of(
            st.none(),
            st.text(
                alphabet=st.characters(min_codepoint=32, max_codepoint=126),
                min_size=1,
                max_size=200
            )
        )) if status == "Failed" else None
    )
    
    return entry


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(entry=changelog_entry_strategy())
def test_property_5_changelog_entry_generation(entry):
    """
    Feature: automation-pipeline, Property 5: Changelog Entry Generation
    
    For any pipeline execution (successful, aborted, or failed), the
    Changelog_Updater should append an entry to CHANGELOG.md with ISO 8601
    timestamp, input file, chapters processed/failed, and execution time.
    
    Validates: Requirements 6.1, 6.4
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        changelog_path = Path(tmpdir) / "CHANGELOG.md"
        updater = ChangelogUpdater(changelog_path)
        
        # Append entry
        updater.append_entry(entry)
        
        # Verify file was created
        assert changelog_path.exists(), "CHANGELOG.md should be created"
        
        # Read content with UTF-8 encoding
        content = changelog_path.read_text(encoding='utf-8')
        
        # Verify header exists
        assert "# CHANGELOG" in content, "Should have CHANGELOG header"
        
        # Verify entry was added
        assert entry.status in content, f"Should contain status '{entry.status}'"
        assert entry.input_file in content, f"Should contain input file '{entry.input_file}'"
        assert f"Chapters Processed: {entry.chapters_processed}" in content, \
            "Should contain chapters processed count"
        assert f"Chapters Failed: {entry.chapters_failed}" in content, \
            "Should contain chapters failed count"
        
        # Verify ISO 8601 timestamp format (YYYY-MM-DD HH:MM:SS)
        timestamp_str = entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        assert timestamp_str in content, "Should contain ISO 8601 formatted timestamp"
        
        # Verify execution time is formatted
        assert "Execution Time:" in content, "Should contain execution time"
        
        # Verify error message if present
        if entry.error_message:
            assert entry.error_message in content, "Should contain error message"
        
        # Verify note for aborted executions
        if entry.status == "Aborted":
            assert "Interrupted by user" in content, "Should contain interruption note"


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    entry1=changelog_entry_strategy(),
    entry2=changelog_entry_strategy()
)
def test_property_5_multiple_entries_chronological_order(entry1, entry2):
    """
    Verify that multiple changelog entries are maintained in chronological order.
    
    The most recent entry should appear first (after the header).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        changelog_path = Path(tmpdir) / "CHANGELOG.md"
        updater = ChangelogUpdater(changelog_path)
        
        # Ensure entries have different timestamps (at least 1 second apart)
        import time
        
        # Append first entry
        updater.append_entry(entry1)
        
        # Wait a moment to ensure different timestamps
        time.sleep(0.01)
        
        # Update entry2 timestamp to be after entry1
        entry2.timestamp = datetime.now(timezone.utc)
        
        # Append second entry
        updater.append_entry(entry2)
        
        # Read content with UTF-8 encoding
        content = changelog_path.read_text(encoding='utf-8')
        
        # Find positions of both entries
        entry1_timestamp = entry1.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        entry2_timestamp = entry2.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        
        pos1 = content.find(entry1_timestamp)
        pos2 = content.find(entry2_timestamp)
        
        # If timestamps are different, second entry should appear before first entry
        if entry1_timestamp != entry2_timestamp:
            assert pos2 < pos1, "Most recent entry should appear first"


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(entry=changelog_entry_strategy())
def test_property_5_changelog_file_creation(entry):
    """
    Verify that CHANGELOG.md is created if it doesn't exist.
    
    Validates: Requirement 6.5
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        changelog_path = Path(tmpdir) / "CHANGELOG.md"
        
        # Verify file doesn't exist
        assert not changelog_path.exists(), "File should not exist initially"
        
        updater = ChangelogUpdater(changelog_path)
        
        # Append entry
        updater.append_entry(entry)
        
        # Verify file was created
        assert changelog_path.exists(), "CHANGELOG.md should be created"
        
        # Verify it has proper structure
        content = changelog_path.read_text(encoding='utf-8')
        assert "# CHANGELOG" in content, "Should have header"
        assert "automatically updated" in content.lower(), "Should have description"



@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    chapter_title=st.text(min_size=1, max_size=100),
    chapter_index=st.integers(min_value=0, max_value=999),
    error_type=st.sampled_from(["ValueError", "RuntimeError", "KeyError", "TypeError"]),
    error_msg=st.text(min_size=1, max_size=200)
)
def test_property_6_issue_reporting_idempotency(chapter_title, chapter_index, error_type, error_msg):
    """
    Feature: automation-pipeline, Property 6: Issue Reporting Idempotency
    
    For any chapter failure, if an identical issue (same error type and chapter ID)
    already exists in ISSUES.md, the Issue_Reporter should NOT create a duplicate entry.
    
    Validates: Requirement 7.3
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        issues_path = Path(tmpdir) / "ISSUES.md"
        reporter = IssueReporter(issues_path)
        
        # Create appropriate exception type
        exception_classes = {
            "ValueError": ValueError,
            "RuntimeError": RuntimeError,
            "KeyError": KeyError,
            "TypeError": TypeError
        }
        error = exception_classes[error_type](error_msg)
        
        # Report the issue first time
        reporter.report_chapter_failure(
            chapter_title=chapter_title,
            chapter_index=chapter_index,
            error=error,
            phase="Phase 1"
        )
        
        # Read content after first report
        content_after_first = issues_path.read_text(encoding='utf-8')
        
        # Count issues
        first_count = len(re.findall(r'^### ISSUE-', content_after_first, re.MULTILINE))
        
        # Report the same issue again
        reporter.report_chapter_failure(
            chapter_title=chapter_title,
            chapter_index=chapter_index,
            error=error,
            phase="Phase 1"
        )
        
        # Read content after second report
        content_after_second = issues_path.read_text(encoding='utf-8')
        
        # Count issues again
        second_count = len(re.findall(r'^### ISSUE-', content_after_second, re.MULTILINE))
        
        # Verify no duplicate was created
        assert second_count == first_count, \
            f"Duplicate issue should not be created. First: {first_count}, Second: {second_count}"
        
        # Verify the issue exists
        assert first_count >= 1, "At least one issue should exist"
        
        # Verify the issue contains the error type and chapter ID
        chapter_id = f"Ch_{chapter_index:03d}"
        assert error_type in content_after_first, f"Should contain error type '{error_type}'"
        assert chapter_id in content_after_first, f"Should contain chapter ID '{chapter_id}'"


@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    chapter_title1=st.text(min_size=1, max_size=100),
    chapter_index1=st.integers(min_value=0, max_value=999),
    chapter_title2=st.text(min_size=1, max_size=100),
    chapter_index2=st.integers(min_value=0, max_value=999),
    error_type=st.sampled_from(["ValueError", "RuntimeError", "KeyError", "TypeError"]),
    error_msg=st.text(min_size=1, max_size=200)
)
def test_property_6_different_chapters_not_duplicate(
    chapter_title1, chapter_index1, chapter_title2, chapter_index2, error_type, error_msg
):
    """
    Verify that the same error type on different chapters creates separate issues.
    """
    # Skip if chapters are the same
    if chapter_index1 == chapter_index2:
        return
    
    with tempfile.TemporaryDirectory() as tmpdir:
        issues_path = Path(tmpdir) / "ISSUES.md"
        reporter = IssueReporter(issues_path)
        
        # Create appropriate exception type
        exception_classes = {
            "ValueError": ValueError,
            "RuntimeError": RuntimeError,
            "KeyError": KeyError,
            "TypeError": TypeError
        }
        error = exception_classes[error_type](error_msg)
        
        # Report issue for first chapter
        reporter.report_chapter_failure(
            chapter_title=chapter_title1,
            chapter_index=chapter_index1,
            error=error,
            phase="Phase 1"
        )
        
        # Report same error type for different chapter
        reporter.report_chapter_failure(
            chapter_title=chapter_title2,
            chapter_index=chapter_index2,
            error=error,
            phase="Phase 1"
        )
        
        # Read content
        content = issues_path.read_text(encoding='utf-8')
        
        # Count issues
        issue_count = len(re.findall(r'^### ISSUE-', content, re.MULTILINE))
        
        # Verify two separate issues were created
        assert issue_count == 2, \
            f"Two separate issues should be created for different chapters. Found: {issue_count}"



@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    chapter_title=st.text(min_size=1, max_size=100),
    chapter_index=st.integers(min_value=0, max_value=999),
    error_type=st.sampled_from(["ValueError", "RuntimeError", "KeyError", "TypeError"]),
    error_msg=st.text(min_size=1, max_size=200)
)
def test_property_7_issue_template_compliance(chapter_title, chapter_index, error_type, error_msg):
    """
    Feature: automation-pipeline, Property 7: Issue Template Compliance
    
    For any issue logged to ISSUES.md, the entry should follow the standard issue
    template format from issue-tracking.md, including ID, phase, category, severity,
    status, problem, root cause, solution, files changed, impact, and prevention sections.
    
    Validates: Requirement 7.4
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        issues_path = Path(tmpdir) / "ISSUES.md"
        reporter = IssueReporter(issues_path)
        
        # Create appropriate exception type
        exception_classes = {
            "ValueError": ValueError,
            "RuntimeError": RuntimeError,
            "KeyError": KeyError,
            "TypeError": TypeError
        }
        error = exception_classes[error_type](error_msg)
        
        # Report the issue
        reporter.report_chapter_failure(
            chapter_title=chapter_title,
            chapter_index=chapter_index,
            error=error,
            phase="Phase 1"
        )
        
        # Read content
        content = issues_path.read_text(encoding='utf-8')
        
        # Verify all required template sections are present
        required_sections = [
            "**ID**:",
            "**Phase**:",
            "**Category**:",
            "**Severity**:",
            "**Status**:",
            "**Reported**:",
            "**Resolved**:",
            "**Reporter**:",
            "**Problem**:",
            "**Root Cause**:",
            "**Solution**:",
            "**Files Changed**:",
            "**Impact**:",
            "**Prevention**:"
        ]
        
        for section in required_sections:
            assert section in content, f"Issue should contain '{section}' section"
        
        # Verify issue ID format (ISSUE-YYYY-MM-DD-NNN)
        assert re.search(r'ISSUE-\d{4}-\d{2}-\d{2}-\d{3}', content), \
            "Issue should have valid ID format"
        
        # Verify status emoji
        assert "🔴 Open" in content, "Issue should have status emoji"
        
        # Verify phase is specified
        assert "Phase 1" in content, "Issue should specify the phase"
        
        # Verify category is specified
        assert "Bug" in content, "Issue should have category"
        
        # Verify severity is specified
        assert "Medium" in content, "Issue should have severity"
        
        # Verify reporter is specified
        assert "Pipeline Automation" in content, "Issue should specify reporter"


@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    error_type=st.sampled_from(["ValueError", "RuntimeError", "KeyError", "TypeError"]),
    error_msg=st.text(min_size=1, max_size=200)
)
def test_property_7_system_failure_template_compliance(error_type, error_msg):
    """
    Verify that system failure issues also follow the template format.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        issues_path = Path(tmpdir) / "ISSUES.md"
        reporter = IssueReporter(issues_path)
        
        # Create appropriate exception type
        exception_classes = {
            "ValueError": ValueError,
            "RuntimeError": RuntimeError,
            "KeyError": KeyError,
            "TypeError": TypeError
        }
        error = exception_classes[error_type](error_msg)
        
        # Report system failure
        reporter.report_system_failure(
            error=error,
            context={"input_file": "test.epub", "phase": "Phase 0"}
        )
        
        # Read content
        content = issues_path.read_text(encoding='utf-8')
        
        # Verify all required template sections are present
        required_sections = [
            "**ID**:",
            "**Phase**:",
            "**Category**:",
            "**Severity**:",
            "**Status**:",
            "**Problem**:",
            "**Root Cause**:",
            "**Solution**:",
            "**Impact**:",
            "**Prevention**:"
        ]
        
        for section in required_sections:
            assert section in content, f"System failure issue should contain '{section}' section"
        
        # Verify it's marked as Critical
        assert "Critical" in content, "System failure should be marked as Critical"
        
        # Verify context is included
        assert "test.epub" in content, "System failure should include context"
