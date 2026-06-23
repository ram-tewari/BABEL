#!/usr/bin/env python3
"""
BABEL FastAPI Server

Provides REST API endpoints for:
- Character name renaming with automatic JSON updates
- Re-rendering chapters after changes
- Real-time progress updates
"""

import os
import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from rename_character import CharacterRenamer
from babel.render.renderer import ChapterRenderer
from babel.sanitize import ChapterMap
from babel.pipeline import PipelineOrchestrator
from babel.data.db import DatabaseManager
from babel.api import corrections
from babel.api.library import router as library_router
from babel.api.character_graph import router as character_graph_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="BABEL API",
    description="REST API for SYSTEM: BABEL character management and rendering",
    version="1.0.0"
)

# Enable CORS - must be added FIRST before other middleware
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Custom exception handler to ensure CORS headers on errors
from fastapi.exceptions import RequestValidationError

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with CORS headers."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Handle validation errors with CORS headers."""
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc)},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

# Include correction router
app.include_router(corrections.router)

# Include library router
app.include_router(library_router)

# Include character graph + glossary router
app.include_router(character_graph_router)

# Global state for tracking operations
operation_status: Dict[str, Dict] = {}


# ============================================================================
# Request/Response Models
# ============================================================================

class CharacterRenameRequest(BaseModel):
    """Request model for character rename operation."""
    old_name: str
    new_name: str
    case_sensitive: bool = False
    skip_glossary: bool = False
    auto_rerender: bool = True


class CharacterRenameResponse(BaseModel):
    """Response model for character rename operation."""
    success: bool
    operation_id: str
    files_modified: int
    total_replacements: int
    message: str
    errors: List[str] = []


class OperationStatus(BaseModel):
    """Status of a background operation."""
    operation_id: str
    status: str  # "pending", "running", "completed", "failed"
    progress: float  # 0.0 to 1.0
    message: str
    files_modified: int = 0
    total_replacements: int = 0
    errors: List[str] = []


class CharacterListResponse(BaseModel):
    """List of characters found in JSON files."""
    characters: List[Dict[str, Any]]  # {name: str, occurrences: int}
    total: int


class ChapterMetadata(BaseModel):
    """Lightweight chapter metadata for dashboard/TOC."""
    id: int
    chapter_index: int
    filename: str
    title: str
    status: str
    phase: str
    token_count: Optional[int] = None
    error_message: Optional[str] = None
    file_path: Optional[str] = None
    novel_id: Optional[int] = None


class ChapterMetadataListResponse(BaseModel):
    """Response containing list of chapter metadata."""
    chapters: List[ChapterMetadata]
    total: int
    novel_id: Optional[int] = None


# ============================================================================
# Helper Functions
# ============================================================================

def generate_operation_id() -> str:
    """Generate unique operation ID."""
    import uuid
    return str(uuid.uuid4())[:8]


async def rename_character_task(
    operation_id: str,
    old_name: str,
    new_name: str,
    case_sensitive: bool,
    skip_glossary: bool,
    auto_rerender: bool
):
    """Background task for character renaming."""
    try:
        operation_status[operation_id] = {
            "status": "running",
            "progress": 0.0,
            "message": "Starting character rename...",
            "files_modified": 0,
            "total_replacements": 0,
            "errors": []
        }
        
        # Initialize renamer
        renamer = CharacterRenamer(old_name, new_name, case_sensitive)
        
        # Get JSON files
        json_dir = Path("data/json")
        json_files = sorted(json_dir.glob("*.json"))
        total_files = len(json_files)
        
        if total_files == 0:
            operation_status[operation_id]["status"] = "failed"
            operation_status[operation_id]["message"] = "No JSON files found"
            return
        
        # Process files
        files_modified = 0
        total_replacements = 0
        errors = []
        
        for i, json_path in enumerate(json_files):
            try:
                modified_data, count = renamer.process_json_file(json_path)
                
                if count > 0:
                    files_modified += 1
                    total_replacements += count
                    
                    # Write back
                    json_path.write_text(
                        json.dumps(modified_data, indent=2, ensure_ascii=False),
                        encoding='utf-8'
                    )
                
                # Update progress
                progress = (i + 1) / total_files * 0.7  # 70% for JSON processing
                operation_status[operation_id]["progress"] = progress
                operation_status[operation_id]["message"] = f"Processing {json_path.name}..."
                
            except Exception as e:
                error_msg = f"Error processing {json_path.name}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Update glossary
        if not skip_glossary:
            operation_status[operation_id]["message"] = "Updating glossary..."
            operation_status[operation_id]["progress"] = 0.75
            
            try:
                glossary_path = Path("config/glossary.yaml")
                renamer.update_glossary(glossary_path)
            except Exception as e:
                error_msg = f"Error updating glossary: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Re-render if requested
        if auto_rerender and files_modified > 0:
            operation_status[operation_id]["message"] = "Re-rendering chapters..."
            operation_status[operation_id]["progress"] = 0.8
            
            try:
                await rerender_chapters_task(operation_id, start_progress=0.8)
            except Exception as e:
                error_msg = f"Error re-rendering: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Complete
        operation_status[operation_id]["status"] = "completed"
        operation_status[operation_id]["progress"] = 1.0
        operation_status[operation_id]["files_modified"] = files_modified
        operation_status[operation_id]["total_replacements"] = total_replacements
        operation_status[operation_id]["errors"] = errors
        operation_status[operation_id]["message"] = (
            f"Completed! {files_modified} files modified, "
            f"{total_replacements} replacements made"
        )
        
    except Exception as e:
        logger.error(f"Operation {operation_id} failed: {e}")
        operation_status[operation_id]["status"] = "failed"
        operation_status[operation_id]["message"] = f"Operation failed: {str(e)}"


