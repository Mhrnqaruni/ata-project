
# /ata-backend/app/routers/dashboard_router.py (MODIFIED AND SUPERVISOR-APPROVED - FLAWLESS VERSION)

"""
This module defines the API endpoints for the main dashboard.

It provides a single, now-protected endpoint (`/summary`) that retrieves high-level
statistics (e.g., class and student counts) for the authenticated user's
homepage dashboard view.
"""

# --- Core FastAPI Imports ---
from fastapi import APIRouter, Depends

# --- Application-specific Imports ---

# Import the business logic service that this router will use.
from app.services import dashboard_service

# Import the database service dependency provider.
from app.services.database_service import DatabaseService, get_db_service

# Import the Pydantic model to define the API's response shape.
from app.models.dashboard_model import DashboardSummary

# --- [CRITICAL SECURITY MODIFICATION 1/3: Import Security Dependencies] ---
# Import the main security dependency that enforces user authentication.
from app.core.deps import get_current_active_user
# Import the SQLAlchemy User model for type hinting the authenticated user object.
from app.db.models.user_model import User as UserModel


# --- APIRouter Instance ---
router = APIRouter()


# --- Endpoint Definition (Now Protected) ---
@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Get Authenticated User's Dashboard Summary",
    description="Retrieves high-level statistics (class count, student count) for the currently authenticated user's main dashboard view."
)
def get_dashboard_summary(
    # FastAPI's dependency injection provides a database session.
    db: DatabaseService = Depends(get_db_service),
    # --- [CRITICAL SECURITY MODIFICATION 2/3: Inject User Dependency] ---
    # This dependency acts as a security gate. FastAPI will run `get_current_active_user`
    # before executing this function. If the user is not authenticated or not active,
    # the request will be rejected with a 401/403 error automatically.
    # On success, the authenticated user's SQLAlchemy object is injected into the
    # `current_user` variable.
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    This endpoint is now a protected "thin" router layer. Its job is to:
    1. Receive an incoming HTTP request.
    2. Ensure the user is authenticated via the `get_current_active_user` dependency.
    3. Delegate the actual work to the "thick" business logic service, now
       passing the authenticated user's context (their ID).
    4. Return the user-specific result.
    """
    
    # --- [CRITICAL SECURITY MODIFICATION 3/3: Pass User Context to Service] ---
    # Delegate immediately to the service layer, passing the authenticated user's
    # unique ID. This instructs the service to calculate the summary based only
    # on the data owned by this specific user.
    return dashboard_service.get_summary_data(db=db, user_id=current_user.id)