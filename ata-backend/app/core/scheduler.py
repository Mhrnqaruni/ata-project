# /ata-backend/app/core/scheduler.py

"""
Background task scheduler for periodic maintenance tasks.
Uses APScheduler to run cleanup tasks automatically.
"""

import os
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.services.file_cleanup_service import get_cleanup_service


# Global scheduler instance
scheduler = BackgroundScheduler()


def cleanup_old_files_task():
    """
    Scheduled task to clean up old assessment files.
    Runs automatically based on the configured schedule.
    """
    db: Session = SessionLocal()
    try:
        # Get hours from environment variable, default to 12 hours
        hours_after_completion = int(os.getenv("FILE_CLEANUP_HOURS", "12"))

        print(f"\n[CLEANUP] Running scheduled file cleanup (files older than {hours_after_completion}h)...")

        cleanup_service = get_cleanup_service()
        stats = cleanup_service.cleanup_old_assessments(
            db=db,
            hours_after_completion=hours_after_completion,
            dry_run=False
        )

        print(f"[CLEANUP] Cleanup complete:")
        print(f"  - Found: {stats['total_found']} eligible assessments")
        print(f"  - Deleted: {stats['deleted_count']} folders")
        print(f"  - Failed: {stats['failed_count']} folders")
        print(f"  - Space freed: {stats['space_freed_mb']} MB\n")

    except Exception as e:
        print(f"[CLEANUP] Error during scheduled cleanup: {str(e)}")
    finally:
        db.close()


def start_scheduler():
    """
    Start the background scheduler with all scheduled tasks.
    """
    # Get schedule from environment variable, default to every 6 hours
    # Format: "0 */6 * * *" means "run at minute 0 of every 6th hour"
    cleanup_schedule = os.getenv("FILE_CLEANUP_SCHEDULE", "0 */6 * * *")

    # Add the cleanup task with explicit timezone to avoid zoneinfo compatibility issues
    scheduler.add_job(
        cleanup_old_files_task,
        trigger=CronTrigger.from_crontab(cleanup_schedule, timezone=pytz.UTC),
        id="file_cleanup",
        name="Clean up old assessment files",
        replace_existing=True
    )

    # Start the scheduler
    scheduler.start()
    print(f"[SCHEDULER] Scheduler started: File cleanup will run on schedule: {cleanup_schedule}")


def stop_scheduler():
    """
    Stop the background scheduler gracefully.
    """
    if scheduler.running:
        scheduler.shutdown()
        print("[SCHEDULER] Scheduler stopped")
