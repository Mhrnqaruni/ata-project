# /app/services/class_helpers/crud.py (MODIFIED AND APPROVED)

"""
This module contains the core, low-level business logic for Create, Read,
Update, and Delete (CRUD) operations on Class and Student entities.

It acts as a specialist helper, called by higher-level services like the main
`class_service` and `roster_ingestion` service. Every function here is now
"user-aware," requiring a `user_id` to ensure all database operations are
securely scoped to the authenticated user.
"""

import uuid
from typing import Dict, Optional

from ...models import class_model, student_model
from ..database_service import DatabaseService
from ...db.models.class_student_models import Class, Student

# --- CLASS-RELATED CORE BUSINESS LOGIC ---

def create_class(class_record: Dict, db: DatabaseService) -> Class:
    """
    Creates a new class record in the database from a pre-validated dictionary.

    This function now expects the incoming `class_record` dictionary to already
    contain the `user_id` of the owner, which is added by the calling service.
    Its primary responsibility is to generate a unique ID for the new class
    and persist it.

    Args:
        class_record: A dictionary containing all necessary data for a new class,
                      including the `user_id`.
        db: The DatabaseService instance for data persistence.

    Returns:
        The newly created SQLAlchemy Class object.
    """
    new_id = f"cls_{uuid.uuid4().hex[:12]}"
    class_record['id'] = new_id
    
    new_class_object = db.add_class(class_record)
    return new_class_object


def update_class(
    class_id: str,
    class_update: class_model.ClassCreate,
    db: DatabaseService,
    user_id: str
) -> Optional[Class]:
    """
    Updates a specific class's details, ensuring the user has ownership.

    Args:
        class_id: The ID of the class to update.
        class_update: A Pydantic model with the new data.
        db: The DatabaseService instance.
        user_id: The ID of the authenticated user making the request.

    Returns:
        The updated SQLAlchemy Class object, or None if not found.
    """
    update_data = class_update.model_dump(exclude_unset=True)
    if not update_data:
        raise ValueError("No update data provided.")
    
    # The user_id is passed down to the data access layer to ensure a user
    # can only update a class that they own.
    updated_class = db.update_class(class_id, user_id, update_data)
    return updated_class


def delete_class_by_id(class_id: str, db: DatabaseService, user_id: str) -> bool:
    """
    Deletes a class and all its associated students, ensuring ownership.

    The initial check for the class's existence is now user-scoped, preventing
    one user from being able to delete another user's class.

    Args:
        class_id: The ID of the class to delete.
        db: The DatabaseService instance.
        user_id: The ID of the authenticated user making the request.

    Returns:
        True if the deletion was successful, False otherwise.
    """
    # This check is now secure. It will only find the class if it exists AND
    # belongs to the current user.
    if not db.get_class_by_id(class_id, user_id):
        return False
    
    # The underlying cascade delete on the Student model handles student deletion.
    # We pass the user_id to the final delete call for consistency and security.
    db.delete_class(class_id, user_id)
    return True


# --- STUDENT-RELATED CORE BUSINESS LOGIC ---

def add_student_to_class_with_status(
    class_id: str,
    student_data: student_model.StudentCreate,
    db: DatabaseService,
    user_id: str
) -> tuple[Student, bool]:
    """
    Adds a student to a class, checking for pre-existence based on studentId.

    This specialist function for batch processing is now secure because its
    initial check for the class's existence is scoped to the current user.

    Args:
        class_id: The ID of the class to add the student to.
        student_data: A Pydantic model with the new student's data.
        db: The DatabaseService instance.
        user_id: The ID of the authenticated user.

    Returns:
        A tuple: (SQLAlchemy Student object, boolean indicating if created).
    """
    # This check is now secure. It prevents a user from adding a student
    # to a class they do not own.
    if not db.get_class_by_id(class_id, user_id):
        raise ValueError(f"Class with ID {class_id} not found or access denied.")

    # Check if student exists globally (studentId should be unique system-wide)
    existing_student = db.get_student_by_student_id(student_data.studentId)

    if existing_student:
        # Student exists - just add them to this class via membership
        print(f"INFO: Student with ID {student_data.studentId} already exists. Adding to class.")
        db.add_student_to_class(existing_student.id, class_id)
        return existing_student, False

    # Create new student
    new_student_id = f"stu_{uuid.uuid4().hex[:12]}"
    new_student_record = student_data.model_dump()
    new_student_record['id'] = new_student_id
    new_student_record['overallGrade'] = 0

    new_student_object = db.add_student(new_student_record)

    # Add student to class via membership table
    db.add_student_to_class(new_student_object.id, class_id)

    return new_student_object, True


def add_student_to_class(
    class_id: str,
    student_data: student_model.StudentCreate,
    db: DatabaseService,
    user_id: str
) -> Student:
    """
    A simpler wrapper for the manual "Add Student" API endpoint.

    This is now secure as it passes the user_id down to the underlying
    `add_student_to_class_with_status` function.
    """
    student_object, _ = add_student_to_class_with_status(
        class_id=class_id,
        student_data=student_data,
        db=db,
        user_id=user_id
    )
    return student_object


def update_student(
    student_id: str,
    student_update: student_model.StudentUpdate,
    db: DatabaseService,
    user_id: str
) -> Optional[Student]:
    """
    Updates a student's details, ensuring the user has ownership via the parent class.

    This function is now secure due to the defense-in-depth principle. It requires
    the `user_id` and passes it to the data access layer, which will verify that
    the student being updated belongs to a class owned by the current user.
    """
    update_data = student_update.model_dump(exclude_unset=True)
    if not update_data:
        raise ValueError("No update data provided.")
        
    # Pass the user_id down to the data access layer for an ownership check.
    updated_student = db.update_student(student_id, user_id, update_data)
    return updated_student