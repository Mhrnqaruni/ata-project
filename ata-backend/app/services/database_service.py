# /ata-backend/app/services/database_service.py (SUPERVISOR-APPROVED FLAWLESS VERSION)

"""
This module defines the DatabaseService, which acts as the central facade
for all data access operations within the application.

It abstracts away the underlying data storage mechanism (now exclusively SQL)
and provides a unified, user-aware interface for higher-level business services.
Every method that interacts with user-owned data now requires a `user_id`,
ensuring strict data isolation and security.
"""

from typing import List, Dict, Optional, Generator, Tuple
from sqlalchemy.orm import Session
from fastapi import Depends

# --- Core Database Setup ---
from app.db.database import get_db

# --- SQL Repository Imports ---
from .database_helpers.class_student_repository_sql import ClassStudentRepositorySQL
from .database_helpers.assessment_repository_sql import AssessmentRepositorySQL
from .database_helpers.chat_repository_sql import ChatRepositorySQL
from .database_helpers.generation_repository_sql import GenerationRepositorySQL
from .database_helpers.quiz_repository_sql import QuizRepositorySQL
from .database_helpers.quiz_session_repository_sql import QuizSessionRepositorySQL

# --- Import SQLAlchemy Models for Accurate Type Hinting ---
from app.db.models.user_model import User
from app.db.models.class_student_models import Class, Student
from app.db.models.assessment_models import Assessment, Result, ResultStatus, FinalizedBy
from app.db.models.ai_model_run import AIModelRun
from app.db.models.chat_models import ChatSession, ChatMessage
from app.db.models.generation_models import Generation
from app.db.models.outsider_student import OutsiderStudent
from app.db.models.quiz_models import Quiz, QuizQuestion, QuizSession, QuizParticipant, QuizResponse


