"""
Pipeline core configuration and types for BABEL.

This module provides the PipelineConfig class and other core types
used throughout the pipeline.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PipelineConfig:
    """
    Configuration for the pipeline orchestrator.
    
    All paths are relative to the output directory unless specified otherwise.
    """
    
    # Directory paths
    output_dir: Path = Path("data")
    clean_dir: Path = Path("data/clean")
    json_dir: Path = Path("data/json")
    render_dir: Path = Path("data/render")
    
    # File paths
    log_file: Path = Path("babel.log")
    
    # Feature flags
    enable_omnibus: bool = False
    
    # Retry configuration
    max_retries: int = 3
    retry_backoff_factor: float = 2.0
    
    # Cleanup options
    cleanup_json: bool = True
    
    # LLM provider
    provider: str = "gemini"
    
    def __post_init__(self):
        """Validate and normalize configuration."""
        # Convert string paths to Path objects
        for field_name in ['output_dir', 'clean_dir', 'json_dir', 'render_dir', 'log_file']:
            value = getattr(self, field_name)
            if isinstance(value, str):
                setattr(self, field_name, Path(value))
        
        # Ensure directories exist (will be created during execution)
        self.output_dir.mkdir(parents=True, exist_ok=True)