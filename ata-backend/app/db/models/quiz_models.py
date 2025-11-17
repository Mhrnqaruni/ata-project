"""
Quiz System Database Models

This module defines all SQLAlchemy ORM models for the quiz system:
1. Quiz - Quiz definitions created by teachers
2. QuizQuestion - Individual questions within quizzes
3. QuizSession - Live quiz session instances
4. QuizParticipant - Participants in sessions (students OR guests)
5. QuizResponse - Individual answer submissions

Key design decisions (research-backed):
- JSONB columns for flexible question types (PostgreSQL)
- Soft delete for quizzes (preserve analytics)
- Check constraints for data integrity
- Composite indexes for performance
- GDPR compliance with anonymization support
- Guest user support via dual-identity pattern
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey,
    CheckConstraint, Index, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..base_class import Base


class Quiz(Base):
    """
    Represents a quiz created by a teacher.

    A quiz is a collection of questions that can be published and
    run in multiple live sessions. Supports soft delete to preserve
    historical data for analytics.
    """
    __tablename__ = "quizzes"

    # ===== PRIMARY KEY =====
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # ===== OWNERSHIP & ASSOCIATION =====
    # Every quiz is owned by a user (teacher)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Optional association with a class
    class_id = Column(String, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True)

    # ===== QUIZ CONTENT =====
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # JSONB column for flexible settings (time limits, shuffle options, etc.)
    # Example: {"shuffle_questions": true, "shuffle_answers": false, "show_correct_answers": true}
    settings = Column(JSONB, nullable=False, server_default='{}')

    # ===== STATUS & LIFECYCLE =====
    # Status: draft, published, archived
    status = Column(String(20), nullable=False, default="draft", index=True)

    # Soft delete support (preserve historical data)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Track the most recent room code used (for quick rejoin)
    last_room_code = Column(String(10), nullable=True, index=True)

    # ===== TIMESTAMPS =====
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # ===== RELATIONSHIPS =====
    # Back-reference to the user who owns this quiz
    owner = relationship("User", back_populates="quizzes")

    # One-to-many relationship with questions (ordered by order_index)
    questions = relationship(
        "QuizQuestion",
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="QuizQuestion.order_index"
    )

    # One-to-many relationship with sessions
    sessions = relationship(
        "QuizSession",
        back_populates="quiz",
        cascade="all, delete-orphan"
    )

    # ===== INDEXES =====
    __table_args__ = (
        # Composite index for common query: user's non-deleted quizzes by status
        Index(
            "idx_quizzes_user_status_not_deleted",
            user_id, status,
            postgresql_where=(deleted_at.is_(None))
        ),
        # Index for class association (non-deleted quizzes)
        Index(
            "idx_quizzes_class_not_deleted",
            class_id,
            postgresql_where=(deleted_at.is_(None))
        ),
    )

    def __repr__(self):
        return f"<Quiz(id={self.id}, title='{self.title}', status='{self.status}')>"


class QuizQuestion(Base):
    """
    Represents a single question within a quiz.

    Supports multiple question types with flexible options stored in JSONB:
    - multiple_choice: options = ["A", "B", "C"], correct_answer = ["A"]
    - true_false: options = [], correct_answer = [true]
    - short_answer: options = [], correct_answer = ["keyword1", "keyword2"]
    - poll: options = ["A", "B"], correct_answer = [] (no correct answer)
    """
    __tablename__ = "quiz_questions"

    # ===== PRIMARY KEY =====
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # ===== FOREIGN KEYS =====
    quiz_id = Column(String, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)

    # ===== QUESTION CONTENT =====
    # Question type: multiple_choice, true_false, short_answer, poll
    question_type = Column(String(20), nullable=False, index=True)

    # The actual question text
    question_text = Column(Text, nullable=False)

    # JSONB column for flexible options based on question type
    # multiple_choice: ["Option A", "Option B", "Option C", "Option D"]
    # true_false: [] (not needed)
    # short_answer: [] (not needed)
    # poll: ["Option A", "Option B", "Option C"]
    options = Column(JSONB, nullable=False, server_default='[]')

    # JSONB column for correct answer(s)
    # multiple_choice: ["A"] or [0] (index)
    # true_false: [true] or [false]
    # short_answer: ["keyword1", "keyword2", "keyword3"]
    # poll: [] (no correct answer)
    correct_answer = Column(JSONB, nullable=False, server_default='[]')

    # ===== SCORING & TIMING =====
    # Points awarded for correct answer
    points = Column(Integer, nullable=False, default=10)

    # Time limit for this question (seconds), null = no limit
    time_limit_seconds = Column(Integer, nullable=True)

    # ===== ORDERING =====
    # Questions are displayed in order (0-indexed)
    order_index = Column(Integer, nullable=False, default=0)

    # ===== OPTIONAL METADATA =====
    # Optional explanation shown after answer is submitted
    explanation = Column(Text, nullable=True)

    # Future: media URL for images/videos
    media_url = Column(String, nullable=True)

    # ===== TIMESTAMPS =====
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # ===== RELATIONSHIPS =====
    quiz = relationship("Quiz", back_populates="questions")

    # One-to-many relationship with responses
    responses = relationship(
        "QuizResponse",
        back_populates="question",
        cascade="all, delete-orphan"
    )

    # ===== INDEXES =====
    __table_args__ = (
        # Composite index for retrieving questions in order
        Index("idx_quiz_questions_quiz_order", quiz_id, order_index),
    )

    def __repr__(self):
        return f"<QuizQuestion(id={self.id}, type='{self.question_type}', text='{self.question_text[:50]}...')>"


class QuizSession(Base):
    """
    Represents a live quiz session (instance of a quiz being run).

    A quiz can have multiple sessions over time. Each session has a unique
    room code that participants use to join.
    """
    __tablename__ = "quiz_sessions"

    # ===== PRIMARY KEY =====
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # ===== FOREIGN KEYS =====
    # The quiz being run
    quiz_id = Column(String, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)

    # The user (teacher) hosting the session
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # NEW: Class association (denormalized from quiz for performance)
    # Allows quick roster lookups without joining through quizzes table
    class_id = Column(String, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True)

    # ===== SESSION IDENTITY =====
    # Unique room code for participants to join (e.g., "AB3K7Q")
    room_code = Column(String(10), nullable=False, unique=True, index=True)

    # ===== SESSION STATE =====
    # Status: waiting, active, completed, cancelled
    status = Column(String(20), nullable=False, default="waiting", index=True)

    # Current question index (0-indexed), null = not started
    current_question_index = Column(Integer, nullable=True, default=None)

    # Snapshot of quiz config at session creation (JSONB)
    # Prevents changes to quiz from affecting active session
    config_snapshot = Column(JSONB, nullable=False, server_default='{}')

    # ===== TIMING & TIMEOUTS =====
    # Session timeout (hours) - auto-end after this period
    timeout_hours = Column(Integer, nullable=False, default=2)

    # When the session was started (status changed to active)
    started_at = Column(DateTime(timezone=True), nullable=True)

    # When the session ended (status changed to completed/cancelled)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    # Auto-ended due to timeout (for analytics)
    auto_ended_at = Column(DateTime(timezone=True), nullable=True)

    # When the current question was started (for time limit enforcement)
    question_started_at = Column(DateTime(timezone=True), nullable=True)

    # ===== TIMESTAMPS =====
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # ===== RELATIONSHIPS =====
    quiz = relationship("Quiz", back_populates="sessions")
    host = relationship("User")

    # NEW: Class relationship (if session is for a specific class)
    class_ = relationship("Class", back_populates="quiz_sessions")

    # One-to-many relationship with participants
    participants = relationship(
        "QuizParticipant",
        back_populates="session",
        cascade="all, delete-orphan"
    )

    # One-to-many relationship with responses
    responses = relationship(
        "QuizResponse",
        back_populates="session",
        cascade="all, delete-orphan"
    )

    # NEW: One-to-many relationship with roster entries
    roster_entries = relationship(
        "QuizSessionRoster",
        back_populates="session",
        cascade="all, delete-orphan"
    )

    # NEW: One-to-many relationship with outsider students
    outsider_students = relationship(
        "QuizOutsiderStudent",
        back_populates="session",
        cascade="all, delete-orphan"
    )

    # ===== INDEXES =====
    __table_args__ = (
        # Composite index for finding active sessions
        Index("idx_quiz_sessions_status_created", status, created_at),
        # Index for user's sessions
        Index("idx_quiz_sessions_user_status", user_id, status),
    )

    def __repr__(self):
        return f"<QuizSession(id={self.id}, room_code='{self.room_code}', status='{self.status}')>"


class QuizParticipant(Base):
    """
    Represents a participant in a quiz session.

    Supports THREE IDENTITY TYPES:
    1. Registered student (has account): student_id set, guest_name/guest_token NULL
    2. Pure guest (anonymous): guest_name/guest_token set, student_id NULL
    3. Identified guest (NEW - student without account): ALL three fields set
       - Students provide name + student_id but don't need an account
       - Common for K-12 quiz participation
       - student_id is arbitrary string (not FK to students table)

    Check constraint ensures one of these three identity patterns is used.
    """
    __tablename__ = "quiz_participants"

    # ===== PRIMARY KEY =====
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # ===== FOREIGN KEYS =====
    session_id = Column(String, ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    # ===== TRIPLE IDENTITY PATTERN =====
    # Student ID (can be from school system, not necessarily in students table)
    # Used for: (1) Registered students (with account) OR (2) Identified guests (without account)
    student_id = Column(String, nullable=True, index=True)

    # For guest users (not registered)
    guest_name = Column(String(50), nullable=True)
    guest_token = Column(String(64), nullable=True, unique=True, index=True)  # 32 bytes = 64 hex chars

    # ===== SCORING =====
    # Cached score (updated on each answer submission)
    score = Column(Integer, nullable=False, default=0)

    # Count of correct answers
    correct_answers = Column(Integer, nullable=False, default=0)

    # Total time taken across all questions (milliseconds)
    total_time_ms = Column(Integer, nullable=False, default=0)

    # ===== STATUS =====
    # Is the participant currently active (connected)?
    is_active = Column(Boolean, nullable=False, default=True)

    # ===== GDPR COMPLIANCE =====
    # Timestamp when guest data was anonymized (GDPR)
    anonymized_at = Column(DateTime(timezone=True), nullable=True)

    # ===== NEW: ROSTER TRACKING =====
    # Quick flag for filtering outsiders (students not on expected roster)
    is_outsider = Column(Boolean, nullable=False, default=False, index=True)

    # Link to roster entry if student was on expected roster
    roster_entry_id = Column(String, ForeignKey("quiz_session_roster.id", ondelete="SET NULL"), nullable=True)

    # ===== TIMESTAMPS =====
    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Last heartbeat/activity timestamp
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # ===== RELATIONSHIPS =====
    session = relationship("QuizSession", back_populates="participants")

    # NOTE: student_id is NO LONGER a foreign key (after migration dfcbca98dcdf)
    # It can be:
    # 1. A reference to students.id (for registered students)
    # 2. An arbitrary school student ID (for identified guests)
    # Therefore, we CANNOT define a relationship here.
    # Use db.get_student_by_student_id(participant.student_id) if you need the Student object.

    # One-to-many relationship with responses
    responses = relationship(
        "QuizResponse",
        back_populates="participant",
        cascade="all, delete-orphan"
    )

    # NEW: Link back to roster entry (if participant was on expected roster)
    roster_entry = relationship(
        "QuizSessionRoster",
        back_populates="participant",
        foreign_keys=[roster_entry_id],
        uselist=False
    )

    # NEW: Link to outsider record (if participant is an outsider)
    outsider_record = relationship(
        "QuizOutsiderStudent",
        back_populates="participant",
        uselist=False
    )

    # ===== CONSTRAINTS & INDEXES =====
    __table_args__ = (
        # CHECK constraint: Three identity types allowed (updated in migration dfcbca98dcdf)
        # 1. Registered student: student_id, no guest fields
        # 2. Pure guest: guest_name + guest_token, no student_id
        # 3. Identified guest: ALL three fields (student_id + guest_name + guest_token)
        # NOTE: This constraint is defined in migration, keeping here for documentation
        # The actual constraint is applied by Alembic migration dfcbca98dcdf
        CheckConstraint(
            "(student_id IS NOT NULL AND guest_name IS NULL AND guest_token IS NULL) OR "
            "(student_id IS NULL AND guest_name IS NOT NULL AND guest_token IS NOT NULL) OR "
            "(student_id IS NOT NULL AND guest_name IS NOT NULL AND guest_token IS NOT NULL)",
            name="chk_participant_identity"
        ),
        # Composite index for leaderboard queries (session + score descending)
        Index("idx_participants_session_score", session_id, score.desc()),
        # Index for active participants
        Index("idx_participants_session_active", session_id, is_active),
        # Index for GDPR cleanup job (find old guests)
        Index(
            "idx_participants_gdpr_cleanup",
            joined_at, anonymized_at,
            postgresql_where=(guest_token.isnot(None))
        ),
    )

    def __repr__(self):
        identity = f"student_id={self.student_id}" if self.student_id else f"guest='{self.guest_name}'"
        return f"<QuizParticipant(id={self.id}, {identity}, score={self.score})>"


class QuizSessionRoster(Base):
    """
    Snapshot of expected students for a quiz session.

    Created when a session starts from the class roster. Provides an immutable
    record of which students were expected to attend, tracks who actually joined,
    and handles roster changes (students added/dropped after quiz creation).
    """
    __tablename__ = "quiz_session_roster"

    # ===== PRIMARY KEY =====
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # ===== FOREIGN KEYS =====
    session_id = Column(String, ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)

    # ===== STUDENT INFO (DENORMALIZED) =====
    # Denormalized for performance - avoid joins when displaying roster
    student_name = Column(String, nullable=False)
    student_school_id = Column(String, nullable=False)  # The studentId field from students table

    # ===== ENROLLMENT STATUS =====
    # Tracks roster changes: 'expected' (on roster at creation), 'added' (added later), 'dropped' (removed from class)
    enrollment_status = Column(String(20), nullable=False, default="expected")

    # ===== ATTENDANCE TRACKING =====
    joined = Column(Boolean, nullable=False, default=False, index=True)
    joined_at = Column(DateTime(timezone=True), nullable=True)

    # ===== PARTICIPANT LINK =====
    # Links to the actual participant record when student joins
    participant_id = Column(String, ForeignKey("quiz_participants.id", ondelete="SET NULL"), nullable=True)

    # ===== TIMESTAMPS =====
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # ===== RELATIONSHIPS =====
    session = relationship("QuizSession", back_populates="roster_entries")
    student = relationship("Student")
    participant = relationship("QuizParticipant", back_populates="roster_entry", foreign_keys=[participant_id])

    # ===== CONSTRAINTS & INDEXES =====
    __table_args__ = (
        # Unique constraint: one roster entry per student per session
        UniqueConstraint("session_id", "student_id", name="uq_session_student"),
        # Composite index for joined students queries
        Index("idx_session_roster_joined", "session_id", "joined"),
    )

    def __repr__(self):
        status = "joined" if self.joined else "absent"
        return f"<QuizSessionRoster(student='{self.student_name}', status='{status}')>"


class QuizOutsiderStudent(Base):
    """
    Tracks students who joined a quiz session but weren't on the expected roster.

    Used for:
    - Security auditing (unauthorized access attempts)
    - Analytics (students joining wrong quizzes)
    - Teacher review and approval
    - Compliance and reporting
    """
    __tablename__ = "quiz_outsider_students"

    # ===== PRIMARY KEY =====
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # ===== FOREIGN KEYS =====
    session_id = Column(String, ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    participant_id = Column(String, ForeignKey("quiz_participants.id", ondelete="CASCADE"), nullable=False, unique=True)

    # ===== STUDENT INFO =====
    # The student ID they entered when joining (may not match any student in system)
    student_school_id = Column(String, nullable=False, index=True)

    # The name they provided
    guest_name = Column(String, nullable=False)

    # ===== DETECTION INFO =====
    # Why they were flagged as outsider:
    # - 'not_in_class': Student ID found in DB but not in this class
    # - 'no_class_set': Quiz has no class_id (all participants are "outsiders")
    # - 'student_not_found': Student ID doesn't exist in any class
    detection_reason = Column(String(50), nullable=False)

    # ===== TEACHER REVIEW =====
    flagged_by_teacher = Column(Boolean, nullable=False, default=False)
    teacher_notes = Column(Text, nullable=True)

    # ===== TIMESTAMPS =====
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # ===== RELATIONSHIPS =====
    session = relationship("QuizSession", back_populates="outsider_students")
    participant = relationship("QuizParticipant", back_populates="outsider_record", foreign_keys=[participant_id])

    # ===== CONSTRAINTS =====
    __table_args__ = (
        # Unique constraint: one outsider record per participant per session
        UniqueConstraint("session_id", "participant_id", name="uq_session_outsider"),
    )

    def __repr__(self):
        return f"<QuizOutsiderStudent(name='{self.guest_name}', student_id='{self.student_school_id}', reason='{self.detection_reason}')>"


class QuizResponse(Base):
    """
    Represents a single answer submission from a participant.

    Stores the answer, correctness, points earned, and timing data.
    Used for both real-time scoring and post-session analytics.
    """
    __tablename__ = "quiz_responses"

    # ===== PRIMARY KEY =====
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # ===== FOREIGN KEYS =====
    session_id = Column(String, ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    participant_id = Column(String, ForeignKey("quiz_participants.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(String, ForeignKey("quiz_questions.id", ondelete="CASCADE"), nullable=False, index=True)

    # ===== ANSWER DATA =====
    # The participant's answer (JSONB for flexibility)
    # multiple_choice: ["A"] or [0]
    # true_false: [true] or [false]
    # short_answer: ["my answer text"]
    # poll: ["B"]
    answer = Column(JSONB, nullable=False)

    # ===== GRADING =====
    # Was the answer correct? (NULL for poll questions)
    is_correct = Column(Boolean, nullable=True)

    # Points earned for this answer
    points_earned = Column(Integer, nullable=False, default=0)

    # ===== TIMING =====
    # Time taken to answer this question (milliseconds)
    # Measured server-side for security
    time_taken_ms = Column(Integer, nullable=False)

    # ===== TIMESTAMPS =====
    answered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # ===== RELATIONSHIPS =====
    session = relationship("QuizSession", back_populates="responses")
    participant = relationship("QuizParticipant", back_populates="responses")
    question = relationship("QuizQuestion", back_populates="responses")

    # ===== CONSTRAINTS & INDEXES =====
    __table_args__ = (
        # UNIQUE constraint: one answer per participant per question
        UniqueConstraint("session_id", "participant_id", "question_id", name="uq_one_answer_per_participant_question"),
        # Composite index for leaderboard calculation
        Index("idx_responses_leaderboard", session_id, is_correct, points_earned),
        # Index for question analytics
        Index("idx_responses_question_analytics", question_id, is_correct, time_taken_ms),
    )

    def __repr__(self):
        return f"<QuizResponse(id={self.id}, correct={self.is_correct}, points={self.points_earned})>"
