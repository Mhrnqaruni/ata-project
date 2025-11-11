# /ata-backend/app/core/quiz_auth.py

"""
This module provides authentication and authorization utilities for the Quiz system.

The quiz system supports two types of participants:
1. Registered students (authenticated via existing JWT system)
2. Guest users (authenticated via session-specific tokens)

This module handles guest token generation, validation, and room code management.
All functions use cryptographically secure random generation to prevent attacks.
"""

import secrets
import hmac
from typing import Optional
from app.core.logger import get_logger

logger = get_logger(__name__)


def generate_guest_token() -> str:
    """
    Generate a cryptographically secure token for guest authentication.

    Uses Python's secrets module with 32 bytes of entropy (256 bits), providing
    astronomical security against brute-force attacks (2^256 possible tokens).

    The token is Base64-encoded and URL-safe, making it easy to transmit in
    HTTP requests without special character encoding.

    Returns:
        URL-safe Base64-encoded token (~43 characters long)

    Example:
        >>> token = generate_guest_token()
        >>> len(token)
        43
        >>> 'special#chars' in token
        False
    """
    # secrets.token_urlsafe() is specifically designed for security-sensitive
    # applications like authentication tokens. It uses os.urandom() internally,
    # which reads from /dev/urandom on Unix systems (cryptographically secure).
    return secrets.token_urlsafe(32)


def validate_guest_token(provided_token: str, stored_token: str) -> bool:
    """
    Validate a guest token using constant-time comparison to prevent timing attacks.

    A timing attack exploits the fact that string comparison (==) short-circuits:
    it returns False immediately when it finds the first differing character.
    By measuring the time it takes to compare, an attacker can gradually
    discover the correct token character by character.

    hmac.compare_digest() compares strings in constant time regardless of
    where they differ, eliminating this vulnerability.

    Args:
        provided_token: Token from the client's request
        stored_token: Token from the database

    Returns:
        True if tokens match exactly, False otherwise

    Example:
        >>> stored = generate_guest_token()
        >>> validate_guest_token(stored, stored)
        True
        >>> validate_guest_token("wrong", stored)
        False
    """
    if not provided_token or not stored_token:
        return False

    # hmac.compare_digest() is the recommended way to compare security-sensitive
    # strings. It's available in Python 2.7.7+ and Python 3.3+.
    return hmac.compare_digest(provided_token, stored_token)


def generate_room_code(length: int = 6) -> str:
    """
    Generate a random room code for quiz sessions.

    Room codes use a restricted character set that excludes visually ambiguous
    characters to improve user experience when manually entering codes:
    - Excludes: O (letter), 0 (zero) - look similar
    - Excludes: I (letter), 1 (one) - look similar
    - Includes: All other uppercase letters and digits 2-9

    Args:
        length: Length of the room code (default: 6)

    Returns:
        Random room code consisting of non-ambiguous alphanumeric characters

    Example:
        >>> code = generate_room_code()
        >>> len(code)
        6
        >>> all(c in "ABCDEFGHJKLMNPQRSTUVWXYZ23456789" for c in code)
        True
    """
    from app.core.quiz_config import QuizConstants

    # Use the predefined character set from configuration
    # This ensures consistency across the application
    chars = QuizConstants.ROOM_CODE_CHARS  # "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    # secrets.choice() is the secure alternative to random.choice()
    # It uses the same cryptographically secure source as token_urlsafe()
    return ''.join(secrets.choice(chars) for _ in range(length))


def is_room_code_unique(room_code: str, db) -> bool:
    """
    Check if a room code is already in use by an active quiz session.

    A room code is considered "in use" if it's associated with a session
    that is either waiting for participants or currently in progress.
    Completed or cancelled sessions free up their room codes.

    Args:
        room_code: The room code to check
        db: Database session (SQLAlchemy Session)

    Returns:
        True if the room code is available (unique), False if already in use

    Note:
        This function is typically used internally by generate_unique_room_code()
        and not called directly in application code.
    """
    from app.db.models.quiz_models import QuizSession

    # Query for any active session using this room code
    # Active sessions are those in "waiting" or "in_progress" status
    existing = db.query(QuizSession).filter(
        QuizSession.room_code == room_code,
        QuizSession.status.in_(["waiting", "in_progress"])
    ).first()

    # If no existing session found, the code is unique
    return existing is None


