"""
Chapter API endpoints with backward compatibility support.

Provides REST API endpoints for:
- Legacy chapter access via /api/chapter/{id}
- Novel-scoped chapter access via /api/library/{novel_id}/chapter/{id}
- Chapter CRUD operations

Supports both legacy (single-novel) and new (multi-novel) URL patterns.

Requirements: 8.3, 8.5
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from babel.data.db import DatabaseManager
from babel.data.models import Chapter, ChapterResponse

logger = logging.getLogger(__name__)

# Router for legacy chapter endpoints
router = APIRouter(prefix="/api/chapter", tags=["chapters"])

# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    """Get or create the database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


class ChapterDetailResponse(BaseModel):
    """Response model for chapter detail endpoint."""
    
    id: int
    novel_id: Optional[int] = None
    chapter_index: int
    filename: str
    title: Optional[str] = None
    content: Optional[str] = None
    created_at: Optional[str] = None


@router.get("/{chapter_id}", response_model=ChapterDetailResponse)
async def get_chapter(chapter_id: int):
    """
    Get a chapter by ID (legacy endpoint).
    
    This endpoint provides backward compatibility for the existing
    single-novel workflow. It allows accessing chapters directly
    by their ID without requiring a novel_id.
    
    For chapters with NULL novel_id (legacy chapters), they are treated
    as belonging to the default "Infinite Mage" legacy novel.
    
    Args:
        chapter_id: The chapter ID to retrieve.
        
    Returns:
        ChapterDetailResponse with chapter details.
        
    Raises:
        HTTPException: If chapter not found (404).
    """
    db = get_db()
    
    chapter = db.get_chapter(chapter_id)
    
    if chapter is None:
        raise HTTPException(
            status_code=404,
            detail=f"Chapter with ID {chapter_id} not found"
        )
    
    # For legacy chapters (NULL novel_id), we could include a flag
    # to indicate this is a legacy chapter
    is_legacy = chapter.get("novel_id") is None
    
    return ChapterDetailResponse(
        id=chapter["id"],
        novel_id=chapter.get("novel_id"),
        chapter_index=chapter["chapter_index"],
        filename=chapter["filename"],
        title=chapter.get("title"),
        content=chapter.get("content"),
        created_at=chapter.get("created_at")
    )


@router.delete("/{chapter_id}")
async def delete_chapter(chapter_id: int):
    """
    Delete a chapter by ID (legacy endpoint).
    
    This endpoint provides backward compatibility for the existing
    single-novel workflow.
    
    Args:
        chapter_id: The chapter ID to delete.
        
    Returns:
        JSON response with success message.
        
    Raises:
        HTTPException: If chapter not found (404).
    """
    db = get_db()
    
    # Check if chapter exists
    chapter = db.get_chapter(chapter_id)
    if chapter is None:
        raise HTTPException(
            status_code=404,
            detail=f"Chapter with ID {chapter_id} not found"
        )
    
    # Delete the chapter
    success = db.delete_chapter(chapter_id)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to delete chapter"
        )
    
    return {"message": f"Chapter {chapter_id} deleted successfully"}


@router.put("/{chapter_id}")
async def update_chapter(chapter_id: int, update_data: Chapter):
    """
    Update a chapter by ID (legacy endpoint).
    
    This endpoint provides backward compatibility for the existing
    single-novel workflow.
    
    Args:
        chapter_id: The chapter ID to update.
        update_data: Fields to update.
        
    Returns:
        JSON response with updated chapter.
        
    Raises:
        HTTPException: If chapter not found (404).
    """
    db = get_db()
    
    # Check if chapter exists
    chapter = db.get_chapter(chapter_id)
    if chapter is None:
        raise HTTPException(
            status_code=404,
            detail=f"Chapter with ID {chapter_id} not found"
        )
    
    # Build update dictionary
    update_fields = {}
    if update_data.chapter_index is not None:
        update_fields["chapter_index"] = update_data.chapter_index
    if update_data.filename is not None:
        update_fields["filename"] = update_data.filename
    if update_data.title is not None:
        update_fields["title"] = update_data.title
    
    # Perform update
    success = db.update_chapter(chapter_id, **update_fields)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to update chapter"
        )
    
    # Return updated chapter
    updated_chapter = db.get_chapter(chapter_id)
    return updated_chapter


# Also create a router for novel-scoped chapter endpoints
# This will be included in the library router for /api/library/{novel_id}/chapter/{id}
novel_chapter_router = APIRouter(prefix="/api/library", tags=["library-chapters"])


@novel_chapter_router.get("/{novel_id}/chapter/{chapter_id}", response_model=ChapterDetailResponse)
async def get_novel_chapter(novel_id: int, chapter_id: int):
    """
    Get a specific chapter from a novel.
    
    This endpoint provides the new URL pattern for accessing chapters
    within the context of a specific novel.
    
    Args:
        novel_id: The novel ID.
        chapter_id: The chapter ID to retrieve.
        
    Returns:
        ChapterDetailResponse with chapter details.
        
    Raises:
        HTTPException: If novel or chapter not found (404).
    """
    db = get_db()
    
    # Check if novel exists
    novel = db.get_novel(novel_id)
    if novel is None:
        raise HTTPException(
            status_code=404,
            detail=f"Novel with ID {novel_id} not found"
        )
    
    # Get the chapter
    chapter = db.get_chapter(chapter_id)
    
    if chapter is None:
        raise HTTPException(
            status_code=404,
            detail=f"Chapter with ID {chapter_id} not found"
        )
    
    # Verify the chapter belongs to this novel
    if chapter.get("novel_id") != novel_id:
        raise HTTPException(
            status_code=404,
            detail=f"Chapter {chapter_id} does not belong to novel {novel_id}"
        )
    
    return ChapterDetailResponse(
        id=chapter["id"],
        novel_id=chapter.get("novel_id"),
        chapter_index=chapter["chapter_index"],
        filename=chapter["filename"],
        title=chapter.get("title"),
        content=chapter.get("content"),
        created_at=chapter.get("created_at")
    )


@novel_chapter_router.delete("/{novel_id}/chapter/{chapter_id}")
async def delete_novel_chapter(novel_id: int, chapter_id: int):
    """
    Delete a specific chapter from a novel.
    
    This endpoint provides the new URL pattern for deleting chapters
    within the context of a specific novel.
    
    Args:
        novel_id: The novel ID.
        chapter_id: The chapter ID to delete.
        
    Returns:
        JSON response with success message.
        
    Raises:
        HTTPException: If novel or chapter not found (404).
    """
    db = get_db()
    
    # Check if novel exists
    novel = db.get_novel(novel_id)
    if novel is None:
        raise HTTPException(
            status_code=404,
            detail=f"Novel with ID {novel_id} not found"
        )
    
    # Check if chapter exists
    chapter = db.get_chapter(chapter_id)
    if chapter is None:
        raise HTTPException(
            status_code=404,
            detail=f"Chapter with ID {chapter_id} not found"
        )
    
    # Verify the chapter belongs to this novel
    if chapter.get("novel_id") != novel_id:
        raise HTTPException(
            status_code=404,
            detail=f"Chapter {chapter_id} does not belong to novel {novel_id}"
        )
    
    # Delete the chapter
    success = db.delete_chapter(chapter_id)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to delete chapter"
        )
    
    return {"message": f"Chapter {chapter_id} deleted successfully"}