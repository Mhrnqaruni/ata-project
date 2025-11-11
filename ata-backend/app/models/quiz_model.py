# /ata-backend/app/models/quiz_model.py

"""
This module defines all Pydantic models (schemas) for the Quiz system API.

Pydantic models serve three purposes in FastAPI:
1. Request validation: Ensure incoming data meets requirements
2. Response serialization: Convert ORM models to JSON automatically
3. API documentation: Generate OpenAPI/Swagger docs automatically

The models are organized by entity: Quiz, Question, Session, Participant, Response.
Each entity typically has Create, Update, and Response schemas.
"""

from pydantic import BaseModel, Field, validator, root_validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum


# =============================================================================
# ENUMS - Constrained string values
# =============================================================================

class QuestionType(str, Enum):
    """Supported question types in quizzes."""
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    POLL = "poll"


class QuizStatus(str, Enum):
    """Lifecycle status of a quiz."""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class SessionStatus(str, Enum):
    """Status of a quiz session."""
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# =============================================================================
# SETTINGS SCHEMAS
# =============================================================================

class QuizSettingsSchema(BaseModel):
    """
    Quiz-level configuration settings.

    These settings control the behavior and features of the quiz.
    Stored as JSONB in the database for flexibility.
    """
    auto_advance: bool = Field(
        default=False,
        description="Automatically advance to next question after time expires"
    )
    show_leaderboard: bool = Field(
        default=True,
        description="Display live leaderboard to participants"
    )
    shuffle_questions: bool = Field(
        default=False,
        description="Randomize question order for each participant"
    )
    shuffle_options: bool = Field(
        default=True,
        description="Randomize answer options for multiple choice questions"
    )
    allow_review: bool = Field(
        default=True,
        description="Show correct answers and explanations after quiz"
    )
    max_participants: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000,
        description="Maximum number of participants (null = unlimited)"
    )
    question_time_default: int = Field(
        default=30,
        ge=5,
        le=600,
        description="Default time limit per question in seconds"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "auto_advance": False,
                "show_leaderboard": True,
                "shuffle_questions": False,
                "shuffle_options": True,
                "allow_review": True,
                "max_participants": 100,
                "question_time_default": 30
            }
        }


# =============================================================================
# QUESTION SCHEMAS
# =============================================================================

class QuestionBase(BaseModel):
    """Base fields common to all question operations."""
    question_text: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="The question text displayed to participants"
    )
    question_type: QuestionType = Field(
        ...,
        description="Type of question (multiple_choice, true_false, short_answer, poll)"
    )
    points: int = Field(
        default=10,
        ge=0,
        le=1000,
        description="Points awarded for correct answer"
    )
    time_limit: Optional[int] = Field(
        None,
        ge=5,
        le=600,
        description="Time limit in seconds (null = use quiz default)"
    )
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Question-type-specific options (JSONB)"
    )
    correct_answer: Dict[str, Any] = Field(
        default_factory=dict,
        description="Correct answer definition (JSONB)"
    )
    explanation: Optional[str] = Field(
        None,
        max_length=1000,
        description="Explanation shown after answering (optional)"
    )

    @validator('options', 'correct_answer')
    def validate_json_not_none(cls, v):
        """Ensure JSONB fields are never None (use empty dict instead)."""
        return v if v is not None else {}

    class Config:
        json_schema_extra = {
            "example": {
                "question_text": "What is the capital of France?",
                "question_type": "multiple_choice",
                "points": 10,
                "time_limit": 30,
                "options": {
                    "choices": [
                        {"id": "a", "text": "London"},
                        {"id": "b", "text": "Paris"},
                        {"id": "c", "text": "Berlin"},
                        {"id": "d", "text": "Madrid"}
                    ]
                },
                "correct_answer": {"answer": "b"},
                "explanation": "Paris has been the capital of France since the 12th century."
            }
        }


class QuestionCreate(QuestionBase):
    """Schema for creating a new question."""
    pass


class QuestionUpdate(BaseModel):
    """
    Schema for updating an existing question.
    All fields are optional to allow partial updates.
    """
    question_text: Optional[str] = Field(None, min_length=3, max_length=1000)
    question_type: Optional[QuestionType] = None
    points: Optional[int] = Field(None, ge=0, le=1000)
    time_limit: Optional[int] = Field(None, ge=5, le=600)
    options: Optional[Dict[str, Any]] = None
    correct_answer: Optional[Dict[str, Any]] = None
    explanation: Optional[str] = Field(None, max_length=1000)


class QuestionResponse(QuestionBase):
    """Schema for question in API responses."""
    id: str
    quiz_id: str
    order_index: int
    created_at: datetime

    class Config:
        from_attributes = True  # Enable ORM mode for SQLAlchemy models


class QuestionReorder(BaseModel):
    """Schema for reordering questions in a quiz."""
    question_ids: List[str] = Field(
        ...,
        min_length=1,
        description="Ordered list of question IDs"
    )


# =============================================================================
# QUIZ SCHEMAS
# =============================================================================

