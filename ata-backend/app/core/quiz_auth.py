"""
Quiz Guest Authentication Module

This module provides secure authentication utilities for guest users in the quiz system.
Uses cryptographically secure random generation (secrets module) for all tokens and codes.

Security features:
- 32-byte guest tokens (256-bit entropy)
- Constant-time token validation (prevents timing attacks)
- Unique room code generation with collision handling
- Participant name deduplication
- GDPR-compliant anonymization helpers

Research sources:
- OWASP security guidelines
- Python secrets module documentation
- LoginRadius authentication best practices
"""

import secrets
import hmac
import string
import hashlib
from typing import Optional, Tuple
from datetime import datetime, timedelta

from .quiz_config import quiz_settings
from ..core.logger import get_logger

logger = get_logger(__name__)


# ===== GUEST TOKEN GENERATION =====

def generate_guest_token() -> str:
    """
    Generate a cryptographically secure random token for guest users.

    Uses Python's secrets module which is suitable for managing security tokens.
    Token length is configurable via GUEST_TOKEN_LENGTH_BYTES (default: 32 bytes = 256 bits).

    Returns:
        str: Hexadecimal string representation of the token (64 characters for 32 bytes)

    Example:
        >>> token = generate_guest_token()
        >>> len(token)
        64
        >>> all(c in '0123456789abcdef' for c in token)
        True

    Security:
        - 32 bytes = 256-bit entropy
        - 2^256 = 1.16 × 10^77 possible combinations
        - Brute force attack: infeasible
        - Collision probability: negligible (< 10^-60)
    """
    num_bytes = quiz_settings.GUEST_TOKEN_LENGTH_BYTES
    token = secrets.token_hex(num_bytes)

    logger.debug(f"Generated guest token (length: {len(token)} chars, {num_bytes} bytes entropy)")
    return token


def validate_guest_token(token1: str, token2: str) -> bool:
    """
    Validate a guest token using constant-time comparison to prevent timing attacks.

    Timing attacks work by measuring how long a comparison takes. If we use normal
    string comparison (==), an attacker can determine correct characters one by one
    by measuring response times. Constant-time comparison prevents this.

    Args:
        token1: First token (e.g., from database)
        token2: Second token (e.g., from user request)

    Returns:
        bool: True if tokens match, False otherwise

    Security:
        Uses hmac.compare_digest() which:
        - Takes the same time regardless of where strings differ
        - Prevents timing attack vulnerabilities
        - Recommended by OWASP for security token comparison
    """
    if not token1 or not token2:
        return False

    # hmac.compare_digest is constant-time for strings of the same length
    # For different lengths, it still prevents timing attacks
    result = hmac.compare_digest(token1, token2)

    if not result:
        logger.warning("Guest token validation failed")

    return result


# ===== ROOM CODE GENERATION =====

def generate_room_code() -> str:
    """
    Generate a unique alphanumeric room code for quiz sessions.

    Uses a charset that excludes visually ambiguous characters (O, 0, I, 1)
    to make room codes easier to read and type.

    Returns:
        str: Random room code (e.g., "AB3K7Q")

    Collision handling:
        - Call is_room_code_unique() before using
        - Retry generation if collision occurs
        - See generate_unique_room_code() for automatic retry logic

    Math:
        - Charset: 33 characters (A-Z except O, I; 2-9)
        - Length: 6 characters (configurable)
        - Combinations: 33^6 = 1,291,467,969 (1.29 billion)
        - Collision probability with 10,000 active sessions: 0.0039%
    """
    charset = quiz_settings.ROOM_CODE_CHARSET
    length = quiz_settings.ROOM_CODE_LENGTH

    room_code = ''.join(secrets.choice(charset) for _ in range(length))

    logger.debug(f"Generated room code: {room_code}")
    return room_code


def is_valid_room_code_format(room_code: str) -> bool:
    """
    Validate room code format (length and character set).

    Args:
        room_code: Room code to validate

    Returns:
        bool: True if valid format, False otherwise
    """
    if not room_code:
        return False

    expected_length = quiz_settings.ROOM_CODE_LENGTH
    valid_charset = set(quiz_settings.ROOM_CODE_CHARSET)

    return (
        len(room_code) == expected_length and
        all(c in valid_charset for c in room_code)
    )


# ===== PARTICIPANT NAME HANDLING =====

