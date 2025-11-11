
# /ata-backend/app/services/database_helpers/assessment_repository_sql.py (FINAL, CORRECTED, SUPERVISOR-APPROVED)

"""
This module contains all the raw SQLAlchemy queries for the Assessment and Result
tables. It is the direct interface to the database for all assessment-related
data, and it is a final point of enforcement for data isolation.

Every method that reads or modifies user-owned data has been updated to
require a `user_id`, ensuring all operations are securely scoped to the
authenticated user. This module follows a "defense-in-depth" principle,
meaning every function is independently secure.
"""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

# Import the SQLAlchemy models this repository will interact with.
from app.db.models.assessment_models import Assessment, Result, ResultStatus, FinalizedBy
from app.db.models.ai_model_run import AIModelRun
from app.db.models.class_student_models import Student, Class
from app.db.models.outsider_student import OutsiderStudent

class AssessmentRepositorySQL:
    def __init__(self, db_session: Session):
        self.db = db_session

    # --- Assessment Job Methods ---

    def add_job(self, record: Dict) -> Assessment:
        """
        Creates a new Assessment record.
        This function expects the `user_id` to be present in the `record` dictionary,
        stamped by the calling service.
        """
        new_job = Assessment(**record)
        self.db.add(new_job)
        self.db.commit()
        self.db.refresh(new_job)
        return new_job

    def get_job(self, job_id: str, user_id: str) -> Optional[Assessment]:
        """
        Retrieves a single assessment by its ID, but only if it is owned by the
        specified user. This prevents unauthorized access to other users' jobs.
        """
        return (
            self.db.query(Assessment)
            .filter(Assessment.id == job_id, Assessment.user_id == user_id)
            .first()
        )

    def get_all_jobs(self, user_id: str) -> List[Assessment]:
        """
        Retrieves all assessment jobs owned by a specific user.
        The query is now filtered by `user_id` to enforce data isolation.
        """
        return (
            self.db.query(Assessment)
            .filter(Assessment.user_id == user_id)
            .order_by(Assessment.created_at.desc())
            .all()
        )

    def update_job_status(self, job_id: str, user_id: str, status: str):
        """
        Updates a job's status, but only if it is owned by the specified user.
        """
        job = self.get_job(job_id=job_id, user_id=user_id)
        if job:
            job.status = status
            self.db.commit()

    def update_job_summary(self, job_id: str, user_id: str, summary: str):
        """
        Updates a job's AI summary, but only if it is owned by the specified user.
        """
        job = self.get_job(job_id=job_id, user_id=user_id)
        if job:
            job.ai_summary = summary
            self.db.commit()

    def delete_job(self, job_id: str, user_id: str) -> bool:
        """
        Deletes a job, but only if it is owned by the specified user.
        """
        job = self.get_job(job_id=job_id, user_id=user_id)
        if job:
            self.db.delete(job)
            self.db.commit()
            return True
        return False

    def add_ai_model_run(self, record: Dict) -> AIModelRun:
        """Creates a new AIModelRun record."""
        new_run = AIModelRun(**record)
        self.db.add(new_run)
        self.db.commit()
        self.db.refresh(new_run)
        return new_run

    def get_ai_model_runs_for_question(self, job_id: str, entity_id: str, question_id: str, is_outsider: bool) -> List[AIModelRun]:
        """Retrieves all AI model runs for a specific question, entity (student or outsider), and job."""
        query = self.db.query(AIModelRun).filter_by(job_id=job_id, question_id=question_id)
        if is_outsider:
            query = query.filter_by(outsider_student_id=entity_id)
        else:
            query = query.filter_by(student_id=entity_id)
        return query.order_by(AIModelRun.run_index).all()

    def update_result_extracted_answer(self, job_id: str, entity_id: str, is_outsider: bool, question_id: str, extracted_answer: str, user_id: str):
        """Updates the extractedAnswer for a specific result, checking for user ownership."""
        query = (
            self.db.query(Result)
            .join(Assessment, Result.job_id == Assessment.id)
            .filter(
                Result.job_id == job_id,
                Result.question_id == question_id,
                Assessment.user_id == user_id
            )
        )
        if is_outsider:
            query = query.filter(Result.outsider_student_id == entity_id)
        else:
            query = query.filter(Result.student_id == entity_id)

        result = query.first()
        if result:
            result.extractedAnswer = extracted_answer
            self.db.commit()

    def are_any_questions_pending_review(self, job_id: str, user_id: str) -> bool:
        """Checks if any results for a job are in PENDING_REVIEW state."""
        return self.db.query(Result).filter(Result.job_id == job_id, Result.status == ResultStatus.PENDING_REVIEW.value).count() > 0

    # --- Assessment Result Methods ---

    def add_result(self, record: Dict) -> Result:
        """
        Creates a new Result record. Ownership is implicitly handled by the
        `job_id` in the record, which is validated by the calling service.
        """
        new_result = Result(**record)
        self.db.add(new_result)
        self.db.commit()
        self.db.refresh(new_result)
        return new_result

    def get_all_results_for_job(self, job_id: str, user_id: str) -> List[Result]:
        """
        Retrieves all results for a given job, but only if the job is
        owned by the specified user. This is a critical defense-in-depth check.
        """
        parent_job = self.get_job(job_id=job_id, user_id=user_id)
        if not parent_job:
            return []
        return self.db.query(Result).filter(Result.job_id == job_id).all()

    def get_result_by_token(self, token: str) -> Optional[Result]:
        """
        Retrieves a single result by its public report token.
        This is a public-facing method and does not require a user_id.
        """
        return self.db.query(Result).filter(Result.report_token == token).first()
        
    def update_result_grade(self, job_id: str, student_id: str, question_id: str, grade: Optional[float], feedback: str, status: str, finalized_by: Optional[str], user_id: str):
        """
        Updates a single result's grade and feedback, but only if the result
        belongs to an assessment job owned by the specified user.
        """
        result = (
            self.db.query(Result)
            .join(Assessment, Result.job_id == Assessment.id)
            .filter(
                Result.job_id == job_id,
                Result.student_id == student_id,
                Result.question_id == question_id,
                Assessment.user_id == user_id
            )
            .first()
        )
        if result:
            result.grade = grade
            result.feedback = feedback
            result.status = status
            result.finalized_by = finalized_by
            self.db.commit()

    def update_outsider_result_grade(self, job_id: str, outsider_student_id: str, question_id: str, grade: Optional[float], feedback: str, status: str, finalized_by: Optional[str], user_id: str):
        """
        Updates a single result's grade and feedback for an OUTSIDER student,
        but only if the result belongs to an assessment job owned by the specified user.
        """
        result = (
            self.db.query(Result)
            .join(Assessment, Result.job_id == Assessment.id)
            .filter(
                Result.job_id == job_id,
                Result.outsider_student_id == outsider_student_id,
                Result.question_id == question_id,
                Assessment.user_id == user_id
            )
            .first()
        )
        if result:
            result.grade = grade
            result.feedback = feedback
            result.status = status
            result.finalized_by = finalized_by
            self.db.commit()

    def update_result_path(self, job_id: str, student_id: str, path: str, content_type: str, user_id: str):
        """
        Updates the answer sheet path for all results belonging to a student
        within a specific job, but only if the job is owned by the user.
        """
        parent_job = self.get_job(job_id=job_id, user_id=user_id)
        if not parent_job:
            return

        results_to_update = self.db.query(Result).filter_by(job_id=job_id, student_id=student_id).all()
        if results_to_update:
            for result in results_to_update:
                result.answer_sheet_path = path
                result.content_type = content_type
                result.status = 'matched'
            self.db.commit()

    def get_entities_with_paths(self, job_id: str, user_id: str) -> List[Dict]:
        """
        Gets a distinct list of entities (students and outsiders) and their matched
        answer sheet paths for a given job, ensuring the user owns the job.
        """
        parent_job = self.get_job(job_id=job_id, user_id=user_id)
        if not parent_job:
            return []

        # Query for rostered students with paths
        roster_stmt = (
            select(
                Result.student_id.label('entity_id'),
                Result.answer_sheet_path,
                Result.content_type
            )
            .where(
                Result.job_id == job_id,
                Result.student_id.isnot(None),
                Result.answer_sheet_path.isnot(None),
                Result.answer_sheet_path != ''
            )
            .distinct()
        )
        roster_results = self.db.execute(roster_stmt).mappings().all()

        # Query for outsider students with paths
        outsider_stmt = (
            select(
                Result.outsider_student_id.label('entity_id'),
                Result.answer_sheet_path,
                Result.content_type
            )
            .where(
                Result.job_id == job_id,
                Result.outsider_student_id.isnot(None),
                Result.answer_sheet_path.isnot(None),
                Result.answer_sheet_path != ''
            )
            .distinct()
        )
        outsider_results = self.db.execute(outsider_stmt).mappings().all()

        # Combine and add the is_outsider flag
        entities = []
        for row in roster_results:
            entities.append({**row, "is_outsider": False})
        for row in outsider_results:
            entities.append({**row, "is_outsider": True})

        return entities

    def get_outsider_student_by_id(self, outsider_student_id: str, user_id: str) -> Optional[OutsiderStudent]:
        """
        Securely fetches a single outsider student by their primary key ID,
        ensuring they belong to an assessment owned by the specified user.
        """
        return (
            self.db.query(OutsiderStudent)
            .join(Assessment, OutsiderStudent.assessment_id == Assessment.id)
            .filter(OutsiderStudent.id == outsider_student_id, Assessment.user_id == user_id)
            .first()
        )

    def get_all_outsider_students_for_job(self, job_id: str, user_id: str) -> List[OutsiderStudent]:
        """
        Retrieves all outsider students for a given job, but only if the job is
        owned by the specified user.
        """
        parent_job = self.get_job(job_id=job_id, user_id=user_id)
        if not parent_job:
            return []
        return self.db.query(OutsiderStudent).filter(OutsiderStudent.assessment_id == job_id).all()

    def get_outsider_by_name_and_job(self, name: str, job_id: str, user_id: str) -> Optional[OutsiderStudent]:
        """
        Retrieves an outsider student by name and job ID, ensuring the job is owned by the user.
        """
        parent_job = self.get_job(job_id=job_id, user_id=user_id)
        if not parent_job:
            return None
        return (
            self.db.query(OutsiderStudent)
            .filter(OutsiderStudent.assessment_id == job_id, OutsiderStudent.name == name)
            .first()
        )

    # --- [START OF NEW METHOD TO FIX ATTRIBUTEERROR] ---
    def get_student_result_path(self, job_id: str, student_id: str, user_id: str) -> Optional[str]:
        """
        Securely retrieves the answer sheet path for a single student within a job.

        This method performs a crucial defense-in-depth check by first verifying
        that the parent job is owned by the user before attempting to fetch the
        result data.

        Args:
            job_id: The ID of the assessment job.
            student_id: The ID of the student.
            user_id: The ID of the authenticated user.

        Returns:
            The answer sheet path string if found and authorized, otherwise None.
        """
        # 1. Security Check: Verify the user owns the parent job.
        parent_job = self.get_job(job_id=job_id, user_id=user_id)
        if not parent_job:
            # If the job doesn't exist or the user doesn't own it, deny access.
            return None

        # 2. Data Retrieval: If security check passes, fetch the result.
        # We only need the first result for this student in this job, as the
        # path is the same for all their question results.
        result = (
            self.db.query(Result)
            .filter(Result.job_id == job_id, Result.student_id == student_id)
            .first()
        )

        # 3. Return the path, or None if no result was found.
        return result.answer_sheet_path if result else None
    # --- [END OF NEW METHOD] ---

    # --- Chatbot Helper Methods ---

    def get_assessments_for_chatbot(self, user_id: str) -> List[Dict]:
        """
        Returns a list of result dictionaries for the chatbot sandbox,
        securely filtered for the authenticated user.
        """
        user_results = (
            self.db.query(Result)
            .join(Assessment, Result.job_id == Assessment.id)
            .filter(Assessment.user_id == user_id)
            .all()
        )
        return [{c.name: getattr(obj, c.name) for c in obj.__table__.columns} for obj in user_results]

    def get_all_results_for_user(self, user_id: str) -> List[Result]:
        """
        Retrieves all results for all jobs owned by a specific user.
        """
        return (
            self.db.query(Result)
            .join(Assessment, Result.job_id == Assessment.id)
            .filter(Assessment.user_id == user_id)
            .all()
        )

    def get_public_report_details_by_token(self, token: str) -> Optional[Dict]:
        """
        Securely and efficiently fetches all necessary details for a public report
        using a single, comprehensive query with joins.
        """
        query_result = (
            self.db.query(
                Result,
                Assessment,
                Student,
                Class
            )
            .join(Assessment, Result.job_id == Assessment.id)
            .join(Student, Result.student_id == Student.id)
            .join(Class, Student.class_id == Class.id)
            .filter(Result.report_token == token)
            .first()
        )
        
        if not query_result:
            return None
        
        result_obj, assessment_obj, student_obj, class_obj = query_result
        
        return {
            "result": result_obj,
            "assessment": assessment_obj,
            "student": student_obj,
            "class": class_obj
        }
    
        # Add this inside the AssessmentRepositorySQL class
    def update_result_status(self, job_id: str, student_id: str, question_id: str, status: str, user_id: str):
        """
        Securely updates the status of a single result record, verifying ownership via a JOIN.
        """
        result = (
            self.db.query(Result)
            .join(Assessment, Result.job_id == Assessment.id)
            .filter(
                Result.job_id == job_id,
                Result.student_id == student_id,
                Result.question_id == question_id,
                Assessment.user_id == user_id
            )
            .first()
        )
        if result:
            result.status = status
            self.db.commit()

    # --- NEW: Student Transcript Methods ---

    def get_assessments_for_class(self, class_id: str, user_id: str) -> List[Assessment]:
        """
        Retrieves all assessments that belong to a specific class.
        Checks the config JSON for classIds array (multi-class) or classId (single class).
        """
        # Get all assessments for the user, then filter in Python
        # This is because JSON (not JSONB) doesn't support the @> operator
        all_assessments = (
            self.db.query(Assessment)
            .filter(Assessment.user_id == user_id)
            .order_by(Assessment.created_at.desc())
            .all()
        )

        # Filter assessments that have this class_id
        matching_assessments = []
        for assessment in all_assessments:
            if not assessment.config:
                continue

            # Check for classIds array (new multi-class format)
            if 'classIds' in assessment.config:
                class_ids = assessment.config.get('classIds', [])
                if class_id in class_ids:
                    matching_assessments.append(assessment)
            # Check for classId string (old single-class format) - BACKWARD COMPATIBILITY
            elif 'classId' in assessment.config:
                if assessment.config.get('classId') == class_id:
                    matching_assessments.append(assessment)

        return matching_assessments

    def get_results_for_student_and_job(self, student_id: str, job_id: str, user_id: str) -> List[Result]:
        """
        Retrieves all results for a specific student in a specific assessment.
        Validates that the assessment belongs to the user.
        """
        parent_job = self.get_job(job_id=job_id, user_id=user_id)
        if not parent_job:
            return []

        return (
            self.db.query(Result)
            .filter(
                Result.job_id == job_id,
                Result.student_id == student_id
            )
            .all()
        )