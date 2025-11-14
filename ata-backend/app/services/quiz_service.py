"""
Quiz Business Logic Service

This module implements all business logic for quiz management:
- Quiz CRUD with validation
- Question management with type-specific rules
- Room code generation with collision handling
- Answer grading (multiple choice, true/false, short answer, poll)
- Analytics calculation

Security: All operations require user_id validation via repository layer.
Pattern: Service methods accept primitive types/dicts and return ORM models or dicts.
"""

from typing import List, Dict, Optional, Tuple
import string
import re
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Core dependencies
from .database_service import DatabaseService
from ..core.quiz_auth import (
    generate_room_code,
    is_valid_room_code_format,
    generate_guest_token,
    handle_duplicate_name,
    sanitize_participant_name
)
from ..core.quiz_config import quiz_settings
from ..core.quiz_shuffling import apply_quiz_randomization
from ..models.quiz_model import (
    QuestionType, QuizStatus, SessionStatus,
    QuizCreate, QuizUpdate, QuizQuestionCreate, QuizQuestionUpdate
)

# For type hints
from ..db.models.quiz_models import Quiz, QuizQuestion, QuizSession, QuizParticipant, QuizResponse


# ==================== QUIZ CRUD OPERATIONS ====================

def get_all_quizzes_with_counts(user_id: str, db: DatabaseService,
                                status: Optional[str] = None,
                                class_id: Optional[str] = None) -> List[Dict]:
    """
    Get all quizzes with question counts and session info.

    Args:
        user_id: User ID
        db: Database service
        status: Optional status filter
        class_id: Optional class filter

    Returns:
        List of quiz summaries with additional metadata
    """
    quizzes = db.get_all_quizzes(user_id, status, class_id)

    summaries = []
    for quiz in quizzes:
        question_count = db.get_question_count(quiz.id, user_id)
        summaries.append({
            "id": quiz.id,
            "user_id": quiz.user_id,
            "class_id": quiz.class_id,
            "title": quiz.title,
            "description": quiz.description,
            "settings": quiz.settings,
            "status": quiz.status,
            "question_count": question_count,
            "last_room_code": quiz.last_room_code,
            "created_at": quiz.created_at,
            "updated_at": quiz.updated_at
        })

    return summaries


def create_quiz_with_questions(quiz_data: QuizCreate, user_id: str, db: DatabaseService) -> Quiz:
    """
    Create a new quiz with initial questions.

    Args:
        quiz_data: Quiz creation data
        user_id: User ID (owner)
        db: Database service

    Returns:
        Created Quiz instance

    Raises:
        ValueError: If validation fails
    """
    # Validate question count
    if len(quiz_data.questions) > quiz_settings.MAX_QUESTIONS_PER_QUIZ:
        raise ValueError(
            f"Quiz cannot have more than {quiz_settings.MAX_QUESTIONS_PER_QUIZ} questions"
        )

    # Create quiz
    quiz_dict = {
        "user_id": user_id,
        "title": quiz_data.title,
        "description": quiz_data.description,
        "settings": quiz_data.settings,
        "status": "draft",  # Always start as draft
        "class_id": quiz_data.class_id
    }
    quiz = db.create_quiz(quiz_dict)

    # Add questions
    for index, question_data in enumerate(quiz_data.questions):
        question_dict = {
            "quiz_id": quiz.id,
            "question_type": question_data.question_type,
            "question_text": question_data.question_text,
            "options": question_data.options,
            "correct_answer": question_data.correct_answer,
            "points": question_data.points,
            "time_limit_seconds": question_data.time_limit_seconds,
            "order_index": index,
            "explanation": question_data.explanation,
            "media_url": question_data.media_url
        }
        db.add_question_to_quiz(question_dict)

    return quiz


def update_quiz_with_validation(quiz_id: str, user_id: str, update_data: QuizUpdate,
                                db: DatabaseService) -> Optional[Quiz]:
    """
    Update a quiz with validation.

    Args:
        quiz_id: Quiz ID
        user_id: User ID
        update_data: Update data
        db: Database service

    Returns:
        Updated Quiz or None if not found

    Raises:
        ValueError: If validation fails
    """
    # Verify quiz exists
    quiz = db.get_quiz_by_id(quiz_id, user_id)
    if not quiz:
        return None

    # Build update dictionary (only include non-None fields)
    update_dict = {}
    if update_data.title is not None:
        update_dict["title"] = update_data.title
    if update_data.description is not None:
        update_dict["description"] = update_data.description
    if update_data.settings is not None:
        update_dict["settings"] = update_data.settings
    if update_data.status is not None:
        # Validate status transitions
        if update_data.status == QuizStatus.PUBLISHED:
            # Ensure quiz has at least one question
            question_count = db.get_question_count(quiz_id, user_id)
            if question_count == 0:
                raise ValueError("Cannot publish quiz with no questions")
        update_dict["status"] = update_data.status
    if update_data.class_id is not None:
        update_dict["class_id"] = update_data.class_id

    return db.update_quiz(quiz_id, user_id, update_dict)


def validate_publish_quiz(quiz_id: str, user_id: str, db: DatabaseService) -> Tuple[bool, Optional[str]]:
    """
    Validate if a quiz can be published.

    Args:
        quiz_id: Quiz ID
        user_id: User ID
        db: Database service

    Returns:
        Tuple of (is_valid, error_message)
    """
    quiz = db.get_quiz_by_id(quiz_id, user_id)
    if not quiz:
        return False, "Quiz not found"

    # Check if quiz has questions
    questions = db.get_questions_by_quiz_id(quiz_id, user_id)
    if not questions:
        return False, "Quiz must have at least one question"

    # Validate all questions
    for question in questions:
        if question.question_type == QuestionType.MULTIPLE_CHOICE:
            if not question.options or len(question.options) < 2:
                return False, f"Question '{question.question_text}' must have at least 2 options"
            if not question.correct_answer or len(question.correct_answer) != 1:
                return False, f"Question '{question.question_text}' must have exactly 1 correct answer"

        elif question.question_type == QuestionType.TRUE_FALSE:
            if not question.correct_answer or len(question.correct_answer) != 1:
                return False, f"Question '{question.question_text}' must have exactly 1 correct answer"

        elif question.question_type == QuestionType.SHORT_ANSWER:
            if not question.correct_answer or len(question.correct_answer) < 1:
                return False, f"Question '{question.question_text}' must have at least 1 keyword"

        elif question.question_type == QuestionType.POLL:
            if not question.options or len(question.options) < 2:
                return False, f"Poll question '{question.question_text}' must have at least 2 options"

    return True, None


