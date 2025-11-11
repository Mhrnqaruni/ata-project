from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import List

from app.services.assessment_service import AssessmentService, get_assessment_service
from app.services.database_service import DatabaseService, get_db_service
from app.models import assessment_model
from app.models.user_model import User
from app.core.deps import get_current_active_user
from app.services.assessment_helpers import analytics_and_matching
from app.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

@router.get(
    "/{job_id}/overview",
    response_model=assessment_model.AssessmentResultsOverviewResponse,
    summary="Get Assessment Results Overview",
    description="Retrieves a summary of the assessment results, including a unified list of all students.",
)
async def get_assessment_results_overview(
    job_id: str,
    user: User = Depends(get_current_active_user),
    assessment_service: AssessmentService = Depends(get_assessment_service),
):
    try:
        # Get the unified list, which is the primary source of truth
        combined_list = await assessment_service.get_combined_overview(job_id=job_id, user_id=str(user.id))

        # Get basic job info for the response
        job = assessment_service.db.get_assessment_job(job_id=job_id, user_id=str(user.id))
        if not job:
            raise ValueError("Job not found")
        config = analytics_and_matching.normalize_config_to_v2(job)

        # Derive legacy lists for backward compatibility, ensuring other UI parts don't break
        students_ai_graded = []
        students_pending = []
        for student_row in combined_list:
            if student_row.status == "PENDING_REVIEW":
                students_pending.append(
                    assessment_model.StudentPendingSummary(
                        student_id=student_row.student_id,
                        name=student_row.student_name,
                        num_pending=1 # Placeholder count
                    )
                )
            elif student_row.status in ["AI_GRADED", "TEACHER_GRADED"] and student_row.total_score is not None:
                students_ai_graded.append(
                    assessment_model.StudentAIGradedSummary(
                        student_id=student_row.student_id,
                        name=student_row.student_name,
                        total_score=student_row.total_score
                    )
                )

        # Construct and return the final, correct response object
        return assessment_model.AssessmentResultsOverviewResponse(
            job_id=job_id,
            assessment_name=config.assessmentName,
            status=job.status,
            students_ai_graded=students_ai_graded,
            students_pending=students_pending,
            students=combined_list
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get(
    "/{job_id}/students/{entity_id}/review",
    response_model=assessment_model.StudentReviewResponse,
    summary="Get Student's Assessment for Review",
    description="Retrieves the detailed results for a single student's assessment, ready for teacher review.",
)
def get_student_assessment_for_review(
    job_id: str,
    entity_id: str,
    user: User = Depends(get_current_active_user),
    assessment_service: AssessmentService = Depends(get_assessment_service),
):
    try:
        review_data = assessment_service.get_student_assessment_for_review(
            job_id=job_id,
            entity_id=entity_id,
            user_id=str(user.id)
        )
        return review_data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch(
    "/{job_id}/students/{entity_id}/questions/{question_id}",
    response_model=assessment_model.StudentSaveConfirmation,
    summary="Save Teacher's Edit for a Question",
    description="Saves a teacher's grade and feedback for a single question and returns the student's updated score.",
)
async def save_teacher_edit(
    job_id: str,
    entity_id: str,
    question_id: str,
    payload: assessment_model.QuestionSaveRequest,
    user: User = Depends(get_current_active_user),
    assessment_service: AssessmentService = Depends(get_assessment_service),
):
    try:
        confirmation = await assessment_service.apply_teacher_edit(
            job_id=job_id,
            entity_id=entity_id,
            question_id=question_id,
            grade=payload.grade,
            feedback=payload.feedback,
            user_id=str(user.id),
        )
        return confirmation
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

@router.get(
    "/{job_id}/students/{entity_id}/report.docx",
    summary="Download Student Report as DOCX",
    description="Generates and downloads a DOCX report for a student based on the latest grades and feedback.",
)
async def download_student_report(
    job_id: str,
    entity_id: str,
    user: User = Depends(get_current_active_user),
    assessment_service: AssessmentService = Depends(get_assessment_service),
    db: DatabaseService = Depends(get_db_service),
):
    try:
        # Get student name for filename
        student_name = "Student"
        rostered_student = db.get_student_by_id(entity_id, str(user.id))
        if rostered_student:
            student_name = rostered_student.name.replace(" ", "_")
            logger.info(f"Found rostered student for report: {student_name}")
        else:
            outsider_student = db.get_outsider_student_by_id(entity_id, str(user.id))
            if outsider_student:
                student_name = outsider_student.name.replace(" ", "_")
                logger.info(f"Found outsider student for report: {student_name}")
            else:
                logger.warning(f"No student found for entity_id={entity_id}, using default name")

        docx_buffer = await assessment_service.build_student_report_docx(
            job_id=job_id,
            entity_id=entity_id,
            user_id=str(user.id)
        )
        filename = f"{student_name}_Report.docx"
        logger.info(f"Generating report with filename: {filename}")
        return StreamingResponse(
            docx_buffer,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))