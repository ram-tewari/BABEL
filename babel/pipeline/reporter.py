"""
Pipeline reporting module for BABEL.

This module provides functionality for logging pipeline execution,
tracking issues, and generating changelogs.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, Set
import re


class ReportStatus(str, Enum):
    """Status for changelog entries."""
    SUCCESS = "Success"
    FAILED = "Failed"
    ABORTED = "Aborted"


@dataclass
class ChangelogEntry:
    """Entry for the changelog."""
    timestamp: datetime
    status: ReportStatus
    input_file: str
    chapters_processed: int
    chapters_failed: int
    execution_time: float
    error_message: Optional[str] = None


class ChangelogUpdater:
    """Updates CHANGELOG.md with pipeline execution entries."""

    def __init__(self, changelog_path: Path):
        """
        Initialize changelog updater.
        
        Args:
            changelog_path: Path to CHANGELOG.md file
        """
        self.changelog_path = Path(changelog_path)
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Create CHANGELOG.md if it doesn't exist."""
        if not self.changelog_path.exists():
            self.changelog_path.parent.mkdir(parents=True, exist_ok=True)
            self.changelog_path.write_text(
                "# CHANGELOG\n\n"
                "This file is automatically updated by the BABEL pipeline.\n"
                "Do not edit manually.\n\n",
                encoding='utf-8'
            )

    def format_entry(self, entry: ChangelogEntry) -> str:
        """Format a changelog entry."""
        lines = [
            f"## {entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {entry.status.value}",
            ""
        ]
        
        if entry.status == ReportStatus.ABORTED:
            lines.extend([
                "**Interrupted by user (Ctrl+C)**",
                ""
            ])
        elif entry.status == ReportStatus.FAILED:
            if entry.error_message:
                lines.extend([
                    f"**Error:** {entry.error_message}",
                    ""
                ])
        
        lines.extend([
            f"**Input:** {entry.input_file}",
            f"**Chapters Processed:** {entry.chapters_processed}/{entry.chapters_processed + entry.chapters_failed}",
        ])
        
        if entry.chapters_failed > 0:
            lines.append(f"**Chapters Failed:** {entry.chapters_failed}")
        
        lines.append(f"**Execution Time:** {self._format_duration(entry.execution_time)}")
        lines.append("")
        
        return "\n".join(lines)

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    def append_entry(self, entry: ChangelogEntry) -> None:
        """Append a new entry to the changelog."""
        formatted = self.format_entry(entry)
        
        if self.changelog_path.exists():
            content = self.changelog_path.read_text(encoding='utf-8')
        else:
            content = ""
        
        # Prepend new entry (most recent first)
        new_content = f"{formatted}\n{content}"
        self.changelog_path.write_text(new_content, encoding='utf-8')