# ==================== SESSION MANAGEMENT ====================

def generate_unique_room_code(db: DatabaseService, max_attempts: int = 10) -> str:
    """
    Generate a unique room code with collision handling.

    Args:
        db: Database service
        max_attempts: Maximum generation attempts

    Returns:
        Unique room code

    Raises:
        RuntimeError: If failed to generate unique code
    """
    for attempt in range(max_attempts):
        room_code = generate_room_code()
        if not db.check_room_code_exists(room_code):
            return room_code

    raise RuntimeError(
        f"Failed to generate unique room code after {max_attempts} attempts"
    )


def create_session_with_room_code(quiz_id: str, user_id: str, db: DatabaseService,
                                  timeout_hours: int = 2) -> QuizSession:
    """
    Create a new quiz session with auto-generated room code.

    Args:
        quiz_id: Quiz ID
        user_id: User ID (host)
        db: Database service
        timeout_hours: Session timeout in hours

    Returns:
        Created QuizSession

    Raises:
        ValueError: If quiz validation fails
        RuntimeError: If room code generation fails
    """
    logger.info(f"[SessionCreate] Creating session for quiz {quiz_id}, user {user_id}")

    # Validate quiz exists and is published
    quiz = db.get_quiz_by_id(quiz_id, user_id)
    if not quiz:
        logger.warning(f"[SessionCreate] Quiz not found: {quiz_id}")
        raise ValueError("Quiz not found")

    if quiz.status != QuizStatus.PUBLISHED:
        logger.warning(f"[SessionCreate] Quiz not published: {quiz_id}, status={quiz.status}")
        raise ValueError("Can only create sessions for published quizzes")

    # Validate quiz has questions
    questions = db.get_questions_by_quiz_id(quiz_id, user_id)
    if not questions:
        logger.warning(f"[SessionCreate] Quiz has no questions: {quiz_id}")
        raise ValueError("Cannot start session for quiz with no questions")

    logger.info(f"[SessionCreate] Quiz validated: {len(questions)} questions")

    # Check concurrent session limit
    active_sessions = db.get_active_quiz_sessions(user_id)
    if len(active_sessions) >= quiz_settings.MAX_CONCURRENT_SESSIONS_PER_USER:
        logger.warning(f"[SessionCreate] User {user_id} has too many active sessions: {len(active_sessions)}")
        raise ValueError(
            f"Maximum of {quiz_settings.MAX_CONCURRENT_SESSIONS_PER_USER} concurrent sessions allowed"
        )

    # Generate unique room code
    room_code = generate_unique_room_code(db)
    logger.info(f"[SessionCreate] Generated room code: {room_code}")

    # Create config snapshot (freeze quiz state)
    config_snapshot = {
        "quiz_title": quiz.title,
        "quiz_settings": quiz.settings,
        "total_questions": len(questions)
    }

    # Create session
    session_data = {
        "quiz_id": quiz_id,
        "user_id": user_id,
        "room_code": room_code,
        "status": SessionStatus.WAITING,
        "current_question_index": None,  # Not started yet
        "config_snapshot": config_snapshot,
        "timeout_hours": timeout_hours
    }
    session = db.create_quiz_session(session_data)

    # Update quiz with last room code
    db.update_last_room_code(quiz_id, user_id, room_code)

    logger.info(f"[SessionCreate] Success: session_id={session.id}, room_code={room_code}")

    return session


def start_session(session_id: str, user_id: str, db: DatabaseService) -> QuizSession:
    """
    Start a quiz session (move from waiting to active).

    Args:
        session_id: Session ID
        user_id: User ID (host)
        db: Database service

    Returns:
        Updated QuizSession

    Raises:
        ValueError: If validation fails
    """
    logger.info(f"[SessionStart] Starting session {session_id} for user {user_id}")

    session = db.get_quiz_session_by_id(session_id, user_id)
    if not session:
        logger.warning(f"[SessionStart] Session not found: {session_id}")
        raise ValueError("Session not found")

    if session.status != SessionStatus.WAITING:
        logger.warning(f"[SessionStart] Invalid status: session={session_id}, status={session.status}")
        raise ValueError(f"Can only start sessions in 'waiting' status, current: {session.status}")

    # Start at first question
    now = datetime.now()
    session = db.update_quiz_session(session_id, user_id, {
        "status": SessionStatus.ACTIVE,
        "started_at": now,
        "current_question_index": 0,
        "question_started_at": now  # Track when question 1 started for time limit enforcement
    })

    logger.info(f"[SessionStart] Success: session_id={session_id}, room_code={session.room_code}")

    return session


