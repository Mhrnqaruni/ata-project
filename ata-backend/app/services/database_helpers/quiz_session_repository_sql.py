"""
Quiz Session Repository - SQLAlchemy Data Access Layer

This module provides database operations for live quiz session management:
- QuizSession: Live session instances with room codes
- QuizParticipant: Both registered students and guest users
- QuizResponse: Answer submissions with timing and grading

Security principles:
- Session operations validate user ownership (host)
- Participant operations validate either student_id OR guest_token
- Response operations validate participant ownership
- Real-time leaderboard queries optimized with indexes

Pattern: Repository methods return SQLAlchemy model instances.
Business logic (grading, scoring, leaderboards) handled in service layer.
"""

from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, and_, or_, func, desc
from datetime import datetime, timedelta, timezone

# Import SQLAlchemy models
from app.db.models.quiz_models import (
    Quiz, QuizQuestion, QuizSession, QuizParticipant, QuizResponse,
    QuizSessionRoster, QuizOutsiderStudent
)
from app.db.models.class_student_models import Student, Class, StudentClassMembership


class QuizSessionRepositorySQL:
    """Repository for quiz session, participant, and response operations."""

    def __init__(self, db_session: Session):
        """
        Initialize repository with database session.

        Args:
            db_session: SQLAlchemy session for database operations
        """
        self.db = db_session

    # ==================== SESSION CRUD OPERATIONS ====================

    def create_session(self, session_data: Dict) -> QuizSession:
        """
        Create a new quiz session.

        Args:
            session_data: Dictionary with session fields (must include user_id, quiz_id, room_code)

        Returns:
            Created QuizSession instance

        Security: user_id establishes ownership
        """
        new_session = QuizSession(**session_data)
        self.db.add(new_session)
        self.db.commit()
        self.db.refresh(new_session)
        return new_session

    def get_session_by_id(self, session_id: str, user_id: Optional[str] = None) -> Optional[QuizSession]:
        """
        Get a session by ID, optionally validating ownership.

        Args:
            session_id: Session ID
            user_id: Optional user ID (if provided, validates ownership)

        Returns:
            QuizSession instance or None if not found/not owned

        Security: If user_id provided, only returns session if user is the host
        """
        query = self.db.query(QuizSession).filter(QuizSession.id == session_id)

        if user_id:
            query = query.filter(QuizSession.user_id == user_id)

        return query.first()

    def get_session_by_room_code(self, room_code: str) -> Optional[QuizSession]:
        """
        Get a session by room code (for participants joining).

        Args:
            room_code: 6-character room code

        Returns:
            QuizSession instance or None if not found

        Note: No user ownership check - room codes are public join links
        """
        return (
            self.db.query(QuizSession)
            .filter(QuizSession.room_code == room_code)
            .first()
        )

    def get_all_sessions(self, user_id: str, status: Optional[str] = None) -> List[QuizSession]:
        """
        Get all sessions hosted by a user.

        Args:
            user_id: User ID (host filter)
            status: Optional status filter (waiting/active/completed/cancelled)

        Returns:
            List of QuizSession instances

        Security: Only returns sessions hosted by user
        """
        query = self.db.query(QuizSession).filter(QuizSession.user_id == user_id)

        if status:
            query = query.filter(QuizSession.status == status)

        return query.order_by(QuizSession.created_at.desc()).all()

    def get_active_sessions(self, user_id: str) -> List[QuizSession]:
        """
        Get all active sessions for a user.

        Args:
            user_id: User ID (host filter)

        Returns:
            List of active QuizSession instances
        """
        return (
            self.db.query(QuizSession)
            .filter(
                QuizSession.user_id == user_id,
                QuizSession.status.in_(["waiting", "active"])
            )
            .order_by(QuizSession.created_at.desc())
            .all()
        )

    def update_session(self, session_id: str, user_id: str, update_data: Dict) -> Optional[QuizSession]:
        """
        Update a session's fields.

        Args:
            session_id: Session ID
            user_id: User ID (host check)
            update_data: Dictionary of fields to update

        Returns:
            Updated QuizSession instance or None if not found/not owned

        Security: Only updates session if user is the host
        """
        session = self.get_session_by_id(session_id, user_id)
        if session:
            for key, value in update_data.items():
                if hasattr(session, key):
                    setattr(session, key, value)
            self.db.commit()
            self.db.refresh(session)
        return session

    def update_session_status(self, session_id: str, user_id: str, status: str) -> Optional[QuizSession]:
        """
        Update session status with automatic timestamp handling.

        Args:
            session_id: Session ID
            user_id: User ID (host check)
            status: New status (waiting/active/completed/cancelled)

        Returns:
            Updated QuizSession instance or None if not found/not owned

        Note: Automatically sets started_at/ended_at based on status transitions
        """
        update_data = {"status": status}

        # Set timestamps based on status transitions
        if status == "active":
            update_data["started_at"] = datetime.now()
        elif status in ["completed", "cancelled"]:
            update_data["ended_at"] = datetime.now()

        return self.update_session(session_id, user_id, update_data)

    def move_to_next_question(self, session_id: str, user_id: str) -> Optional[QuizSession]:
        """
        Move session to the next question.

        Args:
            session_id: Session ID
            user_id: User ID (host check)

        Returns:
            Updated QuizSession instance or None if not found/not owned

        Note: Service layer should validate question count before calling
        """
        from datetime import datetime

        session = self.get_session_by_id(session_id, user_id)
        if session:
            current_index = session.current_question_index
            if current_index is None:
                session.current_question_index = 0
            else:
                session.current_question_index = current_index + 1

            # Track when this question started for time limit enforcement
            session.question_started_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(session)
        return session

    def check_room_code_exists(self, room_code: str) -> bool:
        """
        Check if a room code is already in use.

        Args:
            room_code: Room code to check

        Returns:
            True if room code exists, False otherwise

        Note: Used for collision detection during room code generation
        """
        return (
            self.db.query(QuizSession)
            .filter(QuizSession.room_code == room_code)
            .first()
        ) is not None

    def get_timed_out_sessions(self) -> List[QuizSession]:
        """
        Find sessions that have exceeded their timeout and should be auto-ended.

        Returns:
            List of QuizSession instances that have timed out

        Note: Used by background cleanup jobs
        """
        return (
            self.db.query(QuizSession)
            .filter(
                QuizSession.status.in_(["waiting", "active"]),
                QuizSession.auto_ended_at.is_(None)
            )
            .all()  # Filter by timeout logic in service layer
        )

    # ==================== PARTICIPANT CRUD OPERATIONS ====================

    def add_participant(self, participant_data: Dict) -> QuizParticipant:
        """
        Add a participant to a session (student or guest).

        Args:
            participant_data: Dictionary with participant fields
                For students: {session_id, student_id}
                For guests: {session_id, guest_name, guest_token}

        Returns:
            Created QuizParticipant instance

        Security: CHECK constraint ensures valid identity (student XOR guest)
        """
        new_participant = QuizParticipant(**participant_data)
        self.db.add(new_participant)
        self.db.commit()
        self.db.refresh(new_participant)
        return new_participant

    def get_participant_by_id(self, participant_id: str) -> Optional[QuizParticipant]:
        """
        Get a participant by ID.

        Args:
            participant_id: Participant ID

        Returns:
            QuizParticipant instance or None if not found
        """
        return (
            self.db.query(QuizParticipant)
            .filter(QuizParticipant.id == participant_id)
            .first()
        )

    def get_participant_by_guest_token(self, guest_token: str) -> Optional[QuizParticipant]:
        """
        Get a participant by their guest token (for authentication).

        Args:
            guest_token: 64-character hex token

        Returns:
            QuizParticipant instance or None if not found

        Security: Used for guest authentication
        """
        return (
            self.db.query(QuizParticipant)
            .filter(QuizParticipant.guest_token == guest_token)
            .first()
        )

    def get_participants_by_session(self, session_id: str, active_only: bool = False) -> List[QuizParticipant]:
        """
        Get all participants in a session.

        Args:
            session_id: Session ID
            active_only: If True, only return active participants

        Returns:
            List of QuizParticipant instances
        """
        query = (
            self.db.query(QuizParticipant)
            .filter(QuizParticipant.session_id == session_id)
        )

        if active_only:
            query = query.filter(QuizParticipant.is_active == True)

        return query.order_by(QuizParticipant.joined_at).all()

    def get_participant_by_student_in_session(self, session_id: str, student_id: str) -> Optional[QuizParticipant]:
        """
        Check if a student is already participating in a session.

        Args:
            session_id: Session ID
            student_id: Student ID

        Returns:
            QuizParticipant instance or None if student hasn't joined

        Note: Used to prevent duplicate joins
        """
        return (
            self.db.query(QuizParticipant)
            .filter(
                QuizParticipant.session_id == session_id,
                QuizParticipant.student_id == student_id
            )
            .first()
        )

    def get_participant_names_in_session(self, session_id: str) -> List[str]:
        """
        Get all display names currently in use in a session.

        Args:
            session_id: Session ID

        Returns:
            List of display names (both student names and guest names)

        Note: Used for duplicate name detection
        """
        participants = self.get_participants_by_session(session_id, active_only=True)
        names = []

        for p in participants:
            if p.guest_name:
                # Guest or identified guest - use guest_name
                names.append(p.guest_name)
            elif p.student_id:
                # Registered student - try to lookup name
                try:
                    student = self.get_student_by_student_id(p.student_id)
                    if student and student.name:
                        names.append(student.name)
                except:
                    # If lookup fails, skip this participant's name
                    pass

        return names

    def update_participant(self, participant_id: str, update_data: Dict) -> Optional[QuizParticipant]:
        """
        Update a participant's fields (score, timing, activity status).

        Args:
            participant_id: Participant ID
            update_data: Dictionary of fields to update

        Returns:
            Updated QuizParticipant instance or None if not found
        """
        participant = self.get_participant_by_id(participant_id)
        if participant:
            for key, value in update_data.items():
                if hasattr(participant, key):
                    setattr(participant, key, value)
            self.db.commit()
            self.db.refresh(participant)
        return participant

    def update_participant_score(self, participant_id: str, points_earned: int,
                                 is_correct: bool, time_taken_ms: int) -> Optional[QuizParticipant]:
        """
        Update participant's score and stats after answering a question.

        FIX #2: Uses pessimistic locking (SELECT FOR UPDATE) to prevent race conditions
        when multiple participants submit answers simultaneously.

        Args:
            participant_id: Participant ID
            points_earned: Points earned for this answer
            is_correct: Whether the answer was correct
            time_taken_ms: Time taken to answer (milliseconds)

        Returns:
            Updated QuizParticipant instance or None if not found

        Note: Row-level lock ensures atomicity in concurrent score updates
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            # FIX #2: Lock the row with SELECT FOR UPDATE to prevent race conditions
            # This prevents other transactions from modifying this participant
            # until our transaction commits
            participant = self.db.query(QuizParticipant).filter(
                QuizParticipant.id == participant_id
            ).with_for_update().first()

            if not participant:
                logger.warning(f"[ScoreUpdate] Participant not found: {participant_id}")
                return None

            logger.info(f"[ScoreUpdate] Participant {participant_id}: "
                       f"+{points_earned} pts, correct={is_correct}, time={time_taken_ms}ms")

            # Perform updates while holding the lock
            participant.score += points_earned
            if is_correct:
                participant.correct_answers += 1
            participant.total_time_ms += time_taken_ms
            participant.last_seen_at = datetime.now()

            self.db.commit()
            self.db.refresh(participant)

            logger.info(f"[ScoreUpdate] Success. Total: {participant.score} pts, "
                       f"{participant.correct_answers} correct")

            return participant

        except Exception as e:
            logger.error(f"[ScoreUpdate] Error: {e}", exc_info=True)
            self.db.rollback()
            raise

    def mark_participant_inactive(self, participant_id: str) -> bool:
        """
        Mark a participant as inactive (disconnected).

        Args:
            participant_id: Participant ID

        Returns:
            True if marked inactive, False if not found
        """
        return self.update_participant(participant_id, {"is_active": False}) is not None

    def get_leaderboard(self, session_id: str, limit: int = 10) -> List[QuizParticipant]:
        """
        Get leaderboard for a session (top N participants by score, then time).

        Args:
            session_id: Session ID
            limit: Number of top participants to return (default: 10)

        Returns:
            List of QuizParticipant instances ordered by rank

        Note: Uses composite index for performance
        """
        return (
            self.db.query(QuizParticipant)
            .filter(QuizParticipant.session_id == session_id)
            .order_by(
                desc(QuizParticipant.score),  # Higher score first
                QuizParticipant.total_time_ms  # Faster time breaks ties
            )
            .limit(limit)
            .all()
        )

    def get_participant_rank(self, participant_id: str) -> Tuple[int, int]:
        """
        Get a participant's rank and total participant count.

        Args:
            participant_id: Participant ID

        Returns:
            Tuple of (rank, total_participants)

        Note: rank is 1-indexed (1 = first place)
        """
        participant = self.get_participant_by_id(participant_id)
        if not participant:
            return (0, 0)

        session_id = participant.session_id

        # Count participants with higher score
        higher_score = (
            self.db.query(func.count(QuizParticipant.id))
            .filter(
                QuizParticipant.session_id == session_id,
                QuizParticipant.score > participant.score
            )
            .scalar() or 0
        )

        # Count participants with same score but faster time
        same_score_faster = (
            self.db.query(func.count(QuizParticipant.id))
            .filter(
                QuizParticipant.session_id == session_id,
                QuizParticipant.score == participant.score,
                QuizParticipant.total_time_ms < participant.total_time_ms
            )
            .scalar() or 0
        )

        # Total participants
        total = (
            self.db.query(func.count(QuizParticipant.id))
            .filter(QuizParticipant.session_id == session_id)
            .scalar() or 0
        )

        rank = higher_score + same_score_faster + 1
        return (rank, total)

    def anonymize_old_guests(self, days: int = 30) -> int:
        """
        Anonymize guest data older than specified days (GDPR compliance).

        Args:
            days: Age threshold in days (default: 30)

        Returns:
            Number of guests anonymized

        Security: GDPR compliance - Right to be Forgotten
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        guests_to_anonymize = (
            self.db.query(QuizParticipant)
            .filter(
                QuizParticipant.guest_token.isnot(None),
                QuizParticipant.joined_at < cutoff_date,
                QuizParticipant.anonymized_at.is_(None)
            )
            .all()
        )

        count = 0
        for guest in guests_to_anonymize:
            # Anonymize name using participant ID
            guest.guest_name = f"Anonymous User {str(guest.id)[:6]}"
            guest.anonymized_at = datetime.now()
            count += 1

        self.db.commit()
        return count

    # ==================== RESPONSE CRUD OPERATIONS ====================

    def submit_response(self, response_data: Dict) -> QuizResponse:
        """
        Record a participant's answer to a question.

        Args:
            response_data: Dictionary with response fields
                {session_id, participant_id, question_id, answer, is_correct, points_earned, time_taken_ms}

        Returns:
            Created QuizResponse instance

        Security: UNIQUE constraint prevents duplicate submissions
        """
        new_response = QuizResponse(**response_data)
        self.db.add(new_response)
        self.db.commit()
        self.db.refresh(new_response)
        return new_response

    def get_response_by_id(self, response_id: str) -> Optional[QuizResponse]:
        """
        Get a response by ID.

        Args:
            response_id: Response ID

        Returns:
            QuizResponse instance or None if not found
        """
        return (
            self.db.query(QuizResponse)
            .filter(QuizResponse.id == response_id)
            .first()
        )

    def get_participant_response_for_question(self, participant_id: str,
                                             question_id: str) -> Optional[QuizResponse]:
        """
        Get a participant's response to a specific question.

        Args:
            participant_id: Participant ID
            question_id: Question ID

        Returns:
            QuizResponse instance or None if not answered

        Note: Used to check if participant already answered
        """
        return (
            self.db.query(QuizResponse)
            .filter(
                QuizResponse.participant_id == participant_id,
                QuizResponse.question_id == question_id
            )
            .first()
        )

    def get_responses_by_participant(self, participant_id: str) -> List[QuizResponse]:
        """
        Get all responses submitted by a participant.

        Args:
            participant_id: Participant ID

        Returns:
            List of QuizResponse instances ordered by submission time
        """
        return (
            self.db.query(QuizResponse)
            .filter(QuizResponse.participant_id == participant_id)
            .order_by(QuizResponse.answered_at)
            .all()
        )

    def get_responses_by_session(self, session_id: str) -> List[QuizResponse]:
        """
        Get all responses in a session.

        Args:
            session_id: Session ID

        Returns:
            List of QuizResponse instances
        """
        return (
            self.db.query(QuizResponse)
            .filter(QuizResponse.session_id == session_id)
            .order_by(QuizResponse.answered_at)
            .all()
        )

    def get_responses_by_question(self, question_id: str) -> List[QuizResponse]:
        """
        Get all responses to a specific question.

        Args:
            question_id: Question ID

        Returns:
            List of QuizResponse instances

        Note: Used for question-level analytics
        """
        return (
            self.db.query(QuizResponse)
            .filter(QuizResponse.question_id == question_id)
            .all()
        )

    def get_question_response_count(self, session_id: str, question_id: str) -> int:
        """
        Count how many participants have answered a question.

        Args:
            session_id: Session ID
            question_id: Question ID

        Returns:
            Number of responses

        Note: Used to track question progress in real-time
        """
        return (
            self.db.query(func.count(QuizResponse.id))
            .filter(
                QuizResponse.session_id == session_id,
                QuizResponse.question_id == question_id
            )
            .scalar() or 0
        )

    def get_question_correctness_stats(self, question_id: str) -> Dict:
        """
        Get correctness statistics for a question.

        Args:
            question_id: Question ID

        Returns:
            Dictionary with {total, correct, incorrect, accuracy_rate}

        Note: Used for question analytics
        """
        total = (
            self.db.query(func.count(QuizResponse.id))
            .filter(QuizResponse.question_id == question_id)
            .scalar() or 0
        )

        correct = (
            self.db.query(func.count(QuizResponse.id))
            .filter(
                QuizResponse.question_id == question_id,
                QuizResponse.is_correct == True
            )
            .scalar() or 0
        )

        return {
            "total": total,
            "correct": correct,
            "incorrect": total - correct,
            "accuracy_rate": correct / total if total > 0 else 0.0
        }

    # ==================== ROSTER TRACKING OPERATIONS ====================

    def create_roster_entry(self, roster_data: Dict) -> QuizSessionRoster:
        """
        Create a new roster entry (expected student).

        Args:
            roster_data: Dictionary with roster fields (session_id, student_id, student_name, student_school_id)

        Returns:
            Created QuizSessionRoster instance

        Usage: Called when creating roster snapshot from class membership
        """
        new_roster_entry = QuizSessionRoster(**roster_data)
        self.db.add(new_roster_entry)
        self.db.commit()
        self.db.refresh(new_roster_entry)
        return new_roster_entry

    def create_roster_entries_bulk(self, roster_entries: List[Dict]) -> List[QuizSessionRoster]:
        """
        Create multiple roster entries in a single transaction.

        Args:
            roster_entries: List of roster entry dictionaries

        Returns:
            List of created QuizSessionRoster instances

        Usage: Efficient batch creation when syncing class roster to session
        """
        roster_objects = [QuizSessionRoster(**entry) for entry in roster_entries]
        self.db.add_all(roster_objects)
        self.db.commit()
        for obj in roster_objects:
            self.db.refresh(obj)
        return roster_objects

    def get_roster_by_session(self, session_id: str) -> List[QuizSessionRoster]:
        """
        Get all roster entries for a session.

        Args:
            session_id: Session ID

        Returns:
            List of QuizSessionRoster instances ordered by student_name

        Usage: Display expected students list to teacher
        """
        return (
            self.db.query(QuizSessionRoster)
            .filter(QuizSessionRoster.session_id == session_id)
            .order_by(QuizSessionRoster.student_name)
            .all()
        )

    def get_roster_entry_by_student(
        self, session_id: str, student_id: str
    ) -> Optional[QuizSessionRoster]:
        """
        Get a specific roster entry for a student in a session.

        Args:
            session_id: Session ID
            student_id: Student ID from students table

        Returns:
            QuizSessionRoster instance or None if not found

        Usage: Check if student was expected when they join
        """
        return (
            self.db.query(QuizSessionRoster)
            .filter(
                QuizSessionRoster.session_id == session_id,
                QuizSessionRoster.student_id == student_id
            )
            .first()
        )

    def update_roster_entry_joined(
        self, roster_entry_id: str, participant_id: str, joined_at: datetime
    ) -> Optional[QuizSessionRoster]:
        """
        Mark a roster entry as joined and link to participant.

        Args:
            roster_entry_id: Roster entry ID
            participant_id: Participant ID who joined
            joined_at: Timestamp when student joined

        Returns:
            Updated QuizSessionRoster instance or None if not found

        Usage: Called when expected student joins session
        """
        roster_entry = self.db.query(QuizSessionRoster).filter(
            QuizSessionRoster.id == roster_entry_id
        ).first()

        if roster_entry:
            roster_entry.joined = True
            roster_entry.joined_at = joined_at
            roster_entry.participant_id = participant_id
            self.db.commit()
            self.db.refresh(roster_entry)

        return roster_entry

    def get_roster_attendance_stats(self, session_id: str) -> Dict:
        """
        Get attendance statistics for a session's roster.

        Args:
            session_id: Session ID

        Returns:
            Dictionary with {total_expected, total_joined, total_absent, join_rate}

        Usage: Display attendance summary to teacher
        """
        total_expected = (
            self.db.query(func.count(QuizSessionRoster.id))
            .filter(QuizSessionRoster.session_id == session_id)
            .scalar() or 0
        )

        total_joined = (
            self.db.query(func.count(QuizSessionRoster.id))
            .filter(
                QuizSessionRoster.session_id == session_id,
                QuizSessionRoster.joined == True
            )
            .scalar() or 0
        )

        join_rate = total_joined / total_expected if total_expected > 0 else 0.0

        return {
            "total_expected": total_expected,
            "total_joined": total_joined,
            "total_absent": total_expected - total_joined,
            "join_rate": join_rate
        }

    # ==================== OUTSIDER STUDENT OPERATIONS ====================

    def create_outsider_record(self, outsider_data: Dict) -> QuizOutsiderStudent:
        """
        Create a new outsider student record.

        Args:
            outsider_data: Dictionary with outsider fields (session_id, participant_id, student_school_id, guest_name, detection_reason)

        Returns:
            Created QuizOutsiderStudent instance

        Usage: Called when student joins but isn't on expected roster
        """
        new_outsider = QuizOutsiderStudent(**outsider_data)
        self.db.add(new_outsider)
        self.db.commit()
        self.db.refresh(new_outsider)
        return new_outsider

    def get_outsiders_by_session(self, session_id: str) -> List[QuizOutsiderStudent]:
        """
        Get all outsider students for a session.

        Args:
            session_id: Session ID

        Returns:
            List of QuizOutsiderStudent instances

        Usage: Display outsider list to teacher for review
        """
        return (
            self.db.query(QuizOutsiderStudent)
            .filter(QuizOutsiderStudent.session_id == session_id)
            .order_by(QuizOutsiderStudent.created_at)
            .all()
        )

    def get_outsider_by_participant(
        self, session_id: str, participant_id: str
    ) -> Optional[QuizOutsiderStudent]:
        """
        Get outsider record for a specific participant.

        Args:
            session_id: Session ID
            participant_id: Participant ID

        Returns:
            QuizOutsiderStudent instance or None if not found

        Usage: Check if participant is an outsider
        """
        return (
            self.db.query(QuizOutsiderStudent)
            .filter(
                QuizOutsiderStudent.session_id == session_id,
                QuizOutsiderStudent.participant_id == participant_id
            )
            .first()
        )

    def flag_outsider_by_teacher(
        self, outsider_id: str, flagged: bool, teacher_notes: Optional[str] = None
    ) -> Optional[QuizOutsiderStudent]:
        """
        Flag or unflag an outsider student for teacher review.

        Args:
            outsider_id: Outsider record ID
            flagged: Whether to flag the outsider
            teacher_notes: Optional notes from teacher

        Returns:
            Updated QuizOutsiderStudent instance or None if not found

        Usage: Teacher reviews and marks suspicious outsiders
        """
        outsider = self.db.query(QuizOutsiderStudent).filter(
            QuizOutsiderStudent.id == outsider_id
        ).first()

        if outsider:
            outsider.flagged_by_teacher = flagged
            if teacher_notes is not None:
                outsider.teacher_notes = teacher_notes
            self.db.commit()
            self.db.refresh(outsider)

        return outsider

    def get_outsider_count(self, session_id: str) -> int:
        """
        Get count of outsider students in a session.

        Args:
            session_id: Session ID

        Returns:
            Number of outsider students

        Usage: Quick stats for session dashboard
        """
        return (
            self.db.query(func.count(QuizOutsiderStudent.id))
            .filter(QuizOutsiderStudent.session_id == session_id)
            .scalar() or 0
        )
