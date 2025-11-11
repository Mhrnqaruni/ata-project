# /app/routers/assessments_router.py (SUPERVISOR-APPROVED FLAWLESS VERSION 2.0)

"""
This module defines all API endpoints related to assessment jobs.

Every endpoint is protected and requires user authentication. The router is
responsible for injecting the authenticated user's context into every call to
the business logic layer (the AssessmentService), ensuring all operations are
securely scoped to the correct user. Authorization checks are performed at the
earliest possible point within the router itself.
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Response, BackgroundTasks, Request
from app.core.logger import get_logger

logger = get_logger(__name__)
from typing import List, Dict, Optional
import json

# --- Application-specific Imports ---
from ..services.assessment_service import AssessmentService, get_assessment_service
from ..models import assessment_model
from ..core.deps import get_current_active_user
from ..db.models.user_model import User as UserModel

router = APIRouter()


# --- V2 Endpoints (Now Secure with Router-Level Authorization) ---

@router.post(
    "/parse-document",
    summary="[V2] Parse uploaded document(s) to structure an assessment"
)
async def parse_assessment_document(
    question_file: UploadFile = File(..., description="The main exam document with questions."),
    answer_key_file: Optional[UploadFile] = File(None, description="An optional, separate answer key or rubric file."),
    class_id: str = Form(...),
    assessment_name: str = Form(...),
    assessment_svc: AssessmentService = Depends(get_assessment_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    The endpoint for the V2 wizard's interactive step.
    This protected endpoint first verifies the user owns the target class
    before proceeding with the parsing operation.
    """
    # --- [ARCHITECTURAL REFINEMENT: AUTHORIZATION CHECK IN ROUTER] ---
    # Justification: This is the "Fail Fast" principle. We check for permission
    # at the earliest possible moment. If the user doesn't own the class, we
    # reject the request immediately without engaging the more resource-intensive
    # service logic (file processing, AI calls).
    target_class = assessment_svc.db.get_class_by_id(class_id=class_id, user_id=current_user.id)
    if not target_class:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Class with ID {class_id} not found or you do not have permission to access it."
        )
    # --- [END OF REFINEMENT] ---
    
    try:
        # The service call is now simpler as it's a pure data processor.
        parsed_config_dict = await assessment_svc.parse_document_for_review(
            question_file=question_file,
            answer_key_file=answer_key_file,
            class_id=class_id,
            assessment_name=assessment_name
        )
        return parsed_config_dict
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.info(f"Error during document parsing: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while parsing the document.")


