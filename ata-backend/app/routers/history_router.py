
# /ata-backend/app/routers/history_router.py (SUPERVISOR-APPROVED FLAWLESS VERSION)

"""
This module defines the API endpoints for managing a user's AI generation history.

As a protected resource, every endpoint in this router requires a valid JWT
for access. The `get_current_active_user` dependency is injected into each
endpoint to act as a security gate. This router is responsible for receiving
authenticated requests and passing the user's context (their unique ID) down to
the business logic layer in the `history_service`.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response
from app.core.logger import get_logger

logger = get_logger(__name__)

# --- Application-specific Imports ---

# Import the Pydantic models that define the API data contract.
from ..models import history_model

# Import the business logic service that this router will orchestrate.
from ..services import history_service
from ..services.database_service import DatabaseService, get_db_service

# --- [CRITICAL SECURITY MODIFICATION 1/3]: Import Security Dependencies ---
# `get_current_active_user` is the dependency that will protect our endpoints.
# `UserModel` is the SQLAlchemy model, imported for clear type hinting.
from ..core.deps import get_current_active_user
from ..db.models.user_model import User as UserModel

# --- Router Initialization ---
router = APIRouter()


@router.post(
    "",
    response_model=history_model.GenerationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Save a Generation to History"
)
def save_generation_record(
    payload: history_model.GenerationCreate,
    db: DatabaseService = Depends(get_db_service),
    # --- [CRITICAL SECURITY MODIFICATION 2/3]: Inject Dependency ---
    # This dependency injection is the security gate. FastAPI will execute
    # `get_current_active_user` before this function's code runs. If the token
    # is invalid, the request is rejected with a 401 error. If valid, the
    # authenticated user's SQLAlchemy object is placed in `current_user`.
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Persists a new, user-owned generation record to the database.
    This endpoint is now protected and requires authentication.
    """
    try:
        # --- [CRITICAL SECURITY MODIFICATION 3/3]: Pass User Context ---
        # We pass the authenticated user's ID down to the service layer.
        # The service will then "stamp" this ID onto the new record,
        # creating the ownership link.
        return history_service.save_generation(
            db=db,
            user_id=current_user.id,
            tool_id=payload.tool_id.value,
            settings=payload.settings,
            generated_content=payload.generated_content
        )
    except Exception as e:
        logger.info(f"ERROR saving generation record for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while saving the generation record."
        )


@router.get(
    "",
    response_model=history_model.HistoryResponse,
    summary="Get User's Generation History"
)
def get_user_history(
    search: Optional[str] = None,
    tool_id: Optional[str] = None,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user) # <-- Security Gate
):
    """
    Retrieves the AI generation history exclusively for the authenticated user.
    This endpoint is now protected and requires authentication.
    """
    try:
        # Pass the user's ID to the service layer, which will use it to
        # filter the database query, ensuring no data from other users is returned.
        return history_service.get_history(
            db=db, 
            user_id=current_user.id, 
            search=search, 
            tool_id=tool_id
        )
    except Exception as e:
        logger.info(f"ERROR fetching history for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching the generation history."
        )


@router.delete(
    "/{generation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Generation Record from History"
)
def delete_generation_record(
    generation_id: str,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user) # <-- Security Gate
):
    """
    Permanently deletes a single generation record from the user's history.
    This endpoint is now protected and requires authentication.
    """
    # Pass both the record ID and the user's ID to the service layer.
    # The data access layer will only delete the record if the generation_id
    # exists AND its owner_id matches the current_user.id.
    was_deleted = history_service.delete_generation(
        db=db, 
        generation_id=generation_id, 
        user_id=current_user.id
    )
    
    if not was_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation record with ID {generation_id} not found or you do not have permission to delete it.",
        )
    
    # On success, a 204 response has no body.
    return Response(status_code=status.HTTP_204_NO_CONTENT)


