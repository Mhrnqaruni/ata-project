"""
Quiz Analytics Service

This module provides comprehensive analytics for quiz sessions, questions, and participants.
Teachers can understand quiz effectiveness, question difficulty, and student performance.

Analytics Categories:
1. Session Analytics - Overall session performance and engagement
2. Question Analytics - Question difficulty, discrimination, and timing
3. Participant Analytics - Individual and comparative performance
4. Class/Cohort Analytics - Performance across multiple sessions

Research-backed metrics:
- Completion rates (industry standard: 50-70%)
- Difficulty index (% correct)
- Discrimination index (how well question differentiates high/low performers)
- Average response time
- Engagement metrics
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import statistics
from collections import Counter

# Core dependencies
from .database_service import DatabaseService
from ..db.models.quiz_models import (
    QuizSession, QuizParticipant, QuizResponse, QuizQuestion, Quiz
)
from ..models.quiz_model import SessionStatus


# ==================== SESSION ANALYTICS ====================

def calculate_session_analytics(session_id: str, db: DatabaseService) -> Dict:
    """
    Calculate comprehensive analytics for a quiz session.

    Metrics:
    - Completion rate
    - Average score (absolute and percentage)
    - Median score
    - Score distribution
    - Participation stats
    - Time analytics
    - Question-by-question breakdown

    Args:
        session_id: Session ID
        db: Database service

    Returns:
        Dict with all session analytics

    Reference: Industry standard completion rate is 50-70%
    """
    session = db.get_quiz_session_by_id(session_id)
    if not session:
        return {"error": "Session not found"}

    # Get all participants and responses
    all_participants = db.get_participants_by_session(session_id, active_only=False)
    active_participants = db.get_participants_by_session(session_id, active_only=True)
    all_responses = db.get_responses_by_session(session_id)

    # Get quiz questions
    quiz = db.get_quiz_by_id(session.quiz_id, session.user_id)
    questions = db.get_questions_by_quiz_id(session.quiz_id, session.user_id)
    total_questions = len(questions)

    # Calculate total possible points
    total_possible_points = sum(q.points for q in questions)

    # Participation metrics
    total_participants = len(all_participants)
    active_count = len(active_participants)
    inactive_count = total_participants - active_count

    # Completion metrics
    completed_participants = []
    partial_participants = []
    no_response_participants = []

    for participant in all_participants:
        participant_responses = [r for r in all_responses if r.participant_id == participant.id]
        response_count = len(participant_responses)

        if response_count == total_questions:
            completed_participants.append(participant)
        elif response_count > 0:
            partial_participants.append(participant)
        else:
            no_response_participants.append(participant)

    completion_rate = (len(completed_participants) / total_participants * 100) if total_participants > 0 else 0

    # Score statistics (only for participants who answered at least one question)
    scored_participants = completed_participants + partial_participants
    scores = [p.score for p in scored_participants]
    percentages = [(p.score / total_possible_points * 100) if total_possible_points > 0 else 0
                   for p in scored_participants]

    if scores:
        avg_score = statistics.mean(scores)
        median_score = statistics.median(scores)
        avg_percentage = statistics.mean(percentages)
        min_score = min(scores)
        max_score = max(scores)

        # Calculate standard deviation if we have enough data
        if len(scores) > 1:
            std_dev = statistics.stdev(scores)
        else:
            std_dev = 0
    else:
        avg_score = median_score = avg_percentage = min_score = max_score = std_dev = 0

    # Correct answer statistics
    correct_counts = [p.correct_answers for p in scored_participants]
    if correct_counts:
        avg_correct = statistics.mean(correct_counts)
        accuracy_rate = (avg_correct / total_questions * 100) if total_questions > 0 else 0
    else:
        avg_correct = accuracy_rate = 0

    # Time analytics
    if scored_participants:
        total_times = [p.total_time_ms for p in scored_participants]
        avg_time_ms = statistics.mean(total_times)
        avg_time_per_question_ms = avg_time_ms / total_questions if total_questions > 0 else 0
    else:
        avg_time_ms = avg_time_per_question_ms = 0

    # Score distribution (for charting)
    score_ranges = {
        "0-20%": 0,
        "21-40%": 0,
        "41-60%": 0,
        "61-80%": 0,
        "81-100%": 0
    }

    for pct in percentages:
        if pct <= 20:
            score_ranges["0-20%"] += 1
        elif pct <= 40:
            score_ranges["21-40%"] += 1
        elif pct <= 60:
            score_ranges["41-60%"] += 1
        elif pct <= 80:
            score_ranges["61-80%"] += 1
        else:
            score_ranges["81-100%"] += 1

    # Session timing
    duration_minutes = None
    if session.started_at and session.ended_at:
        duration = session.ended_at - session.started_at
        duration_minutes = duration.total_seconds() / 60

    # Question-level summary
    question_summaries = []
    for question in questions:
        question_stats = db.get_question_correctness_stats(question.id)
        question_summaries.append({
            "question_id": question.id,
            "question_text": question.question_text[:100] + "..." if len(question.question_text) > 100 else question.question_text,
            "question_type": question.question_type,
            "points": question.points,
            "total_responses": question_stats["total"],
            "correct_responses": question_stats["correct"],
            "accuracy_rate": question_stats["accuracy_rate"] * 100
        })

    return {
        "session_id": session_id,
        "quiz_id": session.quiz_id,
        "quiz_title": quiz.title if quiz else "Unknown",
        "room_code": session.room_code,
        "status": session.status,
        "created_at": session.created_at,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "duration_minutes": duration_minutes,

        # Participation metrics
        "participation": {
            "total_participants": total_participants,
            "active_participants": active_count,
            "inactive_participants": inactive_count,
            "completed_count": len(completed_participants),
            "partial_count": len(partial_participants),
            "no_response_count": len(no_response_participants),
            "completion_rate": round(completion_rate, 2),
            "benchmark_completion_rate": "50-70%"  # Industry standard
        },

        # Score statistics
        "score_statistics": {
            "total_possible_points": total_possible_points,
            "average_score": round(avg_score, 2),
            "median_score": round(median_score, 2),
            "average_percentage": round(avg_percentage, 2),
            "min_score": min_score,
            "max_score": max_score,
            "standard_deviation": round(std_dev, 2),
            "score_distribution": score_ranges
        },

        # Accuracy metrics
        "accuracy": {
            "total_questions": total_questions,
            "average_correct_answers": round(avg_correct, 2),
            "overall_accuracy_rate": round(accuracy_rate, 2)
        },

        # Time metrics
        "timing": {
            "average_total_time_ms": round(avg_time_ms, 0),
            "average_time_per_question_ms": round(avg_time_per_question_ms, 0),
            "average_total_time_minutes": round(avg_time_ms / 60000, 2),
            "average_time_per_question_seconds": round(avg_time_per_question_ms / 1000, 2)
        },

        # Question breakdown
        "questions": question_summaries
    }


def calculate_question_analytics(question_id: str, db: DatabaseService) -> Dict:
    """
    Calculate detailed analytics for a specific question.

    Metrics:
    - Difficulty index (% who answered correctly)
    - Discrimination index (correlation with overall score)
    - Response time distribution
    - Answer choice distribution (for multiple choice)
    - Common wrong answers

    Args:
        question_id: Question ID
        db: Database service

    Returns:
        Dict with question analytics

    Reference:
    - Difficulty index: 0.3-0.7 is ideal (not too easy/hard)
    - Discrimination index: >0.3 is good (differentiates high/low performers)
    """
    question = db.get_question_by_id(question_id)
    if not question:
        return {"error": "Question not found"}

    # Get all responses to this question
    responses = db.get_responses_by_question(question_id)

    if not responses:
        return {
            "question_id": question_id,
            "question_text": question.question_text,
            "question_type": question.question_type,
            "total_responses": 0,
            "message": "No responses yet"
        }

    # Basic statistics
    total_responses = len(responses)
    correct_responses = sum(1 for r in responses if r.is_correct)
    incorrect_responses = total_responses - correct_responses

    # Difficulty index (proportion correct)
    difficulty_index = correct_responses / total_responses if total_responses > 0 else 0

    # Interpret difficulty
    if difficulty_index > 0.9:
        difficulty_interpretation = "Too easy"
    elif difficulty_index > 0.7:
        difficulty_interpretation = "Easy"
    elif difficulty_index >= 0.3:
        difficulty_interpretation = "Moderate (ideal)"
    elif difficulty_index >= 0.1:
        difficulty_interpretation = "Hard"
    else:
        difficulty_interpretation = "Too hard"

    # Discrimination index (point-biserial correlation)
    # Compare scores of those who got it right vs wrong
    correct_participant_scores = []
    incorrect_participant_scores = []

    for response in responses:
        participant = db.get_participant_by_id(response.participant_id)
        if participant:
            if response.is_correct:
                correct_participant_scores.append(participant.score)
            else:
                incorrect_participant_scores.append(participant.score)

    if correct_participant_scores and incorrect_participant_scores:
        avg_correct_score = statistics.mean(correct_participant_scores)
        avg_incorrect_score = statistics.mean(incorrect_participant_scores)
        discrimination_index = (avg_correct_score - avg_incorrect_score) / question.points if question.points > 0 else 0

        # Interpret discrimination
        if discrimination_index > 0.3:
            discrimination_interpretation = "Good discrimination"
        elif discrimination_index > 0.15:
            discrimination_interpretation = "Moderate discrimination"
        else:
            discrimination_interpretation = "Poor discrimination (needs review)"
    else:
        discrimination_index = 0
        discrimination_interpretation = "Insufficient data"

    # Response time analytics
    response_times = [r.time_taken_ms for r in responses]
    avg_time_ms = statistics.mean(response_times)
    median_time_ms = statistics.median(response_times)
    if len(response_times) > 1:
        std_dev_time = statistics.stdev(response_times)
    else:
        std_dev_time = 0

    # Answer distribution (for multiple choice and polls)
    answer_distribution = {}
    if question.question_type in ["multiple_choice", "poll"]:
        answer_choices = Counter()
        for response in responses:
            # Answer is stored as list, get first element
            if response.answer and len(response.answer) > 0:
                answer_choices[response.answer[0]] += 1

        # Calculate percentages
        for answer, count in answer_choices.items():
            percentage = (count / total_responses * 100) if total_responses > 0 else 0
            answer_distribution[answer] = {
                "count": count,
                "percentage": round(percentage, 2)
            }

    return {
        "question_id": question_id,
        "question_text": question.question_text,
        "question_type": question.question_type,
        "points": question.points,
        "time_limit_seconds": question.time_limit_seconds,

        # Response statistics
        "responses": {
            "total": total_responses,
            "correct": correct_responses,
            "incorrect": incorrect_responses,
            "accuracy_rate": round(difficulty_index * 100, 2)
        },

        # Question quality metrics
        "quality_metrics": {
            "difficulty_index": round(difficulty_index, 3),
            "difficulty_interpretation": difficulty_interpretation,
            "ideal_difficulty_range": "0.3 - 0.7",
            "discrimination_index": round(discrimination_index, 3),
            "discrimination_interpretation": discrimination_interpretation,
            "minimum_good_discrimination": 0.3
        },

        # Timing analytics
        "timing": {
            "average_time_ms": round(avg_time_ms, 0),
            "median_time_ms": round(median_time_ms, 0),
            "std_dev_time_ms": round(std_dev_time, 0),
            "average_time_seconds": round(avg_time_ms / 1000, 2)
        },

        # Answer distribution (for MC/polls)
        "answer_distribution": answer_distribution if answer_distribution else None
    }


def calculate_participant_analytics(participant_id: str, db: DatabaseService) -> Dict:
    """
    Calculate detailed analytics for an individual participant.

    Metrics:
    - Overall score and ranking
    - Question-by-question performance
    - Response patterns (speed, accuracy)
    - Strengths and weaknesses

    Args:
        participant_id: Participant ID
        db: Database service

    Returns:
        Dict with participant analytics
    """
    participant = db.get_participant_by_id(participant_id)
    if not participant:
        return {"error": "Participant not found"}

    # Get session and quiz info
    session = db.get_quiz_session_by_id(participant.session_id)
    quiz = db.get_quiz_by_id(session.quiz_id, session.user_id) if session else None
    questions = db.get_questions_by_quiz_id(session.quiz_id, session.user_id) if session else []

    # Get all responses
    responses = db.get_responses_by_participant(participant_id)

    # Calculate rank
    rank, total_participants = db.get_participant_rank(participant_id)

    # Performance by question type
    type_performance = {}
    for response in responses:
        question = db.get_question_by_id(response.question_id)
        if question:
            qtype = question.question_type
            if qtype not in type_performance:
                type_performance[qtype] = {"total": 0, "correct": 0}

            type_performance[qtype]["total"] += 1
            if response.is_correct:
                type_performance[qtype]["correct"] += 1

    # Calculate accuracy by type
    for qtype in type_performance:
        stats = type_performance[qtype]
        stats["accuracy_rate"] = round((stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0, 2)

    # Response details
    response_details = []
    for response in responses:
        question = db.get_question_by_id(response.question_id)
        if question:
            response_details.append({
                "question_id": response.question_id,
                "question_text": question.question_text[:100] + "..." if len(question.question_text) > 100 else question.question_text,
                "question_type": question.question_type,
                "points_possible": question.points,
                "points_earned": response.points_earned,
                "is_correct": response.is_correct,
                "time_taken_ms": response.time_taken_ms,
                "time_taken_seconds": round(response.time_taken_ms / 1000, 2),
                "answered_at": response.answered_at
            })

    # Sort by answered_at
    response_details.sort(key=lambda x: x["answered_at"])

    # Determine display name
    display_name = participant.guest_name if participant.guest_name else "Student"
    is_guest = participant.guest_name is not None

    # Calculate total possible points
    total_possible = sum(q.points for q in questions)

    return {
        "participant_id": participant_id,
        "session_id": participant.session_id,
        "display_name": display_name,
        "is_guest": is_guest,
        "quiz_title": quiz.title if quiz else "Unknown",
        "room_code": session.room_code if session else None,

        # Overall performance
        "performance": {
            "score": participant.score,
            "total_possible_points": total_possible,
            "percentage": round((participant.score / total_possible * 100) if total_possible > 0 else 0, 2),
            "correct_answers": participant.correct_answers,
            "total_questions": len(questions),
            "accuracy_rate": round((participant.correct_answers / len(questions) * 100) if len(questions) > 0 else 0, 2)
        },

        # Ranking
        "ranking": {
            "rank": rank,
            "total_participants": total_participants,
            "percentile": round(((total_participants - rank + 1) / total_participants * 100) if total_participants > 0 else 0, 2)
        },

        # Timing
        "timing": {
            "total_time_ms": participant.total_time_ms,
            "total_time_minutes": round(participant.total_time_ms / 60000, 2),
            "average_time_per_question_ms": round(participant.total_time_ms / len(responses) if responses else 0, 0),
            "average_time_per_question_seconds": round((participant.total_time_ms / len(responses) / 1000) if responses else 0, 2)
        },

        # Performance by question type
        "performance_by_type": type_performance,

        # Detailed responses
        "responses": response_details,

        # Status
        "status": {
            "is_active": participant.is_active,
            "joined_at": participant.joined_at,
            "last_seen_at": participant.last_seen_at
        }
    }


def generate_comparative_analytics(quiz_id: str, user_id: str, db: DatabaseService) -> Dict:
    """
    Generate comparative analytics across all sessions of a quiz.

    Shows trends over time, question performance consistency, etc.

    Args:
        quiz_id: Quiz ID
        user_id: User ID (owner)
        db: Database service

    Returns:
        Dict with comparative analytics
    """
    quiz = db.get_quiz_by_id(quiz_id, user_id)
    if not quiz:
        return {"error": "Quiz not found"}

    # Get all sessions for this quiz
    all_sessions = db.get_all_quiz_sessions(user_id)
    quiz_sessions = [s for s in all_sessions if s.quiz_id == quiz_id]

    if not quiz_sessions:
        return {
            "quiz_id": quiz_id,
            "quiz_title": quiz.title,
            "message": "No sessions yet"
        }

    # Calculate basic stats for each session
    session_summaries = []
    for session in quiz_sessions:
        participants = db.get_participants_by_session(session.id)
        if participants:
            avg_score = statistics.mean([p.score for p in participants])
            avg_accuracy = statistics.mean([p.correct_answers for p in participants])
        else:
            avg_score = avg_accuracy = 0

        session_summaries.append({
            "session_id": session.id,
            "room_code": session.room_code,
            "created_at": session.created_at,
            "status": session.status,
            "participant_count": len(participants),
            "average_score": round(avg_score, 2),
            "average_correct_answers": round(avg_accuracy, 2)
        })

    # Sort by creation date
    session_summaries.sort(key=lambda x: x["created_at"])

    # Overall aggregates
    all_scores = []
    all_participants_count = 0

    for session in quiz_sessions:
        participants = db.get_participants_by_session(session.id)
        all_scores.extend([p.score for p in participants])
        all_participants_count += len(participants)

    if all_scores:
        overall_avg = statistics.mean(all_scores)
        overall_median = statistics.median(all_scores)
    else:
        overall_avg = overall_median = 0

    return {
        "quiz_id": quiz_id,
        "quiz_title": quiz.title,
        "total_sessions": len(quiz_sessions),
        "total_participants_all_time": all_participants_count,

        "overall_statistics": {
            "average_score_all_time": round(overall_avg, 2),
            "median_score_all_time": round(overall_median, 2)
        },

        "sessions": session_summaries
    }