@router.post(
    "/v2",
    response_model=assessment_model.AssessmentJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="[V2] Create a New Assessment Grading Job from a V2 Config"
)
async def create_assessment_job_v2(
    background_tasks: BackgroundTasks,
    config: str = Form(...),
    answer_sheets: List[UploadFile] = File(...),
    assessment_svc: AssessmentService = Depends(get_assessment_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Creates a V2 assessment job and schedules it for background processing.
    This is a protected endpoint.
    """
    try:
        config_data = assessment_model.AssessmentConfigV2.model_validate_json(config)

        response = await assessment_svc.create_new_assessment_job_v2(
            config=config_data,
            answer_sheets=answer_sheets,
            user_id=current_user.id
        )

        job_id = response.get("jobId")
        if job_id:
            background_tasks.add_task(assessment_svc.process_assessment_job, job_id, current_user.id)

        return response
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@router.post(
    "/distribute-scores",
    response_model=assessment_model.AssessmentConfigV2,
    summary="[V2] Distribute Total Score with AI",
    description="Uses AI to intelligently distribute a total score across all questions in an assessment configuration."
)
async def distribute_scores(
    request: assessment_model.ScoreDistributionRequest,
    assessment_svc: AssessmentService = Depends(get_assessment_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Takes an assessment config and a total score, and returns the config with
    maxScore populated for each question by the AI.
    This is a protected endpoint.
    """
    try:
        updated_config = await assessment_svc.distribute_scores_with_ai(
            config=request.config,
            total_marks=request.totalMarks
        )
        return updated_config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during score distribution: {e}")


@router.post(
    "/v2/manual",
    response_model=assessment_model.AssessmentJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="[V2] Create a Job with Manual Per-Student Uploads"
)
async def create_assessment_job_with_manual_uploads(
    request: Request,
    background_tasks: BackgroundTasks,
    assessment_svc: AssessmentService = Depends(get_assessment_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Creates a V2 assessment job from a configuration and manually associated
    per-student files, all in a single transaction. This endpoint handles
    multipart form data where student files are keyed dynamically.
    """
    form_data = await request.form()

    config_str = form_data.get("config")
    if not config_str:
        raise HTTPException(status_code=400, detail="Missing 'config' in form data.")

    outsider_names_str = form_data.get("outsider_names", "[]")

    try:
        config = assessment_model.AssessmentConfigV2.model_validate_json(config_str)
        outsider_names = json.loads(outsider_names_str)

        # The service layer will be responsible for parsing the dynamic file keys
        response = await assessment_svc.create_job_with_manual_uploads(
            config=config,
            form_data=form_data,
            outsider_names=outsider_names,
            user_id=current_user.id,
        )

        job_id = response.get("jobId")
        if job_id:
            background_tasks.add_task(assessment_svc.process_assessment_job, job_id, current_user.id)

        return response
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format for 'config' or 'outsider_names'.")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@router.post(
    "/manual-submission",
    summary="[V2] Process a manual, per-student submission",
    status_code=status.HTTP_201_CREATED
)
async def manual_submission(
    job_id: str = Form(...),
    images: List[UploadFile] = File(...),
    student_id: Optional[str] = Form(None),
    outsider_name: Optional[str] = Form(None),
    assessment_svc: AssessmentService = Depends(get_assessment_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Handles the manual upload of images for a single student or outsider.
    Compresses images, merges them into a PDF, and creates result records.
    """
    if not images:
        raise HTTPException(status_code=400, detail="No images were uploaded.")

    try:
        result = await assessment_svc.process_manual_submission(
            job_id=job_id,
            user_id=str(current_user.id),
            images=images,
            student_id=student_id,
            outsider_name=outsider_name
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


# --- V1 & General Endpoints (Now Secure) ---

@router.get(
    "",
    response_model=assessment_model.AssessmentJobListResponse,
    summary="Get All Assessment Jobs"
)
def get_all_assessment_jobs(
    assessment_svc: AssessmentService = Depends(get_assessment_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Retrieves a summary list of all assessment jobs for the authenticated user."""
    return assessment_svc.get_all_assessment_jobs_summary(user_id=current_user.id)


@router.patch(
    "/{job_id}/results/{student_id}/{question_id}",
    summary="Save Teacher Overrides for a Single Question"
)
def save_teacher_overrides(
    job_id: str,
    student_id: str,
    question_id: str,
    overrides: assessment_model.GradingResult,
    assessment_svc: AssessmentService = Depends(get_assessment_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Saves a teacher's final grade/feedback for a single question."""
    try:
        assessment_svc.save_overrides(
            job_id=job_id,
            student_id=student_id,
            question_id=question_id,
            overrides=overrides,
            user_id=current_user.id
        )
        return {"status": "success", "detail": f"Overrides for s:{student_id} q:{question_id} saved."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{job_id}/results",
    response_model=assessment_model.AssessmentResultsResponse,
    summary="Get Full Assessment Job Results"
)
def get_assessment_job_results(
    job_id: str,
    assessment_svc: AssessmentService = Depends(get_assessment_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Retrieves the complete, aggregated results for a user-owned grading job."""
    full_results = assessment_svc.get_full_job_results(job_id=job_id, user_id=current_user.id)
    if full_results is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found or access denied.")
    return full_results


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an Assessment Job"
)
def delete_assessment_job(
    job_id: str,
    assessment_svc: AssessmentService = Depends(get_assessment_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Permanently deletes a user-owned assessment job and all its associated data."""
    was_deleted = assessment_svc.delete_assessment_job(job_id=job_id, user_id=current_user.id)
    if not was_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found or access denied.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{job_id}/config",
    response_model=assessment_model.AssessmentConfigResponse,
    summary="Get Assessment Configuration for Cloning"
)
def get_assessment_config(
    job_id: str,
    assessment_svc: AssessmentService = Depends(get_assessment_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Fetches a previous job's settings for the 'Clone' feature."""
    try:
        config_dict = assessment_svc.get_job_config(job_id=job_id, user_id=current_user.id)
        return assessment_model.AssessmentConfigResponse(**config_dict)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{job_id}/report/{student_id}", response_class=Response)
async def download_single_report(
    job_id: str,
    student_id: str,
    assessment_svc: AssessmentService = Depends(get_assessment_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Generates and returns a single student's report as a .docx file."""
    try:
        report_bytes, filename = await assessment_svc.generate_single_report_docx(job_id, student_id, current_user.id)
        return Response(
            content=report_bytes, 
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
            headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))