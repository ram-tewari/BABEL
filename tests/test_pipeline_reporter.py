"""
Unit tests for the pipeline reporter module.

These tests validate specific examples and edge cases for the ChangelogUpdater
and IssueReporter classes.
"""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from babel.pipeline.reporter import ChangelogEntry, ChangelogUpdater, IssueReporter


class TestChangelogUpdater:
    """Unit tests for ChangelogUpdater class."""
    
    def test_changelog_entry_formatting_success(self):
        """Test formatting of successful execution entry."""
        entry = ChangelogEntry(
            timestamp=datetime(2026, 2, 3, 10, 30, 45, tzinfo=timezone.utc),
            status="Success",
            input_file="novel.epub",
            chapters_processed=48,
            chapters_failed=2,
            execution_time=225.5
        )
        
        updater = ChangelogUpdater(Path("CHANGELOG.md"))
        formatted = updater.format_entry(entry)
        
        assert "## 2026-02-03 10:30:45 - Success" in formatted
        assert "Input: novel.epub" in formatted
        assert "Chapters Processed: 48/50" in formatted
        assert "Chapters Failed: 2" in formatted
        assert "Execution Time: 3m 45s" in formatted
    
    def test_changelog_entry_formatting_aborted(self):
        """Test formatting of aborted execution entry."""
        entry = ChangelogEntry(
            timestamp=datetime(2026, 2, 3, 9, 15, 22, tzinfo=timezone.utc),
            status="Aborted",
            input_file="novel.epub",
            chapters_processed=25,
            chapters_failed=0,
            execution_time=112.0
        )
        
        updater = ChangelogUpdater(Path("CHANGELOG.md"))
        formatted = updater.format_entry(entry)
        
        assert "## 2026-02-03 09:15:22 - Aborted" in formatted
        assert "Interrupted by user (Ctrl+C)" in formatted
    
    def test_changelog_entry_formatting_failed(self):
        """Test formatting of failed execution entry."""
        entry = ChangelogEntry(
            timestamp=datetime(2026, 2, 3, 8, 0, 10, tzinfo=timezone.utc),
            status="Failed",
            input_file="novel.epub",
            chapters_processed=0,
            chapters_failed=0,
            execution_time=0.5,
            error_message="Missing Gemini API key"
        )
        
        updater = ChangelogUpdater(Path("CHANGELOG.md"))
        formatted = updater.format_entry(entry)
        
        assert "## 2026-02-03 08:00:10 - Failed" in formatted
        assert "Error: Missing Gemini API key" in formatted
    
    def test_changelog_entry_time_formatting_seconds(self):
        """Test time formatting for durations under 60 seconds."""
        entry = ChangelogEntry(
            timestamp=datetime.now(timezone.utc),
            status="Success",
            input_file="test.epub",
            chapters_processed=1,
            chapters_failed=0,
            execution_time=45.3
        )
        
        updater = ChangelogUpdater(Path("CHANGELOG.md"))
        formatted = updater.format_entry(entry)
        
        assert "45.3s" in formatted
    
    def test_changelog_entry_time_formatting_minutes(self):
        """Test time formatting for durations under 60 minutes."""
        entry = ChangelogEntry(
            timestamp=datetime.now(timezone.utc),
            status="Success",
            input_file="test.epub",
            chapters_processed=10,
            chapters_failed=0,
            execution_time=185.0  # 3m 5s
        )
        
        updater = ChangelogUpdater(Path("CHANGELOG.md"))
        formatted = updater.format_entry(entry)
        
        assert "3m 5s" in formatted
    
    def test_changelog_entry_time_formatting_hours(self):
        """Test time formatting for durations over 60 minutes."""
        entry = ChangelogEntry(
            timestamp=datetime.now(timezone.utc),
            status="Success",
            input_file="test.epub",
            chapters_processed=100,
            chapters_failed=0,
            execution_time=7325.0  # 2h 2m
        )
        
        updater = ChangelogUpdater(Path("CHANGELOG.md"))
        formatted = updater.format_entry(entry)
        
        assert "2h 2m" in formatted
    
    def test_changelog_creation(self):
        """Test that CHANGELOG.md is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            changelog_path = Path(tmpdir) / "CHANGELOG.md"
            
            assert not changelog_path.exists()
            
            updater = ChangelogUpdater(changelog_path)
            entry = ChangelogEntry(
                timestamp=datetime.now(timezone.utc),
                status="Success",
                input_file="test.epub",
                chapters_processed=5,
                chapters_failed=0,
                execution_time=30.0
            )
            
            updater.append_entry(entry)
            
            assert changelog_path.exists()
            content = changelog_path.read_text(encoding='utf-8')
            assert "# CHANGELOG" in content
            assert "automatically updated" in content.lower()
    
    def test_changelog_append_multiple_entries(self):
        """Test appending multiple entries maintains chronological order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            changelog_path = Path(tmpdir) / "CHANGELOG.md"
            updater = ChangelogUpdater(changelog_path)
            
            # Add first entry
            entry1 = ChangelogEntry(
                timestamp=datetime(2026, 2, 3, 10, 0, 0, tzinfo=timezone.utc),
                status="Success",
                input_file="test1.epub",
                chapters_processed=5,
                chapters_failed=0,
                execution_time=30.0
            )
            updater.append_entry(entry1)
            
            # Add second entry
            entry2 = ChangelogEntry(
                timestamp=datetime(2026, 2, 3, 11, 0, 0, tzinfo=timezone.utc),
                status="Success",
                input_file="test2.epub",
                chapters_processed=10,
                chapters_failed=0,
                execution_time=60.0
            )
            updater.append_entry(entry2)
            
            # Read content
            content = changelog_path.read_text(encoding='utf-8')
            
            # Most recent entry should appear first
            pos1 = content.find("2026-02-03 10:00:00")
            pos2 = content.find("2026-02-03 11:00:00")
            
            assert pos2 < pos1, "Most recent entry should appear first"