class QuizBase(BaseModel):
    """Base fields for quiz operations."""
    title: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="Quiz title"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Quiz description"
    )
    instructions: Optional[str] = Field(
        None,
        max_length=2000,
        description="Instructions displayed to participants before starting"
    )
    class_id: Optional[str] = Field(
        None,
        description="Optional class ID to associate quiz with a specific class"
    )
    settings: QuizSettingsSchema = Field(
        default_factory=QuizSettingsSchema,
        description="Quiz configuration settings"
    )


class QuizCreate(QuizBase):
    """
    Schema for creating a new quiz.
    Optionally includes initial questions.
    """
    questions: List[QuestionCreate] = Field(
        default_factory=list,
        description="Initial questions (can be empty and added later)"
    )


class QuizUpdate(BaseModel):
    """
    Schema for updating a quiz.
    All fields optional for partial updates.
    """
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    instructions: Optional[str] = Field(None, max_length=2000)
    settings: Optional[QuizSettingsSchema] = None


class QuizSummary(BaseModel):
    """
    Schema for quiz in list views.
    Lightweight summary without questions.
    """
    id: str
    title: str
    description: Optional[str]
    status: QuizStatus
    question_count: int = Field(
        ...,
        description="Number of questions in quiz"
    )
    class_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class QuizDetail(QuizBase):
    """
    Schema for full quiz details including all questions.
    Used when viewing/editing a specific quiz.
    """
    id: str
    user_id: str
    status: QuizStatus
    last_room_code: Optional[str]
    deleted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    questions: List[QuestionResponse] = Field(
        default_factory=list,
        description="All questions in quiz (ordered by order_index)"
    )

    class Config:
        from_attributes = True


# =============================================================================
# SESSION SCHEMAS
# =============================================================================

class SessionCreate(BaseModel):
    """Schema for starting a new quiz session."""
    quiz_id: str = Field(..., description="ID of quiz to start")


class SessionSummary(BaseModel):
    """Schema for session in list views."""
    id: str
    quiz_id: str
    quiz_title: str = Field(..., description="Title of the quiz")
    status: SessionStatus
    room_code: str
    participant_count: int
    started_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class SessionDetail(BaseModel):
    """Schema for full session details."""
    id: str
    quiz_id: str
    user_id: str
    status: SessionStatus
    room_code: str
    current_question_index: int
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    created_at: datetime
    session_config: QuizSettingsSchema
    timeout_hours: int

    class Config:
        from_attributes = True


class SessionControl(BaseModel):
    """Schema for session control operations (advance, end)."""
    action: str = Field(
        ...,
        description="Control action: 'advance' or 'end'"
    )

    @validator('action')
    def validate_action(cls, v):
        """Ensure action is valid."""
        if v not in ['advance', 'end']:
            raise ValueError('action must be "advance" or "end"')
        return v


# =============================================================================
# PARTICIPANT SCHEMAS
# =============================================================================

