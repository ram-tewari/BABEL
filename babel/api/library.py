"""
Library management API endpoints.

Provides REST API endpoints for:- EPUB import and novel creation- Novel CRUD operations- Chapter association queries- Metadata fetching- Cover art upload and processing"""

import io
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Union, List, Dict

from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

from babel.api.metadata import (
    get_metadata_client,
    download_cover_image,
    ensure_covers_directory,
    ExternalMetadata
)
from babel.api.metadata_extraction import extract_metadata
from babel.data.db import DatabaseManager
from babel.data.models import (
    NovelResponse,
    NovelListResponse,
    ChapterListResponse,
    ImportResponse,
    MetadataRequest,
    ErrorResponse,
    NovelUpdate,
    CoverUploadResponse,
    ChapterBlock
)
from babel.pipeline.core import PipelineConfig
from babel.pipeline.orchestrator import PipelineOrchestrator
from pydantic import BaseModel
from babel.sanitize import (
    EPUBExtractor,
    extract_epub_metadata,
    sanitize_chapter_text,
    ChapterMap
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/library", tags=["library"])

# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    """Get or create the database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def ensure_covers_directory() -> Path:
    """Ensure the covers directory exists."""
    covers_dir = Path("data/covers")
    covers_dir.mkdir(parents=True, exist_ok=True)
    return covers_dir


def resize_image(image_data: bytes, target_width: int = 400, target_height: int = 600) -> bytes:
    """
    Resize an image to fit within target dimensions while maintaining aspect ratio.
    
    The image will be resized so that it fits within the target box,
    with the longer side scaled to fit and the shorter side padded if needed.
    
    Args:
        image_data: Raw image bytes.
        target_width: Target width in pixels (default: 400).
        target_height: Target height in pixels (default: 600).
        
    Returns:
        Resized image bytes in JPEG format.
        
    Raises:
        ValueError: If the image data is invalid or not an image.
    """
    try:
        # Open the image from bytes
        img = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if necessary (handles PNG with transparency, etc.)
        if img.mode in ('RGBA', 'P', 'LA'):
            # Create a white background for transparency
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Calculate the scaling factor to fit within target dimensions
        # while maintaining aspect ratio
        img_width, img_height = img.size
        width_ratio = target_width / img_width
        height_ratio = target_height / img_height
        ratio = min(width_ratio, height_ratio)
        
        # Calculate new dimensions
        new_width = int(img_width * ratio)
        new_height = int(img_height * ratio)
        
        # Resize the image using LANCZOS for high-quality downsampling
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Create a new image with the target dimensions and white background
        # This ensures all covers have the same dimensions
        result = Image.new('RGB', (target_width, target_height), (255, 255, 255))
        
        # Paste the resized image in the center
        x_offset = (target_width - new_width) // 2
        y_offset = (target_height - new_height) // 2
        result.paste(img, (x_offset, y_offset))
        
        # Save to bytes as JPEG
        output = io.BytesIO()
        result.save(output, format='JPEG', quality=95, optimize=True)
        return output.getvalue()
        
    except Exception as e:
        logger.error(f"Error resizing image: {e}")
        raise ValueError(f"Invalid image data: {str(e)}")


@router.post("/import", response_model=ImportResponse)
async def import_epub(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    """
    Import an EPUB file and create a novel entry.
    
    This endpoint:
    1. Saves the uploaded EPUB to a temporary location
    2. Extracts metadata (title, author) from the EPUB
    3. Creates a Novel_Entry in the database
    4. Extracts chapters and associates them with the novel
    5. Returns the novel_id and import status
    
    On failure, all database changes are rolled back.
    
    Args:
        file: The uploaded EPUB file.
        
    Returns:
        ImportResponse with novel_id, title, chapters_extracted, and status.
        
    Raises:
        HTTPException: If import fails with descriptive error message.
    """
    # Validate file type
    if not file.filename.lower().endswith('.epub'):
        raise HTTPException(
            status_code=400,
            detail="Only EPUB files (.epub) are supported for import"
        )
    
    # Create temporary file for the upload
    with tempfile.NamedTemporaryFile(
        suffix='.epub',
        delete=False
    ) as tmp_file:
        tmp_path = Path(tmp_file.name)
        novel_id = None
        
        try:
            # Write uploaded content to temp file
            content = await file.read()
            tmp_file.write(content)
            tmp_file.flush()
            
            # Extract metadata using the new extraction strategy
            # Prioritizes EPUB internal metadata, falls back to filename
            metadata = extract_metadata(tmp_path, file.filename)
            title = metadata['title']
            author = metadata.get('author')
            
            if not title or not title.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Could not extract novel title from file"
                )
            
            # Get database manager
            db = get_db()
            
            # Create novel entry with transaction safety
            # Wrap novel creation and directory initialization in try/except
            try:
                # Create the novel in database
                novel_id = db.create_novel(
                    title=title.strip(),
                    author=author,
                    status="active"
                )
                logger.info(f"Created novel entry with ID: {novel_id}")
                
                # Initialize pipeline orchestrator with novel_id
                config = PipelineConfig(output_dir=Path("data"))
                orchestrator = PipelineOrchestrator(
                    config=config,
                    input_path=tmp_path,
                    novel_id=novel_id
                )
                
                # Create novel-specific directories
                # If this fails, we need to rollback the novel entry
                try:
                    orchestrator.initialize_directories()
                except OSError as e:
                    logger.error(f"Failed to create directories for novel {novel_id}: {e}")
                    # Rollback: delete novel entry if directory creation fails
                    db.delete_novel(novel_id)
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to create output directories: {str(e)}"
                    )
                
                logger.info(f"Initialized directories for novel {novel_id}")
                
            except Exception as e:
                logger.error(f"Failed to initialize novel: {e}")
                # Rollback is handled above for directory creation failures
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create novel entry: {str(e)}"
                )
            
            # Extract and create chapters
            chapters_extracted = 0
            try:
                epub_metadata = extract_epub_metadata(tmp_path)
                for chapter_data in epub_metadata.chapters:
                    sanitized_content = sanitize_chapter_text(
                        chapter_data.get("content", "")
                    )
                    
                    if sanitized_content.strip():
                        # Create chapter in database with novel_id
                        db.create_chapter(
                            novel_id=novel_id,
                            chapter_index=chapter_data.get("chapter_index", chapters_extracted + 1),
                            filename=chapter_data.get("filename", f"chapter_{chapters_extracted + 1}.xhtml"),
                            title=chapter_data.get("title", f"Chapter {chapters_extracted + 1}")
                        )
                        chapters_extracted += 1
                
                # If no chapters were extracted, create at least one placeholder
                if chapters_extracted == 0:
                    db.create_chapter(
                        novel_id=novel_id,
                        chapter_index=1,
                        filename="placeholder.txt",
                        title="Chapter 1"
                    )
                    chapters_extracted = 1
                    
            except Exception as e:
                logger.error(f"Error extracting chapters: {e}")
                # Don't fail the entire import if chapter extraction fails
                # The novel was created, chapters can be added later
                chapters_extracted = 0
            
            # Return success with novel_id for tracking
            return ImportResponse(
                novel_id=novel_id,
                title=title.strip(),
                chapters_extracted=chapters_extracted,
                status="success"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during import: {e}")
            # Cleanup: delete novel entry if it was created
            if novel_id is not None:
                try:
                    db.delete_novel(novel_id)
                except Exception:
                    pass
            raise HTTPException(
                status_code=500,
                detail=f"Import failed: {str(e)}"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during import: {e}")
            # Cleanup: delete novel entry if it was created
            if novel_id is not None:
                try:
                    db.delete_novel(novel_id)
                except Exception:
                    pass
            raise HTTPException(
                status_code=500,
                detail=f"Import failed: {str(e)}"
            )
        finally:
            # Clean up temporary file
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass


@router.get("/", response_model=NovelListResponse)
async def list_novels(limit: int = 100, offset: int = 0):
    """
    List all novels in the library.
    
    Returns novels sorted by updated_at descending (newest first).
    
    Args:
        limit: Maximum number of novels to return (default: 100).
        offset: Number of novels to skip (default: 0).
        
    Returns:
        NovelListResponse with list of novels and total count.
    """
    db = get_db()
    
    # Use efficient query with COUNT aggregation to avoid N+1 queries
    novels = db.list_novels_with_chapter_count(limit=limit, offset=offset)
    
    # Ensure tags is a list, not None
    for novel in novels:
        if novel.get("tags") is None:
            novel["tags"] = []
    
    # Get total count
    total = db.count_novels()
    
    return NovelListResponse(
        novels=novels,
        total=total
    )


@router.get("/{novel_id}", response_model=NovelResponse)
async def get_novel(novel_id: int):
    """
    Get a single novel by ID.
    
    Args:
        novel_id: The novel ID to retrieve.
        
    Returns:
        NovelResponse with novel details including chapter count.
        
    Raises:
        HTTPException: If novel not found (404).
    """
    db = get_db()
    
    # Use efficient query with COUNT aggregation
    novel = db.get_novel_with_chapter_count(novel_id)
    
    if novel is None:
        raise HTTPException(
            status_code=404,
            detail=f"Novel with ID {novel_id} not found"
        )
    
    # Parse tags from JSON string if stored as string
    tags = novel.get("tags", [])
    if tags is None:
        tags = []
    elif isinstance(tags, str):
        import json
        try:
            tags = json.loads(tags)
        except (json.JSONDecodeError, TypeError):
            tags = []
    
    return NovelResponse(
        id=novel["id"],
        title=novel["title"],
        author=novel.get("author"),
        cover_url=novel.get("cover_url"),
        synopsis=novel.get("synopsis"),
        tags=tags,
        status=novel["status"],
        chapter_count=novel.get("chapter_count", 0),
        created_at=novel.get("created_at"),
        updated_at=novel.get("updated_at")
    )


@router.delete("/{novel_id}")
async def delete_novel(novel_id: int):
    """
    Delete a novel and cascade delete all associated chapters.
    
    Args:
        novel_id: The novel ID to delete.
        
    Returns:
        JSON response with success message.
        
    Raises:
        HTTPException: If novel not found (404).
    """
    db = get_db()
    
    # Check if novel exists
    novel = db.get_novel(novel_id)
    if novel is None:
        raise HTTPException(
            status_code=404,
            detail=f"Novel with ID {novel_id} not found"
        )
    
    # Delete the novel (cascade will delete chapters)
    success = db.delete_novel(novel_id)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to delete novel"
        )
    
    return {"message": f"Novel {novel_id} deleted successfully"}


@router.get("/{novel_id}/chapters", response_model=ChapterListResponse)
async def get_novel_chapters(novel_id: int):
    """
    Get all chapters for a novel.
    
    Args:
        novel_id: The novel ID.
        
    Returns:
        ChapterListResponse with list of chapters.
        
    Raises:
        HTTPException: If novel not found (404).
    """
    db = get_db()
    
    # Check if novel exists
    novel = db.get_novel(novel_id)
    if novel is None:
        raise HTTPException(
            status_code=404,
            detail=f"Novel with ID {novel_id} not found"
        )
    
    chapters = db.get_chapters_by_novel(novel_id)
    
    return ChapterListResponse(
        chapters=chapters,
        total=len(chapters),
        novel_id=novel_id
    )


@router.get("/{novel_id}/status")
async def get_novel_status(novel_id: int):
    """
    Get the processing status for a novel.
    
    Returns pipeline_state for the novel across all phases.
    
    Args:
        novel_id: The novel ID.
        
    Returns:
        JSON response with pipeline status for each phase.
        
    Raises:
        HTTPException: If novel not found (404).
    """
    db = get_db()
    
    # Check if novel exists
    novel = db.get_novel(novel_id)
    if novel is None:
        raise HTTPException(
            status_code=404,
            detail=f"Novel with ID {novel_id} not found"
        )
    
    # Get pipeline state for all phases
    states = db.get_pipeline_states_by_novel(novel_id)
    
    # Compute overall status from phase states
    overall_status = "not_started"
    if states:
        if all(s["status"] == "completed" for s in states):
            overall_status = "completed"
        elif any(s["status"] == "failed" for s in states):
            overall_status = "failed"
        elif any(s["status"] == "running" for s in states):
            overall_status = "running"
        else:
            overall_status = "in_progress"
    
    return {
        "novel_id": novel_id,
        "title": novel["title"],
        "overall_status": overall_status,
        "phases": states
    }


@router.post("/{novel_id}/metadata")
async def fetch_metadata(novel_id: int, request: MetadataRequest):
    """
    Fetch metadata from external source (NovelUpdates or RoyalRoad).
    
    This endpoint:
    1. Queries the external API (NovelUpdates or RoyalRoad) with the novel title
    2. Downloads cover image to data/covers/{novel_id}.jpg
    3. Updates novel entry with cover_url, synopsis, tags, status
    
    Args:
        novel_id: The novel ID to update.
        request: MetadataRequest with source and optional search_query.
        
    Returns:
        JSON response with updated novel metadata.
        
    Raises:
        HTTPException: If novel not found or metadata fetch fails.
    """
    db = get_db()
    
    # Check if novel exists
    novel = db.get_novel(novel_id)
    if novel is None:
        raise HTTPException(
            status_code=404,
            detail=f"Novel with ID {novel_id} not found"
        )
    
    search_query = request.search_query or novel["title"]
    
    logger.info(f"Metadata fetch requested for novel {novel_id} from {request.source}")
    logger.info(f"Search query: {search_query}")
    
    try:
        # Get the appropriate metadata client
        client = get_metadata_client(request.source)
        
        # Search for the novel
        metadata = await client.search(search_query)
        
        if metadata is None:
            raise HTTPException(
                status_code=404,
                detail=f"Novel not found on {request.source} with query: {search_query}"
            )
        
        # Build update dictionary
        update_fields = {}
        
        if metadata.title:
            update_fields["title"] = metadata.title
        if metadata.author:
            update_fields["author"] = metadata.author
        if metadata.synopsis:
            update_fields["synopsis"] = metadata.synopsis
        if metadata.tags:
            update_fields["tags"] = json.dumps(metadata.tags)
        if metadata.status:
            update_fields["status"] = metadata.status
        
        # Download cover image if available
        cover_url = None
        if metadata.cover_url:
            covers_dir = ensure_covers_directory()
            cover_path = covers_dir / f"{novel_id}.jpg"
            
            success = await download_cover_image(metadata.cover_url, cover_path)
            if success:
                cover_url = f"/data/covers/{novel_id}.jpg"
                update_fields["cover_url"] = cover_url
            else:
                # If download failed, use the remote URL
                cover_url = metadata.cover_url
                update_fields["cover_url"] = cover_url
                logger.warning(f"Cover download failed, using remote URL: {metadata.cover_url}")
        
        # Update the novel entry
        if update_fields:
            db.update_novel(novel_id, **update_fields)
        
        # Get updated novel
        updated_novel = db.get_novel(novel_id)
        
        # Parse tags for response
        tags = updated_novel.get("tags", [])
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                tags = []
        
        return {
            "message": "Metadata fetched successfully",
            "source": request.source,
            "metadata": {
                "title": updated_novel["title"],
                "author": updated_novel.get("author"),
                "cover_url": updated_novel.get("cover_url"),
                "synopsis": updated_novel.get("synopsis"),
                "tags": tags,
                "status": updated_novel["status"],
            }
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching metadata: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch metadata: {str(e)}"
        )


@router.post("/{novel_id}/cover", response_model=CoverUploadResponse)
async def upload_cover(novel_id: int, file: UploadFile = File(...)):
    """
    Upload custom cover art for a novel.
    
    Validates file type (jpg, png, webp), resizes to 400x600px,
    and saves to data/covers/{novel_id}.jpg.
    
    Args:
        novel_id: The novel ID.
        file: The uploaded image file.
        
    Returns:
        CoverUploadResponse with cover URL.
        
    Raises:
        HTTPException: If novel not found or upload fails (400).
    """
    db = get_db()
    
    # Check if novel exists
    novel = db.get_novel(novel_id)
    if novel is None:
        raise HTTPException(
            status_code=404,
            detail=f"Novel with ID {novel_id} not found"
        )
    
    # Validate file type
    allowed_types = {'jpg', 'jpeg', 'png', 'webp'}
    file_ext = file.filename.lower().split('.')[-1] if '.' in file.filename else ''
    
    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
        )
    
    # Ensure covers directory exists
    covers_dir = ensure_covers_directory()
    
    # Save cover file
    cover_filename = f"{novel_id}.jpg"
    cover_path = covers_dir / cover_filename
    
    try:
        content = await file.read()
        
        # Resize the image to 400x600px maintaining aspect ratio
        resized_image = resize_image(content, target_width=400, target_height=600)
        
        # Save the resized image
        cover_path.write_bytes(resized_image)
        
        # Update novel entry
        cover_url = f"/data/covers/{cover_filename}"
        db.update_novel(novel_id, cover_url=cover_url)
        
        return CoverUploadResponse(
            novel_id=novel_id,
            cover_url=cover_url,
            message="Cover uploaded successfully"
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error uploading cover: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload cover: {str(e)}"
        )


