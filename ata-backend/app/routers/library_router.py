
# /ata-backend/app/routers/library_router.py (SUPERVISOR-APPROVED FLAWLESS VERSION)

"""
This module defines the API router for accessing the curriculum library.

The endpoints defined here provide access to the application's proprietary
educational content structure. As such, this entire router is protected and
requires a valid user session for access.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends

# --- Application-specific Imports ---

# Import the business logic service that provides the library data.
from ..services import library_service

# --- [CRITICAL MODIFICATION 1/2: IMPORT DEPENDENCIES] ---
# Import the security dependency that will act as our "gatekeeper".
from ..core.deps import get_current_active_user
# Import the SQLAlchemy model for type hinting the authenticated user object.
from ..db.models.user_model import User as UserModel


# --- Router Initialization ---
router = APIRouter()


@router.get(
    "/tree",
    response_model=List[Dict[str, Any]],
    summary="Get Book Library Structure",
    description="Retrieves the complete, hierarchical structure of the book library. This endpoint is protected and requires authentication."
)
def get_library_structure(
    # --- [CRITICAL MODIFICATION 2/2: INJECT DEPENDENCY] ---
    # This `Depends` declaration is the security enforcement mechanism.
    # Before the code inside this function is ever executed, FastAPI will first
    # run our `get_current_active_user` dependency.
    #
    # 1. If the request lacks a valid, unexpired token, the dependency will
    #    immediately raise a 401 Unauthorized error, and the request will be rejected.
    # 2. If the user's account is inactive, it will raise a 403 Forbidden error.
    # 3. Only if the user is fully authenticated and active will FastAPI proceed
    #    to run the code below.
    #
    # The `current_user` variable itself is not used in the function body, but its
    # presence in the signature is what activates the security check.
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Endpoint to retrieve the cached book library tree.

    This is a protected endpoint. It will only return a successful response if the
    request includes a valid `Authorization: Bearer <token>` header for an
    active user.
    """
    # This line is only reached if the user is authenticated.
    # The library content is the same for all users, so we do not need to pass
    # the user_id to the service.
    return library_service.get_library_tree()