def end_session(session_id: str, user_id: str, db: DatabaseService, reason: str = "completed") -> QuizSession:
    """
    End a quiz session.

    Args:
        session_id: Session ID
        user_id: User ID (host)
        db: Database service
        reason: Reason for ending (completed/cancelled)

    Returns:
        Updated QuizSession

    Raises:
        ValueError: If validation fails
    """
    logger.info(f"[SessionEnd] Ending session {session_id}, reason={reason}")

    session = db.get_quiz_session_by_id(session_id, user_id)
    if not session:
        logger.warning(f"[SessionEnd] Session not found: {session_id}")
        raise ValueError("Session not found")

    if session.status not in [SessionStatus.WAITING, SessionStatus.ACTIVE]:
        logger.warning(f"[SessionEnd] Invalid status: session={session_id}, status={session.status}")
        raise ValueError(f"Cannot end session in '{session.status}' status")

    status = SessionStatus.COMPLETED if reason == "completed" else SessionStatus.CANCELLED

    result = db.update_quiz_session_status(session_id, user_id, status)

    # FIX: Update quiz status to "completed" when session successfully completes
    if status == SessionStatus.COMPLETED:
        try:
            db.update_quiz_status(session.quiz_id, user_id, "completed")
            logger.info(f"[SessionEnd] Updated quiz {session.quiz_id} status to completed")
        except Exception as e:
            # Don't fail the session end if quiz update fails
            logger.warning(f"[SessionEnd] Failed to update quiz status: {e}")

    logger.info(f"[SessionEnd] Success: session_id={session_id}, final_status={status}")

    return result


# ==================== AUTO-ADVANCE WITH SCHEDULER ====================

def schedule_auto_advance(
    session_id: str,
    time_limit_seconds: int,
    cooldown_seconds: int,
    db: DatabaseService
) -> str:
    """
    Schedule automatic advancement to the next question.

    Uses APScheduler to run auto_advance_question after time_limit + cooldown.

    Args:
        session_id: Session ID
        time_limit_seconds: Question time limit (0 if no limit)
        cooldown_seconds: Delay before advancing (default 10)
        db: Database service

    Returns:
        Job ID for cancellation

    Note: Stores job ID in session.config_snapshot for cancellation
    """
    from app.core.scheduler import scheduler
    from datetime import timedelta

    # Calculate total wait time
    total_wait = (time_limit_seconds or 0) + cooldown_seconds

    logger.info(f"[AutoAdvance] Scheduling auto-advance for session {session_id} in {total_wait}s")

    # Schedule job
    run_time = datetime.now() + timedelta(seconds=total_wait)
    job_id = f"auto_advance_{session_id}_{datetime.now().timestamp()}"

    job = scheduler.add_job(
        func=auto_advance_question,
        trigger='date',
        run_date=run_time,
        args=[session_id],
        id=job_id,
        name=f"Auto-advance session {session_id}",
        replace_existing=False
    )

    logger.info(f"[AutoAdvance] Scheduled job {job_id} to run at {run_time}")

    return job_id


def cancel_auto_advance(session_id: str, db: DatabaseService) -> None:
    """
    Cancel scheduled auto-advance for a session.

    Args:
        session_id: Session ID
        db: Database service

    Note: Reads job_id from session.config_snapshot['auto_advance_job_id']
    """
    from app.core.scheduler import scheduler

    session = db.get_quiz_session_by_id(session_id)
    if not session:
        return

    config = session.config_snapshot or {}
    job_id = config.get('auto_advance_job_id')

    if job_id:
        try:
            scheduler.remove_job(job_id)
            logger.info(f"[AutoAdvance] Cancelled job {job_id} for session {session_id}")
        except Exception as e:
            # Job already executed or doesn't exist
            logger.warning(f"[AutoAdvance] Failed to cancel job {job_id}: {e}")


def auto_advance_question(session_id: str):
    """
    Background job to automatically advance to the next question.

    This runs in scheduler context with its own DB session.

    Args:
        session_id: Session ID

    Note: Only advances if session is still active and has more questions
    """
    from app.db.database import SessionLocal
    from app.routers.quiz_websocket_router import connection_manager
    from app.core.quiz_websocket import build_question_started_message
    import asyncio

    logger.info(f"[AutoAdvance] Executing auto-advance for session {session_id}")

    db_session = SessionLocal()
    try:
        db = DatabaseService(db_session)

        # Get session
        session = db.get_quiz_session_by_id(session_id)
        if not session:
            logger.warning(f"[AutoAdvance] Session not found: {session_id}")
            return

        # Safety check: only advance if still active
        if session.status != SessionStatus.ACTIVE:
            logger.warning(f"[AutoAdvance] Session not active: {session_id}, status={session.status}")
            return

        # Get quiz and questions
        quiz = db.get_quiz_by_id(session.quiz_id, session.user_id)
        questions = db.get_questions_by_quiz_id(session.quiz_id, session.user_id)

        # Check if there are more questions
        next_index = (session.current_question_index or -1) + 1
        if next_index >= len(questions):
            # No more questions, end session automatically
            logger.info(f"[AutoAdvance] No more questions, ending session {session_id}")
            end_session(session_id, session.user_id, db, reason="completed")

            # Broadcast session_ended
            asyncio.run(connection_manager.broadcast_to_room(
                session_id,
                {
                    "type": "session_ended",
                    "session_id": str(session.id),
                    "reason": "completed",
                    "final_status": "completed"
                }
            ))
            return

        # Advance to next question
        session = db.move_to_next_question(session_id, session.user_id)

        # Broadcast new question
        current_question = questions[session.current_question_index]
        asyncio.run(connection_manager.broadcast_to_room(
            session_id,
            build_question_started_message(
                question_id=str(current_question.id),
                question_text=current_question.question_text,
                question_type=current_question.question_type,
                options=current_question.options if current_question.options else [],
                points=current_question.points,
                order_index=session.current_question_index,
                time_limit_seconds=current_question.time_limit_seconds
            )
        ))

        # Broadcast updated leaderboard
        leaderboard_entries = []
        leaderboard_participants = db.get_leaderboard(session_id, limit=100)
        for rank, p in enumerate(leaderboard_participants, start=1):
            display_name = "Unknown"
            if p.guest_name:
                display_name = p.guest_name
            elif p.student_id:
                try:
                    student = db.get_student_by_student_id(p.student_id)
                    display_name = student.name if student else f"Student {p.student_id}"
                except:
                    display_name = f"Student {p.student_id}"

            leaderboard_entries.append({
                "rank": rank,
                "participant_id": str(p.id),
                "display_name": display_name,
                "score": p.score,
                "correct_answers": p.correct_answers,
                "total_time_ms": p.total_time_ms,
                "is_active": p.is_active
            })

        asyncio.run(connection_manager.broadcast_to_room(
            session_id,
            {
                "type": "leaderboard_update",
                "leaderboard": leaderboard_entries
            }
        ))

        # Schedule next auto-advance if enabled
        config = session.config_snapshot or {}
        if config.get("auto_advance_enabled"):
            job_id = schedule_auto_advance(
                session_id,
                current_question.time_limit_seconds or 0,
                config.get("cooldown_seconds", 10),
                db
            )
            # Update job_id in config
            config["auto_advance_job_id"] = job_id
            db.update_quiz_session(session_id, session.user_id, {"config_snapshot": config})

        logger.info(f"[AutoAdvance] Success: session {session_id} advanced to question {session.current_question_index}")

    except Exception as e:
        logger.error(f"[AutoAdvance] Error in auto-advance: {e}", exc_info=True)
    finally:
        db_session.close()


