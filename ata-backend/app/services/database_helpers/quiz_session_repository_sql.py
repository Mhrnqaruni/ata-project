# /ata-backend/app/services/database_helpers/quiz_session_repository_sql.py

"""
This module contains all the raw SQLAlchemy queries for QuizSession, QuizParticipant,
and QuizResponse tables. It handles the complete session lifecycle including:
- Session creation and management
- Participant joining (both registered students and guests)
- Answer submission and tracking
- Leaderboard calculations

Every method that reads or modifies user-owned data requires a `user_id`,
ensuring all operations are securely scoped to the authenticated user.
"""

from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from datetime import datetime, timedelta

# Import the SQLAlchemy models this repository will interact with.
from app.db.models.quiz_models import (
    Quiz,
    QuizQuestion,
    QuizSession,
    QuizParticipant,
    QuizResponse
)
from app.db.models.class_student_models import Student


class QuizSessionRepositorySQL:
    def __init__(self, db_session: Session):
        self.db = db_session

    # --- Session CRUD Methods ---

    def create_session(self, record: Dict) -> QuizSession:
        """
        Creates a new QuizSession record.
        This function expects `quiz_id`, `user_id`, and `room_code` to be present.
        """
        new_session = QuizSession(**record)
        self.db.add(new_session)
        self.db.commit()
        self.db.refresh(new_session)
        return new_session

    def get_session_by_id(self, session_id: str, user_id: str) -> Optional[QuizSession]:
        """
        Retrieves a single session by its ID, but only if its parent quiz
        is owned by the specified user.
        """
        return (
            self.db.query(QuizSession)
            .join(Quiz, QuizSession.quiz_id == Quiz.id)
            .filter(
                QuizSession.id == session_id,
                Quiz.user_id == user_id
            )
            .first()
        )

    def get_session_by_room_code(self, room_code: str) -> Optional[QuizSession]:
        """
        Retrieves a session by room code. Used for students joining.
        No user_id required since students don't own the session.
        """
        return (
            self.db.query(QuizSession)
            .filter(QuizSession.room_code == room_code)
            .first()
        )

    def get_sessions_by_quiz(self, quiz_id: str, user_id: str) -> List[QuizSession]:
        """
        Retrieves all sessions for a specific quiz, ordered by most recent.
        Ensures the quiz is owned by the user.
        """
        return (
            self.db.query(QuizSession)
            .join(Quiz, QuizSession.quiz_id == Quiz.id)
            .filter(
                QuizSession.quiz_id == quiz_id,
                Quiz.user_id == user_id
            )
            .order_by(QuizSession.created_at.desc())
            .all()
        )

    def get_active_sessions_by_user(self, user_id: str) -> List[QuizSession]:
        """
        Retrieves all active sessions (waiting or in_progress) owned by the user.
        """
        return (
            self.db.query(QuizSession)
            .filter(
                QuizSession.user_id == user_id,
                QuizSession.status.in_(['waiting', 'in_progress'])
            )
            .order_by(QuizSession.created_at.desc())
            .all()
        )

    def update_session_status(self, session_id: str, user_id: str, status: str) -> bool:
        """
        Updates the status of a session. Optionally sets started_at or ended_at.
        """
        session = self.get_session_by_id(session_id=session_id, user_id=user_id)
        if session:
            session.status = status
            if status == 'in_progress' and not session.started_at:
                session.started_at = datetime.now()
            elif status in ['completed', 'cancelled'] and not session.ended_at:
                session.ended_at = datetime.now()
            self.db.commit()
            return True
        return False

    def update_current_question(self, session_id: str, user_id: str, question_index: int) -> bool:
        """
        Updates the current_question_index. Used when advancing to next question.
        """
        session = self.get_session_by_id(session_id=session_id, user_id=user_id)
        if session:
            session.current_question_index = question_index
            self.db.commit()
            return True
        return False

    def is_room_code_unique(self, room_code: str) -> bool:
        """
        Checks if a room code is not currently in use by any active session.
        """
        existing = (
            self.db.query(QuizSession)
            .filter(QuizSession.room_code == room_code)
            .first()
        )
        return existing is None

    def get_expired_sessions(self, hours_ago: int) -> List[QuizSession]:
        """
        Retrieves sessions that are still in 'waiting' or 'in_progress' status
        but were created more than `hours_ago` hours ago (for cleanup job).
        """
        cutoff_time = datetime.now() - timedelta(hours=hours_ago)
        return (
            self.db.query(QuizSession)
            .filter(
                QuizSession.status.in_(['waiting', 'in_progress']),
                QuizSession.created_at < cutoff_time
            )
            .all()
        )

    def auto_end_session(self, session_id: str) -> bool:
        """
        Automatically ends a session that has timed out.
        """
        session = self.db.query(QuizSession).filter(QuizSession.id == session_id).first()
        if session and session.status in ['waiting', 'in_progress']:
            session.status = 'completed'
            session.auto_ended_at = datetime.now()
            if not session.ended_at:
                session.ended_at = datetime.now()
            self.db.commit()
            return True
        return False

    # --- Participant Management Methods ---

    def add_participant(self, record: Dict) -> QuizParticipant:
        """
        Creates a new QuizParticipant record (either student or guest).
        """
        new_participant = QuizParticipant(**record)
        self.db.add(new_participant)
        self.db.commit()
        self.db.refresh(new_participant)
        return new_participant

    def get_participant_by_id(self, participant_id: str) -> Optional[QuizParticipant]:
        """
        Retrieves a participant by ID. No user_id check needed as this is session-specific.
        """
        return (
            self.db.query(QuizParticipant)
            .filter(QuizParticipant.id == participant_id)
            .first()
        )

    def get_participant_by_guest_token(self, guest_token: str) -> Optional[QuizParticipant]:
        """
        Retrieves a participant by their guest authentication token.
        """
        return (
            self.db.query(QuizParticipant)
            .filter(QuizParticipant.guest_token == guest_token)
            .first()
        )

    def get_participants_by_session(self, session_id: str) -> List[QuizParticipant]:
        """
        Retrieves all participants for a session, ordered by join time.
        """
        return (
            self.db.query(QuizParticipant)
            .filter(QuizParticipant.session_id == session_id)
            .order_by(QuizParticipant.joined_at.asc())
            .all()
        )

    def get_active_participants_by_session(self, session_id: str) -> List[QuizParticipant]:
        """
        Retrieves only active participants for a session.
        """
        return (
            self.db.query(QuizParticipant)
            .filter(
                QuizParticipant.session_id == session_id,
                QuizParticipant.is_active == True
            )
            .order_by(QuizParticipant.joined_at.asc())
            .all()
        )

    def update_participant_status(self, participant_id: str, is_active: bool) -> bool:
        """
        Updates the is_active status of a participant.
        """
        participant = self.get_participant_by_id(participant_id=participant_id)
        if participant:
            participant.is_active = is_active
            if not is_active and not participant.left_at:
                participant.left_at = datetime.now()
            self.db.commit()
            return True
        return False

    def update_participant_score(self, participant_id: str, points_to_add: int, time_to_add: int, is_correct: bool) -> bool:
        """
        Updates a participant's score, correct answer count, and total time.
        Called after each answer submission.
        """
        participant = self.get_participant_by_id(participant_id=participant_id)
        if participant:
            participant.score += points_to_add
            participant.total_time_ms += time_to_add
            if is_correct:
                participant.correct_answers += 1
            self.db.commit()
            return True
        return False

    def check_duplicate_participant(self, session_id: str, student_id: Optional[str] = None, guest_name: Optional[str] = None) -> Optional[QuizParticipant]:
        """
        Checks if a student or guest with the same name already joined the session.
        """
        if student_id:
            return (
                self.db.query(QuizParticipant)
                .filter(
                    QuizParticipant.session_id == session_id,
                    QuizParticipant.student_id == student_id
                )
                .first()
            )
        elif guest_name:
            return (
                self.db.query(QuizParticipant)
                .filter(
                    QuizParticipant.session_id == session_id,
                    QuizParticipant.guest_name == guest_name
                )
                .first()
            )
        return None

    def get_leaderboard(self, session_id: str, limit: Optional[int] = None) -> List[QuizParticipant]:
        """
        Retrieves participants ordered by score (desc) then time (asc) for leaderboard.
        Uses the optimized composite index for performance.
        """
        query = (
            self.db.query(QuizParticipant)
            .filter(QuizParticipant.session_id == session_id)
            .order_by(
                desc(QuizParticipant.score),
                QuizParticipant.total_time_ms.asc()
            )
        )

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_participant_rank(self, participant_id: str, session_id: str) -> Optional[int]:
        """
        Calculates the rank of a specific participant in the session.
        Returns 1-indexed rank (1 is first place).
        """
        participant = self.get_participant_by_id(participant_id=participant_id)
        if not participant:
            return None

        # Count participants with better score or same score but faster time
        better_count = (
            self.db.query(func.count(QuizParticipant.id))
            .filter(
                QuizParticipant.session_id == session_id,
                or_(
                    QuizParticipant.score > participant.score,
                    and_(
                        QuizParticipant.score == participant.score,
                        QuizParticipant.total_time_ms < participant.total_time_ms
                    )
                )
            )
            .scalar()
        )

        return better_count + 1

    # --- GDPR Cleanup Methods ---

    def get_old_guest_participants(self, days_ago: int) -> List[QuizParticipant]:
        """
        Retrieves guest participants that need anonymization (older than X days).
        """
        cutoff_date = datetime.now() - timedelta(days=days_ago)
        return (
            self.db.query(QuizParticipant)
            .filter(
                QuizParticipant.guest_name.isnot(None),
                QuizParticipant.anonymized_at.is_(None),
                QuizParticipant.joined_at < cutoff_date
            )
            .all()
        )

    def anonymize_participant(self, participant_id: str) -> bool:
        """
        Anonymizes a guest participant's name for GDPR compliance.
        """
        participant = self.get_participant_by_id(participant_id=participant_id)
        if participant and participant.guest_name:
            # Use last 6 characters of participant_id for unique identifier
            suffix = participant.id[-6:]
            participant.guest_name = f"Anonymous User #{suffix}"
            participant.anonymized_at = datetime.now()
            self.db.commit()
            return True
        return False

    # --- Response/Answer Methods ---

    def add_response(self, record: Dict) -> QuizResponse:
        """
        Creates a new QuizResponse record.
        """
        new_response = QuizResponse(**record)
        self.db.add(new_response)
        self.db.commit()
        self.db.refresh(new_response)
        return new_response

    def get_response_by_id(self, response_id: str) -> Optional[QuizResponse]:
        """
        Retrieves a response by ID.
        """
        return (
            self.db.query(QuizResponse)
            .filter(QuizResponse.id == response_id)
            .first()
        )

    def get_participant_answer(self, session_id: str, participant_id: str, question_id: str) -> Optional[QuizResponse]:
        """
        Retrieves a participant's answer for a specific question.
        Returns None if not answered yet.
        """
        return (
            self.db.query(QuizResponse)
            .filter(
                QuizResponse.session_id == session_id,
                QuizResponse.participant_id == participant_id,
                QuizResponse.question_id == question_id
            )
            .first()
        )

    def get_all_responses_for_session(self, session_id: str) -> List[QuizResponse]:
        """
        Retrieves all responses for a session, ordered by submission time.
        """
        return (
            self.db.query(QuizResponse)
            .filter(QuizResponse.session_id == session_id)
            .order_by(QuizResponse.answered_at.asc())
            .all()
        )

    def get_responses_for_participant(self, participant_id: str) -> List[QuizResponse]:
        """
        Retrieves all responses from a specific participant.
        """
        return (
            self.db.query(QuizResponse)
            .filter(QuizResponse.participant_id == participant_id)
            .all()
        )

    def get_responses_for_question(self, session_id: str, question_id: str) -> List[QuizResponse]:
        """
        Retrieves all responses for a specific question in a session.
        Used for analytics.
        """
        return (
            self.db.query(QuizResponse)
            .filter(
                QuizResponse.session_id == session_id,
                QuizResponse.question_id == question_id
            )
            .all()
        )

    def get_question_analytics(self, session_id: str, question_id: str) -> Dict:
        """
        Calculates analytics for a specific question:
        - Total attempts
        - Correct count
        - Incorrect count
        - Average time taken
        - Correct percentage
        """
        responses = self.get_responses_for_question(session_id, question_id)

        if not responses:
            return {
                'total_attempts': 0,
                'correct_count': 0,
                'incorrect_count': 0,
                'avg_time_ms': 0,
                'correct_percentage': 0
            }

        correct_count = sum(1 for r in responses if r.is_correct)
        incorrect_count = sum(1 for r in responses if r.is_correct == False)  # Exclude None (polls)
        avg_time = sum(r.time_taken_ms for r in responses) / len(responses)

        return {
            'total_attempts': len(responses),
            'correct_count': correct_count,
            'incorrect_count': incorrect_count,
            'avg_time_ms': int(avg_time),
            'correct_percentage': (correct_count / len(responses) * 100) if len(responses) > 0 else 0
        }

    def get_participant_progress(self, participant_id: str, total_questions: int) -> Dict:
        """
        Calculates a participant's progress in the quiz.
        """
        responses = self.get_responses_for_participant(participant_id)

        return {
            'answered': len(responses),
            'remaining': total_questions - len(responses),
            'percentage': (len(responses) / total_questions * 100) if total_questions > 0 else 0
        }

    def has_participant_answered_question(self, session_id: str, participant_id: str, question_id: str) -> bool:
        """
        Checks if a participant has already answered a specific question.
        """
        return self.get_participant_answer(session_id, participant_id, question_id) is not None
