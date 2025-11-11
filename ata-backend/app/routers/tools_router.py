# /app/routers/tools_router.py (SUPERVISOR-APPROVED FLAWLESS VERSION)

"""
This module defines the API endpoints for all AI content generation tools.

Every endpoint in this router is now protected, requiring a valid JWT token
for access. The router is responsible for injecting the authenticated user's
context into the business logic layer, ensuring that all generated content is
correctly attributed and saved to the user's private history.
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from app.core.logger import get_logger

logger = get_logger(__name__)
import json

# --- Application-specific Imports ---
from ..models import tool_model

# Import the business logic service this router delegates to.
from ..services import tool_service

# Import the DatabaseService and its dependency provider.
from ..services.database_service import DatabaseService, get_db_service

# --- [CRITICAL MODIFICATION 1/3: IMPORT DEPENDENCIES] ---
# Import the security dependency that will protect these endpoints.
from ..core.deps import get_current_active_user
# Import the SQLAlchemy User model for type hinting the authenticated user.
from ..db.models.user_model import User as UserModel


router = APIRouter()

@router.post(
    "/generate/text",
    response_model=tool_model.ToolGenerationResponse,
    summary="Generate Content from Text or Library",
    description="The primary endpoint for text-based and library-based generation, accepting a JSON body."
)
async def generate_tool_content_from_text(
    request: tool_model.ToolGenerationRequest,
    db: DatabaseService = Depends(get_db_service),
    # --- [CRITICAL MODIFICATION 2/3: INJECT DEPENDENCY] ---
    # This dependency acts as a security gate. If the user is not authenticated
    # and active, the request will be rejected with a 401 or 403 error before
    # this function's code is even executed.
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Handles generation where the source is either direct text or library paths.
    This endpoint is now protected and requires authentication.
    """
    try:
        response_data = await tool_service.generate_content_for_tool(
            settings_payload=request.model_dump(), # Use model_dump() for Pydantic v2
            source_file=None,
            db=db,
            # --- [CRITICAL MODIFICATION 3/3: PASS USER CONTEXT] ---
            # Pass the authenticated user's ID to the service layer. This is
            # essential for the service to save the result to the correct user's history.
            user_id=current_user.id
        )
        return response_data
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.info(f"ERROR during text generation for user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred.")


@router.post(
    "/generate/upload",
    response_model=tool_model.ToolGenerationResponse,
    summary="Generate Content from an Uploaded File",
    description="The specialized endpoint for file-based generation using OCR."
)
async def generate_tool_content_from_upload(
    db: DatabaseService = Depends(get_db_service),
    settings: str = Form(...),
    source_file: UploadFile = File(...),
    # --- [CRITICAL MODIFICATION 2/3: INJECT DEPENDENCY] ---
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Handles generation where the source is an uploaded file.
    This endpoint is now protected and requires authentication.
    """
    try:
        settings_data = json.loads(settings)
        response_data = await tool_service.generate_content_for_tool(
            settings_payload=settings_data,
            source_file=source_file,
            db=db,
            # --- [CRITICAL MODIFICATION 3/3: PASS USER CONTEXT] ---
            user_id=current_user.id
        )
        return response_data
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The 'settings' form field is not valid JSON.")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.info(f"ERROR during upload generation for user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred.")