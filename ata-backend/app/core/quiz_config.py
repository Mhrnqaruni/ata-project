"""
Quiz System Configuration Module

This module defines all configuration settings for the Quiz system using Pydantic BaseSettings.
Environment variables can override default values by prefixing with QUIZ_ (e.g., QUIZ_MAX_PARTICIPANTS_PER_SESSION).

Research-backed defaults:
- 500 participants/session (small scale, can handle 5,000+ with single server)
- 32-byte tokens (256-bit entropy, 1.16e77 possible combinations)
- 30-day GDPR retention (industry standard)
- 2-3 second leaderboard updates (research: optimal UX)
- Server-side timing (critical for anti-cheating)
"""

from typing import Optional
from pydantic_settings import BaseSettings


class QuizSettings(BaseSettings):
    """
    Configuration settings for the Quiz system.
    All values can be overridden via environment variables with QUIZ_ prefix.
    """

    # ===== CAPACITY & PERFORMANCE =====

    # Maximum number of participants allowed per quiz session
    # Research: Single FastAPI server can handle 45K WebSocket connections
    # Default: 500 (conservative for small scale)
    MAX_PARTICIPANTS_PER_SESSION: int = 500

    # Maximum number of questions allowed per quiz
    MAX_QUESTIONS_PER_QUIZ: int = 100

    # Maximum concurrent quiz sessions per teacher
    MAX_CONCURRENT_SESSIONS_PER_USER: int = 10

    # ===== TIMING & TIMEOUTS =====

    # Default timeout for quiz sessions (hours)
    # Sessions auto-end after this period of inactivity
    DEFAULT_SESSION_TIMEOUT_HOURS: int = 2

    # Maximum session duration (hours)
    # Absolute timeout regardless of activity
    MAX_SESSION_DURATION_HOURS: int = 24

    # Heartbeat interval for WebSocket connections (seconds)
    # Server sends ping every N seconds to detect disconnects
    HEARTBEAT_INTERVAL_SECONDS: int = 30

    # Participant inactivity threshold (seconds)
    # Mark participant as inactive if no heartbeat for this long
    PARTICIPANT_INACTIVITY_THRESHOLD_SECONDS: int = 120  # 2 minutes

    # Remove inactive participants after this duration (seconds)
    REMOVE_INACTIVE_AFTER_SECONDS: int = 300  # 5 minutes

    # ===== AUTHENTICATION & SECURITY =====

    # Length of guest authentication tokens (bytes)
    # 32 bytes = 256-bit entropy = 1.16e77 combinations
    # Research: Cryptographically secure against brute force
    GUEST_TOKEN_LENGTH_BYTES: int = 32

    # Length of room codes (characters)
    # 6 alphanumeric = 2.176 billion combinations
    # Sufficient for avoiding collisions in normal use
    ROOM_CODE_LENGTH: int = 6

    # Room code character set (alphanumeric, excluding ambiguous characters)
    ROOM_CODE_CHARSET: str = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # No O, 0, I, 1

    # Maximum room code generation attempts (collision handling)
    MAX_ROOM_CODE_GENERATION_ATTEMPTS: int = 10

    # ===== GDPR & DATA RETENTION =====

    # Days to retain guest user data before anonymization
    # Research: 30 days is industry standard for guest users
    GUEST_DATA_RETENTION_DAYS: int = 30

    # Days to keep completed sessions before archiving
    SESSION_ARCHIVE_AFTER_DAYS: int = 90

    # Enable automatic GDPR anonymization job
    ENABLE_AUTO_ANONYMIZATION: bool = True

    # ===== LEADERBOARD & UPDATES =====

    # Batch leaderboard updates interval (seconds)
    # Research: 2-3 seconds is optimal for UX (not too spammy, feels real-time)
    LEADERBOARD_UPDATE_INTERVAL_SECONDS: int = 2.5

    # Number of top participants to show on leaderboard
    LEADERBOARD_TOP_COUNT: int = 5

    # ===== QUESTION & ANSWER SETTINGS =====

    # Default time limit per question (seconds)
    # Can be overridden per question
    DEFAULT_QUESTION_TIME_LIMIT_SECONDS: int = 30

    # Maximum time limit per question (seconds)
    MAX_QUESTION_TIME_LIMIT_SECONDS: int = 300  # 5 minutes

    # Default points per question
    DEFAULT_QUESTION_POINTS: int = 10

    # Maximum points per question
    MAX_QUESTION_POINTS: int = 100

    # Server-side time enforcement tolerance (milliseconds)
    # Allow small client-server clock differences
    TIME_ENFORCEMENT_TOLERANCE_MS: int = 2000  # 2 seconds

    # ===== SHORT ANSWER GRADING =====

    # Minimum keyword match percentage for short answer questions
    # E.g., 0.5 = at least 50% of keywords must match
    SHORT_ANSWER_KEYWORD_MATCH_THRESHOLD: float = 0.5

    # Case-insensitive matching for short answers
    SHORT_ANSWER_CASE_INSENSITIVE: bool = True

    # Remove punctuation when matching short answers
    SHORT_ANSWER_STRIP_PUNCTUATION: bool = True

    # ===== WEBSOCKET CONFIGURATION =====

    # WebSocket connection timeout (seconds)
    WEBSOCKET_TIMEOUT_SECONDS: int = 60

    # WebSocket heartbeat/ping interval (seconds)
    # Send ping every N seconds to detect connection health
    WEBSOCKET_HEARTBEAT_INTERVAL_SECONDS: int = 30

    # WebSocket heartbeat timeout (seconds)
    # Close connection if no pong received within this time
    WEBSOCKET_HEARTBEAT_TIMEOUT_SECONDS: int = 90

    # Maximum message size for WebSocket (bytes)
    MAX_WEBSOCKET_MESSAGE_SIZE_BYTES: int = 1048576  # 1 MB

    # Enable WebSocket compression
    WEBSOCKET_COMPRESSION: bool = True

    # ===== SCHEDULED JOBS =====

    # Enable scheduled cleanup jobs
    ENABLE_SCHEDULED_JOBS: bool = True

    # Hour to run daily GDPR anonymization job (0-23, UTC)
    ANONYMIZATION_JOB_HOUR: int = 2  # 2 AM UTC

    # Hour to run weekly session archival job (0-23, UTC)
    ARCHIVE_JOB_HOUR: int = 3  # 3 AM UTC

    # Day of week for weekly jobs (0 = Monday, 6 = Sunday)
    ARCHIVE_JOB_DAY_OF_WEEK: int = 0  # Monday

    class Config:
        env_prefix = "QUIZ_"
        case_sensitive = False