# ==================== PARTICIPANT MANAGEMENT ====================

def join_session_as_guest(room_code: str, guest_name: str, db: DatabaseService) -> Tuple[QuizParticipant, str]:
    """
    Join a session as a guest user.

    Args:
        room_code: Session room code
        guest_name: Guest's display name
        db: Database service

    Returns:
        Tuple of (QuizParticipant, guest_token)

    Raises:
        ValueError: If validation fails
    """
    logger.info(f"[GuestJoin] Guest '{guest_name}' attempting to join room: {room_code}")

    # Validate room code format
    if not is_valid_room_code_format(room_code):
        logger.warning(f"[GuestJoin] Invalid room code format: {room_code}")
        raise ValueError("Invalid room code format")

    # Find session
    session = db.get_quiz_session_by_room_code(room_code)
    if not session:
        logger.warning(f"[GuestJoin] Session not found for room code: {room_code}")
        raise ValueError("Session not found")

    if session.status not in [SessionStatus.WAITING, SessionStatus.ACTIVE]:
        logger.warning(f"[GuestJoin] Invalid session status: room={room_code}, status={session.status}")
        raise ValueError(f"Cannot join session in '{session.status}' status")

    # Check participant limit
    participants = db.get_participants_by_session(session.id, active_only=True)
    if len(participants) >= quiz_settings.MAX_PARTICIPANTS_PER_SESSION:
        logger.warning(f"[GuestJoin] Session full: room={room_code}, participants={len(participants)}")
        raise ValueError(
            f"Session is full (max {quiz_settings.MAX_PARTICIPANTS_PER_SESSION} participants)"
        )

    # Sanitize and handle duplicate names
    guest_name = sanitize_participant_name(guest_name)
    existing_names = db.get_participant_names_in_session(session.id)
    unique_name = handle_duplicate_name(guest_name, existing_names)

    if unique_name != guest_name:
        logger.info(f"[GuestJoin] Name modified to ensure uniqueness: '{guest_name}' -> '{unique_name}'")

    # Generate guest token
    guest_token = generate_guest_token()

    # Create participant
    participant_data = {
        "session_id": session.id,
        "student_id": None,
        "guest_name": unique_name,
        "guest_token": guest_token,
        "score": 0,
        "correct_answers": 0,
        "total_time_ms": 0,
        "is_active": True
    }
    participant = db.add_quiz_participant(participant_data)

    logger.info(f"[GuestJoin] Success: participant_id={participant.id}, name={unique_name}, session={session.id}")

    return participant, guest_token


def join_session_as_student(room_code: str, student_id: str, db: DatabaseService) -> QuizParticipant:
    """
    Join a session as a registered student.

    Args:
        room_code: Session room code
        student_id: Student ID
        db: Database service

    Returns:
        QuizParticipant instance

    Raises:
        ValueError: If validation fails
    """
    # Validate room code
    if not is_valid_room_code_format(room_code):
        raise ValueError("Invalid room code format")

    # Find session
    session = db.get_quiz_session_by_room_code(room_code)
    if not session:
        raise ValueError("Session not found")

    if session.status not in [SessionStatus.WAITING, SessionStatus.ACTIVE]:
        raise ValueError(f"Cannot join session in '{session.status}' status")

    # Check if student already joined
    existing = db.get_participant_by_student_in_session(session.id, student_id)
    if existing:
        # Student already joined - return existing participant (allows rejoin)
        logger.info(f"[StudentJoin] Student {student_id} rejoining session {session.id}, is_active={existing.is_active}")

        if not existing.is_active:
            # Reactivate if inactive
            logger.info(f"[StudentJoin] Reactivating participant: student_id={student_id}")
            return db.update_participant(existing.id, {"is_active": True})

        # Return existing participant (allows recovery)
        return existing

    # Check participant limit
    participants = db.get_participants_by_session(session.id, active_only=True)
    if len(participants) >= quiz_settings.MAX_PARTICIPANTS_PER_SESSION:
        raise ValueError(
            f"Session is full (max {quiz_settings.MAX_PARTICIPANTS_PER_SESSION} participants)"
        )

    # Create participant
    participant_data = {
        "session_id": session.id,
        "student_id": student_id,
        "guest_name": None,
        "guest_token": None,
        "score": 0,
        "correct_answers": 0,
        "total_time_ms": 0,
        "is_active": True
    }
    return db.add_quiz_participant(participant_data)


