# /ata-backend/app/core/security.py

"""
This module serves as the cryptographic core of the application.

It is responsible for all security-critical, pure functions, including:
- Hashing and verifying user passwords.
- Creating and decoding JSON Web Tokens (JWTs) for authentication.

This module is intentionally decoupled from the database and business logic layers.
It operates solely on the data provided to it and reads its configuration
from environment variables.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

from jose import JWTError, jwt
from passlib.context import CryptContext

# --- Configuration Loading ---
# Load secrets and configuration from environment variables for security and flexibility.

# The secret key used to sign JWTs. This MUST be kept secret.
# A fatal error is raised if this is not set, preventing insecure deployments.
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("FATAL ERROR: SECRET_KEY environment variable is not set.")

# The algorithm used for JWT signing. HS256 is a standard choice.
ALGORITHM = os.getenv("ALGORITHM", "HS256")

# The duration for which an access token is valid, in minutes.
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))


# --- Password Hashing ---
# Instantiate the password hashing context, specifying bcrypt as the default scheme.
# bcrypt is a strong, industry-standard hashing algorithm that includes salting.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a stored hash.

    Args:
        plain_password: The password attempt from the user.
        hashed_password: The hash stored in the database.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hashes a plain-text password using bcrypt.

    Args:
        password: The plain-text password to hash.

    Returns:
        A secure bcrypt hash of the password.
    """
    return pwd_context.hash(password)


# --- JSON Web Token (JWT) Management ---

def create_access_token(subject: str | Any, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a new JWT access token.

    Args:
        subject: The subject of the token, typically the user's unique ID.
        expires_delta: An optional timedelta to override the default expiration time.

    Returns:
        A signed JWT string.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject)  # 'sub' (subject) is the standard claim for the user identifier
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[str]:
    """
    Decodes and validates a JWT.

    Args:
        token: The JWT string to decode.

    Returns:
        The subject (user ID) from the token's payload if the token is valid
        and not expired, otherwise None.
    """
    try:
        # The `jwt.decode` function automatically handles signature verification
        # and expiration checking.
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Extract the subject claim.
        subject = payload.get("sub")
        if subject is None:
            return None
        return subject
        
    except JWTError:
        # This exception is raised if the token is expired, has an invalid
        # signature, or is otherwise malformed.
        return None