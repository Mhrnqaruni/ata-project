# /ata-backend/app/core/admin_auth.py

"""
Admin authentication with hardcoded credentials.
This is a simple authentication mechanism for the super admin dashboard.
"""

from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core import security

# Hardcoded admin credentials
ADMIN_EMAIL = "mehran.gharuni.admin@admin.com"
ADMIN_PASSWORD = "s202f3d8458"

security_scheme = HTTPBearer()


def authenticate_admin(email: str, password: str) -> bool:
    """
    Authenticates admin with hardcoded credentials.

    Args:
        email: Email provided during login
        password: Password provided during login

    Returns:
        True if credentials match, False otherwise
    """
    return email == ADMIN_EMAIL and password == ADMIN_PASSWORD


def create_admin_token() -> str:
    """
    Creates a special JWT token for admin access.
    Uses a special subject identifier for admin.

    Returns:
        JWT access token
    """
    return security.create_access_token(subject="ADMIN_USER")


def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)) -> bool:
    """
    Dependency to verify admin token in protected routes.

    Args:
        credentials: Bearer token from request header

    Raises:
        HTTPException: If token is invalid or not an admin token

    Returns:
        True if valid admin token
    """
    token = credentials.credentials
    user_id = security.decode_token(token)

    if not user_id or user_id != "ADMIN_USER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return True
