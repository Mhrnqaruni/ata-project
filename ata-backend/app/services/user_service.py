# /ata-backend/app/services/user_service.py

"""
This service module encapsulates all business logic related to user management.

It acts as an intermediary between the API endpoints (routers) and the raw
database operations, ensuring a clean separation of concerns. The functions
in this module are responsible for:
- Retrieving users from the database.
- Orchestrating the creation of new users, including password hashing.
- Authenticating users by verifying their credentials.
"""

from typing import Optional
from sqlalchemy.orm import Session

# Import the SQLAlchemy model to interact with the database table.
from app.db.models.user_model import User as UserModel

# Import the Pydantic model that defines the data shape for user creation.
from app.models.user_model import UserCreate

# Import the security utilities for password hashing and verification.
from app.core.security import get_password_hash, verify_password


def get_user_by_email(db: Session, email: str) -> Optional[UserModel]:
    """
    Retrieves a single user from the database based on their email address.

    This is a fundamental lookup function used to check for user existence
    before registration and to fetch a user's details during login.

    Args:
        db: The active SQLAlchemy database session.
        email: The email address of the user to retrieve.

    Returns:
        The SQLAlchemy UserModel object if a user is found, otherwise None.
    """
    # Normalize email to lowercase for case-insensitive comparison
    return db.query(UserModel).filter(UserModel.email == email.lower()).first()


def create_user(db: Session, user: UserCreate) -> UserModel:
    """
    Creates a new user record in the database.

    This function orchestrates the entire user creation process:
    1. Checks if a user with the given email already exists.
    2. Hashes the plain-text password provided by the user.
    3. Creates a new SQLAlchemy UserModel instance with the validated data.
    4. Adds the new user to the database session and commits the transaction.

    Args:
        db: The active SQLAlchemy database session.
        user: A Pydantic UserCreate model containing the new user's details
              (email, full_name, and plain-text password).

    Raises:
        ValueError: If a user with the provided email already exists.

    Returns:
        The newly created SQLAlchemy UserModel object, including its server-generated ID.
    """
    # --- [THIS IS THE MODIFICATION] ---
    # The business rule for checking for a duplicate email is now correctly
    # placed within the service layer.
    existing_user = get_user_by_email(db, email=user.email)
    if existing_user:
        # Raising a standard Python exception allows the router to decide
        # which HTTP status code is appropriate.
        raise ValueError("An account with this email already exists.")
    # --- [END OF MODIFICATION] ---

    # Generate a secure hash of the user's password.
    # This is a critical security step. We never store the plain-text password.
    hashed_password = get_password_hash(user.password)

    # Create a new SQLAlchemy UserModel instance.
    # We use `model_dump()` to convert the Pydantic model to a dictionary,
    # excluding the password which we are replacing with the hash.
    # Normalize email to lowercase before storing
    db_user = UserModel(
        **user.model_dump(exclude={"password", "email"}),
        email=user.email.lower(),
        hashed_password=hashed_password
    )
    
    # Add the new user object to the session, commit it to the database,
    # and refresh the instance to get the server-generated values (like the ID).
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user


def authenticate_user(db: Session, email: str, password: str) -> Optional[UserModel]:
    """
    Authenticates a user by verifying their email and password.

    This is the core logic for the login process. It first finds the user by
    email and then uses the secure `verify_password` utility to check if the
    provided password matches the stored hash.

    Args:
        db: The active SQLAlchemy database session.
        email: The email provided by the user during login.
        password: The plain-text password provided by the user during login.

    Returns:
        The authenticated SQLAlchemy UserModel object if credentials are valid,
        otherwise None.
    """
    # First, retrieve the user from the database by their email.
    user = get_user_by_email(db, email=email)
    
    # If no user is found with that email, or if the password verification fails,
    # authentication is unsuccessful. We return None to signal this failure.
    if not user or not verify_password(password, user.hashed_password):
        return None
    
    # If the user exists and the password is correct, return the user object.
    return user