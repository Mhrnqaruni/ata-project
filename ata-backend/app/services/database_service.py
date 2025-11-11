# /ata-backend/app/services/database_service.py (SUPERVISOR-APPROVED FLAWLESS VERSION)

"""
This module defines the DatabaseService, which acts as the central facade
for all data access operations within the application.

It abstracts away the underlying data storage mechanism (now exclusively SQL)
and provides a unified, user-aware interface for higher-level business services.
Every method that interacts with user-owned data now requires a `user_id`,
ensuring strict data isolation and security.
"""

from typing import List, Dict, Optional, Generator
from sqlalchemy.orm import Session
from fastapi import Depends

# --- Core Database Setup ---
from app.db.database import get_db

# --- SQL Repository Imports ---
from .database_helpers.class_student_repository_sql import ClassStudentRepositorySQL
from .database_helpers.assessment_repository_sql import AssessmentRepositorySQL
from .database_helpers.chat_repository_sql import ChatRepositorySQL
from .database_helpers.generation_repository_sql import GenerationRepositorySQL

# --- Import SQLAlchemy Models for Accurate Type Hinting ---
from app.db.models.user_model import User
from app.db.models.class_student_models import Class, Student
from app.db.models.assessment_models import Assessment, Result, ResultStatus, FinalizedBy
from app.db.models.ai_model_run import AIModelRun
from app.db.models.chat_models import ChatSession, ChatMessage
from app.db.models.generation_models import Generation
from app.db.models.outsider_student import OutsiderStudent


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

# --- SIMPLIFIED DEPENDENCY PROVIDER ---
def get_db_service(db: Session = Depends(get_db)) -> Generator[DatabaseService, None, None]:
    """
    FastAPI dependency that provides a DatabaseService instance.
    This simplified version is for a SQL-only production environment.
    """
    yield DatabaseService(db_session=db)