class IssueReporter:
    """Reports and tracks issues in ISSUES.md."""

    def __init__(self, issues_path: Path):
        """
        Initialize issue reporter.
        
        Args:
            issues_path: Path to ISSUES.md file
        """
        self.issues_path = Path(issues_path)
        self._seen_issues: Set[str] = set()
        self._issue_count = 0
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Create ISSUES.md if it doesn't exist."""
        if not self.issues_path.exists():
            self.issues_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_issues_file()

    def _init_issues_file(self) -> None:
        """Initialize the issues file with header."""
        self.issues_path.write_text(
            "# Issue Tracking Log\n\n"
            "## Quick Stats\n"
            "- **Total Issues:** 0\n"
            "- **Open:** 0\n"
            "- **Resolved:** 0\n\n"
            "## Bugs\n\n"
            "*Issues are automatically added by the BABEL pipeline.*\n",
            encoding='utf-8'
        )

    def _generate_issue_id(self) -> str:
        """Generate a unique issue ID."""
        self._issue_count += 1
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        return f"ISSUE-{today}-{self._issue_count:03d}"

    def _get_issue_key(
        self,
        chapter_index: Optional[int],
        phase: str,
        error_type: str
    ) -> str:
        """Generate a key for duplicate detection."""
        return f"{chapter_index}:{phase}:{error_type}"

    def report_chapter_failure(
        self,
        chapter_title: str,
        chapter_index: int,
        error: Exception,
        phase: str
    ) -> None:
        """
        Report a chapter-level failure.
        
        Args:
            chapter_title: Title of the chapter
            chapter_index: Index of the chapter
            error: The exception that was raised
            phase: Phase in which the error occurred
        """
        issue_key = self._get_issue_key(
            chapter_index, phase, type(error).__name__
        )
        
        if issue_key in self._seen_issues:
            return
        
        self._seen_issues.add(issue_key)
        
        issue_id = self._generate_issue_id()
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        
        issue_content = f"""### {issue_id}

**Date:** {timestamp}  
**Type:** Chapter Failure  
**Severity:** Medium  
**Phase:** {phase}  
**Chapter:** Ch_{chapter_index:03d} - {chapter_title}

**Error:** `{type(error).__name__}`  
**Message:** {str(error)}

**Status:** Open

---

"""
        
        self._append_issue(issue_content)
        self._update_stats()

    def report_system_failure(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> None:
        """
        Report a system-level failure.
        
        Args:
            error: The exception that was raised
            context: Additional context about the failure
        """
        issue_key = self._get_issue_key(None, "system", type(error).__name__)
        
        if issue_key in self._seen_issues:
            return
        
        self._seen_issues.add(issue_key)
        
        issue_id = self._generate_issue_id()
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        
        context_lines = "\n".join(
            f"- **{k}:** {v}" for k, v in context.items()
        )
        
        issue_content = f"""### {issue_id}

**Date:** {timestamp}  
**Type:** System Failure  
**Severity:** Critical  
**Phase:** {context.get('phase', 'Unknown')}

**Error:** `{type(error).__name__}`  
**Message:** {str(error)}

**Context:**
{context_lines}

**Status:** Open

---

"""
        
        self._append_issue(issue_content)
        self._update_stats()

    def _append_issue(self, content: str) -> None:
        """Append content to the issues file."""
        if self.issues_path.exists():
            content = self.issues_path.read_text(encoding='utf-8')
        else:
            content = "# Issue Tracking Log\n\n## Bugs\n\n"
        
        # Insert before the "## Bugs" section or at the end
        insert_pos = content.find("## Bugs\n\n")
        if insert_pos == -1:
            content += content
        else:
            insert_pos += len("## Bugs\n\n")
            content = content[:insert_pos] + content + content[insert_pos:]
        
        self.issues_path.write_text(content, encoding='utf-8')

    def _update_stats(self) -> None:
        """Update the quick stats section."""
        if not self.issues_path.exists():
            return
        
        content = self.issues_path.read_text(encoding='utf-8')
        
        # Count issues
        total = len(self._seen_issues)
        
        # Update stats
        stats_pattern = r"(\- \*\*Total Issues:\*\* )\d+"
        stats_replacement = rf"\1{total}"
        content = re.sub(stats_pattern, stats_replacement, content)
        
        stats_pattern = r"(\- \*\*Open:\*\* )\d+"
        stats_replacement = rf"\1{total}"
        content = re.sub(stats_pattern, stats_replacement, content)
        
        self.issues_path.write_text(content, encoding='utf-8')


class Reporter:
    """Combined reporter for changelog and issues."""

    def __init__(
        self,
        changelog: ChangelogUpdater,
        issue_reporter: IssueReporter
    ):
        """
        Initialize combined reporter.
        
        Args:
            changelog: Changelog updater
            issue_reporter: Issue reporter
        """
        self.changelog = changelog
        self.issue_reporter = issue_reporter

    def log_execution(
        self,
        status: ReportStatus,
        input_file: str,
        chapters_processed: int,
        chapters_failed: int,
        execution_time: float,
        error_message: Optional[str] = None
    ) -> None:
        """Log a pipeline execution to the changelog."""
        entry = ChangelogEntry(
            timestamp=datetime.now(timezone.utc),
            status=status,
            input_file=input_file,
            chapters_processed=chapters_processed,
            chapters_failed=chapters_failed,
            execution_time=execution_time,
            error_message=error_message
        )
        self.changelog.append_entry(entry)

    def report_chapter_error(
        self,
        chapter_title: str,
        chapter_index: int,
        error: Exception,
        phase: str
    ) -> None:
        """Report a chapter error."""
        self.issue_reporter.report_chapter_failure(
            chapter_title=chapter_title,
            chapter_index=chapter_index,
            error=error,
            phase=phase
        )

    def report_system_error(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> None:
        """Report a system error."""
        self.issue_reporter.report_system_failure(
            error=error,
            context=context
        )