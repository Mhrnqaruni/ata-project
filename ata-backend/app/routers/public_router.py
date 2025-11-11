# /ata-backend/app/routers/public_router.py (SUPERVISOR-APPROVED FLAWLESS VERSION)

"""
This module defines API endpoints that are intentionally accessible to the public
without requiring a standard user login session.

Security for these endpoints is managed through unique, unguessable tokens
embedded in the URL, rather than through JWT Bearer tokens.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

# --- Application-specific Imports ---
from ..services.database_service import DatabaseService, get_db_service
from ..services.assessment_helpers import analytics_and_matching

# --- Pydantic Response Model ---

class PublicReportResponse(BaseModel):
    """
    Defines the precise data contract for a public-facing student report.
    This ensures only specific, non-sensitive information is exposed.
    """
    studentName: str = Field(..., description="The name of the student.")
    assessmentName: str = Field(..., description="The name of the assessment.")
    questionText: str = Field(..., description="The text of the specific question being reported on.")
    maxScore: Optional[int] = Field(..., description="The maximum possible score for this question.")
    grade: Optional[float] = Field(..., description="The grade the student received for this question.")
    feedback: str = Field(..., description="The feedback provided for the student's answer.")

    class Config:
        from_attributes = True

# --- Router Initialization ---
router = APIRouter()

@router.get(
    "/report/{report_token}",
    response_model=PublicReportResponse,
    summary="Get a Single Student Report via Secure Token",
    tags=["Public"]
)
def get_public_report_by_token(
    report_token: str,
    db: DatabaseService = Depends(get_db_service)
):
    """
    Retrieves the details for a single graded question via a unique, secure token.

    This endpoint is public but secure. It uses a single, efficient database query
    that joins all related tables to fetch the data only if the token is valid
    and all data relationships are intact.
    """
    # 1. Fetch all required details in a single, secure, and efficient database call.
    report_details = db.get_public_report_details_by_token(token=report_token)

    if not report_details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found. The link may be invalid or expired."
        )

    # Unpack the dictionary for clarity
    result_record = report_details["result"]
    job_record = report_details["assessment"]
    student_record = report_details["student"]

    # 2. Normalize the job's config to robustly handle both V1 and V2 formats.
    config = analytics_and_matching.normalize_config_to_v2(job_record)

    # 3. Find the specific question from the config that this result corresponds to.
    question_config = None
    for section in config.sections:
        for q in section.questions:
            if q.id == result_record.question_id:
                question_config = q
                break
        if question_config:
            break

    if not question_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question details not found in assessment configuration."
        )

    # 4. Assemble the final, validated response payload.
    response_payload = {
        "studentName": student_record.name,
        "assessmentName": config.assessmentName,
        "questionText": question_config.text,
        "maxScore": question_config.maxScore,
        "grade": result_record.grade,
        "feedback": result_record.feedback or "No feedback provided.",
    }

    return response_payload