def generate_unique_room_code(db, max_attempts: int = 5) -> str:
    """
    Generate a unique room code with automatic retry logic.

    With a 6-character code using 32 possible characters (no O, I, 0, 1),
    there are 32^6 = 1,073,741,824 possible codes. For typical use cases
    with hundreds or even thousands of concurrent sessions, collisions
    are extremely rare, but we handle them gracefully.

    The function attempts to generate a code up to max_attempts times,
    checking uniqueness after each attempt. If all attempts fail,
    it raises an exception (which is highly unlikely in practice).

    Args:
        db: Database session (SQLAlchemy Session)
        max_attempts: Maximum number of generation attempts (default: 5)

    Returns:
        A unique room code not currently in use by any active session

    Raises:
        RuntimeError: If a unique code cannot be generated after max_attempts

    Example:
        >>> from app.db.database import SessionLocal
        >>> db = SessionLocal()
        >>> code = generate_unique_room_code(db)
        >>> len(code)
        6
        >>> is_room_code_unique(code, db)
        True
    """
    from app.core.quiz_config import quiz_settings

    for attempt in range(max_attempts):
        # Generate a new code using the configured length
        room_code = generate_room_code(quiz_settings.ROOM_CODE_LENGTH)

        # Check if it's unique
        if is_room_code_unique(room_code, db):
            logger.info(f"Generated unique room code on attempt {attempt + 1}")
            return room_code

        # Log collision (rare but possible)
        logger.warning(
            f"Room code collision detected (attempt {attempt + 1}/{max_attempts}): {room_code}"
        )

    # If we've exhausted all attempts, raise an exception
    # This should never happen in practice unless there are thousands of concurrent sessions
    error_msg = f"Failed to generate unique room code after {max_attempts} attempts"
    logger.error(error_msg)
    raise RuntimeError(error_msg)


def format_participant_name(name: str, existing_names: list) -> str:
    """
    Format a participant name to ensure uniqueness within a session.

    If the provided name already exists among participants, appends a number
    in parentheses: "John" → "John (2)" → "John (3)", etc.

    This improves the participant experience on leaderboards and in the
    teacher's participant list, avoiding confusion between users with
    the same name.

    Args:
        name: The desired participant name
        existing_names: List of names already taken in the session

    Returns:
        Unique name (either original or with number appended)

    Example:
        >>> format_participant_name("Alice", [])
        'Alice'
        >>> format_participant_name("Alice", ["Alice"])
        'Alice (2)'
        >>> format_participant_name("Alice", ["Alice", "Alice (2)"])
        'Alice (3)'
    """
    # If name is not taken, return as-is
    if name not in existing_names:
        return name

    # Find the next available number
    counter = 2
    while True:
        formatted_name = f"{name} ({counter})"
        if formatted_name not in existing_names:
            return formatted_name
        counter += 1


def anonymize_guest_name(participant_id: str) -> str:
    """
    Generate an anonymized name for GDPR compliance.

    After the guest data retention period (30 days), guest names are replaced
    with anonymized versions. This function creates a consistent, non-identifiable
    replacement that still allows basic data analysis.

    The format is "Anonymous User #XXXXXX" where XXXXXX is derived from
    the participant ID's last 6 characters, ensuring uniqueness.

    Args:
        participant_id: The participant's unique identifier

    Returns:
        Anonymized name in format "Anonymous User #XXXXXX"

    Example:
        >>> anonymize_guest_name("participant_abc123def456")
        'Anonymous User #f456'
    """
    # Use last 6 characters of participant ID for uniqueness
    # This ensures the anonymized name is consistent and traceable
    # in analytics without revealing the original identity
    suffix = participant_id[-6:] if len(participant_id) >= 6 else participant_id
    return f"Anonymous User #{suffix}"


# --- Utility Functions for WebSocket Authentication ---

def extract_token_from_query(query_params: dict) -> Optional[str]:
    """
    Extract authentication token from WebSocket query parameters.

    WebSocket connections cannot send HTTP headers, so authentication
    tokens are passed as query parameters: ws://host/path?token=XXXXX

    Args:
        query_params: Dictionary of query parameters from WebSocket connection

    Returns:
        Token string if present, None otherwise

    Example:
        >>> extract_token_from_query({"token": "abc123"})
        'abc123'
        >>> extract_token_from_query({})
        None
    """
    return query_params.get("token")


def verify_participant_access(
    participant_id: str,
    session_id: str,
    token: str,
    db
) -> bool:
    """
    Verify that a participant has valid access to a quiz session.

    This function checks three conditions:
    1. Participant exists in database
    2. Participant belongs to the specified session
    3. Token matches (for guests) or student_id is set (for registered)

    Args:
        participant_id: Participant's unique identifier
        session_id: Session they're trying to access
        token: Authentication token (guest token or JWT)
        db: Database session

    Returns:
        True if access is granted, False otherwise

    Note:
        For registered students, this function should be called after
        JWT validation has already confirmed the user's identity.
    """
    from app.db.models.quiz_models import QuizParticipant

    participant = db.query(QuizParticipant).filter(
        QuizParticipant.id == participant_id,
        QuizParticipant.session_id == session_id
    ).first()

    if not participant:
        return False

    # If it's a guest, validate token
    if participant.guest_name:
        return validate_guest_token(token, participant.guest_token)

    # If it's a registered student, they're already authenticated via JWT
    return participant.student_id is not None


# --- Export commonly used functions ---
__all__ = [
    "generate_guest_token",
    "validate_guest_token",
    "generate_room_code",
    "is_room_code_unique",
    "generate_unique_room_code",
    "format_participant_name",
    "anonymize_guest_name",
    "extract_token_from_query",
    "verify_participant_access",
]
