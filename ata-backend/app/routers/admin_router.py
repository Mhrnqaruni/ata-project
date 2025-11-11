# /ata-backend/app/routers/admin_router.py

"""
Admin router for super admin dashboard.
Provides protected endpoints for admin-only operations.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.db.database import get_db
from app.core.admin_auth import verify_admin_token
from app.services import admin_service
from app.services.file_cleanup_service import get_cleanup_service

router = APIRouter()


@router.get("/dashboard", response_model=Dict[str, Any])
def get_admin_dashboard(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """
    Returns comprehensive database statistics and data.
    Protected endpoint - requires admin token.

    Returns:
        Complete database statistics including:
        - Summary counts of all entities
        - Detailed data for users, classes, students, assessments, etc.
    """
    return admin_service.get_admin_dashboard_data(db)


@router.get("/cleanup/preview", response_model=Dict[str, Any])
def preview_file_cleanup(
    hours: int = Query(default=12, ge=1, le=720, description="Hours after completion"),
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """
    Preview what files would be deleted without actually deleting them.
    Protected endpoint - requires admin token.

    Args:
        hours: Number of hours after completion before files are eligible for deletion

    Returns:
        Statistics about what would be deleted (dry run)
    """
    cleanup_service = get_cleanup_service()
    return cleanup_service.get_cleanup_preview(db, hours_after_completion=hours)


@router.post("/cleanup/execute", response_model=Dict[str, Any])
def execute_file_cleanup(
    hours: int = Query(default=12, ge=1, le=720, description="Hours after completion"),
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """
    Actually delete old assessment files.
    Protected endpoint - requires admin token.

    Args:
        hours: Number of hours after completion before files are eligible for deletion

    Returns:
        Statistics about what was deleted
    """
    cleanup_service = get_cleanup_service()
    return cleanup_service.cleanup_old_assessments(
        db=db,
        hours_after_completion=hours,
        dry_run=False
    )