def handle_duplicate_name(base_name: str, existing_names: list[str]) -> str:
    """
    Handle duplicate participant names by appending a number.

    When a guest joins with a name that already exists in the session,
    append a number to make it unique (similar to how file systems work).

    Args:
        base_name: Original name (e.g., "John")
        existing_names: List of names already in use

    Returns:
        str: Unique name (e.g., "John (2)" if "John" exists)

    Examples:
        >>> handle_duplicate_name("John", ["John"])
        "John (2)"
        >>> handle_duplicate_name("John", ["John", "John (2)"])
        "John (3)"
        >>> handle_duplicate_name("Alice", ["Bob", "Carol"])
        "Alice"

    Research:
        Industry standard pattern used by:
        - Zoom (participant names)
        - Google Meet (participant names)
        - Kahoot (player names)
    """
    if base_name not in existing_names:
        return base_name

    # Find the next available number
    counter = 2
    while True:
        candidate = f"{base_name} ({counter})"
        if candidate not in existing_names:
            logger.debug(f"Resolved duplicate name: {base_name} → {candidate}")
            return candidate
        counter += 1

        # Safety check: prevent infinite loop (should never happen)
        if counter > 1000:
            # Fallback: use timestamp
            fallback = f"{base_name} ({int(datetime.now().timestamp())})"
            logger.warning(f"Duplicate name resolution exceeded 1000 attempts, using fallback: {fallback}")
            return fallback


def sanitize_participant_name(name: str, max_length: int = 50) -> str:
    """
    Sanitize participant name by removing/replacing problematic characters.

    Args:
        name: Original name
        max_length: Maximum allowed length (default: 50)

    Returns:
        str: Sanitized name

    Transformations:
        - Trim whitespace
        - Limit length
        - Remove control characters
        - Replace multiple spaces with single space
    """
    if not name:
        return "Guest"

    # Strip leading/trailing whitespace
    name = name.strip()

    # Replace multiple spaces with single space
    name = ' '.join(name.split())

    # Remove control characters
    name = ''.join(char for char in name if ord(char) >= 32)

    # Limit length
    if len(name) > max_length:
        name = name[:max_length].strip()

    # If empty after sanitization, use default
    if not name:
        name = "Guest"

    return name


# ===== GDPR ANONYMIZATION HELPERS =====

def anonymize_guest_name(guest_id: str) -> str:
    """
    Generate an anonymized placeholder name for GDPR compliance.

    After the retention period, guest names are replaced with
    "Anonymous User {hash}" where hash is a short identifier.

    Args:
        guest_id: Original guest/participant ID (UUID)

    Returns:
        str: Anonymized name (e.g., "Anonymous User a1b2c3")

    Example:
        >>> anonymize_guest_name("550e8400-e29b-41d4-a716-446655440000")
        "Anonymous User 550e84"

    GDPR Compliance:
        - Removes personally identifiable information
        - Preserves data structure for analytics
        - Keeps unique identifier for de-duplication
    """
    # Use first 6 characters of guest_id as unique identifier
    short_id = str(guest_id)[:6]
    return f"Anonymous User {short_id}"


def should_anonymize_guest(joined_at: datetime) -> bool:
    """
    Determine if a guest participant should be anonymized based on retention policy.

    Args:
        joined_at: When the guest joined the session

    Returns:
        bool: True if guest data should be anonymized

    Policy:
        - Default retention: 30 days (configurable)
        - After this period, guest names are anonymized
        - Answers and scores are preserved for analytics
    """
    if not joined_at:
        return False

    retention_days = quiz_settings.GUEST_DATA_RETENTION_DAYS
    cutoff_date = datetime.now() - timedelta(days=retention_days)

    return joined_at < cutoff_date


# ===== HASH GENERATION (for caching, not security) =====

def generate_session_hash(session_id: str) -> str:
    """
    Generate a hash for session identification in caching systems.

    NOT for security - just for creating short, consistent identifiers.

    Args:
        session_id: Session UUID

    Returns:
        str: 8-character hex hash

    Note:
        This is NOT cryptographically secure. Use only for:
        - Cache keys
        - Short identifiers
        - Non-security purposes
    """
    hash_object = hashlib.sha256(session_id.encode())
    return hash_object.hexdigest()[:8]


# ===== VALIDATION HELPERS =====

def validate_token_format(token: str) -> Tuple[bool, Optional[str]]:
    """
    Validate guest token format.

    Args:
        token: Token to validate

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)

    Checks:
        - Not empty
        - Correct length (64 hex characters for 32 bytes)
        - Only hexadecimal characters
    """
    if not token:
        return False, "Token is empty"

    expected_length = quiz_settings.GUEST_TOKEN_LENGTH_BYTES * 2  # 2 hex chars per byte

    if len(token) != expected_length:
        return False, f"Token length must be {expected_length} characters"

    if not all(c in string.hexdigits for c in token):
        return False, "Token must contain only hexadecimal characters (0-9, a-f)"

    return True, None
