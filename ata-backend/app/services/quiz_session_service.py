# /ata-backend/app/services/quiz_session_service.py

"""
This service module handles the business logic for quiz session management,
including session creation, participant joining (both students and guests),
session lifecycle, and answer submission.

This is the core service for running live quiz sessions in real-time.
"""

import uuid
from typing import List, Dict, Optional
from datetime import datetime
from fastapi import HTTPException, status

from ..models import quiz_model
from .database_service import DatabaseService
from ..core import quiz_auth, quiz_config

# Get settings instance
settings = quiz_config.get_quiz_settings()


# --- Helper Functions ---

def _generate_session_id() -> str:
    """Generates a unique session ID."""
    return f"session_{uuid.uuid4().hex[:16]}"


def _generate_participant_id() -> str:
    """Generates a unique participant ID."""
    return f"part_{uuid.uuid4().hex[:12]}"


def _generate_response_id() -> str:
    """Generates a unique response ID."""
    return f"resp_{uuid.uuid4().hex[:12]}"


def _create_session_config_snapshot(quiz, questions) -> Dict:
    """
    Creates a frozen snapshot of quiz settings and questions for the session.
    This ensures session behavior doesn't change if quiz is edited mid-session.
    """
    return {
        'quiz_title': quiz.title,
        'quiz_settings': quiz.settings,
        'total_questions': len(questions),
        'questions': [
            {
                'id': q.id,
                'question_text': q.question_text,
                'question_type': q.question_type,
                'order_index': q.order_index,
                'points': q.points,
                'time_limit': q.time_limit or quiz.settings.get('question_time_default', 30)
            }
            for q in questions
        ]
    }


# --- Session Management ---

def create_session(
    quiz_id: str,
    user_id: str,
    db: DatabaseService
) -> quiz_model.SessionSummary:
    """
    Creates a new quiz session with a unique room code.
    Teacher must own the quiz to create a session.
    """
    # Verify quiz exists and is published
    quiz = db.get_quiz_by_id(quiz_id=quiz_id, user_id=user_id)
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with ID {quiz_id} not found or access denied"
        )

    if quiz.status != 'published':
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only published quizzes can be used for sessions"
        )

    # Get questions
    questions = db.get_questions_by_quiz(quiz_id=quiz_id, user_id=user_id)
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot create session for quiz with no questions"
        )

    # Generate unique room code
    room_code = quiz_auth.generate_unique_room_code(db, max_attempts=5)

    # Generate session ID
    session_id = _generate_session_id()

    # Create session config snapshot
    session_config = _create_session_config_snapshot(quiz, questions)

    # Create session record
    session_record = {
        'id': session_id,
        'quiz_id': quiz_id,
        'user_id': user_id,
        'status': 'waiting',
        'room_code': room_code,
        'current_question_index': 0,
        'session_config': session_config,
        'timeout_hours': settings.SESSION_TIMEOUT_HOURS
    }

    db_session = db.create_quiz_session(session_record)

    # Update quiz's last_room_code
    db.update_last_room_code(quiz_id=quiz_id, user_id=user_id, room_code=room_code)

    # Return summary
    return quiz_model.SessionSummary(
        id=db_session.id,
        quiz_id=db_session.quiz_id,
        room_code=db_session.room_code,
        status=db_session.status,
        participant_count=0,
        created_at=db_session.created_at
    )


def get_session_by_id(
    session_id: str,
    user_id: str,
    db: DatabaseService
) -> quiz_model.SessionDetail:
    """
    Retrieves complete session details including participants.
    """
    db_session = db.get_quiz_session_by_id(session_id=session_id, user_id=user_id)
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found or access denied"
        )

    # Get participants
    participants = db.get_participants_by_session(session_id=session_id)

    # Get quiz info
    quiz = db.get_quiz_by_id(quiz_id=db_session.quiz_id, user_id=user_id)

    return quiz_model.SessionDetail(
        id=db_session.id,
        quiz_id=db_session.quiz_id,
        quiz_title=quiz.title if quiz else "Unknown",
        room_code=db_session.room_code,
        status=db_session.status,
        current_question_index=db_session.current_question_index,
        started_at=db_session.started_at,
        ended_at=db_session.ended_at,
        created_at=db_session.created_at,
        participants=[
            quiz_model.ParticipantSummary(
                id=p.id,
                name=p.guest_name or f"Student {p.student_id}",
                score=p.score,
                is_active=p.is_active,
                joined_at=p.joined_at
            )
            for p in participants
        ]
    )