class ParticipantJoinRequest(BaseModel):
    """
    Schema for joining a quiz session.
    Supports both registered students and guest users.
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Participant display name"
    )
    student_id: Optional[str] = Field(
        None,
        description="Student ID if joining as registered student (optional)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Smith",
                "student_id": None
            }
        }


class ParticipantJoinResponse(BaseModel):
    """
    Schema for successful join response.
    Includes guest token for authentication if joining as guest.
    """
    participant_id: str
    session_id: str
    guest_token: Optional[str] = Field(
        None,
        description="Authentication token (only provided for guests)"
    )
    room_code: str
    quiz_title: str


class ParticipantSummary(BaseModel):
    """Schema for participant in lists."""
    id: str
    name: str = Field(..., description="Display name (guest name or student name)")
    score: int
    correct_answers: int
    is_active: bool
    joined_at: datetime

    class Config:
        from_attributes = True


class ParticipantDetail(ParticipantSummary):
    """Schema for full participant details."""
    session_id: str
    total_time_ms: int


# =============================================================================
# ANSWER SUBMISSION SCHEMAS
# =============================================================================

class AnswerSubmission(BaseModel):
    """
    Schema for submitting an answer to a question.
    Answer structure varies by question type.
    """
    question_id: str = Field(..., description="ID of question being answered")
    answer: Dict[str, Any] = Field(
        ...,
        description="Answer data (structure depends on question type)"
    )
    time_taken_ms: int = Field(
        ...,
        ge=0,
        description="Milliseconds taken to answer"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question_id": "q123",
                "answer": {"selected": "b"},
                "time_taken_ms": 15420
            }
        }


class AnswerResult(BaseModel):
    """
    Schema for answer grading result.
    Sent back to participant immediately after submission.
    """
    is_correct: Optional[bool] = Field(
        None,
        description="Whether answer was correct (null for poll questions)"
    )
    points_earned: int = Field(
        ...,
        description="Points earned for this answer"
    )
    new_score: int = Field(
        ...,
        description="Participant's total score after this answer"
    )
    correct_answer: Optional[Dict[str, Any]] = Field(
        None,
        description="Correct answer (only if settings allow immediate reveal)"
    )
    explanation: Optional[str] = Field(
        None,
        description="Question explanation (if available and settings allow)"
    )


# =============================================================================
# LEADERBOARD SCHEMAS
# =============================================================================

class LeaderboardEntry(BaseModel):
    """Schema for a single leaderboard entry."""
    participant_id: str
    name: str
    score: int
    correct_answers: int
    rank: int


class LeaderboardResponse(BaseModel):
    """
    Schema for leaderboard response.
    Shows top 10 + current user's position.
    """
    top_participants: List[LeaderboardEntry] = Field(
        ...,
        description="Top 10 participants by score"
    )
    user_rank: Optional[int] = Field(
        None,
        description="Current user's rank (if participating)"
    )
    user_score: Optional[int] = Field(
        None,
        description="Current user's score (if participating)"
    )
    total_participants: int


# =============================================================================
# ROOM CODE VALIDATION SCHEMAS
# =============================================================================

class RoomCodeValidationRequest(BaseModel):
    """Schema for room code validation request."""
    room_code: str = Field(..., min_length=6, max_length=6)


class RoomCodeValidationResponse(BaseModel):
    """
    Schema for room code validation response.
    Provides session info if valid.
    """
    valid: bool
    session_id: Optional[str] = None
    quiz_title: Optional[str] = None
    quiz_description: Optional[str] = None
    status: Optional[SessionStatus] = None
    participant_count: Optional[int] = None


# =============================================================================
# ANALYTICS SCHEMAS
# =============================================================================

class QuestionAnalytics(BaseModel):
    """Schema for question-level analytics."""
    question_id: str
    question_text: str
    total_responses: int
    correct_percentage: float
    average_time_ms: int
    answer_distribution: Dict[str, int] = Field(
        ...,
        description="Distribution of answers (option_id -> count)"
    )


class SessionAnalytics(BaseModel):
    """Schema for session-level analytics."""
    session_id: str
    quiz_title: str
    total_participants: int
    completed_participants: int
    average_score: float
    median_score: float
    highest_score: int
    lowest_score: int
    average_time_ms: int
    question_analytics: List[QuestionAnalytics]


# =============================================================================
# EXPORT SCHEMAS
# =============================================================================

class ExportFormat(str, Enum):
    """Supported export formats."""
    CSV = "csv"
    JSON = "json"


class ExportRequest(BaseModel):
    """Schema for data export request."""
    format: ExportFormat = Field(default=ExportFormat.CSV)
    include_answers: bool = Field(
        default=True,
        description="Include individual answer data"
    )


# =============================================================================
# ERROR SCHEMAS (for consistent error responses)
# =============================================================================

class ErrorDetail(BaseModel):
    """Schema for error details."""
    field: Optional[str] = Field(None, description="Field that caused error")
    message: str = Field(..., description="Error message")
    code: Optional[str] = Field(None, description="Error code")


class ErrorResponse(BaseModel):
    """Schema for error responses."""
    detail: Union[str, List[ErrorDetail]]


# =============================================================================
# WEBSOCKET MESSAGE SCHEMAS
# =============================================================================

class WSMessageType(str, Enum):
    """WebSocket message types."""
    PARTICIPANT_JOINED = "participant_joined"
    PARTICIPANT_LEFT = "participant_left"
    QUIZ_STARTED = "quiz_started"
    NEW_QUESTION = "new_question"
    QUESTION_ENDED = "question_ended"
    ANSWER_RESULT = "answer_result"
    LEADERBOARD_UPDATE = "leaderboard_update"
    QUIZ_ENDED = "quiz_ended"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    RECONNECT_SYNC = "reconnect_sync"


class WSMessage(BaseModel):
    """Base schema for WebSocket messages."""
    type: WSMessageType
    payload: Dict[str, Any]


# Export all schemas for easy importing
__all__ = [
    # Enums
    "QuestionType",
    "QuizStatus",
    "SessionStatus",
    # Settings
    "QuizSettingsSchema",
    # Questions
    "QuestionBase",
    "QuestionCreate",
    "QuestionUpdate",
    "QuestionResponse",
    "QuestionReorder",
    # Quizzes
    "QuizBase",
    "QuizCreate",
    "QuizUpdate",
    "QuizSummary",
    "QuizDetail",
    # Sessions
    "SessionCreate",
    "SessionSummary",
    "SessionDetail",
    "SessionControl",
    # Participants
    "ParticipantJoinRequest",
    "ParticipantJoinResponse",
    "ParticipantSummary",
    "ParticipantDetail",
    # Answers
    "AnswerSubmission",
    "AnswerResult",
    # Leaderboard
    "LeaderboardEntry",
    "LeaderboardResponse",
    # Room Code
    "RoomCodeValidationRequest",
    "RoomCodeValidationResponse",
    # Analytics
    "QuestionAnalytics",
    "SessionAnalytics",
    # Export
    "ExportFormat",
    "ExportRequest",
    # Errors
    "ErrorDetail",
    "ErrorResponse",
    # WebSocket
    "WSMessageType",
    "WSMessage",
]
