# /ata-backend/app/routers/auth_router.py

"""
This module defines the public-facing API for all authentication-related actions.

It includes endpoints for:
- User registration (`/register`)
- User login and token generation (`/token`)
- Retrieving the current user's profile (`/me`)

This router orchestrates the authentication flow by connecting the HTTP layer
with the underlying business logic in the `user_service` and the cryptographic
utilities in the `core.security` module.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

# --- Application-specific Imports ---
from app.db.database import get_db
from app.models.user_model import User, UserCreate, Token
from app.db.models.user_model import User as UserModel
from app.services import user_service
from app.core import security
from app.core.deps import get_current_active_user, oauth2_scheme
from app.core import admin_auth
from app.services.database_service import get_db_service

# --- Router Initialization ---
router = APIRouter()


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def register_user(
    user_in: UserCreate, 
    db: Session = Depends(get_db)
):
    """
    Handles new user registration.

    Delegates the user creation logic to the user_service and handles any
    business-logic-related exceptions by converting them to HTTP exceptions.
    """
    # --- THIS IS THE ARCHITECTURAL FIX ---
    # The router does not know the business rules. It only knows how to call
    # the service and handle potential errors.
    try:
        new_user = user_service.create_user(db=db, user=user_in)
        return new_user
    except ValueError as e:
        # The user_service will raise a ValueError if the email already exists.
        # The router's job is to catch this specific business error and
        # translate it into a client-friendly HTTP 400 error.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Handles user login, compatible with the OAuth2 Password Flow.

    It authenticates the user with their email (via the 'username' field) and
    password. On success, it generates and returns a JWT access token.

    Special case: If admin credentials are provided, returns an admin token.
    """

    # Check if this is an admin login attempt
    if admin_auth.authenticate_admin(email=form_data.username, password=form_data.password):
        admin_token = admin_auth.create_admin_token()
        return Token(access_token=admin_token, token_type="bearer")

    # Otherwise, proceed with normal user authentication
    user = user_service.authenticate_user(
        db, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = security.create_access_token(
        subject=user.id
    )

    # Use the best practice from V3: return a Pydantic model instance.
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=User)
def read_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Retrieves the profile information for the currently authenticated user.

    This is a protected endpoint. For admin users, returns a special admin profile.
    For regular users, returns their database profile.
    """
    # Decode the token to check if it's an admin token
    user_id = security.decode_token(token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

    # Check if this is the admin user
    if user_id == "ADMIN_USER":
        # Return a mock user object for admin
        return User(
            id="00000000-0000-0000-0000-000000000000",
            email="mehran.gharuni.admin@admin.com",
            fullName="Super Admin",
            isActive=True
        )

    # Otherwise, get the regular user from database
    user = user_service.get_user_by_email(db, email=user_id) if "@" in user_id else None

    # If email lookup failed, try by ID
    if not user:
        from uuid import UUID
        try:
            user_uuid = UUID(user_id)
            user = db.query(UserModel).filter(UserModel.id == user_uuid).first()
        except (ValueError, AttributeError):
            user = None

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

    return user