# Global settings instance
quiz_settings = QuizSettings()


# ===== CONSTANTS =====

# Question types (matching Pydantic enum)
class QuestionType:
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    POLL = "poll"


# Quiz status values
class QuizStatus:
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# Session status values
class SessionStatus:
    WAITING = "waiting"  # Created but not started
    ACTIVE = "active"    # In progress
    COMPLETED = "completed"  # Finished normally
    CANCELLED = "cancelled"  # Ended prematurely


# WebSocket message types
class WSMessageType:
    # Server → Client messages
    PARTICIPANT_JOINED = "participant_joined"
    PARTICIPANT_LEFT = "participant_left"
    QUESTION_STARTED = "question_started"
    QUESTION_ENDED = "question_ended"
    ANSWER_RECEIVED = "answer_received"
    LEADERBOARD_UPDATE = "leaderboard_update"
    SESSION_ENDED = "session_ended"
    HEARTBEAT_PING = "heartbeat_ping"
    ERROR = "error"

    # Client → Server messages
    SUBMIT_ANSWER = "submit_answer"
    HEARTBEAT_PONG = "heartbeat_pong"
    REQUEST_CURRENT_STATE = "request_current_state"


# ===== VALIDATION FUNCTIONS =====

def validate_quiz_settings():
    """
    Validate quiz settings for logical consistency.
    Raises ValueError if any settings are invalid.
    """
    s = quiz_settings

    if s.MAX_PARTICIPANTS_PER_SESSION <= 0:
        raise ValueError("MAX_PARTICIPANTS_PER_SESSION must be positive")

    if s.MAX_QUESTIONS_PER_QUIZ <= 0:
        raise ValueError("MAX_QUESTIONS_PER_QUIZ must be positive")

    if s.DEFAULT_SESSION_TIMEOUT_HOURS <= 0:
        raise ValueError("DEFAULT_SESSION_TIMEOUT_HOURS must be positive")

    if s.MAX_SESSION_DURATION_HOURS < s.DEFAULT_SESSION_TIMEOUT_HOURS:
        raise ValueError("MAX_SESSION_DURATION_HOURS must be >= DEFAULT_SESSION_TIMEOUT_HOURS")

    if s.GUEST_TOKEN_LENGTH_BYTES < 16:
        raise ValueError("GUEST_TOKEN_LENGTH_BYTES must be at least 16 for security")

    if s.ROOM_CODE_LENGTH < 4:
        raise ValueError("ROOM_CODE_LENGTH must be at least 4 to avoid collisions")

    if s.GUEST_DATA_RETENTION_DAYS < 1:
        raise ValueError("GUEST_DATA_RETENTION_DAYS must be at least 1")

    if not (0.0 <= s.SHORT_ANSWER_KEYWORD_MATCH_THRESHOLD <= 1.0):
        raise ValueError("SHORT_ANSWER_KEYWORD_MATCH_THRESHOLD must be between 0.0 and 1.0")

    if s.LEADERBOARD_UPDATE_INTERVAL_SECONDS <= 0:
        raise ValueError("LEADERBOARD_UPDATE_INTERVAL_SECONDS must be positive")

    if not (0 <= s.ANONYMIZATION_JOB_HOUR <= 23):
        raise ValueError("ANONYMIZATION_JOB_HOUR must be between 0 and 23")

    if not (0 <= s.ARCHIVE_JOB_DAY_OF_WEEK <= 6):
        raise ValueError("ARCHIVE_JOB_DAY_OF_WEEK must be between 0 (Monday) and 6 (Sunday)")


# Run validation on module import
try:
    validate_quiz_settings()
except ValueError as e:
    import logging
    logging.error(f"Quiz settings validation failed: {e}")
    raise
