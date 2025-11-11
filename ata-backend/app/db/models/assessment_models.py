# /ata-backend/app/db/models/assessment_models.py (MODIFIED AND APPROVED)

"""
This module defines the SQLAlchemy ORM models for the `Assessment` and `Result`
entities, which represent grading jobs and their individual outcomes, respectively.
"""

import enum
from sqlalchemy import Column, String, Float, JSON, DateTime, ForeignKey, Enum as SAEnum, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
# --- [CRITICAL MODIFICATION] ---
# Import the UUID type from SQLAlchemy's PostgreSQL dialects. This is necessary
# to ensure the `user_id` foreign key column has the exact same data type as
# the `User.id` primary key it points to.
from sqlalchemy.dialects.postgresql import UUID

from ..base_class import Base

class Assessment(Base):
    """
    SQLAlchemy model representing a top-level assessment (grading job).

    This model is now linked to a User, establishing the core ownership
    for the entire assessment feature.
    """
    id = Column(String, primary_key=True, index=True)
    status = Column(String, index=True, nullable=False)
    config = Column(JSON, nullable=False)
    answer_sheet_paths = Column(JSON, nullable=True)
    ai_summary = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    total_pages = Column(Float, nullable=True)  # Total pages across all student submissions

    # --- [CRITICAL MODIFICATION 1/2: THE PHYSICAL LINK] ---
    # This column creates the foreign key relationship to the `users` table.
    # - UUID(as_uuid=True): Ensures type compatibility with the User.id primary key.
    # - ForeignKey("users.id"): The database-level constraint.
    # - nullable=False: Guarantees every assessment has an owner.
    # - index=True: Optimizes database lookups for a user's assessments.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # --- [CRITICAL MODIFICATION 2/2: THE LOGICAL LINK] ---
    # This SQLAlchemy relationship allows for easy, object-oriented access
    # to the owning User object from an Assessment instance (e.g., `my_assessment.owner`).
    # `back_populates="assessments"` creates a two-way link with the `assessments`
    # relationship defined in the `user_model.py` file.
    owner = relationship("User", back_populates="assessments")

    # This relationship remains unchanged. When an Assessment is deleted, all its
    # child Result records are also deleted due to the cascade option.
    results = relationship("Result", back_populates="assessment", cascade="all, delete-orphan")
    outsider_students = relationship("OutsiderStudent", back_populates="assessment", cascade="all, delete-orphan")


class ResultStatus(str, enum.Enum):
    PROCESSING = "PROCESSING"
    AI_GRADED = "AI_GRADED"
    PENDING_REVIEW = "PENDING_REVIEW"
    TEACHER_GRADED = "TEACHER_GRADED"
    FAILED = "FAILED"

class FinalizedBy(str, enum.Enum):
    AI = "AI"
    TEACHER = "TEACHER"

class Result(Base):
    """
    SQLAlchemy model representing the grade and feedback for a single question
    for a single student within an Assessment.
    """
    __tablename__ = "results"
    id = Column(String, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("assessments.id"), nullable=False)
    student_id = Column(String, ForeignKey("students.id"), nullable=True)  # Made nullable
    outsider_student_id = Column(String, ForeignKey("outsider_students.id"), nullable=True)  # New column
    question_id = Column(String, nullable=False)
    
    grade = Column(Float, nullable=True)
    feedback = Column(String, nullable=True)
    extractedAnswer = Column(String, nullable=True)
    status = Column(String, nullable=False, default='pending') # Will be updated by migration
    report_token = Column(String, unique=True, index=True, nullable=True)
    answer_sheet_path = Column(String, nullable=True)
    content_type = Column(String, nullable=True)
    
    # New Columns
    finalized_by = Column(SAEnum(FinalizedBy, name="finalizedby"), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    assessment = relationship("Assessment", back_populates="results")
    student = relationship("Student")
    outsider_student = relationship("OutsiderStudent", back_populates="results")

    ai_responses = Column(JSON, nullable=True)

    __table_args__ = (
        CheckConstraint(
            '(student_id IS NOT NULL AND outsider_student_id IS NULL) OR '
            '(student_id IS NULL AND outsider_student_id IS NOT NULL)',
            name='chk_result_student_or_outsider'
        ),
    )