async def rerender_chapters_task(operation_id: str, start_progress: float = 0.0):
    """Background task for re-rendering chapters."""
    try:
        renderer = ChapterRenderer()
        
        # Load chapter map
        chapter_map_path = Path("config/chapter_map.json")
        chapter_map = None
        if chapter_map_path.exists():
            chapter_map = ChapterMap.model_validate_json(
                chapter_map_path.read_text(encoding='utf-8')
            )
        
        # Get JSON files
        json_dir = Path("data/json")
        output_dir = Path("data/render")
        json_files = sorted(json_dir.glob("*.json"))
        total_files = len(json_files)
        
        # Render each file
        for i, json_path in enumerate(json_files):
            try:
                output_path = output_dir / f"{json_path.stem}.html"
                renderer.render_chapter(json_path, output_path, chapter_map)
                
                # Update progress (20% of total progress allocated for rendering)
                progress = start_progress + ((i + 1) / total_files * 0.2)
                operation_status[operation_id]["progress"] = progress
                operation_status[operation_id]["message"] = f"Rendering {json_path.name}..."
                
            except Exception as e:
                logger.error(f"Error rendering {json_path.name}: {e}")
        
    except Exception as e:
        logger.error(f"Re-rendering failed: {e}")
        raise


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "name": "BABEL API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "rename_character": "/api/characters/rename",
            "operation_status": "/api/operations/{operation_id}",
            "list_characters": "/api/characters/list"
        }
    }


