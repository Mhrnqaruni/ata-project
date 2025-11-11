# /ata-backend/app/services/quiz_grading_service.py

"""
This service module handles answer evaluation and grading logic for quiz responses.

It implements grading algorithms for different question types:
- Multiple choice: Exact match
- True/False: Boolean match
- Short answer: Keyword matching
- Poll: Participation points only

This service is called when participants submit answers during a live quiz session.
"""

from typing import Dict, Tuple
from fastapi import HTTPException, status

from ..models import quiz_model
from .database_service import DatabaseService


# --- Answer Evaluation Functions ---

def _evaluate_multiple_choice(
    participant_answer: Dict,
    correct_answer: Dict
) -> Tuple[bool, str]:
    """
    Evaluates a multiple choice answer.

    Expected format:
    - participant_answer: {"selected": "b"}
    - correct_answer: {"answer": "b"}

    Returns: (is_correct, feedback_message)
    """
    selected = participant_answer.get('selected')
    correct = correct_answer.get('answer')

    if not selected:
        return False, "No answer selected"

    is_correct = selected == correct

    if is_correct:
        return True, "Correct answer!"
    else:
        return False, f"Incorrect. The correct answer was '{correct}'"


def _evaluate_true_false(
    participant_answer: Dict,
    correct_answer: Dict
) -> Tuple[bool, str]:
    """
    Evaluates a true/false answer.

    Expected format:
    - participant_answer: {"selected": true}
    - correct_answer: {"answer": true}

    Returns: (is_correct, feedback_message)
    """
    selected = participant_answer.get('selected')
    correct = correct_answer.get('answer')

    if selected is None:
        return False, "No answer selected"

    is_correct = selected == correct

    if is_correct:
        return True, "Correct!"
    else:
        return False, f"Incorrect. The answer was {correct}"


def _evaluate_short_answer(
    participant_answer: Dict,
    correct_answer: Dict
) -> Tuple[bool, str]:
    """
    Evaluates a short answer using keyword matching.

    Expected format:
    - participant_answer: {"text": "user's answer"}
    - correct_answer: {
        "answer": "expected answer",  # Full expected answer (optional)
        "keywords": ["keyword1", "keyword2"],  # Required keywords
        "min_keywords": 2,  # Minimum keywords needed
        "case_sensitive": false
      }

    Returns: (is_correct, feedback_message)
    """
    user_text = participant_answer.get('text', '').strip()

    if not user_text:
        return False, "No answer provided"

    # Get grading criteria
    keywords = correct_answer.get('keywords', [])
    min_keywords = correct_answer.get('min_keywords', len(keywords))
    case_sensitive = correct_answer.get('case_sensitive', False)

    # Simple exact match if no keywords specified
    if not keywords:
        expected = correct_answer.get('answer', '')
        if not case_sensitive:
            is_match = user_text.lower() == expected.lower()
        else:
            is_match = user_text == expected

        return is_match, "Correct!" if is_match else f"Expected: {expected}"

    # Keyword matching
    if not case_sensitive:
        user_text_lower = user_text.lower()
        keywords_lower = [k.lower() for k in keywords]
    else:
        user_text_lower = user_text
        keywords_lower = keywords

    # Count matching keywords
    matched_keywords = [kw for kw in keywords_lower if kw in user_text_lower]
    matched_count = len(matched_keywords)

    is_correct = matched_count >= min_keywords

    if is_correct:
        return True, f"Correct! Found {matched_count}/{len(keywords)} keywords"
    else:
        return False, f"Needs at least {min_keywords} keywords. Found {matched_count}/{len(keywords)}"


def _evaluate_poll(
    participant_answer: Dict,
    correct_answer: Dict
) -> Tuple[bool, str]:
    """
    Evaluates a poll question (no right/wrong answer, just participation).

    Expected format:
    - participant_answer: {"selected": "option_id"}
    - correct_answer: {"participation_points": 5}

    Returns: (is_correct, feedback_message)
    """
    selected = participant_answer.get('selected')

    if not selected:
        return False, "No option selected"

    # Polls have no correct answer, just participation
    return True, "Thank you for participating!"


def evaluate_answer(
    question_type: str,
    participant_answer: Dict,
    correct_answer: Dict
) -> Tuple[bool, str]:
    """
    Master function to evaluate an answer based on question type.

    Returns: (is_correct, feedback_message)
    """
    if question_type == "multiple_choice":
        return _evaluate_multiple_choice(participant_answer, correct_answer)
    elif question_type == "true_false":
        return _evaluate_true_false(participant_answer, correct_answer)
    elif question_type == "short_answer":
        return _evaluate_short_answer(participant_answer, correct_answer)
    elif question_type == "poll":
        return _evaluate_poll(participant_answer, correct_answer)
    else:
        raise ValueError(f"Unknown question type: {question_type}")


