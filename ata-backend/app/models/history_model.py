# /ata-backend/app/models/history_model.py (DEFINITIVELY CORRECTED)

from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, List
from datetime import datetime # <<< ADD THIS IMPORT

# Import ToolId for strong validation, using our established relative import path
from .tool_model import ToolId

class GenerationRecord(BaseModel):
    """
    Defines the data contract for a single generation history record
    when it is retrieved from the database.
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    tool_id: ToolId
    
    # --- [THE FIX IS HERE] ---
    # The data type is now correctly defined as `datetime`.
    # FastAPI will automatically serialize this to an ISO 8601 string in the JSON response.
    created_at: datetime
    # --- [END OF FIX] ---
    
    # The settings_snapshot is a dictionary, parsed from a JSON string by the service.
    settings_snapshot: Dict[str, Any] 
    generated_content: str

class HistoryResponse(BaseModel):
    """
    Defines the data contract for the GET /api/history response.
    """
    model_config = ConfigDict(from_attributes=True)

    results: List[GenerationRecord]
    total: int
    page: int
    hasNextPage: bool

class GenerationCreate(BaseModel):
    """
    Defines the contract for the data required to save a new generation.
    This model is for incoming requests and does not need to be changed.
    """
    model_config = ConfigDict(populate_by_name=True)

    tool_id: ToolId
    settings: Dict[str, Any]
    generated_content: str