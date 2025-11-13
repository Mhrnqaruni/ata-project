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
    session = db.update_quiz_session(session_id, user_id, {
        "status": SessionStatus.ACTIVE,
        "started_at": datetime.now(),
        "current_question_index": 0
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
