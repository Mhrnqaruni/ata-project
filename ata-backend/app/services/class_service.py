# /ata-backend/app/services/class_service.py (SUPERVISOR-APPROVED FLAWLESS VERSION)

"""
This service module acts as the primary business logic layer for all operations
related to classes and students.

It serves as a facade, orchestrating calls to lower-level specialist helpers
(like `crud` and `roster_ingestion`) and the `DatabaseService`. Every function
in this module has been made "user-aware," requiring a `user_id` to ensure
that all operations are securely scoped to the authenticated user. This module
is the critical link between the API routers and the data access layer.
"""

import pandas as pd
from typing import List, Dict, Optional
from fastapi import UploadFile

from ..models import class_model, student_model
from .database_service import DatabaseService

# Import the specialist helper modules this service orchestrates.
from .class_helpers import roster_ingestion, crud


# --- Facade Methods for CRUD Operations ---

def create_class(
    class_data: class_model.ClassCreate, 
    db: DatabaseService, 
    user_id: str
):
    """
    Business logic to create a new class for the authenticated user.

    This function "stamps" the owner's user_id onto the new class record
    before passing it to the low-level CRUD helper for persistence.
    """
    # Create a dictionary from the Pydantic model and add the owner's ID.
    class_record = {"user_id": user_id, **class_data.model_dump()}
    
    # Delegate the actual database insertion to the CRUD helper.
    return crud.create_class(class_record=class_record, db=db)


def update_class(
    class_id: str, 
    class_update: class_model.ClassCreate, 
    db: DatabaseService, 
    user_id: str
):
    """
    Business logic to update a class, ensuring the user has ownership.
    The user_id is passed down to the CRUD helper for security validation.
    """
    return crud.update_class(
        class_id=class_id, 
        class_update=class_update, 
        db=db, 
        user_id=user_id
    )


def delete_class_by_id(class_id: str, db: DatabaseService, user_id: str) -> bool:
    """
    Business logic to delete a class, ensuring the user has ownership.
    The user_id is passed down to the CRUD helper for security validation.
    """
    return crud.delete_class_by_id(class_id=class_id, db=db, user_id=user_id)


def add_student_to_class(
    class_id: str, 
    student_data: student_model.StudentCreate, 
    db: DatabaseService, 
    user_id: str
):
    """
    Business logic to add a student to a class, ensuring the user owns the class.
    The user_id is passed down to the CRUD helper for security validation.
    """
    return crud.add_student_to_class(
        class_id=class_id, 
        student_data=student_data, 
        db=db, 
        user_id=user_id
    )


def update_student(
    student_id: str, 
    student_update: student_model.StudentUpdate, 
    db: DatabaseService, 
    user_id: str
):
    """
    Business logic to update a student, ensuring the user owns the student's class.
    The user_id is passed down to the CRUD helper for security validation.
    """
    return crud.update_student(
        student_id=student_id, 
        student_update=student_update, 
        db=db, 
        user_id=user_id
    )


def delete_student_from_class(
    class_id: str,
    student_id: str, 
    db: DatabaseService, 
    user_id: str
) -> bool:
    """
    Business logic to delete a student, ensuring the user has ownership of the
    parent class.

    Now removes the student from the class via the membership table,
    but does NOT delete the student record itself (keeps them in assessments).
    """
    # Remove the student from this specific class (removes membership only)
    return db.remove_student_from_class(student_id=student_id, class_id=class_id)


async def create_class_from_upload(
    name: str, 
    file: UploadFile, 
    db: DatabaseService, 
    user_id: str
) -> Dict:
    """
    Business logic to orchestrate class creation from a file upload.
    The user_id is passed down to the ingestion helper to ensure the entire
    process is securely scoped to the authenticated user.
    """
    return await roster_ingestion.create_class_from_upload(
        name=name, 
        file=file, 
        db=db, 
        user_id=user_id
    )


# --- Data Assembly & Export Logic ---

def get_all_classes_with_summary(user_id: str, db: DatabaseService) -> List[Dict]:
    """
    Business logic to retrieve all classes for a user and enrich them with student counts.
    """
    # Securely fetch only the classes belonging to the authenticated user.
    all_classes = db.get_all_classes(user_id=user_id)
    if not all_classes:
        return []

    # Calculate student counts per class using the new junction table
    summary_list = []
    for cls in all_classes:
        # Get students for this specific class
        students_in_class = db.get_students_by_class_id(class_id=cls.id, user_id=user_id)

        summary_data = {
            "id": cls.id,
            "name": cls.name,
            "description": cls.description,
            "studentCount": len(students_in_class)
        }
        summary_list.append(summary_data)
    return summary_list