def get_sessions_by_quiz(
    quiz_id: str,
    user_id: str,
    db: DatabaseService
) -> List[quiz_model.SessionSummary]:
    """
    Retrieves all sessions for a specific quiz.
    """
    sessions = db.get_sessions_by_quiz(quiz_id=quiz_id, user_id=user_id)

    summaries = []
    for session in sessions:
        participant_count = len(db.get_participants_by_session(session_id=session.id))
        summaries.append(
            quiz_model.SessionSummary(
                id=session.id,
                quiz_id=session.quiz_id,
                room_code=session.room_code,
                status=session.status,
                participant_count=participant_count,
                created_at=session.created_at
            )
        )

    return summaries


def start_session(
    session_id: str,
    user_id: str,
    db: DatabaseService
) -> quiz_model.SessionDetail:
    """
    Starts a session (changes status from 'waiting' to 'in_progress').
    """
    session = db.get_quiz_session_by_id(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found or access denied"
        )

    if session.status != 'waiting':
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot start session with status '{session.status}'"
        )

    # Update status
    db.update_session_status(session_id=session_id, user_id=user_id, status='in_progress')

    return get_session_by_id(session_id=session_id, user_id=user_id, db=db)


def end_session(
    session_id: str,
    user_id: str,
    db: DatabaseService
) -> quiz_model.SessionDetail:
    """
    Ends a session (changes status to 'completed').
    """
    session = db.get_quiz_session_by_id(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found or access denied"
        )

    if session.status not in ['waiting', 'in_progress']:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot end session with status '{session.status}'"
        )

    # Update status
    db.update_session_status(session_id=session_id, user_id=user_id, status='completed')

    return get_session_by_id(session_id=session_id, user_id=user_id, db=db)


def advance_question(
    session_id: str,
    user_id: str,
    db: DatabaseService
) -> int:
    """
    Advances to the next question in the session.
    Returns the new question index.
    """
    session = db.get_quiz_session_by_id(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found or access denied"
        )

    if session.status != 'in_progress':
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Can only advance questions in active sessions"
        )

    # Get total questions from session config
    total_questions = session.session_config.get('total_questions', 0)
    next_index = session.current_question_index + 1

    if next_index >= total_questions:
        # Automatically end session when all questions answered
        db.update_session_status(session_id=session_id, user_id=user_id, status='completed')
        return session.current_question_index

    # Update current question index
    db.update_current_question(session_id=session_id, user_id=user_id, question_index=next_index)

    return next_index


# --- Participant Management ---

def join_session_as_guest(
    room_code: str,
    guest_name: str,
    db: DatabaseService
) -> quiz_model.ParticipantJoinResponse:
    """
    Allows a guest user to join a session via room code.
    Returns participant ID and guest token for authentication.
    """
    # Find session by room code
    session = db.get_quiz_session_by_room_code(room_code=room_code)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active session found with room code {room_code}"
        )

    if session.status not in ['waiting', 'in_progress']:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This session is no longer accepting participants"
        )

    # Check participant limit
    current_count = len(db.get_active_participants(session_id=session.id))
    if current_count >= settings.MAX_PARTICIPANTS_PER_SESSION:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Session is full"
        )

    # Get existing participant names to handle duplicates
    participants = db.get_participants_by_session(session_id=session.id)
    existing_names = [p.guest_name for p in participants if p.guest_name]

    # Format name to handle duplicates
    formatted_name = quiz_auth.format_participant_name(guest_name, existing_names)

    # Generate guest token
    guest_token = quiz_auth.generate_guest_token()

    # Create participant record
    participant_id = _generate_participant_id()
    participant_record = {
        'id': participant_id,
        'session_id': session.id,
        'student_id': None,
        'guest_name': formatted_name,
        'guest_token': guest_token,
        'score': 0,
        'correct_answers': 0,
        'total_time_ms': 0,
        'is_active': True
    }

    db_participant = db.add_quiz_participant(participant_record)

    return quiz_model.ParticipantJoinResponse(
        participant_id=db_participant.id,
        session_id=session.id,
        guest_token=guest_token,
        room_code=room_code,
        formatted_name=formatted_name
    )


