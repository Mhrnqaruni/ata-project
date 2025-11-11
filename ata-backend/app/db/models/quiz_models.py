# /ata-backend/app/db/models/quiz_models.py

"""
This module defines all SQLAlchemy ORM models for the Quiz system.

The Quiz system supports interactive, real-time quizzes where teachers can create
quizzes and students (registered or guest) can participate in live sessions with
instant feedback and leaderboards.

Models:
    - Quiz: Top-level quiz definition created by teachers
    - QuizQuestion: Individual questions within a quiz
    - QuizSession: Live quiz session instances
    - QuizParticipant: Participants in a session (registered students or guests)
    - QuizResponse: Individual answer submissions from participants
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, CheckConstraint, Index, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..base_class import Base


class Quiz(Base):
    """
    SQLAlchemy model representing a quiz created by a teacher.

    A quiz is a collection of questions that can be published and run as live
    sessions. Quizzes support soft deletion to preserve historical data.
    """
    __tablename__ = "quizzes"

    # --- Primary Key ---
    id = Column(String, primary_key=True, index=True)

    # --- Ownership (Foreign Key to User) ---
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # --- Optional Class Association ---
    # Quizzes can optionally be associated with a specific class
    class_id = Column(
        String,
        ForeignKey("classes.id"),
        nullable=True,
        index=True
    )

    # --- Quiz Metadata ---
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    instructions = Column(Text, nullable=True)

    # --- Quiz Status ---
    # Values: 'draft', 'published', 'archived'
    status = Column(String, nullable=False, default="draft", index=True)

    # --- Room Code for Sessions ---
    # 6-character alphanumeric code for students to join sessions
    # This is generated when a session is started, not at quiz creation
    # Kept on quiz for quick reference, but actual active code is in QuizSession
    last_room_code = Column(String(6), nullable=True, index=True)

    # --- Quiz Settings (JSONB) ---
    # Stores quiz-level configuration as JSONB for flexibility and performance
    # Example structure:
    # {
    #     "auto_advance": false,
    #     "show_leaderboard": true,
    #     "shuffle_questions": false,
    #     "shuffle_options": true,
    #     "allow_review": true,
    #     "max_participants": null,
    #     "question_time_default": 30
    # }
    settings = Column(JSONB, nullable=False, default={})

    # --- Soft Delete Support ---
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # --- Timestamps ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # --- Relationships ---
    owner = relationship("User", back_populates="quizzes")
    class_ = relationship("Class", backref="quizzes")  # backref since Class doesn't define this
    questions = relationship(
        "QuizQuestion",
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="QuizQuestion.order_index"
    )
    sessions = relationship(
        "QuizSession",
        back_populates="quiz",
        cascade="all, delete-orphan"
    )

    # --- Indexes ---
    __table_args__ = (
        # Composite index for common query: user's quizzes by status, excluding deleted
        Index('idx_quizzes_user_status_not_deleted', user_id, status,
              postgresql_where=(deleted_at.is_(None))),
        # Index for class association
        Index('idx_quizzes_class_not_deleted', class_id,
              postgresql_where=(deleted_at.is_(None))),
    )


class QuizQuestion(Base):
    """
    SQLAlchemy model representing a single question within a quiz.

    Questions support multiple types (multiple choice, true/false, short answer, poll)
    with type-specific configuration stored in JSONB columns for flexibility.
    """
    __tablename__ = "quiz_questions"

    # --- Primary Key ---
    id = Column(String, primary_key=True, index=True)

    # --- Foreign Key to Quiz ---
    quiz_id = Column(
        String,
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # --- Question Content ---
    question_text = Column(Text, nullable=False)

    # --- Question Type ---
    # Values: 'multiple_choice', 'true_false', 'short_answer', 'poll'
    question_type = Column(String, nullable=False, index=True)

    # --- Question Order ---
    # Used for sorting questions in quiz. 0-indexed.
    order_index = Column(Integer, nullable=False)

    # --- Scoring ---
    points = Column(Integer, nullable=False, default=10)

    # --- Time Limit ---
    # Time limit in seconds for this specific question
    # Null means use quiz default
    time_limit = Column(Integer, nullable=True)

    # --- Question Options (JSONB) ---
    # Type-specific configuration stored as JSONB
    # Structure varies by question_type:
    #
    # For multiple_choice:
    # {
    #     "choices": [
    #         {"id": "a", "text": "Option A"},
    #         {"id": "b", "text": "Option B"},
    #         {"id": "c", "text": "Option C"},
    #         {"id": "d", "text": "Option D"}
    #     ],
    #     "shuffle_options": true
    # }
    #
    # For true_false:
    # {} (empty, no options needed)
    #
    # For short_answer:
    # {
    #     "max_length": 200,
    #     "placeholder": "Enter your answer..."
    # }
    #
    # For poll:
    # {
    #     "choices": [
    #         {"id": "opt1", "text": "Option 1"},
    #         {"id": "opt2", "text": "Option 2"}
    #     ]
    # }
    options = Column(JSONB, nullable=False, default={})

    # --- Correct Answer (JSONB) ---
    # Stores the correct answer in a type-specific format
    #
    # For multiple_choice:
    # {"answer": "b"}
    #
    # For true_false:
    # {"answer": true}
    #
    # For short_answer:
    # {
    #     "answer": "expected text",
    #     "case_sensitive": false,
    #     "keywords": ["word1", "word2", "word3"],
    #     "min_keywords": 2
    # }
    #
    # For poll:
    # {"participation_points": 5}  (no correct answer, just participation)
    correct_answer = Column(JSONB, nullable=False, default={})

    # --- Explanation ---
    # Optional explanation shown after question is answered
    explanation = Column(Text, nullable=True)

    # --- Media ---
    # Future feature: URL to image/video for question
    media_url = Column(String, nullable=True)

    # --- Timestamps ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # --- Relationships ---
    quiz = relationship("Quiz", back_populates="questions")
    responses = relationship(
        "QuizResponse",
        back_populates="question",
        cascade="all, delete-orphan"
    )

    # --- Indexes ---
    __table_args__ = (
        # Composite index for fetching quiz questions in order
        Index('idx_quiz_questions_quiz_order', quiz_id, order_index),
        # Index for question type filtering
        Index('idx_quiz_questions_type', question_type),
    )


class QuizSession(Base):
    """
    SQLAlchemy model representing a live quiz session.

    A session is an instance of a quiz being actively run by a teacher.
    Students join the session via room code and answer questions in real-time.
    """
    __tablename__ = "quiz_sessions"

    # --- Primary Key ---
    id = Column(String, primary_key=True, index=True)

    # --- Foreign Keys ---
    quiz_id = Column(
        String,
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # User who started/hosts this session (teacher)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # --- Session Status ---
    # Values: 'waiting', 'in_progress', 'completed', 'cancelled'
    status = Column(String, nullable=False, default="waiting", index=True)

    # --- Room Code ---
    # Unique 6-character alphanumeric code for joining this session
    room_code = Column(String(6), unique=True, nullable=False, index=True)

    # --- Current Question ---
    # Tracks which question is currently active (0-indexed)
    current_question_index = Column(Integer, nullable=False, default=0)

    # --- Timestamps ---
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # --- Session Configuration Snapshot (JSONB) ---
    # Snapshot of quiz settings at session start
    # This ensures session behavior doesn't change if quiz is edited mid-session
    session_config = Column(JSONB, nullable=False, default={})

    # --- Timeout Tracking ---
    # Session will auto-end after this many hours (from quiz_config)
    timeout_hours = Column(Integer, nullable=False, default=2)
    auto_ended_at = Column(DateTime(timezone=True), nullable=True)

    # --- Relationships ---
    quiz = relationship("Quiz", back_populates="sessions")
    host = relationship("User", backref="hosted_quiz_sessions")
    participants = relationship(
        "QuizParticipant",
        back_populates="session",
        cascade="all, delete-orphan"
    )
    responses = relationship(
        "QuizResponse",
        back_populates="session",
        cascade="all, delete-orphan"
    )

    # --- Indexes ---
    __table_args__ = (
        # Index for active sessions
        Index('idx_quiz_sessions_status', status),
        # Index for finding user's sessions
        Index('idx_quiz_sessions_user_status', user_id, status),
        # Index for room code lookups
        Index('idx_quiz_sessions_room_code', room_code),
    )


class QuizParticipant(Base):
    """
    SQLAlchemy model representing a participant in a quiz session.

    Participants can be either:
    1. Registered students (linked via student_id)
    2. Guest users (identified by guest_name and guest_token)

    For GDPR compliance, guest data is anonymized after 30 days.
    """
    __tablename__ = "quiz_participants"

    # --- Primary Key ---
    id = Column(String, primary_key=True, index=True)

    # --- Foreign Key to Session ---
    session_id = Column(
        String,
        ForeignKey("quiz_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # --- Participant Identity ---
    # Either student_id OR guest_name must be set, not both
    # Registered student
    student_id = Column(
        String,
        ForeignKey("students.id"),
        nullable=True,
        index=True
    )

    # Guest user name
    guest_name = Column(String, nullable=True)

    # --- Guest Authentication ---
    # Secure token for guest participants (32 characters)
    # Used for session-specific authentication
    guest_token = Column(String, unique=True, nullable=True, index=True)

    # --- Participation Tracking ---
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    left_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    # --- Score Tracking ---
    # These are cached values updated on each answer submission
    score = Column(Integer, nullable=False, default=0)
    correct_answers = Column(Integer, nullable=False, default=0)
    total_time_ms = Column(Integer, nullable=False, default=0)

    # --- GDPR Compliance ---
    # When guest data is anonymized, this timestamp is set
    anonymized_at = Column(DateTime(timezone=True), nullable=True)

    # --- Relationships ---
    session = relationship("QuizSession", back_populates="participants")
    student = relationship("Student", backref="quiz_participations")
    responses = relationship(
        "QuizResponse",
        back_populates="participant",
        cascade="all, delete-orphan"
    )

    # --- Constraints ---
    __table_args__ = (
        # Ensure either student_id OR guest_name is set, not both
        CheckConstraint(
            '(student_id IS NOT NULL AND guest_name IS NULL) OR '
            '(student_id IS NULL AND guest_name IS NOT NULL)',
            name='chk_participant_identity'
        ),
        # Composite index for session participant lists
        Index('idx_participants_session_active', session_id, is_active),
        # Index for GDPR cleanup job
        Index('idx_participants_anonymization',
              guest_name, joined_at,
              postgresql_where=(guest_name.isnot(None)) & (anonymized_at.is_(None))),
        # Index for leaderboard queries
        Index('idx_participants_session_score', session_id, score, total_time_ms),
    )


class QuizResponse(Base):
    """
    SQLAlchemy model representing a participant's answer to a question.

    Stores the answer, correctness, points earned, and timing data.
    Each participant can submit one response per question.
    """
    __tablename__ = "quiz_responses"

    # --- Primary Key ---
    id = Column(String, primary_key=True, index=True)

    # --- Foreign Keys ---
    session_id = Column(
        String,
        ForeignKey("quiz_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    participant_id = Column(
        String,
        ForeignKey("quiz_participants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    question_id = Column(
        String,
        ForeignKey("quiz_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # --- Answer Data (JSONB) ---
    # Structure varies by question type:
    #
    # For multiple_choice:
    # {"selected": "b"}
    #
    # For true_false:
    # {"selected": true}
    #
    # For short_answer:
    # {"text": "user's answer text"}
    #
    # For poll:
    # {"selected": "option_id"}
    answer = Column(JSONB, nullable=False)

    # --- Grading ---
    # Null for poll questions (no correct/incorrect)
    is_correct = Column(Boolean, nullable=True)

    # Points earned for this answer
    points_earned = Column(Integer, nullable=False, default=0)

    # --- Timing ---
    # Milliseconds taken to answer (from question start to submission)
    time_taken_ms = Column(Integer, nullable=False)

    # --- Timestamp ---
    answered_at = Column(DateTime(timezone=True), server_default=func.now())

    # --- Relationships ---
    session = relationship("QuizSession", back_populates="responses")
    participant = relationship("QuizParticipant", back_populates="responses")
    question = relationship("QuizQuestion", back_populates="responses")

    # --- Indexes ---
    __table_args__ = (
        # Composite index for leaderboard calculation
        Index('idx_responses_leaderboard', session_id, participant_id, is_correct),
        # Index for question analytics
        Index('idx_responses_question_correct', question_id, is_correct),
        # Unique constraint: one answer per participant per question
        Index('idx_responses_unique_answer', session_id, participant_id, question_id, unique=True),
    )


# Add relationship to User model (this will be imported in base.py)
# This allows accessing user.quizzes
# We can't import User here due to circular dependency, so we use string reference
# The relationship will be added when User imports this module via base.py