@app.post("/api/characters/rename", response_model=CharacterRenameResponse)
async def rename_character(
    request: CharacterRenameRequest,
    background_tasks: BackgroundTasks
):
    """
    Rename a character across all JSON files.
    
    This endpoint:
    1. Validates the request
    2. Starts a background task to rename the character
    3. Optionally re-renders all chapters
    4. Returns an operation ID for tracking progress
    """
    try:
        # Validate names
        if not request.old_name or not request.new_name:
            raise HTTPException(
                status_code=400,
                detail="Both old_name and new_name are required"
            )
        
        if request.old_name == request.new_name:
            raise HTTPException(
                status_code=400,
                detail="Old name and new name cannot be the same"
            )
        
        # Generate operation ID
        operation_id = generate_operation_id()
        
        # Initialize operation status
        operation_status[operation_id] = {
            "status": "pending",
            "progress": 0.0,
            "message": "Operation queued",
            "files_modified": 0,
            "total_replacements": 0,
            "errors": []
        }
        
        # Start background task
        background_tasks.add_task(
            rename_character_task,
            operation_id,
            request.old_name,
            request.new_name,
            request.case_sensitive,
            request.skip_glossary,
            request.auto_rerender
        )
        
        return CharacterRenameResponse(
            success=True,
            operation_id=operation_id,
            files_modified=0,
            total_replacements=0,
            message=f"Character rename operation started. Use operation_id to track progress."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting rename operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/operations/{operation_id}", response_model=OperationStatus)
async def get_operation_status(operation_id: str):
    """
    Get the status of a background operation.
    
    Returns real-time progress updates for character rename operations.
    """
    if operation_id not in operation_status:
        raise HTTPException(
            status_code=404,
            detail=f"Operation {operation_id} not found"
        )
    
    status = operation_status[operation_id]
    
    return OperationStatus(
        operation_id=operation_id,
        status=status["status"],
        progress=status["progress"],
        message=status["message"],
        files_modified=status.get("files_modified", 0),
        total_replacements=status.get("total_replacements", 0),
        errors=status.get("errors", [])
    )


@app.get("/api/characters/list", response_model=CharacterListResponse)
async def list_characters():
    """
    List all unique characters found in JSON files.
    
    Returns a list of characters with their occurrence counts.
    """
    try:
        json_dir = Path("data/json")
        json_files = list(json_dir.glob("*.json"))
        
        if not json_files:
            return CharacterListResponse(characters=[], total=0)
        
        # Collect all speakers
        character_counts: Dict[str, int] = {}
        
        for json_path in json_files:
            try:
                data = json.loads(json_path.read_text(encoding='utf-8'))
                
                for block in data.get('blocks', []):
                    speaker = block.get('speaker')
                    if speaker:
                        character_counts[speaker] = character_counts.get(speaker, 0) + 1
                        
            except Exception as e:
                logger.error(f"Error reading {json_path.name}: {e}")
        
        # Format response
        characters = [
            {"name": name, "occurrences": count}
            for name, count in sorted(
                character_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )
        ]
        
        return CharacterListResponse(
            characters=characters,
            total=len(characters)
        )
        
    except Exception as e:
        logger.error(f"Error listing characters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chapters/rerender")
async def rerender_all_chapters(background_tasks: BackgroundTasks):
    """
    Re-render all chapters with current JSON data.
    
    Useful after manual JSON edits or character renames.
    """
    try:
        operation_id = generate_operation_id()
        
        operation_status[operation_id] = {
            "status": "pending",
            "progress": 0.0,
            "message": "Re-render queued",
            "files_modified": 0,
            "total_replacements": 0,
            "errors": []
        }
        
        background_tasks.add_task(
            rerender_chapters_task,
            operation_id,
            start_progress=0.0
        )
        
        return {
            "success": True,
            "operation_id": operation_id,
            "message": "Re-render operation started"
        }
        
    except Exception as e:
        logger.error(f"Error starting re-render: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chapters/metadata", response_model=ChapterMetadataListResponse)
async def get_chapters_metadata(
    novel_id: Optional[int] = None,
    phase: str = "transform"
):
    """
    Get chapter metadata with optional novel filtering.
    
    Queries the database instead of scanning filesystem for better performance.
    
    Args:
        novel_id: Optional novel ID to filter chapters. If omitted, returns all chapters.
        phase: The processing phase (default: transform)
        
    Returns:
        ChapterMetadataListResponse with chapter metadata.
    """
    try:
        from babel.data.db import DatabaseManager
        db = DatabaseManager()
        
        # Query database instead of scanning filesystem
        if novel_id is not None:
            # Filter by novel_id
            chapters = db.get_chapters_by_novel(novel_id)
            
            # Verify novel exists
            if not chapters and db.get_novel(novel_id) is None:
                # Novel doesn't exist, return empty list
                return ChapterMetadataListResponse(
                    chapters=[],
                    total=0,
                    novel_id=novel_id
                )
        else:
            # Return all chapters including legacy (NULL novel_id)
            chapters = db.get_all_chapters()
        
        # Enrich chapter data with file paths based on novel_id
        metadata_list = []
        for chapter in chapters:
            chapter_novel_id = chapter.get("novel_id")
            
            # Build file path based on novel_id
            if chapter_novel_id is not None:
                base_path = Path(f"data/{phase}/novel_{chapter_novel_id}")
            else:
                base_path = Path(f"data/{phase}")
            
            file_path = str(base_path / chapter["filename"])
            
            metadata_list.append(ChapterMetadata(
                id=chapter["id"],
                chapter_index=chapter["chapter_index"],
                filename=chapter["filename"],
                title=chapter.get("title", f"Chapter {chapter['chapter_index']}"),
                status='complete',
                phase=phase,
                token_count=0,
                file_path=file_path,
                novel_id=chapter_novel_id
            ))
        
        # Sort by chapter index
        metadata_list.sort(key=lambda x: x.chapter_index)
        
        return ChapterMetadataListResponse(
            chapters=metadata_list,
            total=len(metadata_list),
            novel_id=novel_id
        )
        
    except Exception as e:
        logger.error(f"Error fetching chapter metadata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Chapter Content Endpoints
# ============================================================================

from babel.data.models import ChapterBlock

class ChapterResponse(BaseModel):
    """Full chapter content response."""
    id: int
    chapter_index: int
    filename: str
    title: str
    blocks: List[ChapterBlock]
    metadata: Dict[str, Any]
    navigation: Dict[str, Optional[int]]

@app.get("/api/chapters/{chapter_id}")
async def get_chapter(chapter_id: int):
    """
    Get full chapter content by ID.
    
    Queries database for chapter metadata and loads JSON from novel-specific folder.
    """
    try:
        from babel.data.db import DatabaseManager
        db = DatabaseManager()
        
        # Get chapter from database
        chapter = db.get_chapter(chapter_id)
        if not chapter:
            raise HTTPException(status_code=404, detail=f"Chapter {chapter_id} not found")
        
        novel_id = chapter.get("novel_id")
        filename = chapter["filename"]
        
        # Build path to JSON file based on novel_id
        if novel_id is not None:
            # Novel-specific folder: data/json/novel_{id}/filename.json
            json_filename = filename.replace('.xhtml', '.json').replace('.html', '.json')
            if not json_filename.endswith('.json'):
                json_filename += '.json'
            json_path = Path(f"data/json/novel_{novel_id}") / json_filename
        else:
            # Legacy: data/json/filename.json
            json_filename = filename.replace('.xhtml', '.json').replace('.html', '.json')
            if not json_filename.endswith('.json'):
                json_filename += '.json'
            json_path = Path("data/json") / json_filename
        
        if not json_path.exists():
            raise HTTPException(status_code=404, detail=f"Chapter content not found at {json_path}")
        
        # Read content
        data = json.loads(json_path.read_text(encoding='utf-8'))
        
        # Get navigation (prev/next chapters in same novel)
        if novel_id is not None:
            all_chapters = db.get_chapters_by_novel(novel_id)
        else:
            all_chapters = db.get_all_chapters()
        
        # Sort by chapter_index
        all_chapters.sort(key=lambda x: x["chapter_index"])
        
        # Find current position
        current_idx = next((i for i, ch in enumerate(all_chapters) if ch["id"] == chapter_id), None)
        
        navigation = {
            "prev": all_chapters[current_idx - 1]["id"] if current_idx and current_idx > 0 else None,
            "next": all_chapters[current_idx + 1]["id"] if current_idx is not None and current_idx < len(all_chapters) - 1 else None
        }

        return {
            "id": chapter_id,
            "chapter_index": chapter["chapter_index"],
            "filename": filename,
            "title": chapter.get("title", f"Chapter {chapter['chapter_index']}"),
            "blocks": data.get('blocks', []),
            "metadata": data.get('metadata', {}),
            "navigation": navigation,
            "novel_id": novel_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching chapter {chapter_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/ingest")
async def ingest_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    """
    Ingest a new chapter file (TXT or EPUB).
    
    Uploads the file and triggers the processing pipeline.
    """
    try:
        if not file.filename.endswith(('.txt', '.epub')):
             raise HTTPException(status_code=400, detail="Only .txt and .epub files are supported")
        
        # Save file to data/raw
        upload_dir = Path("data/raw")
        upload_dir.mkdir(exist_ok=True)
        file_path = upload_dir / file.filename
        
        with file_path.open("wb") as buffer:
            import shutil
            shutil.copyfileobj(file.file, buffer)
            
        # Generate operation ID
        operation_id = generate_operation_id()
        
        operation_status[operation_id] = {
            "status": "pending",
            "progress": 0.0,
            "message": "Ingestion queued",
            "files_modified": 0,
            "total_replacements": 0,
            "errors": []
        }
        
        # Trigger pipeline in background
        background_tasks.add_task(
            run_ingestion_pipeline,
            operation_id,
            file_path
        )
        
        return {
            "success": True,
            "operation_id": operation_id,
            "message": f"File {file.filename} uploaded and ingestion started."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ingesting file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def run_ingestion_pipeline(operation_id: str, file_path: Path):
    """Background task to run the full pipeline on an ingested file."""
    try:
        operation_status[operation_id]["status"] = "running"
        operation_status[operation_id]["message"] = "Initializing pipeline..."
        operation_status[operation_id]["progress"] = 0.1
        
        # Initialize orchestrator with proper config
        from babel.pipeline.orchestrator import PipelineOrchestrator, PipelineConfig
        
        config = PipelineConfig()
        orchestrator = PipelineOrchestrator(config=config, input_path=file_path)
        
        # Run pipeline (this is synchronous in current implementation, might block but running in threadpool via FastAPI background tasks usually fine for short tasks, strictly speaking should be run_in_executor if heavy CPU)
        # For now, we wrap it simply.
        
        operation_status[operation_id]["message"] = f"Processing {file_path.name}..."
        
        operation_status[operation_id]["message"] = f"Processing {file_path.name}..."
        operation_status[operation_id]["progress"] = 0.3
        
        # Run the pipeline
        result = orchestrator.execute()
        
        operation_status[operation_id]["progress"] = 0.9
        operation_status[operation_id]["message"] = "Finalizing..."
        
        # Success
        operation_status[operation_id]["status"] = "completed"
        operation_status[operation_id]["progress"] = 1.0
        operation_status[operation_id]["message"] = f"Ingestion complete: {result.chapters_processed} chapters processed, {result.chapters_failed} failed"
        operation_status[operation_id]["files_modified"] = result.chapters_processed
        
    except Exception as e:
        logger.error(f"Pipeline failed for {file_path}: {e}")
        operation_status[operation_id]["status"] = "failed"
        operation_status[operation_id]["message"] = str(e)


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting BABEL API Server...")
    logger.info("API Documentation: http://localhost:8000/docs")
    logger.info("Health Check: http://localhost:8000/health")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