@router.put("/{novel_id}")
async def update_novel(novel_id: int, update_data: NovelUpdate):
    """
    Update novel metadata.
    
    Args:
        novel_id: The novel ID.
        update_data: Fields to update (title, author, cover_url, synopsis, tags, status).
        
    Returns:
        JSON response with updated novel.
        
    Raises:
        HTTPException: If novel not found or update fails.
    """
    db = get_db()
    
    # Check if novel exists
    novel = db.get_novel(novel_id)
    if novel is None:
        raise HTTPException(
            status_code=404,
            detail=f"Novel with ID {novel_id} not found"
        )
    
    # Build update dictionary from model
    update_fields = update_data.model_dump(exclude_unset=True)
    
    # Perform update
    success = db.update_novel(novel_id, **update_fields)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to update novel"
        )
    
    # Return updated novel
    updated_novel = db.get_novel(novel_id)
    return updated_novel


# Novel-scoped chapter endpoints (new URL pattern)
# These complement the legacy /api/chapter/{id} endpoints


class ChapterDetailResponse(BaseModel):
    """Response model for chapter detail endpoint."""
    
    id: int
    novel_id: Optional[int] = None
    chapter_index: int
    filename: str
    title: Optional[str] = None
    content: Optional[str] = None
    blocks: List[ChapterBlock] = []
    navigation: Optional[Dict[str, Optional[int]]] = None
    created_at: Optional[str] = None


