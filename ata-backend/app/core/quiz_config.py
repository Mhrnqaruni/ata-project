# /ata-backend/app/core/quiz_config.py

"""
This module defines all configuration settings for the Quiz system.

The QuizSettings class uses Pydantic's BaseSettings to load configuration
values from environment variables with sensible defaults. This allows for
easy configuration across different deployment environments (development,
staging, production) without code changes.

All environment variables for quiz configuration should be prefixed with QUIZ_
for clarity and to avoid conflicts with other system settings.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class QuizSettings(BaseSettings):
    """
    Configuration settings for the Quiz system.

    All settings can be overridden via environment variables with the prefix QUIZ_
    Example: QUIZ_MAX_PARTICIPANTS_PER_SESSION=1000
    """

    # --- Capacity Limits ---
    # Based on confirmed small scale deployment initially

    MAX_PARTICIPANTS_PER_SESSION: int = 500
    """Maximum number of participants allowed in a single quiz session."""

    MAX_QUESTIONS_PER_QUIZ: int = 100
    """Maximum number of questions allowed in a single quiz."""

    MAX_CONCURRENT_SESSIONS: int = 100
    """Maximum number of concurrent quiz sessions supported."""

    # --- Session Management ---

    SESSION_TIMEOUT_HOURS: int = 2
    """Maximum duration of a quiz session before auto-termination."""

    SESSION_WARNING_HOURS: int = 1
    """Duration after which to warn about approaching session timeout."""

    AUTO_ADVANCE_DEFAULT: bool = False
    """Default setting for automatic question advancement."""

    # --- Performance Optimization ---

    LEADERBOARD_BATCH_INTERVAL: int = 2
    """Interval in seconds between leaderboard broadcast updates (batch updates)."""

    HEARTBEAT_INTERVAL: int = 30
    """Interval in seconds for WebSocket heartbeat pings."""

    RECONNECTION_GRACE_PERIOD: int = 30
    """Grace period in seconds to allow reconnection with state recovery."""

    # --- Data Retention & GDPR Compliance ---

    GUEST_DATA_RETENTION_DAYS: int = 30
    """Number of days to retain guest participant data before anonymization."""

    CLEANUP_JOB_SCHEDULE: str = "0 2 * * *"
    """Cron schedule for running GDPR cleanup job (default: daily at 2 AM)."""

    # --- Room Code Generation ---

    ROOM_CODE_LENGTH: int = 6
    """Length of alphanumeric room codes for quiz sessions."""

    ROOM_CODE_RETRIES: int = 5
    """Number of times to retry generating a unique room code before failing."""

    # --- Question Defaults ---

    DEFAULT_QUESTION_TIME_LIMIT: int = 30
    """Default time limit in seconds for questions without specific time limits."""

    DEFAULT_QUESTION_POINTS: int = 10
    """Default points awarded for correct answers."""

    POLL_PARTICIPATION_POINTS: int = 5
    """Points awarded just for participating in poll questions."""

    # --- Grading Configuration ---

    SHORT_ANSWER_MIN_KEYWORD_MATCH: float = 0.5
    """Minimum percentage of keywords that must match for short answer correctness."""

    SHORT_ANSWER_CASE_SENSITIVE_DEFAULT: bool = False
    """Default case sensitivity for short answer matching."""

    # --- WebSocket Configuration ---

    WS_CONNECTION_TIMEOUT: int = 60
    """Timeout in seconds for establishing WebSocket connections."""

    WS_MESSAGE_QUEUE_SIZE: int = 100
    """Maximum size of message queue per WebSocket connection."""

    # --- Database Configuration ---
    # These leverage the existing database connection pool settings
    # but can be overridden specifically for quiz operations if needed

    QUIZ_DB_POOL_SIZE: Optional[int] = None
    """Database connection pool size for quiz operations (None = use default)."""

    QUIZ_DB_MAX_OVERFLOW: Optional[int] = None
    """Max overflow connections for quiz operations (None = use default)."""

    # --- Feature Flags ---
    # Allows toggling features without code deployment

    ENABLE_QUIZ_ANALYTICS: bool = True
    """Enable detailed analytics and reporting features."""

    ENABLE_CSV_EXPORT: bool = True
    """Enable CSV export of quiz results."""

    ENABLE_PARTIAL_CREDIT: bool = False
    """Enable partial credit grading (Phase 2 feature - currently disabled)."""

    # --- Logging ---

    QUIZ_LOG_LEVEL: str = "INFO"
    """Logging level for quiz-related operations."""

    LOG_WEBSOCKET_MESSAGES: bool = False
    """Enable detailed logging of WebSocket messages (debug only)."""

    # --- Security ---

    GUEST_TOKEN_LENGTH: int = 32
    """Length of secure random tokens for guest authentication."""

    REQUIRE_UNIQUE_PARTICIPANT_NAMES: bool = True
    """Enforce unique participant names within a session (append numbers if duplicate)."""

    class Config:
        """Pydantic configuration."""
        env_prefix = "QUIZ_"
        case_sensitive = True
        # Allow reading from .env file
        env_file = os.getenv("QUIZ_ENV_FILE", ".env")
        env_file_encoding = "utf-8"


# Singleton instance to be imported throughout the application
quiz_settings = QuizSettings()


# --- Utility Functions ---

def get_quiz_settings() -> QuizSettings:
    """
    Dependency injection helper for FastAPI endpoints.

    Usage:
        @router.get("/quiz")
        def endpoint(settings: QuizSettings = Depends(get_quiz_settings)):
            max_participants = settings.MAX_PARTICIPANTS_PER_SESSION

    Returns:
        The global quiz settings instance.
    """
    return quiz_settings


def validate_quiz_settings() -> bool:
    """
    Validates that all quiz settings are within acceptable ranges.

    This function is called during application startup to catch configuration
    errors early before they cause runtime failures.

    Returns:
        True if all settings are valid, raises ValueError otherwise.

    Raises:
        ValueError: If any setting is invalid or out of acceptable range.
    """
    settings = quiz_settings

    # Validate capacity limits
    if settings.MAX_PARTICIPANTS_PER_SESSION < 1:
        raise ValueError("MAX_PARTICIPANTS_PER_SESSION must be at least 1")

    if settings.MAX_QUESTIONS_PER_QUIZ < 1:
        raise ValueError("MAX_QUESTIONS_PER_QUIZ must be at least 1")

    if settings.MAX_CONCURRENT_SESSIONS < 1:
        raise ValueError("MAX_CONCURRENT_SESSIONS must be at least 1")

    # Validate timeouts
    if settings.SESSION_TIMEOUT_HOURS < 1:
        raise ValueError("SESSION_TIMEOUT_HOURS must be at least 1")

    if settings.SESSION_WARNING_HOURS >= settings.SESSION_TIMEOUT_HOURS:
        raise ValueError("SESSION_WARNING_HOURS must be less than SESSION_TIMEOUT_HOURS")

    # Validate intervals
    if settings.LEADERBOARD_BATCH_INTERVAL < 1:
        raise ValueError("LEADERBOARD_BATCH_INTERVAL must be at least 1 second")

    if settings.HEARTBEAT_INTERVAL < 10:
        raise ValueError("HEARTBEAT_INTERVAL must be at least 10 seconds")

    # Validate retention
    if settings.GUEST_DATA_RETENTION_DAYS < 1:
        raise ValueError("GUEST_DATA_RETENTION_DAYS must be at least 1")

    # Validate room code
    if settings.ROOM_CODE_LENGTH < 4 or settings.ROOM_CODE_LENGTH > 10:
        raise ValueError("ROOM_CODE_LENGTH must be between 4 and 10")

    # Validate points
    if settings.DEFAULT_QUESTION_POINTS < 0:
        raise ValueError("DEFAULT_QUESTION_POINTS cannot be negative")

    if settings.POLL_PARTICIPATION_POINTS < 0:
        raise ValueError("POLL_PARTICIPATION_POINTS cannot be negative")

    # Validate grading
    if settings.SHORT_ANSWER_MIN_KEYWORD_MATCH < 0 or settings.SHORT_ANSWER_MIN_KEYWORD_MATCH > 1:
        raise ValueError("SHORT_ANSWER_MIN_KEYWORD_MATCH must be between 0 and 1")

    # Validate security
    if settings.GUEST_TOKEN_LENGTH < 16:
        raise ValueError("GUEST_TOKEN_LENGTH must be at least 16 for security")

    return True


# --- Constants ---
# These are not configurable and represent system constraints

class QuizConstants:
    """
    System constants that should not be changed without careful consideration.
    These represent fundamental design decisions and constraints.
    """

    # Question Types
    QUESTION_TYPE_MULTIPLE_CHOICE = "multiple_choice"
    QUESTION_TYPE_TRUE_FALSE = "true_false"
    QUESTION_TYPE_SHORT_ANSWER = "short_answer"
    QUESTION_TYPE_POLL = "poll"

    VALID_QUESTION_TYPES = [
        QUESTION_TYPE_MULTIPLE_CHOICE,
        QUESTION_TYPE_TRUE_FALSE,
        QUESTION_TYPE_SHORT_ANSWER,
        QUESTION_TYPE_POLL,
    ]

    # Quiz Status
    QUIZ_STATUS_DRAFT = "draft"
    QUIZ_STATUS_PUBLISHED = "published"
    QUIZ_STATUS_ARCHIVED = "archived"

    VALID_QUIZ_STATUSES = [
        QUIZ_STATUS_DRAFT,
        QUIZ_STATUS_PUBLISHED,
        QUIZ_STATUS_ARCHIVED,
    ]

    # Session Status
    SESSION_STATUS_WAITING = "waiting"
    SESSION_STATUS_IN_PROGRESS = "in_progress"
    SESSION_STATUS_COMPLETED = "completed"
    SESSION_STATUS_CANCELLED = "cancelled"

    VALID_SESSION_STATUSES = [
        SESSION_STATUS_WAITING,
        SESSION_STATUS_IN_PROGRESS,
        SESSION_STATUS_COMPLETED,
        SESSION_STATUS_CANCELLED,
    ]

    # Room Code Characters (alphanumeric, avoiding ambiguous characters)
    ROOM_CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # No O, I, 0, 1

    # WebSocket Message Types
    WS_TYPE_PARTICIPANT_JOINED = "participant_joined"
    WS_TYPE_PARTICIPANT_LEFT = "participant_left"
    WS_TYPE_QUIZ_STARTED = "quiz_started"
    WS_TYPE_NEW_QUESTION = "new_question"
    WS_TYPE_QUESTION_ENDED = "question_ended"
    WS_TYPE_ANSWER_RESULT = "answer_result"
    WS_TYPE_LEADERBOARD_UPDATE = "leaderboard_update"
    WS_TYPE_QUIZ_ENDED = "quiz_ended"
    WS_TYPE_ERROR = "error"
    WS_TYPE_HEARTBEAT = "heartbeat"
    WS_TYPE_RECONNECT_SYNC = "reconnect_sync"


# Export commonly used items
__all__ = [
    "QuizSettings",
    "quiz_settings",
    "get_quiz_settings",
    "validate_quiz_settings",
    "QuizConstants",
]
