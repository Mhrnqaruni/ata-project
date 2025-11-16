"""
Quiz Analytics API Router

This module provides REST API endpoints for quiz analytics and reporting.
Teachers can retrieve detailed performance metrics, export results, and track trends.

Endpoints:
- GET /api/quiz-analytics/sessions/{session_id} - Session analytics
- GET /api/quiz-analytics/questions/{question_id} - Question analytics
- GET /api/quiz-analytics/participants/{participant_id} - Participant analytics
- GET /api/quiz-analytics/quizzes/{quiz_id}/comparative - Comparative analytics
- GET /api/quiz-analytics/sessions/{session_id}/export-csv - Export CSV
- GET /api/quiz-analytics/sessions/{session_id}/export-pdf - Export PDF (future)

Security: All endpoints require JWT authentication and validate ownership.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import StreamingResponse
from typing import Dict
import io
import csv
from datetime import datetime

# Application imports
from ..services import quiz_analytics_service
from ..services.database_service import DatabaseService, get_db_service
from ..core.deps import get_current_active_user
from ..db.models.user_model import User as UserModel

router = APIRouter()


# ==================== SESSION ANALYTICS ====================

@router.get("/sessions/{session_id}", response_model=Dict, summary="Get Session Analytics")
def get_session_analytics(
    session_id: str,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get comprehensive analytics for a quiz session.

    Path Parameters:
    - session_id: Session ID

    Returns:
    - Participation metrics (completion rate, active/inactive counts)
    - Score statistics (average, median, distribution, std dev)
    - Accuracy metrics (correct answers, overall accuracy rate)
    - Timing metrics (average time per question)
    - Question-by-question breakdown

    Raises:
    - 404: Session not found or access denied

    Industry Benchmarks:
    - Completion rate: 50-70% is standard
    - Difficulty index: 0.3-0.7 is ideal
    """
    # Verify ownership
    session = db.get_quiz_session_by_id(session_id, current_user.id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found or access denied"
        )

    analytics = quiz_analytics_service.calculate_session_analytics(session_id, db)

    if "error" in analytics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=analytics["error"]
        )

    return analytics


# ==================== QUESTION ANALYTICS ====================

@router.get("/questions/{question_id}", response_model=Dict, summary="Get Question Analytics")
def get_question_analytics(
    question_id: str,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get detailed analytics for a specific question.

    Path Parameters:
    - question_id: Question ID

    Returns:
    - Difficulty index (proportion correct)
    - Discrimination index (differentiates high/low performers)
    - Response time distribution
    - Answer choice distribution (for multiple choice)
    - Quality metrics and interpretations

    Raises:
    - 404: Question not found or access denied

    Quality Indicators:
    - Difficulty: 0.3-0.7 is ideal (not too easy/hard)
    - Discrimination: >0.3 indicates good question quality
    """
    # Verify ownership via question → quiz → user
    question = db.get_question_by_id(question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question with ID {question_id} not found"
        )

    # Verify user owns the quiz
    quiz = db.get_quiz_by_id(question.quiz_id, current_user.id)
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Access denied to this question"
        )

    analytics = quiz_analytics_service.calculate_question_analytics(question_id, db)

    if "error" in analytics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=analytics["error"]
        )

    return analytics


# ==================== PARTICIPANT ANALYTICS ====================

@router.get("/participants/{participant_id}", response_model=Dict, summary="Get Participant Analytics")
def get_participant_analytics(
    participant_id: str,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get detailed analytics for an individual participant.

    Path Parameters:
    - participant_id: Participant ID

    Returns:
    - Overall performance (score, percentage, ranking)
    - Question-by-question breakdown
    - Performance by question type
    - Response patterns (speed, accuracy)

    Raises:
    - 404: Participant not found or access denied
    """
    # Verify ownership via participant → session → user
    participant = db.get_participant_by_id(participant_id)
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Participant with ID {participant_id} not found"
        )

    # Verify user owns the session
    session = db.get_quiz_session_by_id(participant.session_id, current_user.id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Access denied to this participant's data"
        )

    analytics = quiz_analytics_service.calculate_participant_analytics(participant_id, db)

    if "error" in analytics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=analytics["error"]
        )

    return analytics


# ==================== COMPARATIVE ANALYTICS ====================