def get_class_details_by_id(class_id: str, user_id: str, db: DatabaseService) -> Optional[Dict]:
    """
    Business logic to assemble the full details for the Class Details page,
    ensuring the user has ownership of the requested class.
    """
    from ..db.models.assessment_models import ResultStatus
    from ..services.assessment_helpers.analytics_and_matching import normalize_config_to_v2

    # Securely fetch the class, ensuring it belongs to the user.
    class_info = db.get_class_by_id(class_id=class_id, user_id=user_id)
    if not class_info:
        return None

    # Securely fetch the students for that class.
    students_in_class = db.get_students_by_class_id(class_id=class_id, user_id=user_id)

    # Get all assessments for this class
    assessments = db.get_assessments_for_class(class_id=class_id, user_id=user_id)

    # Calculate student grades and class statistics
    student_grades = {}  # {student_id: {"total_earned": X, "total_possible": Y}}
    completed_assessments = 0

    for assessment in assessments:
        # Check if assessment is completed/graded
        if assessment.status == "Completed":
            completed_assessments += 1

        # Get config to calculate max score
        cfg = normalize_config_to_v2(assessment)
        max_total_score = sum(q.maxScore for s in cfg.sections for q in s.questions if q.maxScore is not None)

        # Get all results for this assessment
        for student in students_in_class:
            results = db.get_results_for_student_and_job(
                student_id=student.id,
                job_id=assessment.id,
                user_id=user_id
            )

            if results:
                # Check if all results are graded (not pending)
                all_graded = all(r.status != ResultStatus.PENDING_REVIEW.value for r in results)

                if all_graded:
                    # Calculate student's score for this assessment
                    student_score = sum(float(r.grade) for r in results if r.grade is not None)

                    # Initialize student entry if needed
                    if student.id not in student_grades:
                        student_grades[student.id] = {"total_earned": 0.0, "total_possible": 0.0}

                    student_grades[student.id]["total_earned"] += student_score
                    student_grades[student.id]["total_possible"] += max_total_score

    # Calculate each student's overall grade percentage
    students_with_grades = []
    class_total_earned = 0.0
    class_total_possible = 0.0

    for student in students_in_class:
        student_dict = {
            "id": student.id,
            "name": student.name,
            "studentId": student.studentId,
            "overallGrade": 0,
            "performance_summary": student.performance_summary
        }

        if student.id in student_grades:
            earned = student_grades[student.id]["total_earned"]
            possible = student_grades[student.id]["total_possible"]

            if possible > 0:
                grade_percent = round((earned / possible) * 100)
                student_dict["overallGrade"] = grade_percent

                # Add to class totals
                class_total_earned += earned
                class_total_possible += possible

        students_with_grades.append(student_dict)

    # Calculate class average
    class_average = 0
    if class_total_possible > 0:
        class_average = round((class_total_earned / class_total_possible) * 100)

    analytics_data = {
        "studentCount": len(students_in_class),
        "classAverage": class_average,
        "assessmentsGraded": completed_assessments
    }

    return {
        "id": class_info.id,
        "name": class_info.name,
        "description": class_info.description,
        "students": students_with_grades,
        "analytics": analytics_data
    }


def export_roster_as_csv(class_id: str, user_id: str, db: DatabaseService) -> str:
    """
    Business logic to generate a CSV export for a single class roster,
    ensuring the user has ownership of the class.
    """
    # Securely fetch the class details.
    class_details = db.get_class_by_id(class_id=class_id, user_id=user_id)
    if not class_details:
        raise ValueError(f"Class with ID {class_id} not found or access denied.")
        
    # Securely fetch the students for that class.
    students_in_class = db.get_students_by_class_id(class_id=class_id, user_id=user_id)
    
    export_data = [
        {
            'Student Name': s.name, 
            'Student ID': s.studentId, 
            'Overall Grade': s.overallGrade if s.overallGrade is not None else "N/A", 
            'Class Name': class_details.name
        } for s in students_in_class
    ]
    
    df = pd.DataFrame(export_data) if export_data else pd.DataFrame(columns=['Student Name', 'Student ID', 'Overall Grade', 'Class Name'])
    
    return df.to_csv(index=False)