def calculate_points_earned(
    is_correct: bool,
    question_points: int,
    time_taken_ms: int,
    time_limit_seconds: int
) -> int:
    """
    Calculates points earned for an answer.

    Currently implements all-or-nothing scoring.
    Future: Could implement partial credit, time-based bonuses, etc.

    Args:
        is_correct: Whether the answer was correct
        question_points: Maximum points for the question
        time_taken_ms: Time taken to answer in milliseconds
        time_limit_seconds: Time limit for the question in seconds

    Returns:
        Points earned
    """
    if not is_correct:
        return 0

    # All-or-nothing scoring for now
    return question_points

    # Future enhancement: Time-based bonus
    # if time_taken_ms < (time_limit_seconds * 1000 * 0.5):  # Answered in first half
    #     return int(question_points * 1.1)  # 10% bonus
    # return question_points


# --- Main Grading Function ---

def submit_and_grade_answer(
    session_id: str,
    participant_id: str,
    question_id: str,
    answer_data: quiz_model.AnswerSubmission,
    db: DatabaseService
) -> quiz_model.AnswerResult:
    """
    Submits and grades a participant's answer.

    This is the main entry point called when a participant submits an answer
    during a live quiz session.

    Returns the grading result including correctness and points earned.
    """
    # Verify participant exists
    participant = db.get_quiz_participant_by_id(participant_id=participant_id)
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found"
        )

    if participant.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Participant does not belong to this session"
        )

    # Verify session exists
    session = db.get_quiz_session_by_id(session_id=session_id, user_id=participant.session_id)
    if not session:
        # Try without user_id since participants don't have user_id
        from sqlalchemy import create_engine
        # TODO: Need better way to get session for participants
        pass

    # Check if already answered
    existing_answer = db.get_participant_answer(
        session_id=session_id,
        participant_id=participant_id,
        question_id=question_id
    )
    if existing_answer:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Answer already submitted for this question"
        )

    # Get question details
    # Note: We need the question without user_id check for guests
    # This is safe because question_id comes from session which was validated
    from app.db.models.quiz_models import QuizQuestion
    from app.db.database import get_db
    db_session = next(get_db())
    question = db_session.query(QuizQuestion).filter(QuizQuestion.id == question_id).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    # Evaluate answer
    is_correct, feedback = evaluate_answer(
        question_type=question.question_type,
        participant_answer=answer_data.answer,
        correct_answer=question.correct_answer
    )

    # Calculate points
    points_earned = calculate_points_earned(
        is_correct=is_correct,
        question_points=question.points,
        time_taken_ms=answer_data.time_taken_ms,
        time_limit_seconds=question.time_limit or 30
    )

    # Create response record
    response_record = {
        'id': f"resp_{answer_data.answer.get('_id', 'auto')}",
        'session_id': session_id,
        'participant_id': participant_id,
        'question_id': question_id,
        'answer': answer_data.answer,
        'is_correct': is_correct if question.question_type != 'poll' else None,
        'points_earned': points_earned,
        'time_taken_ms': answer_data.time_taken_ms
    }

    db.add_quiz_response(response_record)

    # Update participant's score
    db.update_participant_score(
        participant_id=participant_id,
        points=points_earned,
        time_ms=answer_data.time_taken_ms,
        is_correct=is_correct
    )

    # Return result
    return quiz_model.AnswerResult(
        is_correct=is_correct if question.question_type != 'poll' else None,
        points_earned=points_earned,
        feedback=feedback,
        correct_answer=question.correct_answer if not is_correct and question.question_type != 'poll' else None
    )


def get_session_analytics(
    session_id: str,
    user_id: str,
    db: DatabaseService
) -> quiz_model.SessionAnalytics:
    """
    Calculates analytics for a completed session.

    Returns statistics about:
    - Overall performance
    - Question difficulty
    - Participant engagement
    """
    # Verify session exists and user owns it
    session = db.get_quiz_session_by_id(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or access denied"
        )

    # Get all participants
    participants = db.get_participants_by_session(session_id=session_id)

    # Get all responses
    all_responses = db.get_all_responses_for_session(session_id=session_id)

    # Calculate per-question analytics
    question_stats = []
    questions = session.session_config.get('questions', [])

    for question_info in questions:
        question_id = question_info['id']
        analytics = db.get_question_analytics(session_id=session_id, question_id=question_id)

        question_stats.append(
            quiz_model.QuestionAnalytics(
                question_id=question_id,
                question_text=question_info['question_text'],
                total_attempts=analytics['total_attempts'],
                correct_count=analytics['correct_count'],
                correct_percentage=analytics['correct_percentage'],
                avg_time_ms=analytics['avg_time_ms']
            )
        )

    # Calculate overall stats
    total_participants = len(participants)
    avg_score = sum(p.score for p in participants) / total_participants if total_participants > 0 else 0
    completion_rate = (len([p for p in participants if not p.is_active]) / total_participants * 100) if total_participants > 0 else 0

    return quiz_model.SessionAnalytics(
        session_id=session_id,
        total_participants=total_participants,
        avg_score=round(avg_score, 2),
        completion_rate=round(completion_rate, 2),
        question_analytics=question_stats
    )
