from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class BlockCorrection(BaseModel):
    """Model for submitting a block correction."""
    type: str # 'dialogue', 'thought', etc.
    speaker: Optional[str] = None
    text: str # Content of the block
    correction_reason: Optional[str] = None

class CorrectionResponse(BaseModel):
    """Response returned after a successful correction."""
    success: bool
    correction_id: int
    updated_block: Dict[str, Any]
    message: str

class CorrectionStats(BaseModel):
    """Statistics about corrections."""
    total_corrections: int
    by_type: Dict[str, int]
    recent_corrections: List[Dict[str, Any]]

class CorrectionExport(BaseModel):
    """Model for exported correction data."""
    id: int
    chapter_id: str
    block_index: int
    original_type: str
    original_speaker: Optional[str]
    original_text: str
    corrected_type: str
    corrected_speaker: Optional[str]
    corrected_text: str
    correction_reason: Optional[str]
    created_at: str
