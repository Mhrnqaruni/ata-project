"""
Quiz System Pydantic Schemas

This module defines all Pydantic models (schemas) used for request validation
and response serialization in the Quiz system API.

Schema Categories:
1. Enums - Type-safe enumeration values
2. Quiz Schemas - Quiz CRUD operations
3. Question Schemas - Question definitions with validation
4. Session Schemas - Live quiz session management
5. Participant Schemas - Student and guest participant data
6. Answer Schemas - Response submission and grading
7. Analytics Schemas - Statistics and insights
8. WebSocket Schemas - Real-time message formats

Research-backed validation:
- String-based enums for JSON compatibility
- Field-level validation for data integrity
- Optional fields with sensible defaults
- Comprehensive type hints for IDE support
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict
from uuid import UUID


# ==================== ENUMS ====================

class QuestionType(str, Enum):
    """
    Question type enumeration.
    Uses str inheritance for JSON serialization compatibility.
    """
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    POLL = "poll"


class QuizStatus(str, Enum):
    """Quiz publication status."""
    DRAFT = "draft"
    PUBLISHED = "published"
    COMPLETED = "completed"  # Quiz has been used and completed
    ARCHIVED = "archived"


class SessionStatus(str, Enum):
    """Live quiz session status."""
    WAITING = "waiting"      # Created but not started
    ACTIVE = "active"        # In progress
    COMPLETED = "completed"  # Finished normally
    CANCELLED = "cancelled"  # Ended prematurely


class WSMessageType(str, Enum):
    """WebSocket message types for real-time communication."""
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


# ==================== BASE SCHEMAS ====================

class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
        str_strip_whitespace=True
    )


# ==================== QUIZ QUESTION SCHEMAS ====================

class QuizQuestionBase(BaseSchema):
    """Base schema for quiz questions (shared fields)."""
    question_type: QuestionType = Field(..., description="Type of question")
    question_text: str = Field(..., min_length=1, max_length=2000, description="Question text")
    options: List[str] = Field(default_factory=list, description="Answer options for multiple choice/poll")
    correct_answer: List[Union[str, bool, int]] = Field(default_factory=list, description="Correct answer(s)")
    points: int = Field(default=10, ge=1, le=100, description="Points awarded for correct answer")
    time_limit_seconds: Optional[int] = Field(None, ge=5, le=300, description="Time limit in seconds")
    explanation: Optional[str] = Field(None, max_length=1000, description="Explanation shown after answer")
    media_url: Optional[str] = Field(None, max_length=500, description="URL to image/video")
    order_index: int = Field(default=0, ge=0, description="Display order (0-indexed)")

    @field_validator('options')
    @classmethod
    def validate_options(cls, v: List[str], info) -> List[str]:
        """Validate options based on question type."""
        question_type = info.data.get('question_type')

        if question_type == QuestionType.MULTIPLE_CHOICE:
            if len(v) < 2 or len(v) > 6:
                raise ValueError("Multiple choice questions must have 2-6 options")
        elif question_type == QuestionType.POLL:
            if len(v) < 2 or len(v) > 10:
                raise ValueError("Poll questions must have 2-10 options")
        elif question_type in [QuestionType.TRUE_FALSE, QuestionType.SHORT_ANSWER]:
            if len(v) > 0:
                raise ValueError(f"{question_type} questions should not have options")

        return v

    @field_validator('correct_answer')
    @classmethod
    def validate_correct_answer(cls, v: List[Any], info) -> List[Any]:
        """Validate correct answer based on question type."""
        question_type = info.data.get('question_type')

        if question_type == QuestionType.POLL:
            # Polls have no correct answer
            if len(v) > 0:
                raise ValueError("Poll questions should not have correct answers")
        elif question_type == QuestionType.MULTIPLE_CHOICE:
            if len(v) != 1:
                raise ValueError("Multiple choice questions must have exactly 1 correct answer")
        elif question_type == QuestionType.TRUE_FALSE:
            if len(v) != 1 or not isinstance(v[0], bool):
                raise ValueError("True/false questions must have exactly 1 boolean answer")
        elif question_type == QuestionType.SHORT_ANSWER:
            if len(v) < 1:
                raise ValueError("Short answer questions must have at least 1 keyword")

        return v


class QuizQuestionCreate(QuizQuestionBase):
    """Schema for creating a new question."""
    pass


class QuizQuestionUpdate(BaseSchema):
    """Schema for updating an existing question (all fields optional)."""
    question_type: Optional[QuestionType] = None
    question_text: Optional[str] = Field(None, min_length=1, max_length=2000)
    options: Optional[List[str]] = None
    correct_answer: Optional[List[Union[str, bool, int]]] = None
    points: Optional[int] = Field(None, ge=1, le=100)
    time_limit_seconds: Optional[int] = Field(None, ge=5, le=300)
    explanation: Optional[str] = Field(None, max_length=1000)
    media_url: Optional[str] = Field(None, max_length=500)
    order_index: Optional[int] = Field(None, ge=0)


class QuizQuestionResponse(QuizQuestionBase):
    """Schema for question responses (includes database fields)."""
    id: str
    quiz_id: str
    created_at: datetime

    # Exclude correct_answer for participants (add it in admin view)
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class QuizQuestionAdminResponse(QuizQuestionResponse):
    """Schema for question responses with correct answers (admin only)."""
    pass


class QuizQuestionParticipantResponse(BaseSchema):
    """Schema for questions shown to participants (no correct answer)."""
    id: str
    question_type: QuestionType
    question_text: str
    options: List[str]
    points: int
    time_limit_seconds: Optional[int]
    media_url: Optional[str]
    order_index: int


# ==================== QUIZ SCHEMAS ====================

class QuizBase(BaseSchema):
    """Base schema for quizzes (shared fields)."""
    title: str = Field(..., min_length=1, max_length=200, description="Quiz title")
    description: Optional[str] = Field(None, max_length=5000, description="Quiz description")
    settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Quiz settings (shuffle, time limits, etc.)"
    )
    class_id: Optional[str] = Field(None, description="Associated class ID")


class QuizCreate(QuizBase):
    """Schema for creating a new quiz."""
    questions: List[QuizQuestionCreate] = Field(
        default_factory=list,
        max_length=100,
        description="Initial questions"
    )


class QuizUpdate(BaseSchema):
    """Schema for updating an existing quiz (all fields optional)."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    settings: Optional[Dict[str, Any]] = None
    status: Optional[QuizStatus] = None
    class_id: Optional[str] = None