@router.get("/quizzes/{quiz_id}/comparative", response_model=Dict, summary="Get Comparative Analytics")
def get_comparative_analytics(
    quiz_id: str,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get comparative analytics across all sessions of a quiz.

    Path Parameters:
    - quiz_id: Quiz ID

    Returns:
    - Session-by-session comparison
    - Overall trends and aggregates
    - Performance over time

    Raises:
    - 404: Quiz not found or access denied

    Use Case:
    Track quiz effectiveness over multiple classes/semesters.
    """
    analytics = quiz_analytics_service.generate_comparative_analytics(
        quiz_id, current_user.id, db
    )

    if "error" in analytics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=analytics["error"]
        )

    return analytics


# ==================== EXPORT ENDPOINTS ====================

@router.get("/sessions/{session_id}/export-csv", summary="Export Session Results as CSV")
def export_session_csv(
    session_id: str,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Export session results as CSV file.

    Path Parameters:
    - session_id: Session ID

    Returns:
    - CSV file with participant results

    Format:
    - Participant name, score, correct answers, accuracy %, time taken, rank

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

    # Get quiz info
    quiz = db.get_quiz_by_id(session.quiz_id, current_user.id)
    questions = db.get_questions_by_quiz_id(session.quiz_id, current_user.id)
    total_possible_points = sum(q.points for q in questions)

    # Get participants
    participants = db.get_participants_by_session(session_id, active_only=False)

    # Sort by rank (score desc, time asc)
    participants.sort(key=lambda p: (-p.score, p.total_time_ms))

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Rank",
        "Participant Name",
        "Type",
        "Score",
        "Total Possible",
        "Percentage",
        "Correct Answers",
        "Total Questions",
        "Accuracy %",
        "Time Taken (minutes)",
        "Status"
    ])

    # Data rows
    for rank, participant in enumerate(participants, start=1):
        display_name = participant.guest_name if participant.guest_name else "Student"
        participant_type = "Guest" if participant.guest_name else "Registered"
        percentage = round((participant.score / total_possible_points * 100) if total_possible_points > 0 else 0, 2)
        accuracy = round((participant.correct_answers / len(questions) * 100) if len(questions) > 0 else 0, 2)
        time_minutes = round(participant.total_time_ms / 60000, 2)
        status = "Active" if participant.is_active else "Inactive"

        writer.writerow([
            rank,
            display_name,
            participant_type,
            participant.score,
            total_possible_points,
            percentage,
            participant.correct_answers,
            len(questions),
            accuracy,
            time_minutes,
            status
        ])

    # Get CSV content
    csv_content = output.getvalue()
    output.close()

    # Generate filename
    quiz_title_safe = "".join(c for c in quiz.title if c.isalnum() or c in (' ', '-', '_'))[:50]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"quiz_results_{quiz_title_safe}_{session.room_code}_{timestamp}.csv"

    # Return as downloadable file
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/sessions/{session_id}/export-detailed-csv", summary="Export Detailed Results as CSV")
def export_session_detailed_csv(
    session_id: str,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Export detailed session results including question-by-question breakdown.

    Path Parameters:
    - session_id: Session ID

    Returns:
    - CSV file with detailed participant responses

    Format:
    - One row per participant per question

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

    # Get quiz info
    quiz = db.get_quiz_by_id(session.quiz_id, current_user.id)
    questions = db.get_questions_by_quiz_id(session.quiz_id, current_user.id)

    # Get all responses
    all_responses = db.get_responses_by_session(session_id)

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Participant Name",
        "Type",
        "Question #",
        "Question Text",
        "Question Type",
        "Points Possible",
        "Points Earned",
        "Correct?",
        "Time Taken (seconds)",
        "Answered At"
    ])

    # Group responses by participant
    participant_responses = {}
    for response in all_responses:
        if response.participant_id not in participant_responses:
            participant_responses[response.participant_id] = []
        participant_responses[response.participant_id].append(response)

    # Data rows
    for participant_id, responses in participant_responses.items():
        participant = db.get_participant_by_id(participant_id)
        if not participant:
            continue

        display_name = participant.guest_name if participant.guest_name else "Student"
        participant_type = "Guest" if participant.guest_name else "Registered"

        # Sort responses by answered_at
        responses.sort(key=lambda r: r.answered_at)

        for response in responses:
            question = db.get_question_by_id(response.question_id)
            if not question:
                continue

            question_num = question.order_index + 1
            question_text = question.question_text[:100] + "..." if len(question.question_text) > 100 else question.question_text
            time_seconds = round(response.time_taken_ms / 1000, 2)
            correct_str = "Yes" if response.is_correct else "No" if response.is_correct is not None else "N/A"

            writer.writerow([
                display_name,
                participant_type,
                question_num,
                question_text,
                question.question_type,
                question.points,
                response.points_earned,
                correct_str,
                time_seconds,
                response.answered_at.strftime("%Y-%m-%d %H:%M:%S")
            ])

    # Get CSV content
    csv_content = output.getvalue()
    output.close()

    # Generate filename
    quiz_title_safe = "".join(c for c in quiz.title if c.isalnum() or c in (' ', '-', '_'))[:50]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"quiz_detailed_{quiz_title_safe}_{session.room_code}_{timestamp}.csv"

    # Return as downloadable file
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
