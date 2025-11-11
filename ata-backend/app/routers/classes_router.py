
# /ata-backend/app/routers/classes_router.py (SUPERVISOR-APPROVED FLAWLESS VERSION)

"""
This module defines the secure API endpoints for managing Class and Student data.

Every endpoint in this router is protected and requires a valid JWT Bearer token
for an active user. The router is responsible for:
1. Receiving HTTP requests for class and student operations.
2. Using the `get_current_active_user` dependency to authenticate and authorize the user.
3. Passing the authenticated user's context (`user_id`) down to the business
   logic layer (`class_service`).
4. Handling HTTP-specific concerns like status codes and exceptions.
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Response
from fastapi.responses import StreamingResponse
from typing import List

# --- Application-specific Imports ---
from ..models import class_model, student_model
from ..services import class_service
from ..services.database_service import DatabaseService, get_db_service

# --- [CRITICAL MODIFICATION 1/2: IMPORT SECURITY DEPENDENCIES] ---
from ..core.deps import get_current_active_user
from ..db.models.user_model import User as UserModel

router = APIRouter()

# --- CLASS COLLECTION ENDPOINTS (/api/classes) ---

@router.get("", response_model=List[class_model.ClassSummary], summary="Get All Classes for Current User")
def get_all_classes(
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user) # <-- Security Dependency
):
    """
    Retrieves a summary list of all classes owned by the currently authenticated user.
    """
    # Pass the authenticated user's ID to the service layer.
    return class_service.get_all_classes_with_summary(user_id=current_user.id, db=db)

@router.post("", response_model=class_model.Class, status_code=status.HTTP_201_CREATED, summary="Create a New Class")
def create_new_class(
    class_create: class_model.ClassCreate, 
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user) # <-- Security Dependency
):
    """
    Creates a new class, automatically assigning ownership to the authenticated user.
    """
    # Pass the user's ID to the service layer to be stamped on the new record.
    return class_service.create_class(class_data=class_create, db=db, user_id=current_user.id)

@router.post("/upload", response_model=class_model.ClassUploadResponse, status_code=status.HTTP_202_ACCEPTED, summary="Create a Class via Roster Upload")
async def create_class_with_upload(
    name: str = Form(...), 
    file: UploadFile = File(...),
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user) # <-- Security Dependency
):
    """
    Creates a new class and populates its roster from an uploaded file.
    Ownership is assigned to the authenticated user.
    """
    try:
        # Pass the user's ID to the service layer for the entire secure transaction.
        result = await class_service.create_class_from_upload(name=name, file=file, db=db, user_id=current_user.id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected server error occurred: {e}")

# --- INDIVIDUAL CLASS RESOURCE ENDPOINTS (/api/classes/{class_id}) ---

@router.get("/{class_id}", response_model=class_model.ClassDetails, summary="Get a Single Class by ID")
def get_class_by_id(
    class_id: str, 
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user) # <-- Security Dependency
):
    """
    Retrieves the full details of a single class, but only if it is owned by the
    authenticated user.
    """
    # Pass the user's ID to the service layer for an ownership check.
    class_details = class_service.get_class_details_by_id(class_id=class_id, user_id=current_user.id, db=db)
    if class_details is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Class with ID {class_id} not found or access denied.")
    return class_details

@router.put("/{class_id}", response_model=class_model.Class, summary="Update a Class")
def update_class_details(
    class_id: str, 
    class_update: class_model.ClassCreate, 
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user) # <-- Security Dependency
):
    """
    Updates a class's details, but only if it is owned by the authenticated user.
    """
    try:
        # Pass the user's ID to the service layer for an ownership check.
        updated_class = class_service.update_class(class_id=class_id, class_update=class_update, db=db, user_id=current_user.id)
        if updated_class is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Class with ID {class_id} not found or access denied.")
        return updated_class
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a Class")
def delete_class(
    class_id: str, 
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user) # <-- Security Dependency
):
    """
    Deletes a class and all its students, but only if it is owned by the
    authenticated user.
    """
    # Pass the user's ID to the service layer for an ownership check.
    was_deleted = class_service.delete_class_by_id(class_id=class_id, db=db, user_id=current_user.id)
    if not was_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Class with ID {class_id} not found or access denied.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/{class_id}/export", summary="Export Class Roster as CSV", response_class=StreamingResponse)
def export_class_roster_csv(
    class_id: str, 
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user) # <-- Security Dependency
):
    """
    Generates a CSV export of a class roster, but only if the class is owned
    by the authenticated user.
    """
    try:
        # Pass the user's ID to the service layer for an ownership check.
        csv_string = class_service.export_roster_as_csv(class_id=class_id, user_id=current_user.id, db=db)
        class_details = class_service.get_class_details_by_id(class_id, current_user.id, db)
        class_name = class_details.get('name', 'class_roster') if class_details else 'class_roster'
        file_name = f"roster_{class_name.replace(' ', '_').lower()}.csv"
        return StreamingResponse(iter([csv_string]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={file_name}"})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

# --- STUDENT SUB-RESOURCE ENDPOINTS ---

@router.post("/{class_id}/students", response_model=student_model.Student, status_code=status.HTTP_201_CREATED, summary="Add a Student to a Class")
def add_student(
    class_id: str, 
    student_create: student_model.StudentCreate, 
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user) # <-- Security Dependency
):
    """
    Adds a new student to a class, but only if the class is owned by the
    authenticated user.
    """
    try:
        # Pass the user's ID to the service layer for an ownership check on the parent class.
        new_student = class_service.add_student_to_class(class_id=class_id, student_data=student_create, db=db, user_id=current_user.id)
        return new_student
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.put("/{class_id}/students/{student_id}", response_model=student_model.Student, summary="Update a Student")
def update_student_details(
    class_id: str, 
    student_id: str, 
    student_update: student_model.StudentUpdate, 
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user) # <-- Security Dependency
):
    """
    Updates a student's details, but only if the student belongs to a class
    owned by the authenticated user.
    """
    try:
        # Pass the user's ID to the service layer for an ownership check.
        updated_student = class_service.update_student(student_id=student_id, student_update=student_update, db=db, user_id=current_user.id)
        if updated_student is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Student with ID {student_id} not found or access denied.")
        return updated_student
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{class_id}/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a Student from a Class")
def remove_student_from_class(
    class_id: str, 
    student_id: str, 
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user) # <-- Security Dependency
):
    """
    Removes a student from a class, but only if the class is owned by the
    authenticated user.
    """
    # Pass the user's ID to the service layer for an ownership check.
    was_deleted = class_service.delete_student_from_class(class_id=class_id, student_id=student_id, db=db, user_id=current_user.id)
    if not was_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Student with ID {student_id} not found in class {class_id} or access denied.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)