def join_session_as_student(
    room_code: str,
    student_id: str,
    user_id: str,
    db: DatabaseService
) -> quiz_model.ParticipantJoinResponse:
    """
    Allows a registered student to join a session.
    Requires authentication (user must be logged in).
    """
    # Find session by room code
    session = db.get_quiz_session_by_room_code(room_code=room_code)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active session found with room code {room_code}"
        )

    if session.status not in ['waiting', 'in_progress']:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This session is no longer accepting participants"
        )

    # Verify student exists (optional: could also check if student belongs to user's classes)
    student = db.get_student_by_student_id(student_id=student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found"
        )

    # Check if already joined
    duplicate = db.check_duplicate_participant(session_id=session.id, student_id=student_id)
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Student has already joined this session"
        )

    # Create participant record
    participant_id = _generate_participant_id()
    participant_record = {
        'id': participant_id,
        'session_id': session.id,
        'student_id': student_id,
        'guest_name': None,
        'guest_token': None,
        'score': 0,
        'correct_answers': 0,
        'total_time_ms': 0,
        'is_active': True
    }

    db_participant = db.add_quiz_participant(participant_record)

    return quiz_model.ParticipantJoinResponse(
        participant_id=db_participant.id,
        session_id=session.id,
        guest_token=None,  # Students don't need guest token
        room_code=room_code,
        formatted_name=student.name
    )


def get_leaderboard(
    session_id: str,
    limit: Optional[int] = 10,
    db: DatabaseService
) -> quiz_model.LeaderboardResponse:
    """
    Retrieves the current leaderboard for a session.
    Can be called by teacher (with user_id) or public (without user_id for WebSocket).
    """
    # Get top participants
    top_participants = db.get_leaderboard(session_id=session_id, limit=limit)

    # Get total participant count
    all_participants = db.get_participants_by_session(session_id=session_id)
    total_count = len(all_participants)

    # Format leaderboard entries
    entries = []
    for idx, participant in enumerate(top_participants, start=1):
        entries.append(
            quiz_model.LeaderboardEntry(
                rank=idx,
                participant_id=participant.id,
                name=participant.guest_name or f"Student {participant.student_id}",
                score=participant.score,
                correct_answers=participant.correct_answers,
                total_time_ms=participant.total_time_ms
            )
        )

    return quiz_model.LeaderboardResponse(
        top_participants=entries,
        total_participants=total_count
    )


def get_participant_rank(
    participant_id: str,
    session_id: str,
    db: DatabaseService
) -> Optional[int]:
    """
    Gets the rank of a specific participant.
    """
    return db.get_participant_rank(participant_id=participant_id, session_id=session_id)


# --- Session Info for Participants ---

def get_session_info_by_room_code(
    room_code: str,
    db: DatabaseService
) -> Dict:
    """
    Gets public session info for join page (no auth required).
    """
    session = db.get_quiz_session_by_room_code(room_code=room_code)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No session found with room code {room_code}"
        )

    # Get quiz info
    quiz = db.get_quiz_by_id(quiz_id=session.quiz_id, user_id=session.user_id)

    # Get participant count
    participant_count = len(db.get_active_participants(session_id=session.id))

    return {
        'room_code': room_code,
        'quiz_title': quiz.title if quiz else "Quiz",
        'quiz_description': quiz.description if quiz else None,
        'status': session.status,
        'participant_count': participant_count,
        'is_accepting_participants': session.status in ['waiting', 'in_progress']
    }


def get_current_question_for_session(
    session_id: str,
    db: DatabaseService
) -> Dict:
    """
    Gets the current question being displayed in a session.
    Used by WebSocket to broadcast question to all participants.
    """
    session = db.get_quiz_session_by_room_code(room_code=session_id)
    if not session:
        # Try by session_id directly
        session = db.get_quiz_session_by_id(session_id=session_id, user_id=session.user_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )

    # Get questions from session config
    questions = session.session_config.get('questions', [])
    current_index = session.current_question_index

    if current_index >= len(questions):
        return {'status': 'completed', 'message': 'All questions answered'}

    current_question = questions[current_index]

    # Get full question details
    question = db.get_question_by_id(question_id=current_question['id'], user_id=session.user_id)

    return {
        'question_index': current_index,
        'total_questions': len(questions),
        'question_id': question.id,
        'question_text': question.question_text,
        'question_type': question.question_type,
        'points': question.points,
        'time_limit': question.time_limit,
        'options': question.options  # Will include choices for MC, etc.
    }
