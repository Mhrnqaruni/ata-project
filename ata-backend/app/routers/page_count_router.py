# /ata-backend/app/routers/page_count_router.py

"""
This module defines the API endpoint for counting pages in uploaded documents.

The endpoint accepts multiple files (PDF, DOCX, images) and returns the total
number of pages, which is used by the frontend to calculate processing time estimates.
"""

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from typing import List
from pydantic import BaseModel

from ..services import page_count_service
from ..core.deps import get_current_active_user
from ..db.models.user_model import User as UserModel

router = APIRouter()


class PageCountResponse(BaseModel):
    """Response model for page count endpoint"""
    total_pages: int
    file_count: int
    estimated_seconds: int


@router.post(
    "/count-pages",
    response_model=PageCountResponse,
    summary="Count total pages in uploaded documents",
    description="Accepts multiple files (PDF, DOCX, images) and returns total page count for processing time estimation."
)
async def count_pages(
    files: List[UploadFile] = File(..., description="List of files to count pages from (PDF, DOCX, or images)"),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Count the total number of pages across all uploaded files.

    - **files**: List of uploaded files (PDF, DOCX, JPG, PNG)
    - Returns: Total page count and estimated processing time (15 seconds per page)
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded.")

    try:
        total_pages = await page_count_service.count_total_pages(files)

        # Calculate estimated time: 15 seconds per page
        estimated_seconds = total_pages * 15

        return PageCountResponse(
            total_pages=total_pages,
            file_count=len(files),
            estimated_seconds=estimated_seconds
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error counting pages: {str(e)}"
        )