class QuizSummary(QuizBase):
    """Schema for quiz list responses (summary view)."""
    id: str
    user_id: UUID
    status: QuizStatus
    question_count: int = Field(default=0, description="Number of questions")
    created_at: datetime
    updated_at: datetime
    last_room_code: Optional[str] = None


class QuizDetail(QuizBase):
    """Schema for detailed quiz responses (includes questions)."""
    id: str
    user_id: UUID
    status: QuizStatus
    questions: List[QuizQuestionAdminResponse]
    created_at: datetime
    updated_at: datetime
    last_room_code: Optional[str] = None
    deleted_at: Optional[datetime] = None


# ==================== SESSION SCHEMAS ====================

class QuizSessionCreate(BaseSchema):
    """Schema for creating a new quiz session."""
    quiz_id: str = Field(..., description="Quiz to run")
    timeout_hours: int = Field(default=2, ge=1, le=24, description="Session timeout")


class QuizSessionStart(BaseSchema):
    """Schema for starting a session (moving from waiting to active)."""
    pass  # No additional fields needed


class QuizSessionEnd(BaseSchema):
    """Schema for ending a session."""
    reason: Optional[str] = Field(None, max_length=200, description="Reason for ending")


class QuizSessionSummary(BaseSchema):
    """Schema for session list responses."""
    id: str
    quiz_id: str
    quiz_title: str
    room_code: str
    status: SessionStatus
    participant_count: int = Field(default=0, description="Number of participants")
    current_question_index: Optional[int] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime


class QuizSessionDetail(BaseSchema):
    """Schema for detailed session responses."""
    id: str
    quiz_id: str
    quiz_title: str
    user_id: UUID
    room_code: str
    status: SessionStatus
    current_question_index: Optional[int] = None
    config_snapshot: Dict[str, Any]
    timeout_hours: int
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    auto_ended_at: Optional[datetime] = None
    created_at: datetime
    participant_count: int = 0
    questions: List[QuizQuestionAdminResponse] = Field(default_factory=list)


# ==================== PARTICIPANT SCHEMAS ====================

class ParticipantJoinRequest(BaseSchema):
    """Schema for joining a quiz session."""
    room_code: str = Field(..., min_length=6, max_length=10, description="Session room code")
    # For registered students (optional)
    student_id: Optional[str] = Field(None, description="Student ID if registered")
    # For guest users (optional)
    guest_name: Optional[str] = Field(None, min_length=1, max_length=50, description="Guest name")

    @field_validator('guest_name')
    @classmethod
    def sanitize_guest_name(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize guest name."""
        if v:
            # Remove control characters
            v = ''.join(char for char in v if ord(char) >= 32)
            # Trim and collapse whitespace
            v = ' '.join(v.split())
        return v or None


class ParticipantJoinResponse(BaseSchema):
    """Schema for successful join response with nested objects."""

    class SessionInfo(BaseSchema):
        """Nested session information."""
        id: str
        room_code: str
        status: SessionStatus
        current_question_index: Optional[int] = None

    class ParticipantInfo(BaseSchema):
        """Nested participant information."""
        id: str
        display_name: str
        guest_name: Optional[str] = None
        student_id: Optional[str] = None
        is_guest: bool

    session: SessionInfo
    participant: ParticipantInfo
    guest_token: Optional[str] = Field(None, description="Token for guest authentication")


class ParticipantSummary(BaseSchema):
    """Schema for participant in lists."""
    id: str
    display_name: str
    is_guest: bool
    score: int
    correct_answers: int
    total_time_ms: int
    is_active: bool
    joined_at: datetime


class ParticipantDetail(ParticipantSummary):
    """Schema for detailed participant view."""
    session_id: str
    student_id: Optional[str] = None
    last_seen_at: datetime


class LeaderboardEntry(BaseSchema):
    """Schema for leaderboard entries."""
    rank: int
    participant_id: str
    display_name: str
    score: int
    correct_answers: int
    total_time_ms: int
    is_active: bool


class LeaderboardResponse(BaseSchema):
    """Schema for leaderboard response."""
    session_id: str
    entries: List[LeaderboardEntry]
    total_participants: int
    updated_at: datetime


# ==================== ANSWER SCHEMAS ====================

class AnswerSubmission(BaseSchema):
    """Schema for submitting an answer."""
    question_id: str = Field(..., description="Question being answered")
    answer: Union[List[str], List[bool], List[int]] = Field(..., description="Participant's answer")
    time_taken_ms: int = Field(..., ge=0, le=600000, description="Time taken (client-reported)")


class AnswerResult(BaseSchema):
    """Schema for answer grading result."""
    response_id: str
    question_id: str
    is_correct: Optional[bool] = Field(None, description="Correctness (null for polls)")
    points_earned: int
    correct_answer: Optional[List[Union[str, bool, int]]] = Field(None, description="Shown after submission")
    explanation: Optional[str] = None
    time_taken_ms: int


class AnswerSubmissionBatch(BaseSchema):
    """Schema for submitting multiple answers at once (future feature)."""
    answers: List[AnswerSubmission]


# ==================== ANALYTICS SCHEMAS ====================

class QuestionAnalytics(BaseSchema):
    """Schema for question-level analytics."""
    question_id: str
    question_text: str
    question_type: QuestionType
    total_responses: int
    correct_responses: int
    accuracy_rate: float = Field(..., ge=0.0, le=1.0, description="Correct rate (0-1)")
    average_time_ms: float
    options_distribution: Optional[Dict[str, int]] = Field(
        None,
        description="Distribution of answers for multiple choice/poll"
    )


class SessionAnalytics(BaseSchema):
    """Schema for session-level analytics."""
    session_id: str
    quiz_title: str
    room_code: str
    status: SessionStatus
    total_participants: int
    active_participants: int
    total_questions: int
    questions_completed: int
    average_score: float
    median_score: float
    highest_score: int
    lowest_score: int
    average_accuracy_rate: float
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[float] = None
    question_analytics: List[QuestionAnalytics] = Field(default_factory=list)


class ParticipantAnalytics(BaseSchema):
    """Schema for individual participant analytics."""
    participant_id: str
    display_name: str
    score: int
    correct_answers: int
    total_answers: int
    accuracy_rate: float
    total_time_ms: int
    average_time_per_question_ms: float
    rank: int
    responses: List[AnswerResult] = Field(default_factory=list)


# ==================== WEBSOCKET SCHEMAS ====================

class WSMessage(BaseSchema):
    """Base schema for WebSocket messages."""
    type: WSMessageType
    timestamp: datetime = Field(default_factory=datetime.now)
    data: Dict[str, Any] = Field(default_factory=dict)


class WSParticipantJoined(BaseSchema):
    """WebSocket message: participant joined."""
    type: WSMessageType = WSMessageType.PARTICIPANT_JOINED
    data: ParticipantSummary


class WSParticipantLeft(BaseSchema):
    """WebSocket message: participant left."""
    type: WSMessageType = WSMessageType.PARTICIPANT_LEFT
    data: Dict[str, str]  # {"participant_id": "...", "display_name": "..."}


class WSQuestionStarted(BaseSchema):
    """WebSocket message: question started."""
    type: WSMessageType = WSMessageType.QUESTION_STARTED
    data: Dict[str, Any]  # {"question": QuizQuestionParticipantResponse, "index": int}


class WSQuestionEnded(BaseSchema):
    """WebSocket message: question ended."""
    type: WSMessageType = WSMessageType.QUESTION_ENDED
    data: Dict[str, Any]  # {"question_id": "...", "index": int}


class WSAnswerReceived(BaseSchema):
    """WebSocket message: answer received (broadcast to host only)."""
    type: WSMessageType = WSMessageType.ANSWER_RECEIVED
    data: Dict[str, Any]  # {"participant_id": "...", "question_id": "...", "is_correct": bool}


class WSLeaderboardUpdate(BaseSchema):
    """WebSocket message: leaderboard update."""
    type: WSMessageType = WSMessageType.LEADERBOARD_UPDATE
    data: LeaderboardResponse


class WSSessionEnded(BaseSchema):
    """WebSocket message: session ended."""
    type: WSMessageType = WSMessageType.SESSION_ENDED
    data: Dict[str, Any]  # {"reason": "...", "final_leaderboard": LeaderboardResponse}


class WSError(BaseSchema):
    """WebSocket message: error."""
    type: WSMessageType = WSMessageType.ERROR
    data: Dict[str, str]  # {"message": "...", "code": "..."}


class WSHeartbeatPing(BaseSchema):
    """WebSocket message: server ping."""
    type: WSMessageType = WSMessageType.HEARTBEAT_PING
    data: Dict[str, Any] = Field(default_factory=dict)


class WSHeartbeatPong(BaseSchema):
    """WebSocket message: client pong."""
    type: WSMessageType = WSMessageType.HEARTBEAT_PONG
    data: Dict[str, Any] = Field(default_factory=dict)


class WSSubmitAnswer(BaseSchema):
    """WebSocket message: client submits answer."""
    type: WSMessageType = WSMessageType.SUBMIT_ANSWER
    data: AnswerSubmission


class WSRequestCurrentState(BaseSchema):
    """WebSocket message: client requests current session state."""
    type: WSMessageType = WSMessageType.REQUEST_CURRENT_STATE
    data: Dict[str, Any] = Field(default_factory=dict)


# ==================== UTILITY SCHEMAS ====================

class ErrorResponse(BaseSchema):
    """Standard error response schema."""
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class SuccessResponse(BaseSchema):
    """Standard success response schema."""
    message: str
    data: Optional[Dict[str, Any]] = None


class PaginatedResponse(BaseSchema):
    """Paginated response schema."""
    items: List[Any]
    total: int
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    total_pages: int
