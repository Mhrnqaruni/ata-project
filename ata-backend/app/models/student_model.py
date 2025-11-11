# /ata-backend/app/models/student_model.py (CORRECTED WITH Pydantic V2 CONFIG)

# --- Core Imports ---
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

# --- Model Definitions ---

class StudentBase(BaseModel):
    """
    The base model for a Student. Contains fields common to create and read operations.
    """
    name: str = Field(..., min_length=2, description="The full name of the student.")
    studentId: str = Field(..., description="The official, user-provided ID number for the student.")

class StudentCreate(StudentBase):
    """The model used for creating a new student. Inherits all fields from the base."""
    pass

class StudentUpdate(BaseModel):
    """
    The model for updating a student. All fields are optional to allow for
    partial updates.
    """
    # --- [THE FIX IS HERE] ---
    model_config = ConfigDict(from_attributes=True)
    # --- [END OF FIX] ---

    name: Optional[str] = Field(default=None, min_length=2)
    studentId: Optional[str] = Field(default=None)
    overallGrade: Optional[int] = Field(default=None)
    performance_summary: Optional[str] = Field(default=None)

class Student(StudentBase):
    """
    The full representation of a Student resource, as it is stored in the
    database and returned by the API.
    Note: class_id removed - students can now belong to multiple classes.
    """
    # --- [THE FIX IS HERE] ---
    model_config = ConfigDict(from_attributes=True)
    # --- [END OF FIX] ---

    id: str = Field(..., description="The unique, server-generated identifier for the student.")
    overallGrade: int = Field(
        default=0,
        description="The student's current overall grade. Defaults to 0 for new students."
    )
    performance_summary: Optional[str] = Field(
        default=None,
        description="An AI-generated summary of the student's performance (V2 feature)."
    )


# --- Student Transcript Models ---

class ClassInfo(BaseModel):
    """Information about a class the student is enrolled in."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class StudentAssessmentRow(BaseModel):
    """Represents one assessment in a student's transcript."""
    model_config = ConfigDict(from_attributes=True)

    jobId: str = Field(..., description="The assessment ID")
    assessmentName: str = Field(..., description="Name of the assessment")
    classId: str = Field(..., description="ID of the class this assessment belongs to")
    className: str = Field(..., description="Name of the class")
    createdAt: Optional[str] = Field(None, description="Date the assessment was created (ISO format)")
    totalScore: Optional[float] = Field(None, description="Student's total score")
    maxTotalScore: float = Field(..., description="Maximum possible score")
    status: str = Field(..., description="GRADED, PENDING_REVIEW, or ABSENT")
    reportUrl: Optional[str] = Field(None, description="URL to download the report")


class ClassTranscript(BaseModel):
    """Transcript data for a single class."""
    model_config = ConfigDict(from_attributes=True)

    classId: str
    className: str
    averagePercent: Optional[float] = Field(None, description="Average grade in this class")
    assessments: List[StudentAssessmentRow] = Field(default_factory=list)


class StudentTranscriptResponse(BaseModel):
    """Complete transcript response for a student across all classes."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    studentId: str
    name: str
    overallAveragePercent: Optional[float] = Field(None, description="Overall average across all classes")
    classSummaries: List[ClassTranscript] = Field(default_factory=list, description="Per-class breakdown")