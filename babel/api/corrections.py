"""
Block Correction API Endpoints

Provides REST API for:
- Manual block corrections
- Correction statistics
- Correction data export for ML training
"""

import json
import csv
from io import StringIO
from pathlib import Path
from typing import Optional, Literal
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response

from babel.data.db import DatabaseManager
from babel.api.models import (
    BlockCorrection,
    CorrectionResponse,
    CorrectionStats,
    CorrectionExport
)


router = APIRouter(prefix="/api", tags=["corrections"])


def get_db() -> DatabaseManager:
    """Dependency for database access."""
    return DatabaseManager()


@router.put("/chapters/{chapter_id}/blocks/{block_index}", response_model=CorrectionResponse)
async def update_block(
    chapter_id: str,
    block_index: int,
    correction: BlockCorrection,
    db: DatabaseManager = Depends(get_db)
) -> CorrectionResponse:
    """
    Update a block with manual correction.
    
    Steps:
    1. Load current JSON file
    2. Extract original block values
    3. Apply correction
    4. Save to JSON atomically
    5. Log correction to database
    
    Returns the updated block and correction ID.
    """
    
    # Validate block index
    if block_index < 0:
        raise HTTPException(400, "Block index must be non-negative")
    
    # Load chapter JSON
    json_path = Path(f"data/json/{chapter_id}.json")
    if not json_path.exists():
        raise HTTPException(404, f"Chapter {chapter_id} not found")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            chapter_data = json.load(f)
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"Invalid JSON in chapter file: {str(e)}")
    
    # Validate block index range
    blocks = chapter_data.get('blocks', [])
    if block_index >= len(blocks):
        raise HTTPException(400, f"Block index {block_index} out of range (max: {len(blocks)-1})")
    
    # Get original block
    original_block = blocks[block_index]
    
    # Extract context (surrounding blocks for ML training)
    context = {
        "preceding": blocks[block_index-1] if block_index > 0 else None,
        "following": blocks[block_index+1] if block_index < len(blocks)-1 else None
    }
    
    # Log correction to database
    correction_id = db.log_correction(
        chapter_id=chapter_id,
        block_index=block_index,
        original_type=original_block.get('type', 'UNKNOWN'),
        original_speaker=original_block.get('speaker'),
        original_text=original_block.get('text', ''),
        corrected_type=correction.type,
        corrected_speaker=correction.speaker,
        corrected_text=correction.text,
        correction_reason=correction.correction_reason,
        context_json=json.dumps(context)
    )
    
    # Update block in memory
    updated_block = {
        "type": correction.type.lower(),  # Normalize to lowercase for consistency
        "text": correction.text,
        "corrected": True,  # Mark as manually corrected
        "correction_id": correction_id
    }
    
    if correction.speaker:
        updated_block["speaker"] = correction.speaker
    
    # Preserve other fields (emotion, metadata, etc.)
    for key in ["emotion", "metadata", "tone"]:
        if key in original_block:
            updated_block[key] = original_block[key]
    
    # Update blocks array
    blocks[block_index] = updated_block
    chapter_data['blocks'] = blocks
    
    # Save updated JSON atomically (write to temp, then rename)
    temp_path = json_path.with_suffix('.json.tmp')
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(chapter_data, f, indent=2, ensure_ascii=False)
        
        # Atomic rename
        temp_path.replace(json_path)
        
    except Exception as e:
        # Clean up temp file on error
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(500, f"Failed to save correction: {str(e)}")
    
    return CorrectionResponse(
        success=True,
        correction_id=correction_id,
        updated_block=updated_block,
        message=f"Block {block_index} corrected successfully"
    )


@router.get("/corrections/stats", response_model=CorrectionStats)
async def get_correction_stats(
    chapter_id: Optional[str] = None,
    db: DatabaseManager = Depends(get_db)
) -> CorrectionStats:
    """
    Get correction statistics.
    
    Query params:
    - chapter_id: Filter by specific chapter (optional)
    
    Returns:
    - Total corrections
    - Corrections by type transition (e.g., "DIALOGUE->THOUGHT")
    - Recent corrections list
    """
    
    stats = db.get_correction_stats(chapter_id)
    
    return CorrectionStats(
        total_corrections=stats["total_corrections"],
        by_type=stats["by_type"],
        recent_corrections=stats["recent_corrections"]
    )


@router.get("/corrections/export")
async def export_corrections(
    format: Literal["json", "csv", "jsonl"] = "json",
    db: DatabaseManager = Depends(get_db)
):
    """
    Export corrections for ML training.
    
    Formats:
    - json: Standard JSON array
    - csv: Comma-separated values
    - jsonl: JSON Lines (one object per line)
    
    Returns file download with appropriate content type.
    """
    
    corrections = db.get_all_corrections()
    
    if not corrections:
        raise HTTPException(404, "No corrections found")
    
    if format == "json":
        content = json.dumps(corrections, indent=2, ensure_ascii=False)
        media_type = "application/json"
        filename = "corrections.json"
        
    elif format == "csv":
        output = StringIO()
        if corrections:
            fieldnames = corrections[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(corrections)
        
        content = output.getvalue()
        media_type = "text/csv"
        filename = "corrections.csv"
        
    elif format == "jsonl":
        lines = [json.dumps(row, ensure_ascii=False) for row in corrections]
        content = "\n".join(lines)
        media_type = "application/x-jsonlines"
        filename = "corrections.jsonl"
    
    else:
        raise HTTPException(400, f"Unsupported format: {format}")
    
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )
