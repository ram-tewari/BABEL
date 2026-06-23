"""
Pipeline orchestrator for BABEL.

This module provides the PipelineOrchestrator class that coordinates
the complete processing pipeline with multi-novel support.
"""

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from babel.pipeline.core import PipelineConfig
from babel.pipeline.state import (
    JobStateManager,
    ChapterStatus,
    JobState
)
from babel.pipeline.rate_limiter import RateLimiter
from babel.pipeline.reporter import Reporter, ChangelogUpdater, IssueReporter, ReportStatus
from babel.pipeline.locking import PipelineLock, PipelineLockError


@dataclass
class PipelineResult:
    """Result of a pipeline execution."""
    success: bool
    chapters_processed: int
    chapters_failed: int
    execution_time: float
    error_message: Optional[str] = None


class PipelineOrchestrator:
    """
    Orchestrates the complete BABEL processing pipeline.
    
    Supports multi-novel processing by tracking novel_id throughout
    all transformation operations.
    
    Attributes:
        novel_id: The novel ID this pipeline is processing (None for legacy)
        config: Pipeline configuration
        input_path: Path to input file/directory
        state_manager: Manages job state persistence
        rate_limiter: Controls API call frequency
        reporter: Reports execution results and issues
        logger: Logging instance
    """
    
    def __init__(
        self,
        config: PipelineConfig,
        input_path: Path,
        state_manager: Optional[JobStateManager] = None,
        rate_limiter: Optional[RateLimiter] = None,
        reporter: Optional[Reporter] = None,
        novel_id: Optional[int] = None
    ):
        """
        Initialize the pipeline orchestrator.
        
        Args:
            config: Pipeline configuration
            input_path: Path to input file or directory
            state_manager: Optional state manager (created if not provided)
            rate_limiter: Optional rate limiter (created if not provided)
            reporter: Optional reporter (created if not provided)
            novel_id: Optional novel ID for multi-novel support
        """
        self.config = config
        self.input_path = Path(input_path)
        self.novel_id = novel_id  # Track novel_id for multi-novel support
        
        # Initialize state manager with novel_id
        if state_manager is None:
            state_file = self.config.output_dir / "job_status.json"
            state_manager = JobStateManager(state_file, novel_id=self.novel_id)
        self.state_manager = state_manager
        
        # Initialize rate limiter
        if rate_limiter is None:
            rate_limiter = RateLimiter()
        self.rate_limiter = rate_limiter
        
        # Initialize reporter
        if reporter is None:
            changelog_path = self.config.output_dir / "CHANGELOG.md"
            issues_path = self.config.output_dir / "ISSUES.md"
            changelog = ChangelogUpdater(changelog_path)
            issue_reporter = IssueReporter(issues_path)
            reporter = Reporter(changelog, issue_reporter)
        self.reporter = reporter

        # Initialize lock manager for concurrent processing prevention
        self._lock_manager = PipelineLock()

        # Initialize logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Add file handler if log file is specified
        if self.config.log_file:
            self.config.log_file.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(self.config.log_file)
            handler.setFormatter(
                logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            )
            self.logger.addHandler(handler)
    
    @property
    def current_novel_id(self) -> Optional[int]:
        """Get the novel ID being processed."""
        return self.novel_id
    
    def _get_phase_directory(self, phase: str) -> Path:
        """
        Get the directory for a specific phase.
        
        If novel_id is set, returns data/{phase}/novel_{id}/
        Otherwise returns data/{phase}/ for backward compatibility
        
        Args:
            phase: Phase name (clean, json, render)
            
        Returns:
            Path to phase directory
        """
        base_dir = self.config.output_dir / phase
        
        if self.novel_id is not None:
            return base_dir / f"novel_{self.novel_id}"
        else:
            return base_dir
    
    def _get_chapter_map_path(self) -> Path:
        """
        Get the path to the chapter map file.
        
        If novel_id is set, returns config/chapter_map_novel_{id}.json
        Otherwise returns config/chapter_map.json for backward compatibility
        
        Returns:
            Path to chapter map file
        """
        config_dir = Path("config")
        
        if self.novel_id is not None:
            return config_dir / f"chapter_map_novel_{self.novel_id}.json"
        else:
            return config_dir / "chapter_map.json"
    
    def initialize_directories(self) -> None:
        """
        Create novel-specific directories for all pipeline phases.
        
        Creates:
        - data/clean/novel_{id}/ (or data/clean/ for legacy)
        - data/json/novel_{id}/ (or data/json/ for legacy)
        - data/render/novel_{id}/ (or data/render/ for legacy)
        
        Raises:
            OSError: If directory creation fails
        """
        phases = ['clean', 'json', 'render']
        
        for phase in phases:
            phase_dir = self._get_phase_directory(phase)
            phase_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Created phase directory: {phase_dir}")
    
    def initialize(
        self,
        input_file: str,
        chapters: List[Dict[str, Any]]
    ) -> JobState:
        """
        Initialize the pipeline state.
        
        Args:
            input_file: Path to input file
            chapters: List of chapter metadata
            
        Returns:
            Initialized JobState
        """
        return self.state_manager.initialize(input_file, chapters)
    
    def execute(self) -> PipelineResult:
        """
        Execute the complete pipeline.
        
        Prevents concurrent processing of the same novel using file-based locking.
        
        Returns:
            PipelineResult with execution status and statistics
            
        Raises:
            PipelineLockError: If novel is already being processed
        """
        start_time = time.time()
        chapters_processed = 0
        chapters_failed = 0
        lock_acquired = False
        
        try:
            # Acquire lock for concurrent processing prevention (Requirement 9.5)
            if self.novel_id is not None:
                self._lock_manager.acquire(self.novel_id)
                lock_acquired = True
            
            self.logger.info(f"Starting pipeline for {self.input_path}")
            
            # Execute phases
            chapters_processed, chapters_failed = self._run_all_phases()
            
            execution_time = time.time() - start_time
            
            # Log success
            self.reporter.log_execution(
                status=ReportStatus.SUCCESS,
                input_file=str(self.input_path),
                chapters_processed=chapters_processed,
                chapters_failed=chapters_failed,
                execution_time=execution_time
            )
            
            return PipelineResult(
                success=True,
                chapters_processed=chapters_processed,
                chapters_failed=chapters_failed,
                execution_time=execution_time
            )
            
        except KeyboardInterrupt:
            execution_time = time.time() - start_time
            
            self.reporter.log_execution(
                status=ReportStatus.ABORTED,
                input_file=str(self.input_path),
                chapters_processed=chapters_processed,
                chapters_failed=chapters_failed,
                execution_time=execution_time
            )
            
            self.logger.info("Pipeline interrupted by user")
            sys.exit(130)
            
        except PipelineLockError:
            # Re-raise lock errors without modification
            raise
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            self.reporter.log_execution(
                status=ReportStatus.FAILED,
                input_file=str(self.input_path),
                chapters_processed=chapters_processed,
                chapters_failed=chapters_failed,
                execution_time=execution_time,
                error_message=str(e)
            )
            
            self.reporter.report_system_error(
                error=e,
                context={
                    "input_file": str(self.input_path),
                    "phase": "pipeline",
                    "novel_id": self.novel_id
                }
            )
            
            self.logger.error(f"Pipeline failed: {e}")
            raise
            
        finally:
            # Always release the lock
            if lock_acquired and self.novel_id is not None:
                self._lock_manager.release(self.novel_id)
    
    def _run_all_phases(self) -> tuple:
        """Run all pipeline phases."""
        chapters_processed = 0
        chapters_failed = 0
        
        # Phase 0: Sanitization
        self.logger.info("Phase 0: Sanitization")
        phase_processed, phase_failed = self._execute_phase_0()
        chapters_processed += phase_processed
        chapters_failed += phase_failed
        
        # Phase 1: Transformation
        self.logger.info("Phase 1: Transformation")
        phase_processed, phase_failed = self._execute_phase_1()
        chapters_processed += phase_processed
        chapters_failed += phase_failed
        
        # Phase 2: Rendering
        self.logger.info("Phase 2: Rendering")
        phase_processed, phase_failed = self._execute_phase_2()
        chapters_processed += phase_processed
        chapters_failed += phase_failed
        
        return chapters_processed, chapters_failed
    
    def _execute_phase_0(self) -> tuple:
        """
        Execute Phase 0: Sanitization.
        
        Extracts and cleans raw chapter content.
        
        Returns:
            Tuple of (processed_count, failed_count)
        """
        chapters = self.state_manager.get_chapters_for_phase(0)
        processed = 0
        failed = 0
        
        for chapter in chapters:
            try:
                self._sanitize_chapter(chapter)
                self.state_manager.update_chapter(chapter.index, ChapterStatus.CLEAN)
                processed += 1
            except Exception as e:
                self._handle_chapter_error(chapter, e, "Phase 0")
                self.state_manager.update_chapter(
                    chapter.index, ChapterStatus.FAILED, str(e)
                )
                failed += 1
        
        return processed, failed
    
    def _execute_phase_1(self) -> tuple:
        """
        Execute Phase 1: Transformation.
        
        Transforms cleaned content to structured JSON.
        
        Returns:
            Tuple of (processed_count, failed_count)
        """
        chapters = self.state_manager.get_chapters_for_phase(1)
        processed = 0
        failed = 0
        
        for chapter in chapters:
            try:
                self._transform_chapter(chapter)
                self.state_manager.update_chapter(chapter.index, ChapterStatus.JSON)
                processed += 1
            except Exception as e:
                self._handle_chapter_error(chapter, e, "Phase 1")
                self.state_manager.update_chapter(
                    chapter.index, ChapterStatus.FAILED, str(e)
                )
                failed += 1
        
        return processed, failed
    
    def _execute_phase_2(self) -> tuple:
        """
        Execute Phase 2: Rendering.
        
        Renders JSON to HTML output.
        
        Returns:
            Tuple of (processed_count, failed_count)
        """
        chapters = self.state_manager.get_chapters_for_phase(2)
        processed = 0
        failed = 0
        
        for chapter in chapters:
            try:
                self._render_chapter(chapter)
                self.state_manager.update_chapter(chapter.index, ChapterStatus.HTML)
                processed += 1
            except Exception as e:
                self._handle_chapter_error(chapter, e, "Phase 2")
                self.state_manager.update_chapter(
                    chapter.index, ChapterStatus.RENDER_FAILED, str(e)
                )
                failed += 1
        
        return processed, failed
    
    def _sanitize_chapter(self, chapter) -> None:
        """Sanitize a single chapter."""
        # Placeholder - actual implementation would sanitize content
        self.logger.debug(f"Sanitizing chapter {chapter.index}: {chapter.title}")
    
    def _transform_chapter(self, chapter) -> None:
        """Transform a single chapter to JSON."""
        # Placeholder - actual implementation would transform content
        self.logger.debug(f"Transforming chapter {chapter.index}: {chapter.title}")
    
    def _render_chapter(self, chapter) -> None:
        """Render a single chapter to HTML."""
        # Placeholder - actual implementation would render content
        self.logger.debug(f"Rendering chapter {chapter.index}: {chapter.title}")
    
    def _handle_chapter_error(self, chapter, error: Exception, phase: str) -> None:
        """Handle a chapter processing error."""
        self.logger.error(
            f"Chapter {chapter.index} ({chapter.title}) failed in {phase}: {error}"
        )
        self.reporter.report_chapter_error(
            chapter_title=chapter.title,
            chapter_index=chapter.index,
            error=error,
            phase=phase
        )
    
    def get_progress(self) -> Dict[str, Any]:
        """
        Get current pipeline progress.
        
        Returns:
            Dictionary with progress information including novel_id
        """
        state = self.state_manager.state
        if state is None:
            return {
                "novel_id": self.novel_id,
                "status": "not_started",
                "progress": {}
            }
        
        total = len(state.chapters)
        completed = sum(
            1 for c in state.chapters
            if c.status in (ChapterStatus.HTML, ChapterStatus.FAILED, ChapterStatus.RENDER_FAILED)
        )
        
        return {
            "novel_id": self.novel_id,  # Include novel_id in progress
            "status": "running" if state else "not_started",
            "progress": {
                "total_chapters": total,
                "completed_chapters": completed,
                "percentage": (completed / total * 100) if total > 0 else 0
            }
        }
    
    @classmethod
    def from_state(cls, state: JobState, config: PipelineConfig) -> 'PipelineOrchestrator':
        """
        Create orchestrator from saved state.
        
        Args:
            state: Saved JobState
            config: Pipeline configuration
            
        Returns:
            New PipelineOrchestrator instance
        """
        state_file = config.output_dir / "job_status.json"
        state_manager = JobStateManager(state_file, novel_id=state.novel_id)
        state_manager.load()
        
        return cls(
            config=config,
            input_path=Path(state.input_file),
            state_manager=state_manager,
            novel_id=state.novel_id  # Restore novel_id from state
        )