"""
Quiz Session API Router

This module defines REST API endpoints for live quiz session management.
Supports both teacher (host) and participant (student/guest) operations.

Host Endpoints (Requires Authentication):
- POST /api/quiz-sessions - Create new session
- GET /api/quiz-sessions - List user's sessions
- GET /api/quiz-sessions/{session_id} - Get session details
- POST /api/quiz-sessions/{session_id}/start - Start session
- POST /api/quiz-sessions/{session_id}/end - End session
- POST /api/quiz-sessions/{session_id}/next-question - Move to next question
- GET /api/quiz-sessions/{session_id}/participants - Get participants
- GET /api/quiz-sessions/{session_id}/leaderboard - Get leaderboard

Participant Endpoints (Public or Guest Token Auth):
- POST /api/quiz-sessions/join - Join session as guest or student
- GET /api/quiz-sessions/{session_id}/current-question - Get current question
- POST /api/quiz-sessions/{session_id}/submit-answer - Submit answer
- GET /api/quiz-sessions/{session_id}/my-stats - Get participant stats

Security:
- Host operations: JWT authentication (get_current_active_user)
- Participant operations: Guest token or student authentication
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from typing import List, Optional

# Application imports
from ..models import quiz_model
from ..services import quiz_service
from ..services.database_service import DatabaseService, get_db_service
from ..core.deps import get_current_active_user
from ..db.models.user_model import User as UserModel
from ..core.quiz_websocket import (
    connection_manager,
    build_session_started_message,
    build_question_started_message
)

router = APIRouter()


# ==================== HOST ENDPOINTS (Authenticated) ====================

@router.post("", response_model=quiz_model.QuizSessionDetail, status_code=status.HTTP_201_CREATED, summary="Create Quiz Session")
def create_session(
    session_data: quiz_model.QuizSessionCreate,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Create a new quiz session with auto-generated room code.

    Request Body:
    - quiz_id: Quiz to run
    - timeout_hours: Session timeout (default: 2)

    Returns:
    - Created session with room code

    Raises:
    - 404: Quiz not found
    - 422: Quiz not published, no questions, or too many active sessions
    """
    try:
        session = quiz_service.create_session_with_room_code(
            quiz_id=session_data.quiz_id,
            user_id=current_user.id,
            db=db,
            timeout_hours=session_data.timeout_hours
        )

        # Get quiz details for response
        quiz = db.get_quiz_by_id(session_data.quiz_id, current_user.id)

        return {
            **session.__dict__,
            "quiz_title": quiz.title if quiz else "Unknown",
            "participant_count": 0,
            "questions": []
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("", response_model=List[quiz_model.QuizSessionSummary], summary="Get User's Sessions")
def get_sessions(
    status_filter: Optional[str] = None,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get all sessions hosted by the current user.

    Query Parameters:
    - status: Filter by status (waiting/active/completed/cancelled)

    Returns:
    - List of session summaries
    """
    sessions = db.get_all_quiz_sessions(current_user.id, status_filter)

    summaries = []
    for session in sessions:
        quiz = db.get_quiz_by_id(session.quiz_id, current_user.id)
        participant_count = len(db.get_participants_by_session(session.id))

        summaries.append({
            "id": session.id,
            "quiz_id": session.quiz_id,
            "quiz_title": quiz.title if quiz else "Unknown",
            "room_code": session.room_code,
            "status": session.status,
            "participant_count": participant_count,
            "current_question_index": session.current_question_index,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "created_at": session.created_at
        })

    return summaries


@router.get("/{session_id}", response_model=quiz_model.QuizSessionDetail, summary="Get Session Details")
def get_session(
    session_id: str,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get detailed information about a session.

    Path Parameters:
    - session_id: Session ID

    Returns:
    - Session details with questions and participants

    Raises:
    - 404: Session not found or access denied
    """
    session = db.get_quiz_session_by_id(session_id, current_user.id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found or access denied"
        )

    # Get related data
    quiz = db.get_quiz_by_id(session.quiz_id, current_user.id)
    questions = db.get_questions_by_quiz_id(session.quiz_id, current_user.id)
    participants = db.get_participants_by_session(session_id)

    return {
        **session.__dict__,
        "quiz_title": quiz.title if quiz else "Unknown",
        "participant_count": len(participants),
        "questions": questions
    }


@router.post("/{session_id}/start", response_model=quiz_model.QuizSessionDetail, summary="Start Session")
async def start_session(
    session_id: str,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Start a quiz session (move from waiting to active).

    Path Parameters:
    - session_id: Session ID

    Returns:
    - Updated session

    Raises:
    - 404: Session not found
    - 422: Session already started or wrong status
    """
    try:
        session = quiz_service.start_session(
            session_id=session_id,
            user_id=current_user.id,
            db=db
        )

        # Get related data
        quiz = db.get_quiz_by_id(session.quiz_id, current_user.id)
        questions = db.get_questions_by_quiz_id(session.quiz_id, current_user.id)
        participants = db.get_participants_by_session(session_id)

        # FIX: Broadcast session_started to all participants via WebSocket
        await connection_manager.broadcast_to_room(
            session_id,
            build_session_started_message(
                session_id=str(session.id),
                quiz_title=quiz.title if quiz else "Quiz"
            )
        )

        # FIX: Broadcast first question to all participants
        if questions and len(questions) > 0:
            first_question = questions[0]
            await connection_manager.broadcast_to_room(
                session_id,
                build_question_started_message(
                    question_id=str(first_question.id),
                    question_text=first_question.question_text,
                    question_type=first_question.question_type,
                    options=first_question.options if first_question.options else [],
                    points=first_question.points,
                    order_index=0,
                    time_limit_seconds=first_question.time_limit_seconds
                )
            )

        return {
            **session.__dict__,
            "quiz_title": quiz.title if quiz else "Unknown",
            "participant_count": len(participants),
            "questions": questions
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.post("/{session_id}/end", response_model=quiz_model.QuizSessionDetail, summary="End Session")
async def end_session(
    session_id: str,
    end_data: quiz_model.QuizSessionEnd,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    End a quiz session.

    Path Parameters:
    - session_id: Session ID

    Request Body:
    - reason: Optional reason for ending

    Returns:
    - Updated session

    Raises:
    - 404: Session not found
    - 422: Session already ended
    """
    try:
        reason = "completed" if not end_data.reason else end_data.reason
        session = quiz_service.end_session(
            session_id=session_id,
            user_id=current_user.id,
            db=db,
            reason=reason
        )

        # Get related data first (needed for leaderboard)
        quiz = db.get_quiz_by_id(session.quiz_id, current_user.id)
        questions = db.get_questions_by_quiz_id(session.quiz_id, current_user.id)
        participants = db.get_participants_by_session(session_id)

        # FIX: Broadcast FINAL leaderboard before session_ended
        # This ensures students see correct scores when quiz ends
        leaderboard_entries = []
        leaderboard_participants = db.get_leaderboard(session_id, limit=100)  # Get all
        for rank, p in enumerate(leaderboard_participants, start=1):
            # Determine display name
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

        await connection_manager.broadcast_to_room(
            session_id,
            {
                "type": "leaderboard_update",
                "leaderboard": leaderboard_entries
            }
        )

        # FIX: Broadcast session_ended to all participants via WebSocket
        await connection_manager.broadcast_to_room(
            session_id,
            {
                "type": "session_ended",
                "session_id": str(session.id),
                "reason": reason,
                "final_status": session.status
            }
        )

        return {
            **session.__dict__,
            "quiz_title": quiz.title if quiz else "Unknown",
            "participant_count": len(participants),
            "questions": questions
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.post("/{session_id}/next-question", response_model=quiz_model.QuizSessionDetail, summary="Move to Next Question")
async def next_question(
    session_id: str,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Move session to the next question.

    Path Parameters:
    - session_id: Session ID

    Returns:
    - Updated session

    Raises:
    - 404: Session not found
    - 422: No more questions or session not active
    """
    session = db.move_to_next_question(session_id, current_user.id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found"
        )

    # Get related data
    quiz = db.get_quiz_by_id(session.quiz_id, current_user.id)
    questions = db.get_questions_by_quiz_id(session.quiz_id, current_user.id)
    participants = db.get_participants_by_session(session_id)

    # Validate we haven't exceeded question count
    if session.current_question_index >= len(questions):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No more questions remaining"
        )

    # FIX: Broadcast new question to all participants via WebSocket
    current_question = questions[session.current_question_index]
    await connection_manager.broadcast_to_room(
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
    )

    return {
        **session.__dict__,
        "quiz_title": quiz.title if quiz else "Unknown",
        "participant_count": len(participants),
        "questions": questions
    }


@router.get("/{session_id}/participants", response_model=List[quiz_model.ParticipantSummary], summary="Get Participants")
def get_participants(
    session_id: str,
    active_only: bool = False,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get all participants in a session.

    Path Parameters:
    - session_id: Session ID

    Query Parameters:
    - active_only: Only return active participants (default: false)

    Returns:
    - List of participants

    Raises:
    - 404: Session not found or access denied
    """
    # Verify ownership
    session = db.get_quiz_session_by_id(session_id, current_user.id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found or access denied"
        )

    participants = db.get_participants_by_session(session_id, active_only)

    # Build response with display names
    result = []
    for p in participants:
        # Determine display name based on identity type:
        # 1. Has guest_name → use it (pure guest or identified guest)
        # 2. Has student_id only → try to lookup student by ID (registered student)
        # 3. Fallback → "Unknown"
        display_name = "Unknown"

        if p.guest_name:
            # Guest or identified guest
            display_name = p.guest_name
        elif p.student_id:
            # Registered student - try to lookup
            try:
                student = db.get_student_by_student_id(p.student_id)
                display_name = student.name if student else f"Student {p.student_id}"
            except:
                display_name = f"Student {p.student_id}"

        result.append({
            "id": p.id,
            "display_name": display_name,
            "is_guest": p.guest_name is not None,
            "score": p.score,
            "correct_answers": p.correct_answers,
            "total_time_ms": p.total_time_ms,
            "is_active": p.is_active,
            "joined_at": p.joined_at
        })

    return result


@router.get("/{session_id}/leaderboard", response_model=quiz_model.LeaderboardResponse, summary="Get Leaderboard")
def get_leaderboard(
    session_id: str,
    limit: int = 10,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get session leaderboard (top N participants).

    Path Parameters:
    - session_id: Session ID

    Query Parameters:
    - limit: Number of top participants (default: 10)

    Returns:
    - Leaderboard with rankings

    Raises:
    - 404: Session not found or access denied
    """
    # Verify ownership
    session = db.get_quiz_session_by_id(session_id, current_user.id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found or access denied"
        )

    participants = db.get_leaderboard(session_id, limit)
    total_participants = len(db.get_participants_by_session(session_id))

    # Build leaderboard entries
    # FIX: Convert UUID to string for JSON serialization
    entries = []
    for rank, p in enumerate(participants, start=1):
        # Determine display name (same logic as get_participants)
        display_name = "Unknown"

        if p.guest_name:
            # Guest or identified guest
            display_name = p.guest_name
        elif p.student_id:
            # Registered student - try to lookup
            try:
                student = db.get_student_by_student_id(p.student_id)
                display_name = student.name if student else f"Student {p.student_id}"
            except:
                display_name = f"Student {p.student_id}"

        entries.append({
            "rank": rank,
            "participant_id": str(p.id),
            "display_name": display_name,
            "score": p.score,
            "correct_answers": p.correct_answers,
            "total_time_ms": p.total_time_ms,
            "is_active": p.is_active
        })

    return {
        "session_id": session_id,
        "entries": entries,
        "total_participants": total_participants,
        "updated_at": session.updated_at if hasattr(session, 'updated_at') else session.created_at
    }


# ==================== PARTICIPANT ENDPOINTS (Public/Guest Token) ====================

@router.post("/join", response_model=quiz_model.ParticipantJoinResponse, summary="Join Session")
def join_session(
    join_data: quiz_model.ParticipantJoinRequest,
    db: DatabaseService = Depends(get_db_service)
):
    """
    Join a quiz session as a guest, registered student, or identified guest.

    Request Body:
    - room_code: Session room code (required)
    - guest_name: Name for guest users (optional)
    - student_id: Student ID (optional)

    Join Modes:
    1. Identified Guest (MOST COMMON): Provide both guest_name AND student_id
       - Students without accounts (K-12 use case)
       - Teacher can track by student ID
    2. Pure Guest: Provide only guest_name
       - Anonymous participation
    3. Registered Student: Provide only student_id
       - Student with existing account

    Returns:
    - Participant details with guest_token (for guests) or session info (for students)

    Raises:
    - 400: Invalid room code, session full, duplicate join
    """
    try:
        # MODE 1: Identified Guest (both name and student ID) - MOST COMMON
        if join_data.guest_name and join_data.student_id:
            participant, guest_token = quiz_service.join_session_as_identified_guest(
                room_code=join_data.room_code,
                student_name=join_data.guest_name,
                student_id=join_data.student_id,
                db=db
            )

            session = db.get_quiz_session_by_id(participant.session_id)
            quiz = db.get_quiz_by_id(session.quiz_id, session.user_id) if session else None

            # FIX: Return nested objects for frontend compatibility
            return {
                "session": {
                    "id": str(participant.session_id),
                    "room_code": join_data.room_code,
                    "quiz_title": quiz.title if quiz else "Quiz",
                    "status": session.status if session else "waiting",
                    "current_question_index": session.current_question_index if session else None
                },
                "participant": {
                    "id": str(participant.id),
                    "display_name": participant.guest_name,
                    "guest_name": participant.guest_name,
                    "student_id": participant.student_id,
                    "is_guest": True
                },
                "guest_token": guest_token
            }

        # MODE 2: Pure Guest (only name, no student ID)
        elif join_data.guest_name:
            participant, guest_token = quiz_service.join_session_as_guest(
                room_code=join_data.room_code,
                guest_name=join_data.guest_name,
                db=db
            )

            session = db.get_quiz_session_by_id(participant.session_id)
            quiz = db.get_quiz_by_id(session.quiz_id, session.user_id) if session else None

            # FIX: Return nested objects for frontend compatibility
            return {
                "session": {
                    "id": str(participant.session_id),
                    "room_code": join_data.room_code,
                    "quiz_title": quiz.title if quiz else "Quiz",
                    "status": session.status if session else "waiting",
                    "current_question_index": session.current_question_index if session else None
                },
                "participant": {
                    "id": str(participant.id),
                    "display_name": participant.guest_name,
                    "guest_name": participant.guest_name,
                    "student_id": None,
                    "is_guest": True
                },
                "guest_token": guest_token
            }

        # MODE 3: Registered Student (only student ID, has account)
        elif join_data.student_id:
            participant = quiz_service.join_session_as_student(
                room_code=join_data.room_code,
                student_id=join_data.student_id,
                db=db
            )

            session = db.get_quiz_session_by_id(participant.session_id)
            quiz = db.get_quiz_by_id(session.quiz_id, session.user_id) if session else None
            student = db.get_student_by_student_id(join_data.student_id)

            # FIX: Return nested objects for frontend compatibility
            return {
                "session": {
                    "id": str(participant.session_id),
                    "room_code": join_data.room_code,
                    "quiz_title": quiz.title if quiz else "Quiz",
                    "status": session.status if session else "waiting",
                    "current_question_index": session.current_question_index if session else None
                },
                "participant": {
                    "id": str(participant.id),
                    "display_name": student.name if student else "Student",
                    "guest_name": None,
                    "student_id": participant.student_id,
                    "is_guest": False
                },
                "guest_token": None
            }

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must provide either guest_name or student_id (or both for identified guests)"
            )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{session_id}/current-question", response_model=quiz_model.QuizQuestionParticipantResponse, summary="Get Current Question")
def get_current_question(
    session_id: str,
    db: DatabaseService = Depends(get_db_service)
):
    """
    Get the current question for a session (participant view, no correct answers).

    Path Parameters:
    - session_id: Session ID

    Returns:
    - Current question details

    Raises:
    - 404: Session not found or no current question
    """
    session = db.get_quiz_session_by_id(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found"
        )

    if session.current_question_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session has not started yet"
        )

    # Get questions
    questions = db.get_questions_by_quiz_id(session.quiz_id, session.user_id)

    if session.current_question_index >= len(questions):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No current question (session may have ended)"
        )

    question = questions[session.current_question_index]

    # Return participant view (no correct answer)
    return {
        "id": question.id,
        "question_type": question.question_type,
        "question_text": question.question_text,
        "options": question.options,
        "points": question.points,
        "time_limit_seconds": question.time_limit_seconds,
        "media_url": question.media_url,
        "order_index": question.order_index
    }


@router.post("/{session_id}/submit-answer", response_model=quiz_model.AnswerResult, summary="Submit Answer")
async def submit_answer(
    session_id: str,
    answer_data: quiz_model.AnswerSubmission,
    guest_token: Optional[str] = Header(None, alias="X-Guest-Token"),
    db: DatabaseService = Depends(get_db_service)
):
    """
    Submit an answer to a question (guest or student).

    Path Parameters:
    - session_id: Session ID

    Headers:
    - X-Guest-Token: Guest authentication token (required for guests)

    Request Body:
    - question_id: Question being answered
    - answer: Answer data
    - time_taken_ms: Time taken (milliseconds)

    Returns:
    - Grading result

    Raises:
    - 401: Invalid or missing guest token
    - 400: Duplicate answer, question not found, etc.
    """
    # TODO: Add proper authentication for students
    # For now, require guest token
    if not guest_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Guest token required (X-Guest-Token header)"
        )

    # Find participant by guest token
    participant = db.get_participant_by_guest_token(guest_token)
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid guest token"
        )

    if participant.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token does not match session"
        )

    try:
        result = quiz_service.submit_answer_with_grading(
            participant_id=participant.id,
            question_id=answer_data.question_id,
            answer=answer_data.answer,
            time_taken_ms=answer_data.time_taken_ms,
            db=db
        )

        # FIX: Broadcast participant_answered to teacher (host) via WebSocket
        await connection_manager.broadcast_to_hosts(
            session_id,
            {
                "type": "participant_answered",
                "participant_id": str(participant.id),
                "question_id": answer_data.question_id,
                "is_correct": result["is_correct"],
                "timestamp": result.get("timestamp") if isinstance(result, dict) else None
            }
        )

        # FIX: Get updated session stats and broadcast to teacher
        session = db.get_quiz_session_by_id(session_id)
        if session:
            # Get total participants and answers for current question
            participants_list = db.get_participants_by_session(session_id, active_only=True)
            total_participants = len(participants_list)

            # Count how many have answered the current question
            answers_count = 0
            if session.current_question_index is not None:
                questions = db.get_questions_by_quiz_id(session.quiz_id, session.user_id)
                if session.current_question_index < len(questions):
                    current_question_id = questions[session.current_question_index].id
                    # Count responses for current question
                    for p in participants_list:
                        existing_response = db.get_participant_response_for_question(p.id, current_question_id)
                        if existing_response:
                            answers_count += 1

            await connection_manager.broadcast_to_hosts(
                session_id,
                {
                    "type": "stats_update",
                    "total_participants": total_participants,
                    "answers_received": answers_count,
                    "completion_percentage": (answers_count / total_participants * 100) if total_participants > 0 else 0
                }
            )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{session_id}/my-stats", response_model=quiz_model.ParticipantDetail, summary="Get My Stats")
def get_my_stats(
    session_id: str,
    guest_token: Optional[str] = Header(None, alias="X-Guest-Token"),
    db: DatabaseService = Depends(get_db_service)
):
    """
    Get stats for the current participant.

    Path Parameters:
    - session_id: Session ID

    Headers:
    - X-Guest-Token: Guest authentication token (required for guests)

    Returns:
    - Participant stats and rank

    Raises:
    - 401: Invalid or missing guest token
    """
    if not guest_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Guest token required (X-Guest-Token header)"
        )

    participant = db.get_participant_by_guest_token(guest_token)
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid guest token"
        )

    if participant.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token does not match session"
        )

    return {
        "id": participant.id,
        "session_id": participant.session_id,
        "student_id": participant.student_id,
        "display_name": participant.guest_name or "Student",
        "is_guest": participant.guest_name is not None,
        "score": participant.score,
        "correct_answers": participant.correct_answers,
        "total_time_ms": participant.total_time_ms,
        "is_active": participant.is_active,
        "joined_at": participant.joined_at,
        "last_seen_at": participant.last_seen_at
    }


# ==================== ANALYTICS ENDPOINTS (Authenticated) ====================

@router.get("/{session_id}/analytics", response_model=quiz_model.SessionAnalytics, summary="Get Session Analytics")
def get_session_analytics(
    session_id: str,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get comprehensive analytics for a completed quiz session.

    Includes:
    - Participant statistics (total, active, avg/median/high/low scores)
    - Question completion stats
    - Overall accuracy rate
    - Session duration
    - Question-level analytics (for each question: responses, accuracy, avg time)

    Path Parameters:
    - session_id: Session ID

    Returns:
    - Complete session analytics with question breakdown

    Raises:
    - 403: User doesn't own this session
    - 404: Session not found
    """
    try:
        analytics = quiz_service.get_session_analytics(
            session_id=session_id,
            user_id=current_user.id,
            db=db
        )
        return analytics

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.get("/{session_id}/participant-analytics", response_model=List[quiz_model.ParticipantAnalytics], summary="Get All Participants Analytics")
def get_participant_analytics(
    session_id: str,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get analytics for all participants in a session.

    Returns list sorted by rank (score descending, time ascending).

    For each participant:
    - Rank, name, score
    - Correct/total answers and accuracy rate
    - Total time and average time per question

    Path Parameters:
    - session_id: Session ID

    Returns:
    - List of participant analytics

    Raises:
    - 403: User doesn't own this session
    - 404: Session not found
    """
    try:
        analytics_list = quiz_service.get_participant_analytics_list(
            session_id=session_id,
            user_id=current_user.id,
            db=db
        )
        return analytics_list

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.get("/{session_id}/participant-analytics/{participant_id}", response_model=quiz_model.ParticipantAnalytics, summary="Get Individual Participant Analytics")
def get_participant_detail(
    session_id: str,
    participant_id: str,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get detailed analytics for a single participant including all their responses.

    Returns:
    - Participant summary stats
    - Complete list of responses with:
      - Question ID
      - Correctness and points earned
      - Correct answer and explanation
      - Time taken

    Path Parameters:
    - session_id: Session ID
    - participant_id: Participant ID

    Returns:
    - Detailed participant analytics with all responses

    Raises:
    - 403: User doesn't own this session
    - 404: Session or participant not found
    """
    try:
        analytics = quiz_service.get_participant_detail_analytics(
            participant_id=participant_id,
            session_id=session_id,
            user_id=current_user.id,
            db=db
        )
        return analytics

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.get("/{session_id}/export/csv", summary="Export Session to CSV")
def export_session_csv(
    session_id: str,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Export session data to CSV format.

    CSV includes:
    - Base columns: Rank, Name, Score, Correct, Total, Accuracy, Time, Avg Time
    - Question columns: Q1, Q2, etc. (with ✓ for correct, ✗ for incorrect, - for poll)

    Path Parameters:
    - session_id: Session ID

    Returns:
    - CSV file download

    Raises:
    - 403: User doesn't own this session
    - 404: Session not found
    """
    from fastapi.responses import Response

    try:
        csv_content = quiz_service.export_session_to_csv(
            session_id=session_id,
            user_id=current_user.id,
            db=db
        )

        # Return CSV with proper headers for download
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=quiz_session_{session_id}_analytics.csv"
            }
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