@router.get("/{novel_id}/chapter/{chapter_id}", response_model=ChapterDetailResponse)
async def get_novel_chapter(novel_id: int, chapter_id: int):
    """
    Get a specific chapter from a novel.
    
    This endpoint provides the new URL pattern for accessing chapters
    within the context of a specific novel. Reads chapter content from JSON files.
    
    Args:
        novel_id: The novel ID.
        chapter_id: The chapter ID to retrieve.
        
    Returns:
        ChapterDetailResponse with chapter details.
        
    Raises:
        HTTPException: If novel or chapter not found (404).
    """
    import json
    from pathlib import Path
    
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

    # Load chapter content from JSON file
    blocks = []
    # Try novel-specific directory first, then fall back to legacy directory
    json_path = Path(f"data/json/novel_{novel_id}") / chapter["filename"]
    if not json_path.exists():
        json_path = Path("data/json") / chapter["filename"]
    
    if json_path.exists():
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                chapter_data = json.load(f)
                blocks = chapter_data.get("blocks", [])
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load chapter JSON {json_path}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to load chapter content"
            )
    else:
        logger.warning(f"Chapter JSON file not found: {json_path}")
        raise HTTPException(
            status_code=404,
            detail=f"Chapter content file not found"
        )
            
    # Calculate navigation (prev/next chapter IDs)
    # Fetch all chapters to determine order
    all_chapters = db.get_chapters_by_novel(novel_id)
    prev_chapter_id = None
    next_chapter_id = None
    
    for i, ch in enumerate(all_chapters):
        if ch["id"] == chapter_id:
            if i > 0:
                prev_chapter_id = all_chapters[i-1]["id"]
            if i < len(all_chapters) - 1:
                next_chapter_id = all_chapters[i+1]["id"]
            break
            
    navigation = {
        "prev": prev_chapter_id,
        "next": next_chapter_id
    }
    
    return ChapterDetailResponse(
        id=chapter["id"],
        novel_id=chapter.get("novel_id"),
        chapter_index=chapter["chapter_index"],
        filename=chapter["filename"],
        title=chapter.get("title"),
        blocks=blocks,
        navigation=navigation,
        created_at=chapter.get("created_at")
    )


@router.delete("/{novel_id}/chapter/{chapter_id}")
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