# /app/services/class_helpers/roster_ingestion.py (MODIFIED AND APPROVED)

"""
This module acts as the high-level orchestrator for the "Create Class from
File Upload" feature.

It connects the API router to the various specialist helpers (file processors,
CRUD helpers) and AI services to execute the entire ingestion pipeline. As a
primary entry point for a user-initiated action, its main security role is to
receive the authenticated user's ID and "thread" it down into the lower-level
modules that interact with the database.
"""

import json
import asyncio
import pandas as pd
from typing import Dict
from fastapi import UploadFile

from ...models import class_model, student_model
from ..database_service import DatabaseService
from .. import ocr_service, gemini_service, prompt_library

# Import the specialist helper modules this orchestrator uses.
from . import file_processors
from . import crud


async def create_class_from_upload(
    name: str, 
    file: UploadFile, 
    db: DatabaseService, 
    user_id: str
) -> Dict:
    """
    Orchestrates the advanced pipeline for creating a class from a roster file.

    This function is now fully "user-aware." It receives the authenticated
    user's ID and ensures that all database operations performed during the
    ingestion process are correctly associated with that user.

    Args:
        name: The name for the new class, provided by the user.
        file: The uploaded roster file (e.g., .csv, .xlsx, .pdf).
        db: The DatabaseService instance for data persistence.
        user_id: The unique ID of the authenticated user creating the class.

    Raises:
        ValueError: If the file is unreadable, unsupported, or if any part of
                    the ingestion or database operation fails.

    Returns:
        A dictionary containing the details of the newly created class and a
        count of the students who were newly added.
    """
    
    # 1. Prepare the class data dictionary, now including the owner's user_id.
    class_data_with_owner = {
        "name": name,
        "description": f"Roster uploaded from {file.filename}",
        "user_id": user_id
    }
    
    # The `create_class` helper now receives the complete record, including the user_id.
    # We pass the dictionary directly as `class_record`.
    new_class_object = crud.create_class(class_record=class_data_with_owner, db=db)
    
    students_to_process = []
    newly_created_student_count = 0
    
    try:
        file_bytes = await file.read()
        content_type = file.content_type

        # --- Smart Ingestion Routing (This logic remains the same) ---
        if content_type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"]:
            students_to_process = file_processors.extract_students_from_tabular(file_bytes, is_excel=True)
        elif content_type == "text/csv":
            students_to_process = file_processors.extract_students_from_tabular(file_bytes, is_excel=False)
        else:
            raw_text = ""
            if content_type in ["image/jpeg", "image/png", "application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
                raw_text = await asyncio.to_thread(ocr_service.extract_text_from_file, file_bytes, content_type)
            else: 
                raise ValueError(f"Unsupported file type: {content_type}")

            if not raw_text or not raw_text.strip():
                raise ValueError("Could not extract any readable text from the document.")

            prompt = prompt_library.ROSTER_EXTRACTION_PROMPT.format(raw_ocr_text=raw_text)
            ai_response_str = await gemini_service.generate_text(prompt, temperature=0.1)

            try:
                json_start, json_end = ai_response_str.find('{'), ai_response_str.rfind('}') + 1
                parsed_response = json.loads(ai_response_str[json_start:json_end])
            except Exception:
                raise ValueError("The AI could not structure the data from the document.")
            
            students_to_process = parsed_response.get("students", [])

        # 2. Process and save students, now passing the user_id for permission checks.
        if students_to_process:
            for student_data in students_to_process:
                if 'studentId' not in student_data or pd.isna(student_data.get('studentId')):
                    student_data['studentId'] = 'N/A'
                
                if student_data['studentId'] == 'N/A':
                    print(f"WARNING: Skipping student with missing ID: {student_data.get('name')}")
                    continue

                validated_student = student_model.StudentCreate(**student_data)
                
                # The user_id is now passed down to the CRUD helper.
                # This ensures the check `db.get_class_by_id(class_id, user_id)`
                # inside the helper will succeed.
                _ , was_created = crud.add_student_to_class_with_status(
                    class_id=new_class_object.id, 
                    student_data=validated_student, 
                    db=db,
                    user_id=user_id # <-- CRITICAL MODIFICATION
                )
                
                if was_created:
                    newly_created_student_count += 1

    except Exception as e:
        print(f"ERROR processing upload for class {new_class_object.id} owned by {user_id}: {e}")
        # Transactional Rollback: If any part of the process fails, we must
        # delete the class we created at the beginning to prevent orphaned data.
        # We pass the user_id to ensure we only delete the correct class.
        db.delete_class(new_class_object.id, user_id)
        raise ValueError(str(e))
    
    # The response dictionary construction remains the same.
    return {
        "message": "Upload successful. Roster processed.",
        "class_info": {
            "id": new_class_object.id,
            "name": new_class_object.name,
            "description": new_class_object.description,
            "studentCount": newly_created_student_count
        }
    }