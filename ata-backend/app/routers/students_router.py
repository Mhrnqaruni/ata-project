"""
This router handles all API endpoints related to individual students,
such as fetching a student's transcript.
"""

from fastapi import APIRouter, Depends, HTTPException
from app.services.student_service import StudentService
from app.services.database_service import get_db_service, DatabaseService
from app.core.deps import get_current_active_user
from app.models.student_model import StudentTranscriptResponse
from app.db.models.user_model import User

router = APIRouter(
    tags=["students"],
    dependencies=[Depends(get_current_active_user)]
)

@router.get("/{student_id}/transcript", response_model=StudentTranscriptResponse)
def get_student_transcript(
    student_id: str,
    current_user: User = Depends(get_current_active_user),
    db: DatabaseService = Depends(get_db_service)
):
    """
    Retrieves a comprehensive transcript for a single student, including all their
    assessments, grades, and an overall average. This is a protected endpoint.
    """
    svc = StudentService(db)
    try:
        transcript = svc.get_transcript(student_id=student_id, user_id=str(current_user.id))
        return transcript
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # Generic error handler for unexpected issues
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")