def join_session_as_identified_guest(
    room_code: str,
    student_name: str,
    student_id: str,
    db: DatabaseService
) -> Tuple[QuizParticipant, str]:
    """
    Join a session as an identified guest (student with ID but no account).

    This is the most common flow for K-12 quiz participation:
    - Students don't need accounts
    - They provide their name + student ID from school
    - Teacher can track individual student performance
    - Students are authenticated via guest_token

    Args:
        room_code: Session room code
        student_name: Student's display name
        student_id: Student ID from school (arbitrary string)
        db: Database service

    Returns:
        Tuple of (QuizParticipant, guest_token)

    Raises:
        ValueError: If validation fails
    """
    logger.info(f"[IdentifiedGuestJoin] Student '{student_name}' (ID: {student_id}) attempting to join room: {room_code}")

    # Validate room code format
    if not is_valid_room_code_format(room_code):
        logger.warning(f"[IdentifiedGuestJoin] Invalid room code format: {room_code}")
        raise ValueError("Invalid room code format")

    # Validate student_id format (basic validation)
    if not student_id or len(student_id.strip()) == 0:
        raise ValueError("Student ID cannot be empty")

    student_id = student_id.strip()

    # Find session
    session = db.get_quiz_session_by_room_code(room_code)
    if not session:
        logger.warning(f"[IdentifiedGuestJoin] Session not found for room code: {room_code}")
        raise ValueError("Session not found")

    if session.status not in [SessionStatus.WAITING, SessionStatus.ACTIVE]:
        logger.warning(f"[IdentifiedGuestJoin] Invalid session status: room={room_code}, status={session.status}")
        raise ValueError(f"Cannot join session in '{session.status}' status")

    # Check if student already joined this session
    existing = db.get_participant_by_student_in_session(session.id, student_id)
    if existing:
        # Student already joined - return existing participant and token
        # This allows students to rejoin if they lost their token (cleared browser, different device)
        logger.info(f"[IdentifiedGuestJoin] Student {student_id} rejoining session {session.id}, is_active={existing.is_active}")

        if not existing.is_active:
            # Reactivate if inactive
            logger.info(f"[IdentifiedGuestJoin] Reactivating participant: student_id={student_id}")
            existing = db.update_participant(existing.id, {"is_active": True})

        # Return existing participant and guest_token (allows recovery if token was lost)
        return existing, existing.guest_token

    # Check participant limit
    participants = db.get_participants_by_session(session.id, active_only=True)
    if len(participants) >= quiz_settings.MAX_PARTICIPANTS_PER_SESSION:
        logger.warning(f"[IdentifiedGuestJoin] Session full: room={room_code}, participants={len(participants)}")
        raise ValueError(
            f"Session is full (max {quiz_settings.MAX_PARTICIPANTS_PER_SESSION} participants)"
        )

    # Sanitize name and handle duplicates
    sanitized_name = sanitize_participant_name(student_name)
    existing_names = db.get_participant_names_in_session(session.id)
    unique_name = handle_duplicate_name(sanitized_name, existing_names)

    if unique_name != sanitized_name:
        logger.info(f"[IdentifiedGuestJoin] Name modified to ensure uniqueness: '{sanitized_name}' -> '{unique_name}'")

    # Generate guest token for authentication
    guest_token = generate_guest_token()

    # Create participant with BOTH student_id AND guest info
    participant_data = {
        "session_id": session.id,
        "student_id": student_id,  # For tracking
        "guest_name": unique_name,  # For display
        "guest_token": guest_token,  # For authentication
        "score": 0,
        "correct_answers": 0,
        "total_time_ms": 0,
        "is_active": True
    }
    participant = db.add_quiz_participant(participant_data)

    logger.info(f"[IdentifiedGuestJoin] Success: participant_id={participant.id}, student_id={student_id}, name={unique_name}, session={session.id}")

    return participant, guest_token


# ==================== ANSWER GRADING ====================

def grade_answer(question: QuizQuestion, participant_answer: List) -> Tuple[bool, int]:
    """
    Grade a participant's answer.

    Args:
        question: Question being answered
        participant_answer: Participant's submitted answer

    Returns:
        Tuple of (is_correct, points_earned)
    """
    if question.question_type == QuestionType.POLL:
        # Polls have no correct answer
        return None, 0

    is_correct = False

    if question.question_type == QuestionType.MULTIPLE_CHOICE:
        # Compare selected option
        is_correct = participant_answer == question.correct_answer

    elif question.question_type == QuestionType.TRUE_FALSE:
        # Compare boolean value
        is_correct = participant_answer == question.correct_answer

    elif question.question_type == QuestionType.SHORT_ANSWER:
        # Keyword matching with configurable threshold
        answer_text = str(participant_answer[0]).strip() if participant_answer else ""
        keywords = [str(k).strip() for k in question.correct_answer]

        if quiz_settings.SHORT_ANSWER_CASE_INSENSITIVE:
            answer_text = answer_text.lower()
            keywords = [k.lower() for k in keywords]

        if quiz_settings.SHORT_ANSWER_STRIP_PUNCTUATION:
            answer_text = re.sub(r'[^\w\s]', '', answer_text)
            keywords = [re.sub(r'[^\w\s]', '', k) for k in keywords]

        # Count matching keywords
        matches = sum(1 for keyword in keywords if keyword in answer_text)
        match_ratio = matches / len(keywords) if keywords else 0

        is_correct = match_ratio >= quiz_settings.SHORT_ANSWER_KEYWORD_MATCH_THRESHOLD

    # Award points if correct
    points_earned = question.points if is_correct else 0

    return is_correct, points_earned


