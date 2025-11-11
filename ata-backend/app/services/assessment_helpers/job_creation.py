# /ata-backend/app/services/assessment_helpers/job_creation.py

"""
This module contains specialist helper functions for the initial creation of an
assessment job.

It is called by the main `assessment_service` and is responsible for:
1. Handling the physical saving of uploaded answer sheet files to disk.
2. Creating the initial `Assessment` and placeholder `Result` records in the
   database, ensuring that the new `Assessment` record is correctly stamped
   with the owner's `user_id`.
"""

import os
import uuid
import datetime
from typing import List, Dict
from fastapi import UploadFile

from ..database_service import DatabaseService
from ...models import assessment_model

# A centralized constant for the root directory of all assessment-related file uploads.
ASSESSMENT_UPLOADS_DIR = "assessment_uploads"

def _save_uploaded_files(job_id: str, answer_sheets: List[UploadFile]) -> List[Dict]:
    """
    Handles the file system operations for saving uploaded answer sheets.

    This function is a pure utility and does not require user context. It creates
    a dedicated, uniquely named directory structure for each job to prevent
    file collisions.

    Args:
        job_id: The unique ID of the assessment job being created.
        answer_sheets: A list of `UploadFile` objects from the FastAPI request.

    Returns:
        A list of dictionaries, where each dictionary contains the physical `path`
        and `contentType` of a successfully saved file.
    """
    # This function remains unchanged as it is a pure utility.
    os.makedirs(ASSESSMENT_UPLOADS_DIR, exist_ok=True)
    
    job_dir = os.path.join(ASSESSMENT_UPLOADS_DIR, job_id)
    unassigned_dir = os.path.join(job_dir, 'unassigned')
    os.makedirs(unassigned_dir, exist_ok=True)
    
    answer_sheet_data = []
    for sheet in answer_sheets:
        safe_filename = f"answer_{uuid.uuid4().hex[:8]}_{os.path.basename(sheet.filename or 'untitled')}"
        path = os.path.join(unassigned_dir, safe_filename)
        with open(path, "wb") as buffer:
            content = sheet.file.read()
            buffer.write(content)
        answer_sheet_data.append({"path": path, "contentType": sheet.content_type})
    
    return answer_sheet_data

def _create_initial_job_records(
    db: DatabaseService, 
    job_id: str, 
    config: assessment_model.AssessmentConfig, 
    answer_sheet_data: List[Dict],
    user_id: str
):
    """
    Specialist for creating the database records for a V1 assessment job.

    This function is now user-aware. It receives the authenticated user's ID
    and stamps it onto the new `Assessment` job record, satisfying the
    database's `NOT NULL` constraint for the `user_id` foreign key.

    Args:
        db: The DatabaseService instance for data persistence.
        job_id: The unique ID for the new assessment job.
        config: The Pydantic model containing the V1 assessment configuration.
        answer_sheet_data: A list of dictionaries with file path and content type info.
        user_id: The unique ID of the user who owns this new assessment.
    """
    job_record = {
        "id": job_id,
        "status": assessment_model.JobStatus.QUEUED.value,
        "config": config.model_dump(),
        "answer_sheet_paths": answer_sheet_data,
        "user_id": user_id,  # Stamp the owner's ID onto the new record.
        "created_at": datetime.datetime.now(datetime.timezone.utc),
        "ai_summary": ""
    }
    db.add_assessment_job(job_record)
    
    # The logic for creating placeholder results for every student has been removed.
    # Result records will now be created only after a file has been successfully
    # matched to a student in the analytics_and_matching helper.
    pass

def _create_initial_job_records_v2(
    db: DatabaseService,
    job_id: str,
    config: assessment_model.AssessmentConfigV2,
    answer_sheet_data: List[Dict],
    user_id: str,
    total_pages: int = 0,
    is_manual_upload: bool = False
):
    """
    Specialist for creating the database records for a V2 assessment job.

    Like its V1 counterpart, this function is now user-aware and ensures the new
    `Assessment` job record is correctly associated with an owner.

    Args:
        db: The DatabaseService instance.
        job_id: The unique ID for the new assessment job.
        config: The Pydantic model containing the V2 assessment configuration.
        answer_sheet_data: A list of dictionaries with file path and content type info.
        user_id: The unique ID of the user who owns this new assessment.
        total_pages: Total number of pages across all student submissions.
        is_manual_upload: True if this job was created via manual upload (files already matched).
    """
    # Store the is_manual_upload flag inside the config to avoid database schema changes
    config_dict = config.model_dump()
    config_dict['is_manual_upload'] = is_manual_upload

    job_record = {
        "id": job_id,
        "status": assessment_model.JobStatus.QUEUED.value,
        "config": config_dict,
        "answer_sheet_paths": answer_sheet_data,
        "user_id": user_id,  # Stamp the owner's ID onto the new record.
        "created_at": datetime.datetime.now(datetime.timezone.utc),
        "ai_summary": "",
        "total_pages": total_pages
    }
    db.add_assessment_job(job_record)
    
    # The logic for creating placeholder results for every student has been removed.
    # Result records will now be created only after a file has been successfully
    # matched to a student in the analytics_and_matching helper.
    pass