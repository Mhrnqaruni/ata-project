# /ata-backend/app/services/file_cleanup_service.py

"""
Service for cleaning up old assessment upload files.
Removes files from completed assessments after a specified time period.
"""

import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy.orm import Session
from typing import List, Dict

from app.db.models.assessment_models import Assessment
from app.models.assessment_model import JobStatus


class FileCleanupService:
    """
    Service responsible for cleaning up old assessment files.
    """

    def __init__(self, upload_directory: str = "assessment_uploads"):
        """
        Initialize the cleanup service.

        Args:
            upload_directory: Path to the assessment uploads directory
        """
        self.upload_directory = Path(upload_directory)

    def cleanup_old_assessments(
        self,
        db: Session,
        hours_after_completion: int = 12,
        dry_run: bool = False
    ) -> Dict[str, any]:
        """
        Clean up files from assessments completed more than X hours ago.

        Args:
            db: Database session
            hours_after_completion: Hours to wait after completion before deleting files
            dry_run: If True, only report what would be deleted without actually deleting

        Returns:
            Dictionary with cleanup statistics
        """
        # Calculate the cutoff time
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_after_completion)

        # Find completed assessments older than cutoff
        old_assessments = db.query(Assessment).filter(
            Assessment.status == JobStatus.COMPLETED.value,
            Assessment.created_at < cutoff_time
        ).all()

        stats = {
            "total_found": len(old_assessments),
            "deleted_count": 0,
            "failed_count": 0,
            "space_freed_mb": 0,
            "deleted_jobs": [],
            "failed_jobs": [],
            "dry_run": dry_run
        }

        for assessment in old_assessments:
            job_dir = self.upload_directory / f"job_{assessment.id}"

            # Check if directory exists
            if not job_dir.exists():
                continue

            # Calculate directory size
            dir_size = self._get_directory_size(job_dir)

            if dry_run:
                # In dry run mode, just report what would be deleted
                stats["deleted_jobs"].append({
                    "job_id": assessment.id,
                    "created_at": assessment.created_at.isoformat(),
                    "size_mb": round(dir_size / (1024 * 1024), 2)
                })
                stats["space_freed_mb"] += dir_size / (1024 * 1024)
                stats["deleted_count"] += 1
            else:
                # Actually delete the directory
                try:
                    shutil.rmtree(job_dir)
                    stats["deleted_jobs"].append({
                        "job_id": assessment.id,
                        "created_at": assessment.created_at.isoformat(),
                        "size_mb": round(dir_size / (1024 * 1024), 2)
                    })
                    stats["space_freed_mb"] += dir_size / (1024 * 1024)
                    stats["deleted_count"] += 1
                    print(f"✓ Deleted: job_{assessment.id} ({round(dir_size / (1024 * 1024), 2)} MB)")
                except Exception as e:
                    stats["failed_jobs"].append({
                        "job_id": assessment.id,
                        "error": str(e)
                    })
                    stats["failed_count"] += 1
                    print(f"✗ Failed to delete job_{assessment.id}: {str(e)}")

        stats["space_freed_mb"] = round(stats["space_freed_mb"], 2)
        return stats

    def _get_directory_size(self, directory: Path) -> int:
        """
        Calculate total size of a directory in bytes.

        Args:
            directory: Path to directory

        Returns:
            Total size in bytes
        """
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    filepath = Path(dirpath) / filename
                    if filepath.exists():
                        total_size += filepath.stat().st_size
        except Exception as e:
            print(f"Error calculating size for {directory}: {str(e)}")
        return total_size

    def get_cleanup_preview(self, db: Session, hours_after_completion: int = 12) -> Dict:
        """
        Get a preview of what would be cleaned up without actually deleting.

        Args:
            db: Database session
            hours_after_completion: Hours threshold

        Returns:
            Preview statistics
        """
        return self.cleanup_old_assessments(db, hours_after_completion, dry_run=True)


# Singleton instance
_cleanup_service = FileCleanupService()


def get_cleanup_service() -> FileCleanupService:
    """Get the global cleanup service instance."""
    return _cleanup_service