def submit_answer_with_grading(participant_id: str, question_id: str, answer: List,
                               time_taken_ms: int, db: DatabaseService) -> Dict:
    """
    Submit and grade an answer.

    Args:
        participant_id: Participant ID
        question_id: Question ID
        answer: Participant's answer
        time_taken_ms: Time taken (milliseconds)
        db: Database service

    Returns:
        Grading result dict

    Raises:
        ValueError: If validation fails
    """
    logger.info(f"[AnswerSubmit] Participant {participant_id} submitting answer for question {question_id}")

    # Get participant
    participant = db.get_participant_by_id(participant_id)
    if not participant:
        logger.warning(f"[AnswerSubmit] Participant not found: {participant_id}")
        raise ValueError("Participant not found")

    if not participant.is_active:
        logger.warning(f"[AnswerSubmit] Participant not active: {participant_id}")
        raise ValueError("Participant is not active")

    # Check if already answered (FIX #9: Duplicate prevention)
    existing = db.get_participant_response_for_question(participant_id, question_id)
    if existing:
        logger.warning(f"[AnswerSubmit] Duplicate answer attempt: participant={participant_id}, question={question_id}")
        raise ValueError("Question already answered")

    # Get question
    question = db.get_question_by_id(question_id)
    if not question:
        logger.warning(f"[AnswerSubmit] Question not found: {question_id}")
        raise ValueError("Question not found")

    # FIX Issue 1: Enforce time limit - reject late submissions
    if question.time_limit_seconds is not None and question.time_limit_seconds > 0:
        # Get session to check when question started
        session = db.get_quiz_session_by_id(participant.session_id)
        if session and session.question_started_at:
            elapsed_seconds = (datetime.now() - session.question_started_at).total_seconds()
            if elapsed_seconds > question.time_limit_seconds:
                logger.warning(
                    f"[AnswerSubmit] Time limit exceeded: "
                    f"participant={participant_id}, question={question_id}, "
                    f"elapsed={elapsed_seconds:.1f}s, limit={question.time_limit_seconds}s"
                )
                raise ValueError("Time limit exceeded for this question")

    logger.info(f"[AnswerSubmit] Grading answer: type={question.question_type}, time={time_taken_ms}ms")

    # Grade answer
    is_correct, points_earned = grade_answer(question, answer)

    logger.info(f"[AnswerSubmit] Grade result: correct={is_correct}, points={points_earned}")

    # Save response
    response_data = {
        "session_id": participant.session_id,
        "participant_id": participant_id,
        "question_id": question_id,
        "answer": answer,
        "is_correct": is_correct,
        "points_earned": points_earned,
        "time_taken_ms": time_taken_ms
    }
    response = db.submit_quiz_response(response_data)

    # Update participant score
    db.update_participant_score(participant_id, points_earned, is_correct or False, time_taken_ms)

    logger.info(f"[AnswerSubmit] Success: response_id={response.id}, participant={participant_id}")

    # Build result
    result = {
        "response_id": response.id,
        "question_id": question_id,
        "is_correct": is_correct,
        "points_earned": points_earned,
        "correct_answer": question.correct_answer if is_correct is not None else None,
        "explanation": question.explanation,
        "time_taken_ms": time_taken_ms
    }

    return result


# ==================== QUESTION DELIVERY WITH RANDOMIZATION ====================

def get_questions_for_participant(session_id: str, participant_id: str, db: DatabaseService) -> List[Dict]:
    """
    Get quiz questions for a participant with randomization applied.

    Applies shuffling based on quiz settings:
    - Question order shuffling
    - Answer option shuffling
    - Participant-specific deterministic seeds

    Args:
        session_id: Session ID
        participant_id: Participant ID
        db: Database service

    Returns:
        List of question dictionaries (participant view, no correct answers)

    Note: Each participant gets questions in their own randomized order
    """
    # Get session
    session = db.get_quiz_session_by_id(session_id)
    if not session:
        raise ValueError("Session not found")

    # Get quiz questions
    quiz = db.get_quiz_by_id(session.quiz_id, session.user_id)
    questions = db.get_questions_by_quiz_id(session.quiz_id, session.user_id)

    # Convert to dictionaries
    question_dicts = []
    for q in questions:
        question_dicts.append({
            "id": q.id,
            "question_type": q.question_type,
            "question_text": q.question_text,
            "options": q.options if q.options else [],
            "correct_answer": q.correct_answer if q.correct_answer else [],
            "points": q.points,
            "time_limit_seconds": q.time_limit_seconds,
            "order_index": q.order_index,
            "explanation": q.explanation,
            "media_url": q.media_url
        })

    # Apply randomization if enabled in quiz settings
    if quiz and quiz.settings:
        randomized = apply_quiz_randomization(
            question_dicts,
            quiz.settings,
            participant_id=participant_id,
            session_id=session_id
        )
    else:
        randomized = question_dicts

    # Remove correct answers for participant view
    for q in randomized:
        q.pop('correct_answer', None)
        q.pop('explanation', None)  # Don't show until after answer

    return randomized


# ==================== ANALYTICS SERVICE FUNCTIONS ====================

