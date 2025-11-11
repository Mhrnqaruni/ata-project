"""
This service contains the business logic for fetching and processing
student-related data, such as the data for the student transcript page.
"""

from typing import List, Dict, Optional
from ..services.database_service import DatabaseService
from ..db.models.assessment_models import ResultStatus
from ..models.student_model import StudentAssessmentRow, StudentTranscriptResponse, ClassTranscript
from ..services.assessment_helpers.analytics_and_matching import normalize_config_to_v2

class StudentService:
    def __init__(self, db: DatabaseService):
        self.db = db

    def get_transcript(self, student_id: str, user_id: str) -> StudentTranscriptResponse:
        """
        Constructs the detailed transcript for a single student, organized by class.
        Each class gets its own table with assessments and class-specific average.
        """
        student = self.db.get_student_by_id(student_id, user_id)
        if not student:
            raise ValueError("Student not found or access denied.")

        # Get all classes the student is a member of
        memberships = self.db.get_class_memberships_for_student(student_id, user_id)
        if not memberships:
            return StudentTranscriptResponse(
                id=student.id,
                studentId=student.studentId,
                name=student.name,
                overallAveragePercent=None,
                classSummaries=[]
            )

        # Build transcript per class
        class_summaries: List[ClassTranscript] = []
        overall_earned = 0.0
        overall_possible = 0.0

        for membership in memberships:
            class_id = membership.class_id
            class_name = membership.class_name

            # Get all assessments for this class
            assessments = self.db.get_assessments_for_class(class_id, user_id)

            class_rows: List[StudentAssessmentRow] = []
            class_earned = 0.0
            class_possible = 0.0

            for job in assessments:
                cfg = normalize_config_to_v2(job)
                max_total_score = sum(q.maxScore for s in cfg.sections for q in s.questions if q.maxScore is not None)

                # Get results for this specific student and job
                results = self.db.get_results_for_student_and_job(student_id, job.id, user_id)

                if not results:
                    status = "ABSENT"
                    total_score = None
                    report_url = None
                else:
                    any_pending = any(r.status == ResultStatus.PENDING_REVIEW.value for r in results)
                    if any_pending:
                        status = "PENDING_REVIEW"
                        total_score = None
                    else:
                        status = "GRADED"
                        total_score = sum(float(r.grade) for r in results if r.grade is not None)
                        class_earned += total_score
                        class_possible += max_total_score

                    report_url = f"/api/assessments/{job.id}/students/{student.id}/report.docx"

                created_at_str = job.created_at.isoformat() if job.created_at else None
                print(f"[STUDENT SERVICE] Job {job.id}: created_at = {job.created_at}, ISO = {created_at_str}")

                class_rows.append(StudentAssessmentRow(
                    jobId=job.id,
                    assessmentName=cfg.assessmentName,
                    classId=class_id,
                    className=class_name,
                    createdAt=created_at_str,
                    totalScore=total_score,
                    maxTotalScore=max_total_score,
                    status=status,
                    reportUrl=report_url
                ))

            # Calculate class average
            class_avg = (class_earned / class_possible * 100) if class_possible > 0 else None

            class_summaries.append(ClassTranscript(
                classId=class_id,
                className=class_name,
                averagePercent=class_avg,
                assessments=class_rows
            ))

            # Add to overall totals
            overall_earned += class_earned
            overall_possible += class_possible

        # Calculate overall average
        overall_avg = (overall_earned / overall_possible * 100) if overall_possible > 0 else None

        return StudentTranscriptResponse(
            id=student.id,
            studentId=student.studentId,
            name=student.name,
            overallAveragePercent=overall_avg,
            classSummaries=class_summaries
        )