# /ata-backend/app/core/deps.py

"""
This module centralizes all common FastAPI dependencies for the application.

The primary dependency, `get_current_user`, is the gatekeeper for our entire
protected API. It is responsible for:
1. Extracting the JWT Bearer token from the request's Authorization header.
2. Decoding and validating the token using the functions in `core.security`.
3. Fetching the corresponding user from the database via the DatabaseService.
4. Raising a 401 Unauthorized HTTPException if any step fails.
5. Returning the full, validated User database object on success.

This ensures a consistent, secure, and efficient method for protecting API endpoints.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core import security
from app.services.database_service import DatabaseService, get_db_service
from app.db.models.user_model import User as UserModel

# --- Dependency Configuration ---

# This creates an instance of the OAuth2 password flow.
# The `tokenUrl` points to the exact API endpoint that the client will use to
# obtain a token (i.e., the login endpoint). This is crucial for the
# interactive OpenAPI/Swagger documentation.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

# --- The Main Security Dependency ---

def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: DatabaseService = Depends(get_db_service)
) -> UserModel:
    """
    A FastAPI dependency that verifies the JWT token from the request header
    and returns the corresponding user object from the database.

    This is the primary security gate for all protected endpoints.

    Args:
        token: The OAuth2 bearer token, injected by FastAPI from the request.
        db: The database service instance, injected by FastAPI.

    Raises:
        HTTPException(401): If the token is invalid, expired, malformed, or the
                            user associated with it does not exist.

    Returns:
        The SQLAlchemy User object for the authenticated user.
    """
    # Define a standard exception to be raised for all authentication failures.
    # This ensures a consistent error response for the client.
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1. Decode the token to get the user ID (subject).
    user_id = security.decode_token(token)
    if user_id is None:
        # If decoding fails (invalid signature, expired, etc.), `decode_token`
        # returns None. We immediately raise the exception.
        raise credentials_exception
    
    # 2. Fetch the user from the database using the ID from the token.
    user = db.get_user_by_id(user_id=user_id)
    if user is None:
        # This is a critical security check. It handles the case where a token
        # might be valid, but the user has been deleted from the system since
        # the token was issued.
        raise credentials_exception
    
    # 3. Return the fully validated user object.
    return user


def get_current_active_user(
    current_user: UserModel = Depends(get_current_user)
) -> UserModel:
    """
    A secondary dependency that layers on top of `get_current_user`.

    It first ensures the user is authenticated, then checks if their account
    is marked as active. This is useful for endpoints that should not be
    accessible by deactivated users.

    Args:
        current_user: The user object, injected by the `get_current_user` dependency.

    Raises:
        HTTPException(403): If the user's account is inactive. A 403 Forbidden
                           is more semantically correct here than a 400.

    Returns:
        The active, authenticated SQLAlchemy User object.
    """
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return current_user