def get_session_analytics(session_id: str, user_id: str, db: DatabaseService) -> Dict:
    """
    Calculate comprehensive analytics for a completed quiz session.

    Returns session summary with:
    - Participant statistics (total, active, avg/median/high/low scores)
    - Question completion stats
    - Overall accuracy rate
    - Session duration
    - Question-level analytics

    Args:
        session_id: Session ID
        user_id: User ID (ownership validation)
        db: Database service

    Returns:
        Dictionary matching SessionAnalytics schema

    Raises:
        ValueError: If session not found or user doesn't own it
    """
    logger.info(f"[Analytics] Generating session analytics: session_id={session_id}")

    # Get session with ownership validation
    session = db.get_quiz_session_by_id(session_id, user_id=user_id)
    if not session:
        raise ValueError("Session not found or access denied")

    # Get quiz details
    quiz = db.get_quiz_by_id(session.quiz_id, user_id)
    if not quiz:
        raise ValueError("Quiz not found")

    # Get all participants
    participants = db.get_participants_by_session(session_id, active_only=False)
    total_participants = len(participants)
    active_participants = len([p for p in participants if p.is_active])

    # Get all questions
    questions = db.get_questions_by_quiz_id(session.quiz_id, user_id)
    total_questions = len(questions)

    # Calculate questions completed (based on current_question_index)
    questions_completed = 0
    if session.current_question_index is not None:
        questions_completed = min(session.current_question_index + 1, total_questions)
    elif session.status == SessionStatus.COMPLETED:
        questions_completed = total_questions

    # Calculate participant score statistics
    scores = [p.score for p in participants] if participants else [0]
    average_score = sum(scores) / len(scores) if scores else 0.0

    # Calculate median score
    sorted_scores = sorted(scores)
    n = len(sorted_scores)
    if n == 0:
        median_score = 0.0
    elif n % 2 == 0:
        median_score = (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2.0
    else:
        median_score = float(sorted_scores[n // 2])

    highest_score = max(scores) if scores else 0
    lowest_score = min(scores) if scores else 0

    # Calculate overall accuracy rate
    total_correct = sum(p.correct_answers for p in participants)
    total_responses = sum(len(db.get_responses_by_participant(p.id)) for p in participants)
    average_accuracy_rate = total_correct / total_responses if total_responses > 0 else 0.0

    # Calculate session duration
    duration_minutes = None
    if session.started_at and session.ended_at:
        duration_seconds = (session.ended_at - session.started_at).total_seconds()
        duration_minutes = duration_seconds / 60.0

    # Get question-level analytics
    question_analytics_list = []
    for question in questions:
        q_stats = get_question_analytics_single(question.id, session_id, db)
        question_analytics_list.append(q_stats)

    logger.info(f"[Analytics] Session summary: {total_participants} participants, "
               f"avg_score={average_score:.1f}, accuracy={average_accuracy_rate:.2%}")

    return {
        "session_id": str(session.id),
        "quiz_title": quiz.title,
        "room_code": session.room_code,
        "status": session.status,
        "total_participants": total_participants,
        "active_participants": active_participants,
        "total_questions": total_questions,
        "questions_completed": questions_completed,
        "average_score": round(average_score, 2),
        "median_score": round(median_score, 2),
        "highest_score": highest_score,
        "lowest_score": lowest_score,
        "average_accuracy_rate": round(average_accuracy_rate, 4),
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "duration_minutes": round(duration_minutes, 2) if duration_minutes else None,
        "question_analytics": question_analytics_list
    }


def get_question_analytics_single(question_id: str, session_id: str, db: DatabaseService) -> Dict:
    """
    Calculate analytics for a single question in a session.

    Returns:
    - Total responses
    - Correct count and accuracy rate
    - Average time taken
    - Answer distribution (for multiple choice/poll)

    Args:
        question_id: Question ID
        session_id: Session ID (to filter responses)
        db: Database service

    Returns:
        Dictionary matching QuestionAnalytics schema
    """
    # Get question details
    question = db.get_question_by_id(question_id)
    if not question:
        raise ValueError("Question not found")

    # FIX: Get all responses for this session, then filter by question in Python
    # (DatabaseService doesn't expose db_session, so we use available repository methods)
    all_session_responses = db.get_responses_by_session(session_id)
    responses = [r for r in all_session_responses if r.question_id == question_id]

    total_responses = len(responses)

    if total_responses == 0:
        return {
            "question_id": str(question.id),
            "question_text": question.question_text,
            "question_type": question.question_type,
            "total_responses": 0,
            "correct_responses": 0,
            "accuracy_rate": 0.0,
            "average_time_ms": 0.0,
            "options_distribution": None
        }

    # Calculate correctness stats
    correct_responses = len([r for r in responses if r.is_correct is True])
    accuracy_rate = correct_responses / total_responses if total_responses > 0 else 0.0

    # Calculate average time
    total_time = sum(r.time_taken_ms for r in responses)
    average_time_ms = total_time / total_responses if total_responses > 0 else 0.0

    # Calculate answer distribution for multiple choice and poll questions
    options_distribution = None
    if question.question_type in [QuestionType.MULTIPLE_CHOICE, QuestionType.POLL]:
        distribution = {}
        for response in responses:
            # Answer is stored as JSONB array, e.g., ["A"] or [0]
            answer_value = response.answer[0] if response.answer else None
            if answer_value is not None:
                answer_key = str(answer_value)
                distribution[answer_key] = distribution.get(answer_key, 0) + 1
        options_distribution = distribution

    return {
        "question_id": str(question.id),
        "question_text": question.question_text,
        "question_type": question.question_type,
        "total_responses": total_responses,
        "correct_responses": correct_responses,
        "accuracy_rate": round(accuracy_rate, 4),
        "average_time_ms": round(average_time_ms, 2),
        "options_distribution": options_distribution
    }


def get_participant_analytics_list(session_id: str, user_id: str, db: DatabaseService) -> List[Dict]:
    """
    Get analytics for all participants in a session.

    Returns list sorted by rank (score desc, time asc).

    Args:
        session_id: Session ID
        user_id: User ID (ownership validation)
        db: Database service

    Returns:
        List of dictionaries with participant stats
    """
    logger.info(f"[Analytics] Generating participant analytics list: session_id={session_id}")

    # Validate session ownership
    session = db.get_quiz_session_by_id(session_id, user_id=user_id)
    if not session:
        raise ValueError("Session not found or access denied")

    # Get leaderboard (sorted by score desc, time asc)
    participants = db.get_leaderboard(session_id, limit=1000)

    result = []
    for rank, participant in enumerate(participants, start=1):
        # Get participant responses
        responses = db.get_responses_by_participant(participant.id)
        total_answers = len(responses)

        # Calculate accuracy rate
        accuracy_rate = participant.correct_answers / total_answers if total_answers > 0 else 0.0

        # Calculate average time per question
        avg_time = participant.total_time_ms / total_answers if total_answers > 0 else 0.0

        # Get display name (handle both guest and student)
        display_name = participant.guest_name if participant.guest_name else "Student"
        if participant.student_id and not participant.guest_name:
            # Try to get student name from database
            try:
                student = db.get_student_by_student_id(participant.student_id)
                if student and student.name:
                    display_name = student.name
                else:
                    display_name = f"Student {participant.student_id}"
            except:
                display_name = f"Student {participant.student_id}"

        result.append({
            "participant_id": str(participant.id),
            "display_name": display_name,
            "score": participant.score,
            "correct_answers": participant.correct_answers,
            "total_answers": total_answers,
            "accuracy_rate": round(accuracy_rate, 4),
            "total_time_ms": participant.total_time_ms,
            "average_time_per_question_ms": round(avg_time, 2),
            "rank": rank
        })

    logger.info(f"[Analytics] Generated analytics for {len(result)} participants")
    return result


def get_participant_detail_analytics(participant_id: str, session_id: str, user_id: str, db: DatabaseService) -> Dict:
    """
    Get detailed analytics for a single participant including all their responses.

    Args:
        participant_id: Participant ID
        session_id: Session ID
        user_id: User ID (ownership validation)
        db: Database service

    Returns:
        Dictionary with participant details and all responses

    Raises:
        ValueError: If participant not found or session ownership invalid
    """
    logger.info(f"[Analytics] Getting participant detail: participant_id={participant_id}")

    # Validate session ownership
    session = db.get_quiz_session_by_id(session_id, user_id=user_id)
    if not session:
        raise ValueError("Session not found or access denied")

    # Get participant
    participant = db.get_participant_by_id(participant_id)
    if not participant or participant.session_id != session_id:
        raise ValueError("Participant not found in this session")

    # Get all responses
    responses = db.get_responses_by_participant(participant_id)
    total_answers = len(responses)

    # Calculate accuracy and rank
    accuracy_rate = participant.correct_answers / total_answers if total_answers > 0 else 0.0
    avg_time = participant.total_time_ms / total_answers if total_answers > 0 else 0.0
    rank, total_participants = db.get_participant_rank(participant_id)

    # Get display name
    display_name = participant.guest_name if participant.guest_name else "Student"
    if participant.student_id and not participant.guest_name:
        try:
            student = db.get_student_by_student_id(participant.student_id)
            if student and student.name:
                display_name = student.name
            else:
                display_name = f"Student {participant.student_id}"
        except:
            display_name = f"Student {participant.student_id}"

    # Build response details
    response_list = []
    for response in responses:
        question = db.get_question_by_id(response.question_id)
        if question:
            response_list.append({
                "response_id": str(response.id),
                "question_id": str(response.question_id),
                "is_correct": response.is_correct,
                "points_earned": response.points_earned,
                "correct_answer": question.correct_answer if question.correct_answer else None,
                "explanation": question.explanation,
                "time_taken_ms": response.time_taken_ms
            })

    return {
        "participant_id": str(participant.id),
        "display_name": display_name,
        "score": participant.score,
        "correct_answers": participant.correct_answers,
        "total_answers": total_answers,
        "accuracy_rate": round(accuracy_rate, 4),
        "total_time_ms": participant.total_time_ms,
        "average_time_per_question_ms": round(avg_time, 2),
        "rank": rank,
        "responses": response_list
    }


def export_session_to_csv(session_id: str, user_id: str, db: DatabaseService) -> str:
    """
    Export session data to CSV format.

    Returns CSV string with columns:
    - Rank, Name, Score, Correct, Total, Accuracy, Time (ms), Avg Time per Q
    - Followed by individual question columns (Q1, Q2, etc.)

    Args:
        session_id: Session ID
        user_id: User ID (ownership validation)
        db: Database service

    Returns:
        CSV string
    """
    import csv
    import io

    logger.info(f"[Analytics] Exporting session to CSV: session_id={session_id}")

    # Validate session ownership
    session = db.get_quiz_session_by_id(session_id, user_id=user_id)
    if not session:
        raise ValueError("Session not found or access denied")

    # Get quiz and questions
    quiz = db.get_quiz_by_id(session.quiz_id, user_id)
    questions = db.get_questions_by_quiz_id(session.quiz_id, user_id)

    # Get participant analytics
    participants_data = get_participant_analytics_list(session_id, user_id, db)

    # Build CSV
    output = io.StringIO()

    # Determine columns
    base_columns = [
        "Rank", "Name", "Score", "Correct Answers", "Total Answers",
        "Accuracy (%)", "Total Time (ms)", "Avg Time per Question (ms)"
    ]

    # Add question columns
    question_columns = [f"Q{i+1} ({q.question_type})" for i, q in enumerate(questions)]
    all_columns = base_columns + question_columns

    writer = csv.DictWriter(output, fieldnames=all_columns)
    writer.writeheader()

    # Write participant data
    for p_data in participants_data:
        participant = db.get_participant_by_id(p_data["participant_id"])
        responses = db.get_responses_by_participant(participant.id)

        # Build question responses dict (keyed by question order)
        question_results = {}
        for response in responses:
            question = db.get_question_by_id(response.question_id)
            if question:
                q_key = f"Q{question.order_index + 1} ({question.question_type})"
                if response.is_correct is True:
                    question_results[q_key] = "✓"
                elif response.is_correct is False:
                    question_results[q_key] = "✗"
                else:
                    question_results[q_key] = "-"  # Poll or no answer

        row = {
            "Rank": p_data["rank"],
            "Name": p_data["display_name"],
            "Score": p_data["score"],
            "Correct Answers": p_data["correct_answers"],
            "Total Answers": p_data["total_answers"],
            "Accuracy (%)": f"{p_data['accuracy_rate'] * 100:.1f}",
            "Total Time (ms)": p_data["total_time_ms"],
            "Avg Time per Question (ms)": f"{p_data['average_time_per_question_ms']:.1f}"
        }

        # Add question results
        row.update(question_results)

        writer.writerow(row)

    csv_content = output.getvalue()
    logger.info(f"[Analytics] CSV export complete: {len(participants_data)} participants")

    return csv_content
