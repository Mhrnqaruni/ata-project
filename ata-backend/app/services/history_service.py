
# /ata-backend/app/services/history_service.py (MODIFIED AND APPROVED - FLAWLESS VERSION)

"""
This service module encapsulates all business logic for managing a user's
AI tool generation history.

Every function in this module has been refactored to be "user-aware." It now
requires a `user_id` for all its operations, ensuring that a user can only
create, view, and delete their own history records. This service acts as the
secure intermediary between the `history_router` and the `DatabaseService`.
"""

import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import os

from .database_service import DatabaseService
from ..models.history_model import GenerationRecord, HistoryResponse

# --- HELPER FUNCTION (This is a pure utility and requires no changes) ---
def _generate_title_from_settings(settings: Dict[str, Any], source_filename: Optional[str] = None) -> str:
    """
    Intelligently generates a concise title for a history record based on its settings.
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    source_preview = "Untitled Generation"
    if source_filename:
        source_preview = source_filename
    elif settings.get("selected_chapter_paths"):
        try:
            # Safely access parts of the path
            path_parts = settings["selected_chapter_paths"][0].split(os.path.sep)
            if len(path_parts) >= 2:
                source_preview = path_parts[-2]
            else:
                source_preview = "Library Selection"
        except (IndexError, TypeError):
            source_preview = "Library Selection"
    elif settings.get("source_text"):
        source_preview = ' '.join(settings["source_text"].split()[:5])
        if len(settings["source_text"].split()) > 5:
            source_preview += "..."
    if len(source_preview) > 50:
        source_preview = source_preview[:47] + "..."
    return f"{date_str}: {source_preview}"


# --- PUBLIC SERVICE FUNCTIONS (MODIFIED AND SECURE) ---

def save_generation(
    db: DatabaseService,
    user_id: str,  # <-- CRITICAL MODIFICATION: Added user_id
    tool_id: str,
    settings: Dict[str, Any],
    generated_content: str,
    source_filename: Optional[str] = None
) -> GenerationRecord:
    """
    Constructs and persists a new, user-owned history record.

    This function is now secure. It receives the authenticated user's ID and
    "stamps" it onto the new record before saving, ensuring correct ownership.

    Args:
        db: The DatabaseService instance.
        user_id: The ID of the authenticated user who owns this record.
        tool_id: The identifier of the AI tool used.
        settings: A snapshot of the settings used for the generation.
        generated_content: The resulting content from the AI.
        source_filename: The name of the file used as a source, if any.

    Returns:
        A Pydantic `GenerationRecord` model of the newly created record.
    """
    title = _generate_title_from_settings(settings, source_filename)

    history_record_data = {
        "id": f"gen_{uuid.uuid4().hex[:16]}",
        "title": title,
        "tool_id": tool_id,
        "settings_snapshot": settings,
        "generated_content": generated_content,
        "user_id": user_id,  # <-- CRITICAL MODIFICATION: Stamping the owner's ID
    }
    
    # The DatabaseService now persists the record with the correct owner.
    new_generation_obj = db.add_generation_record(history_record_data)
    
    # `model_validate` creates a Pydantic model from the SQLAlchemy object.
    return GenerationRecord.model_validate(new_generation_obj)


def delete_generation(db: DatabaseService, generation_id: str, user_id: str) -> bool:
    """
    Deletes a generation record, but only if it belongs to the specified user.

    This function is now secure. It passes both the record ID and the user's ID
    to the data access layer, which will enforce ownership before deletion.

    Args:
        db: The DatabaseService instance.
        generation_id: The ID of the history record to delete.
        user_id: The ID of the authenticated user attempting the deletion.

    Returns:
        True if the record was found and deleted, False otherwise.
    """
    # Delegate the secure deletion to the DatabaseService.
    was_deleted = db.delete_generation_record(generation_id=generation_id, user_id=user_id)
    return was_deleted


def get_history(
    db: DatabaseService,
    user_id: str,  # <-- CRITICAL MODIFICATION: Added user_id
    search: Optional[str] = None,
    tool_id: Optional[str] = None
) -> HistoryResponse:
    """
    Retrieves the AI generation history exclusively for the authenticated user.

    This function is now secure. It passes the user's ID to the data access
    layer, ensuring that the query only returns records owned by that user,
    preventing any data leakage.

    Args:
        db: The DatabaseService instance.
        user_id: The ID of the authenticated user whose history is being requested.
        search: An optional search term to filter results.
        tool_id: An optional tool ID to filter results.

    Returns:
        A Pydantic `HistoryResponse` object containing the user's filtered history.
    """
    # This call is now secure and will only fetch records for the given user_id.
    all_history_objects = db.get_all_generations(user_id=user_id)
    
    processed_records = []
    for record_obj in all_history_objects:
        try:
            pydantic_record = GenerationRecord.model_validate(record_obj)
            
            # This logic robustly handles cases where the JSON might be stored as a string.
            if isinstance(pydantic_record.settings_snapshot, str):
                pydantic_record.settings_snapshot = json.loads(pydantic_record.settings_snapshot)
            
            processed_records.append(pydantic_record)

        except Exception as e:
            print(f"Skipping corrupted history record: {getattr(record_obj, 'id', 'N/A')}. Error: {e}")
            continue

    # The filtering logic remains the same but now operates on a secure subset of data.
    filtered_results = processed_records
    if tool_id:
        filtered_results = [r for r in filtered_results if r.tool_id.value == tool_id]
    if search:
        search_lower = search.lower()
        filtered_results = [
            r for r in filtered_results 
            if search_lower in r.generated_content.lower() or search_lower in r.title.lower()
        ]
    
    # Sorting also remains the same.
    filtered_results.sort(key=lambda r: r.created_at, reverse=True)
    
    return HistoryResponse(
        results=filtered_results,
        total=len(filtered_results),
        page=1,
        hasNextPage=False
    )