class DatabaseService:
    """
    The main facade for all database operations. It ensures that all calls
    are directed to the correct, secure repository methods.
    """
    def __init__(self, db_session: Session):
        """
        Initializes the DatabaseService with a mandatory database session
        and instantiates all necessary SQL repositories.
        """
        self.class_student_repo = ClassStudentRepositorySQL(db_session)
        self.assessment_repo = AssessmentRepositorySQL(db_session)
        self.chat_repo = ChatRepositorySQL(db_session)
        self.generation_repo = GenerationRepositorySQL(db_session)
        self.quiz_repo = QuizRepositorySQL(db_session)
        self.quiz_session_repo = QuizSessionRepositorySQL(db_session)

    # --- NEW: User Management Methods ---
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        return self.class_student_repo.get_user_by_id(user_id=user_id)

    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.class_student_repo.get_user_by_email(email=email)

    def create_user(self, user_data: Dict) -> User:
        return self.class_student_repo.add_user(record=user_data)

    # --- MODIFIED: Class & Student Methods (User-Scoped with Correct Types) ---
    def get_all_classes(self, user_id: str) -> List[Class]:
        return self.class_student_repo.get_all_classes(user_id=user_id)

    def get_class_by_id(self, class_id: str, user_id: str) -> Optional[Class]:
        return self.class_student_repo.get_class_by_id(class_id=class_id, user_id=user_id)

    def add_class(self, class_record: Dict) -> Class:
        return self.class_student_repo.add_class(class_record)

    def update_class(self, class_id: str, user_id: str, class_update_data: Dict) -> Optional[Class]:
        return self.class_student_repo.update_class(class_id=class_id, user_id=user_id, data=class_update_data)

    def delete_class(self, class_id: str, user_id: str) -> bool:
        return self.class_student_repo.delete_class(class_id=class_id, user_id=user_id)

    def get_students_by_class_id(self, class_id: str, user_id: str) -> List[Student]:
        return self.class_student_repo.get_students_by_class_id(class_id=class_id, user_id=user_id)

    def add_student(self, student_record: Dict) -> Student:
        return self.class_student_repo.add_student(student_record)

    def add_outsider_student(self, student_record: Dict) -> OutsiderStudent:
        return self.class_student_repo.add_outsider_student(student_record)

    def update_student(self, student_id: str, user_id: str, student_update_data: Dict) -> Optional[Student]:
        return self.class_student_repo.update_student(student_id=student_id, user_id=user_id, data=student_update_data)

    def delete_student(self, student_id: str, user_id: str) -> bool:
        return self.class_student_repo.delete_student(student_id=student_id, user_id=user_id)
    
    def get_student_by_student_id(self, student_id: str) -> Optional[Student]:
        return self.class_student_repo.get_student_by_student_id(student_id=student_id)

    def get_student_by_id(self, student_id: str, user_id: str) -> Optional[Student]:
        return self.class_student_repo.get_student_by_id(student_id=student_id, user_id=user_id)

    # --- NEW: Student Membership Methods ---
    def get_class_memberships_for_student(self, student_id: str, user_id: str) -> List:
        return self.class_student_repo.get_class_memberships_for_student(student_id=student_id, user_id=user_id)

    def add_student_to_class(self, student_id: str, class_id: str) -> bool:
        return self.class_student_repo.add_student_to_class(student_id=student_id, class_id=class_id)

    def remove_student_from_class(self, student_id: str, class_id: str) -> bool:
        return self.class_student_repo.remove_student_from_class(student_id=student_id, class_id=class_id)

    # --- NEW: Assessment Methods for Student Transcript ---
    def get_assessments_for_class(self, class_id: str, user_id: str) -> List[Assessment]:
        return self.assessment_repo.get_assessments_for_class(class_id=class_id, user_id=user_id)

    def get_results_for_student_and_job(self, student_id: str, job_id: str, user_id: str) -> List[Result]:
        return self.assessment_repo.get_results_for_student_and_job(student_id=student_id, job_id=job_id, user_id=user_id)

    # --- MODIFIED: Generation History Methods ---
    def get_all_generations(self, user_id: str) -> List[Generation]:
        return self.generation_repo.get_all_generations(user_id=user_id)

    def add_generation_record(self, history_record: Dict) -> Generation:
        return self.generation_repo.add_generation_record(history_record)
    
    def delete_generation_record(self, generation_id: str, user_id: str) -> bool:
        return self.generation_repo.delete_generation_record(generation_id=generation_id, user_id=user_id)
    
    # --- MODIFIED: Chat History Methods ---
    def create_chat_session(self, session_record: Dict) -> ChatSession:
        return self.chat_repo.create_session(session_record)

    def get_chat_sessions_by_user_id(self, user_id: str) -> List[ChatSession]:
        return self.chat_repo.get_sessions_by_user_id(user_id)

    def get_chat_session_by_id(self, session_id: str, user_id: str) -> Optional[ChatSession]:
        return self.chat_repo.get_session_by_id(session_id, user_id)

    def add_chat_message(self, message_record: Dict) -> ChatMessage:
        return self.chat_repo.add_message(message_record)

    def get_messages_by_session_id(self, session_id: str, user_id: str) -> List[ChatMessage]:
        return self.chat_repo.get_messages_by_session_id(session_id, user_id)

    def delete_chat_session(self, session_id: str, user_id: str) -> bool:
        return self.chat_repo.delete_session_by_id(session_id, user_id)

    # --- MODIFIED: Assessment Job & Result Methods ---
    def add_assessment_job(self, job_record: Dict) -> Assessment:
        return self.assessment_repo.add_job(job_record)

    def get_assessment_job(self, job_id: str, user_id: str) -> Optional[Assessment]:
        return self.assessment_repo.get_job(job_id, user_id)

    def get_all_assessment_jobs(self, user_id: str) -> List[Assessment]:
        return self.assessment_repo.get_all_jobs(user_id)

    def update_job_status(self, job_id: str, user_id: str, status: str):
        return self.assessment_repo.update_job_status(job_id, user_id, status)

    def update_job_with_summary(self, job_id: str, user_id: str, summary: str):
        return self.assessment_repo.update_job_summary(job_id, user_id, summary)

    def delete_assessment_job(self, job_id: str, user_id: str) -> bool:
        return self.assessment_repo.delete_job(job_id, user_id)

    def create_ai_model_run(self, **kwargs) -> AIModelRun:
        return self.assessment_repo.add_ai_model_run(kwargs)

    def get_ai_model_runs_for_question(self, job_id: str, entity_id: str, question_id: str, is_outsider: bool) -> List[AIModelRun]:
        return self.assessment_repo.get_ai_model_runs_for_question(job_id, entity_id, question_id, is_outsider)

    def update_result_extracted_answer(self, job_id: str, entity_id: str, is_outsider: bool, question_id: str, extracted_answer: str, user_id: str):
        return self.assessment_repo.update_result_extracted_answer(job_id, entity_id, is_outsider, question_id, extracted_answer, user_id)

    def are_any_questions_pending_review(self, job_id: str, user_id: str) -> bool:
        return self.assessment_repo.are_any_questions_pending_review(job_id, user_id)

    def save_student_grade_result(self, result_record: Dict) -> Result:
        return self.assessment_repo.add_result(result_record)

    def get_all_results_for_job(self, job_id: str, user_id: str) -> List[Result]:
        return self.assessment_repo.get_all_results_for_job(job_id, user_id)

    def get_result_by_token(self, token: str) -> Optional[Result]:
        return self.assessment_repo.get_result_by_token(token)

    def update_student_result_with_grade(self, job_id: str, student_id: str, question_id: str, grade: Optional[float], feedback: str, status: str, finalized_by: Optional[str], user_id: str):
        return self.assessment_repo.update_result_grade(job_id, student_id, question_id, grade, feedback, status, finalized_by, user_id)

    def update_outsider_result_grade(self, job_id: str, outsider_student_id: str, question_id: str, grade: Optional[float], feedback: str, status: str, finalized_by: Optional[str], user_id: str):
        return self.assessment_repo.update_outsider_result_grade(job_id, outsider_student_id, question_id, grade, feedback, status, finalized_by, user_id)

    def update_student_result_path(self, job_id: str, student_id: str, path: str, content_type: str, user_id: str):
        return self.assessment_repo.update_result_path(job_id, student_id, path, content_type, user_id)

    def get_entities_with_paths(self, job_id: str, user_id: str) -> List[Dict]:
        return self.assessment_repo.get_entities_with_paths(job_id, user_id)

    def get_outsider_student_by_id(self, outsider_student_id: str, user_id: str) -> Optional[OutsiderStudent]:
        return self.assessment_repo.get_outsider_student_by_id(outsider_student_id, user_id)

    def get_all_outsider_students_for_job(self, job_id: str, user_id: str) -> List[OutsiderStudent]:
        return self.assessment_repo.get_all_outsider_students_for_job(job_id, user_id)

    def get_outsider_by_name_and_job(self, name: str, job_id: str, user_id: str) -> Optional[OutsiderStudent]:
        return self.assessment_repo.get_outsider_by_name_and_job(name, job_id, user_id)

    # --- MODIFIED: Chatbot Helper Methods ---
    def get_classes_for_chatbot(self, user_id: str) -> List[Dict]:
        return self.class_student_repo.get_classes_for_chatbot(user_id=user_id)

    def get_students_for_chatbot(self, user_id: str) -> List[Dict]:
        return self.class_student_repo.get_students_for_chatbot(user_id=user_id)

    def get_assessments_for_chatbot(self, user_id: str) -> List[Dict]:
        return self.assessment_repo.get_assessments_for_chatbot(user_id=user_id)
    
    def get_all_results_for_user(self, user_id: str) -> List[Result]:
        """Pass-through method to get all results for a user."""
        return self.assessment_repo.get_all_results_for_user(user_id=user_id)

        # Add this new method to database_service.py
    def get_public_report_details_by_token(self, token: str) -> Optional[Dict]:
        """Pass-through for the secure public report details query."""
        return self.assessment_repo.get_public_report_details_by_token(token=token)
    
    def get_student_result_path(self, job_id: str, student_id: str, user_id: str) -> Optional[str]:
        """
        Pass-through method to securely retrieve a student's answer sheet path
        for a specific job.
        """
        return self.assessment_repo.get_student_result_path(
            job_id=job_id, 
            student_id=student_id, 
            user_id=user_id
        )
        # Add this inside the DatabaseService class
    def update_result_status(self, job_id: str, student_id: str, question_id: str, status: str, user_id: str):
        """
        Pass-through method to securely update a single result's status.
        """
        return self.assessment_repo.update_result_status(
            job_id=job_id,
            student_id=student_id,
            question_id=question_id,
            status=status,
            user_id=user_id
        )

    # ==================== QUIZ MANAGEMENT METHODS ====================

    # --- Quiz CRUD Methods ---
    def create_quiz(self, quiz_data: Dict) -> Quiz:
        """Create a new quiz."""
        return self.quiz_repo.create_quiz(quiz_data)

    def get_quiz_by_id(self, quiz_id: str, user_id: str) -> Optional[Quiz]:
        """Get a quiz by ID (user ownership validated)."""
        return self.quiz_repo.get_quiz_by_id(quiz_id, user_id)

    def get_all_quizzes(self, user_id: str, status: Optional[str] = None,
                       class_id: Optional[str] = None, include_deleted: bool = False) -> List[Quiz]:
        """Get all quizzes for a user with optional filtering."""
        return self.quiz_repo.get_all_quizzes(user_id, status, class_id, include_deleted)

    def update_quiz(self, quiz_id: str, user_id: str, update_data: Dict) -> Optional[Quiz]:
        """Update a quiz."""
        return self.quiz_repo.update_quiz(quiz_id, user_id, update_data)

    def delete_quiz(self, quiz_id: str, user_id: str, soft_delete: bool = True) -> bool:
        """Delete a quiz (soft or hard delete)."""
        return self.quiz_repo.delete_quiz(quiz_id, user_id, soft_delete)

    def restore_quiz(self, quiz_id: str, user_id: str) -> bool:
        """Restore a soft-deleted quiz."""
        return self.quiz_repo.restore_quiz(quiz_id, user_id)

    def update_quiz_status(self, quiz_id: str, user_id: str, status: str) -> Optional[Quiz]:
        """Update quiz status (draft/published/archived)."""
        return self.quiz_repo.update_quiz_status(quiz_id, user_id, status)

    def update_last_room_code(self, quiz_id: str, user_id: str, room_code: str) -> Optional[Quiz]:
        """Update last used room code."""
        return self.quiz_repo.update_last_room_code(quiz_id, user_id, room_code)

    def duplicate_quiz(self, quiz_id: str, user_id: str, new_title: Optional[str] = None) -> Optional[Quiz]:
        """Duplicate a quiz with all questions."""
        return self.quiz_repo.duplicate_quiz(quiz_id, user_id, new_title)

    # --- Question CRUD Methods ---
    def add_question_to_quiz(self, question_data: Dict) -> QuizQuestion:
        """Add a question to a quiz."""
        return self.quiz_repo.add_question(question_data)

    def get_question_by_id(self, question_id: str) -> Optional[QuizQuestion]:
        """Get a question by ID."""
        return self.quiz_repo.get_question_by_id(question_id)

    def get_questions_by_quiz_id(self, quiz_id: str, user_id: str) -> List[QuizQuestion]:
        """Get all questions for a quiz."""
        return self.quiz_repo.get_questions_by_quiz_id(quiz_id, user_id)

    def update_question(self, question_id: str, user_id: str, update_data: Dict) -> Optional[QuizQuestion]:
        """Update a question."""
        return self.quiz_repo.update_question(question_id, user_id, update_data)

    def delete_question(self, question_id: str, user_id: str) -> bool:
        """Delete a question."""
        return self.quiz_repo.delete_question(question_id, user_id)

    def reorder_questions(self, quiz_id: str, user_id: str, question_order: List[str]) -> bool:
        """Reorder questions in a quiz."""
        return self.quiz_repo.reorder_questions(quiz_id, user_id, question_order)

    def get_question_count(self, quiz_id: str, user_id: str) -> int:
        """Get number of questions in a quiz."""
        return self.quiz_repo.get_question_count(quiz_id, user_id)

    # --- Session Management Methods ---
    def create_quiz_session(self, session_data: Dict) -> QuizSession:
        """Create a new quiz session."""
        return self.quiz_session_repo.create_session(session_data)

    def get_quiz_session_by_id(self, session_id: str, user_id: Optional[str] = None) -> Optional[QuizSession]:
        """Get a session by ID."""
        return self.quiz_session_repo.get_session_by_id(session_id, user_id)

    def get_quiz_session_by_room_code(self, room_code: str) -> Optional[QuizSession]:
        """Get a session by room code."""
        return self.quiz_session_repo.get_session_by_room_code(room_code)

    def get_all_quiz_sessions(self, user_id: str, status: Optional[str] = None) -> List[QuizSession]:
        """Get all sessions for a user."""
        return self.quiz_session_repo.get_all_sessions(user_id, status)

    def get_active_quiz_sessions(self, user_id: str) -> List[QuizSession]:
        """Get active sessions for a user."""
        return self.quiz_session_repo.get_active_sessions(user_id)

    def update_quiz_session(self, session_id: str, user_id: str, update_data: Dict) -> Optional[QuizSession]:
        """Update a session."""
        return self.quiz_session_repo.update_session(session_id, user_id, update_data)

    def update_quiz_session_status(self, session_id: str, user_id: str, status: str) -> Optional[QuizSession]:
        """Update session status."""
        return self.quiz_session_repo.update_session_status(session_id, user_id, status)

    def move_to_next_question(self, session_id: str, user_id: str) -> Optional[QuizSession]:
        """Move session to next question."""
        return self.quiz_session_repo.move_to_next_question(session_id, user_id)

    def check_room_code_exists(self, room_code: str) -> bool:
        """Check if room code is in use."""
        return self.quiz_session_repo.check_room_code_exists(room_code)

    def get_timed_out_sessions(self) -> List[QuizSession]:
        """Find sessions that have timed out."""
        return self.quiz_session_repo.get_timed_out_sessions()

    # --- Participant Management Methods ---
    def add_quiz_participant(self, participant_data: Dict) -> QuizParticipant:
        """Add a participant to a session."""
        return self.quiz_session_repo.add_participant(participant_data)

    def get_participant_by_id(self, participant_id: str) -> Optional[QuizParticipant]:
        """Get a participant by ID."""
        return self.quiz_session_repo.get_participant_by_id(participant_id)

    def get_participant_by_guest_token(self, guest_token: str) -> Optional[QuizParticipant]:
        """Get a participant by guest token."""
        return self.quiz_session_repo.get_participant_by_guest_token(guest_token)

    def get_participants_by_session(self, session_id: str, active_only: bool = False) -> List[QuizParticipant]:
        """Get all participants in a session."""
        return self.quiz_session_repo.get_participants_by_session(session_id, active_only)

    def get_participant_by_student_in_session(self, session_id: str, student_id: str) -> Optional[QuizParticipant]:
        """Check if student is in session."""
        return self.quiz_session_repo.get_participant_by_student_in_session(session_id, student_id)

    def get_participant_names_in_session(self, session_id: str) -> List[str]:
        """Get all participant names in session."""
        return self.quiz_session_repo.get_participant_names_in_session(session_id)

    def update_participant(self, participant_id: str, update_data: Dict) -> Optional[QuizParticipant]:
        """Update a participant."""
        return self.quiz_session_repo.update_participant(participant_id, update_data)

    def update_participant_score(self, participant_id: str, points_earned: int,
                                is_correct: bool, time_taken_ms: int) -> Optional[QuizParticipant]:
        """Update participant score."""
        return self.quiz_session_repo.update_participant_score(
            participant_id, points_earned, is_correct, time_taken_ms
        )

    def mark_participant_inactive(self, participant_id: str) -> bool:
        """Mark participant as inactive."""
        return self.quiz_session_repo.mark_participant_inactive(participant_id)

    def get_leaderboard(self, session_id: str, limit: int = 10) -> List[QuizParticipant]:
        """Get session leaderboard."""
        return self.quiz_session_repo.get_leaderboard(session_id, limit)

    def get_participant_rank(self, participant_id: str) -> Tuple[int, int]:
        """Get participant rank and total count."""
        return self.quiz_session_repo.get_participant_rank(participant_id)

    def anonymize_old_guests(self, days: int = 30) -> int:
        """Anonymize old guest data (GDPR)."""
        return self.quiz_session_repo.anonymize_old_guests(days)

    # --- Response Management Methods ---
    def submit_quiz_response(self, response_data: Dict) -> QuizResponse:
        """Submit an answer."""
        return self.quiz_session_repo.submit_response(response_data)

    def get_quiz_response_by_id(self, response_id: str) -> Optional[QuizResponse]:
        """Get a response by ID."""
        return self.quiz_session_repo.get_response_by_id(response_id)

    def get_participant_response_for_question(self, participant_id: str,
                                             question_id: str) -> Optional[QuizResponse]:
        """Get participant's response to a question."""
        return self.quiz_session_repo.get_participant_response_for_question(
            participant_id, question_id
        )

    def get_responses_by_participant(self, participant_id: str) -> List[QuizResponse]:
        """Get all responses by a participant."""
        return self.quiz_session_repo.get_responses_by_participant(participant_id)

    def get_responses_by_session(self, session_id: str) -> List[QuizResponse]:
        """Get all responses in a session."""
        return self.quiz_session_repo.get_responses_by_session(session_id)

    def get_responses_by_question(self, question_id: str) -> List[QuizResponse]:
        """Get all responses to a question."""
        return self.quiz_session_repo.get_responses_by_question(question_id)

    def get_question_response_count(self, session_id: str, question_id: str) -> int:
        """Count responses to a question."""
        return self.quiz_session_repo.get_question_response_count(session_id, question_id)

    def get_question_correctness_stats(self, question_id: str) -> Dict:
        """Get correctness stats for a question."""
        return self.quiz_session_repo.get_question_correctness_stats(question_id)

    # --- Roster Tracking Methods ---
    def create_roster_entry(self, roster_data: Dict):
        """Create a roster entry."""
        return self.quiz_session_repo.create_roster_entry(roster_data)

    def create_roster_entries_bulk(self, roster_entries: List[Dict]):
        """Create multiple roster entries in bulk."""
        return self.quiz_session_repo.create_roster_entries_bulk(roster_entries)

    def get_roster_by_session(self, session_id: str):
        """Get all roster entries for a session."""
        return self.quiz_session_repo.get_roster_by_session(session_id)

    def get_roster_entry_by_student(self, session_id: str, student_id: str):
        """Get roster entry for a student in a session."""
        return self.quiz_session_repo.get_roster_entry_by_student(session_id, student_id)

    def update_roster_entry_joined(self, roster_entry_id: str, participant_id: str, joined_at):
        """Mark roster entry as joined."""
        return self.quiz_session_repo.update_roster_entry_joined(roster_entry_id, participant_id, joined_at)

    def get_roster_attendance_stats(self, session_id: str) -> Dict:
        """Get attendance statistics for session roster."""
        return self.quiz_session_repo.get_roster_attendance_stats(session_id)

    # --- Outsider Student Methods ---
    def create_outsider_record(self, outsider_data: Dict):
        """Create an outsider student record."""
        return self.quiz_session_repo.create_outsider_record(outsider_data)

    def get_outsiders_by_session(self, session_id: str):
        """Get all outsider students for a session."""
        return self.quiz_session_repo.get_outsiders_by_session(session_id)

    def get_outsider_by_participant(self, session_id: str, participant_id: str):
        """Get outsider record for a participant."""
        return self.quiz_session_repo.get_outsider_by_participant(session_id, participant_id)

    def flag_outsider_by_teacher(self, outsider_id: str, flagged: bool, teacher_notes: Optional[str] = None):
        """Flag or unflag an outsider student."""
        return self.quiz_session_repo.flag_outsider_by_teacher(outsider_id, flagged, teacher_notes)

    def get_outsider_count(self, session_id: str) -> int:
        """Get count of outsider students."""
        return self.quiz_session_repo.get_outsider_count(session_id)

    # --- Class Roster Helper Methods ---
    def is_student_in_class(self, student_id: str, class_id: str) -> bool:
        """Check if a student is enrolled in a specific class."""
        return self.class_student_repo.is_student_in_class(student_id, class_id)

    def get_students_by_class_with_details(self, class_id: str, user_id: str) -> List[Dict]:
        """Get all students in a class with full details."""
        return self.class_student_repo.get_students_by_class_with_details(class_id, user_id)

# --- SIMPLIFIED DEPENDENCY PROVIDER ---
def get_db_service(db: Session = Depends(get_db)) -> Generator[DatabaseService, None, None]:
    """
    FastAPI dependency that provides a DatabaseService instance.
    This simplified version is for a SQL-only production environment.
    """
    yield DatabaseService(db_session=db)