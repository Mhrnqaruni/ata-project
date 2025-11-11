# /app/models/class_model.py

# --- Core Imports ---
from pydantic import BaseModel, Field
from typing import List, Optional

# --- Local Imports ---
from . import student_model

# --- Model Definitions ---

class ClassBase(BaseModel):
    """
    The base model for a Class.
    """
    name: str = Field(..., min_length=3, max_length=100, description="The user-defined name of the class.")
    description: Optional[str] = Field(default=None, max_length=500, description="An optional description for the class.")

class ClassCreate(ClassBase):
    """
    The model used for creating a new class.
    """
    pass

class Class(ClassBase):
    """
    The full representation of a Class resource, including server-generated fields.
    """
    id: str = Field(..., description="The unique, server-generated identifier for the class.")
    class Config:
        from_attributes = True

class ClassSummary(Class):
    """
    An extended model for the 'Your Classes' grid view, including student count.
    """
    studentCount: int = Field(..., description="The total number of students enrolled in this class.")
    class Config:
        from_attributes = True
    

class ClassAnalytics(BaseModel):
    """A sub-model for class-specific analytics data."""
    studentCount: int
    classAverage: int
    assessmentsGraded: int
    class Config:
        from_attributes = True

class ClassDetails(Class):
    """
    The comprehensive model for the 'Class Details' page.
    """
    students: List[student_model.Student]
    analytics: ClassAnalytics
    class Config:
        from_attributes = True

class ClassUploadResponse(BaseModel):
    """
    Defines the response contract for a successful roster file upload.
    """
    message: str
    
    # <<< CORRECTION: Simplified the field name to avoid alias issues.
    # The key in the final JSON response will now be 'class_info'.
    # The service layer will return a dictionary with a matching 'class_info' key.
    class_info: ClassSummary
    class Config:
        from_attributes = True