class TestIssueReporter:
    """Unit tests for IssueReporter class."""
    
    def test_report_chapter_failure(self):
        """Test reporting a chapter-level failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            issues_path = Path(tmpdir) / "ISSUES.md"
            reporter = IssueReporter(issues_path)
            
            error = ValueError("Invalid JSON format")
            
            reporter.report_chapter_failure(
                chapter_title="Chapter 1: The Beginning",
                chapter_index=1,
                error=error,
                phase="Phase 1"
            )
            
            assert issues_path.exists()
            content = issues_path.read_text(encoding='utf-8')
            
            # Verify issue was created
            assert "ISSUE-" in content
            assert "ValueError" in content
            assert "Ch_001" in content
            assert "Chapter 1: The Beginning" in content
            assert "Phase 1" in content
    
    def test_report_system_failure(self):
        """Test reporting a system-level failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            issues_path = Path(tmpdir) / "ISSUES.md"
            reporter = IssueReporter(issues_path)
            
            error = RuntimeError("Missing API key")
            context = {
                "input_file": "novel.epub",
                "phase": "Phase 0"
            }
            
            reporter.report_system_failure(error=error, context=context)
            
            assert issues_path.exists()
            content = issues_path.read_text(encoding='utf-8')
            
            # Verify system failure was created
            assert "ISSUE-" in content
            assert "System Failure" in content
            assert "RuntimeError" in content
            assert "Missing API key" in content
            assert "novel.epub" in content
            assert "Critical" in content
    
    def test_duplicate_issue_detection(self):
        """Test that duplicate issues are not created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            issues_path = Path(tmpdir) / "ISSUES.md"
            reporter = IssueReporter(issues_path)
            
            error = ValueError("Test error")
            
            # Report first time
            reporter.report_chapter_failure(
                chapter_title="Chapter 1",
                chapter_index=1,
                error=error,
                phase="Phase 1"
            )
            
            # Report same error again
            reporter.report_chapter_failure(
                chapter_title="Chapter 1",
                chapter_index=1,
                error=error,
                phase="Phase 1"
            )
            
            content = issues_path.read_text(encoding='utf-8')
            
            # Count issue entries
            issue_count = content.count("### ISSUE-")
            
            assert issue_count == 1, "Should not create duplicate issue"
    
    def test_different_chapters_not_duplicate(self):
        """Test that same error on different chapters creates separate issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            issues_path = Path(tmpdir) / "ISSUES.md"
            reporter = IssueReporter(issues_path)
            
            error = ValueError("Test error")
            
            # Report for chapter 1
            reporter.report_chapter_failure(
                chapter_title="Chapter 1",
                chapter_index=1,
                error=error,
                phase="Phase 1"
            )
            
            # Report for chapter 2
            reporter.report_chapter_failure(
                chapter_title="Chapter 2",
                chapter_index=2,
                error=error,
                phase="Phase 1"
            )
            
            content = issues_path.read_text(encoding='utf-8')
            
            # Count issue entries
            issue_count = content.count("### ISSUE-")
            
            assert issue_count == 2, "Should create separate issues for different chapters"
    
    def test_quick_stats_update(self):
        """Test that Quick Stats section is updated correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            issues_path = Path(tmpdir) / "ISSUES.md"
            reporter = IssueReporter(issues_path)
            
            # Report an issue
            error = ValueError("Test error")
            reporter.report_chapter_failure(
                chapter_title="Chapter 1",
                chapter_index=1,
                error=error,
                phase="Phase 1"
            )
            
            content = issues_path.read_text(encoding='utf-8')
            
            # Verify Quick Stats
            assert "## Quick Stats" in content
            assert "Total Issues: 1" in content
            assert "Open: 1" in content
            assert "Resolved: 0" in content
    
    def test_issue_id_generation(self):
        """Test that issue IDs are generated correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            issues_path = Path(tmpdir) / "ISSUES.md"
            reporter = IssueReporter(issues_path)
            
            # Generate first issue ID
            issue_id1 = reporter._generate_issue_id()
            
            # Verify format
            assert issue_id1.startswith("ISSUE-")
            assert len(issue_id1) == 20  # ISSUE-YYYY-MM-DD-NNN (20 chars)
            
            # Create an issue
            error = ValueError("Test error")
            reporter.report_chapter_failure(
                chapter_title="Chapter 1",
                chapter_index=1,
                error=error,
                phase="Phase 1"
            )
            
            # Generate second issue ID
            issue_id2 = reporter._generate_issue_id()
            
            # Verify it's incremented
            assert issue_id2 > issue_id1
    
    def test_issues_file_creation(self):
        """Test that ISSUES.md is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            issues_path = Path(tmpdir) / "ISSUES.md"
            
            assert not issues_path.exists()
            
            reporter = IssueReporter(issues_path)
            error = ValueError("Test error")
            
            reporter.report_chapter_failure(
                chapter_title="Chapter 1",
                chapter_index=1,
                error=error,
                phase="Phase 1"
            )
            
            assert issues_path.exists()
            content = issues_path.read_text(encoding='utf-8')
            assert "# Issue Tracking Log" in content
            assert "## Quick Stats" in content
            assert "## Bugs" in content
