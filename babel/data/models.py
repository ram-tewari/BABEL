"""
Pydantic data models for BABEL multi-novel library management.

This module provides validated data models for novels, chapters, pipeline state,
and API responses used throughout the library management system.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class Novel(BaseModel):
    """
    Novel entity with metadata.
    
    Represents a complete webnovel with associated chapters, cover art,
    and processing status.
    """
    
    id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=500)
    author: Optional[str] = Field(None, max_length=200)
    cover_url: Optional[str] = Field(None, max_length=1000)
    synopsis: Optional[str] = Field(None, max_length=5000)
    tags: List[str] = Field(default_factory=list)
    status: str = Field(default="active", pattern="^(active|completed|dropped)$")
    chapter_count: int = Field(default=0, description="Number of chapters in the novel")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Ensure all tags are non-empty strings."""
        return [tag.strip() for tag in v if isinstance(tag, str) and tag.strip()]
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Return of the Mount Hua Sect",
                "author": "Biga",
                "status": "active",
                "tags": ["martial arts", "regression", "action"]
            }
        }


class NovelCreate(BaseModel):
    """Model for creating a new novel."""
    
    title: str = Field(..., min_length=1, max_length=500)
    author: Optional[str] = Field(None, max_length=200)
    cover_url: Optional[str] = Field(None, max_length=1000)
    status: str = Field(default="active", pattern="^(active|completed|dropped)$")


class NovelUpdate(BaseModel):
    """Model for updating novel metadata."""
    
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    author: Optional[str] = Field(None, max_length=200)
    cover_url: Optional[str] = Field(None, max_length=1000)
    synopsis: Optional[str] = Field(None, max_length=5000)
    tags: Optional[List[str]] = None
    status: Optional[str] = Field(None, pattern="^(active|completed|dropped)$")
    
    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Ensure all tags are non-empty strings."""
        if v is None:
            return None
        return [tag.strip() for tag in v if isinstance(tag, str) and tag.strip()]



class ChapterBlock(BaseModel):
    """Content block within a chapter."""
    type: str # 'dialogue', 'thought', 'narrator', 'action', 'system', 'monologue'
    speaker: Optional[str] = None
    content: Optional[str] = None
    text: Optional[str] = None  # Alternative field name for backward compatibility
    tone: Optional[str] = None
    
    def __init__(self, **data):
        """Initialize and normalize content field."""
        # If content is missing but text is present, use text as content
        if 'content' not in data and 'text' in data:
            data['content'] = data['text']
        super().__init__(**data)


class Chapter(BaseModel):
    """
    Chapter entity with novel association.
    
    Supports NULL novel_id for backward compatibility with existing
    chapters that were created before the multi-novel system.
    """
    
    id: Optional[int] = None
    novel_id: Optional[int] = None  # NULL for backward compatibility
    chapter_index: int = Field(..., ge=1)
    filename: str = Field(..., min_length=1, max_length=500)
    title: Optional[str] = Field(None, max_length=500)
    created_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "chapter_index": 1,
                "filename": "chapter_01.txt",
                "title": "Chapter 1: The Beginning"
            }
        }


class PipelineState(BaseModel):
    """
    Pipeline processing state for a novel.
    
    Tracks the status of each phase (sanitize, transform, render)
    for a specific novel. Supports NULL novel_id for legacy single-novel
    processing.
    """
    
    id: Optional[int] = None
    novel_id: Optional[int] = None  # NULL for legacy single-novel
    phase: str = Field(..., pattern="^(sanitize|transform|render)$")
    status: str = Field(..., pattern="^(pending|running|complete|failed)$")
    last_chapter: Optional[int] = Field(None, ge=0)
    total_chapters: Optional[int] = Field(None, ge=0)
    error_message: Optional[str] = None
    updated_at: Optional[datetime] = None


class ExternalMetadata(BaseModel):
    """
    Metadata fetched from external source.
    
    Represents the structured data retrieved from external APIs
    like NovelUpdates or RoyalRoad.
    """
    
    title: str
    author: Optional[str] = None
    cover_url: Optional[str] = None
    synopsis: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    status: str = Field(default="active", pattern="^(active|completed|dropped)$")
    source: str = Field(..., description="Source of metadata: 'novelupdates' or 'royalroad'")
    
    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Ensure all tags are non-empty strings."""
        return [tag.strip() for tag in v if isinstance(tag, str) and tag.strip()]


class CoverUploadResponse(BaseModel):
    """Response model for cover upload operations."""
    
    novel_id: int
    cover_url: str
    message: str = "Cover uploaded successfully"


class ImportResponse(BaseModel):
    """Response model for EPUB import operations."""
    
    novel_id: int
    title: str
    chapters_extracted: int
    status: str = "success"


class NovelListResponse(BaseModel):
    """Response model for listing novels."""
    
    novels: List[Novel]
    total: int


class NovelResponse(BaseModel):
    """Response model for a single novel with chapter count."""
    
    id: int
    title: str
    author: Optional[str] = None
    cover_url: Optional[str] = None
    synopsis: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    status: str
    chapter_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ChapterListResponse(BaseModel):
    """Response model for listing chapters."""
    
    chapters: List[Chapter]
    total: int
    novel_id: int


class MetadataRequest(BaseModel):
    """Request model for metadata fetching."""
    
    source: str = Field(..., pattern="^(novelupdates|royalroad)$")
    search_query: Optional[str] = Field(None, max_length=500)


class ErrorResponse(BaseModel):
    """Standard error response model."""
    
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None