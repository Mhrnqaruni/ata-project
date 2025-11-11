# /ata-backend/app/db/models/student_class_membership.py

"""
This module defines the SQLAlchemy ORM model for the StudentClassMembership
junction table, which enables many-to-many relationships between Students and Classes.

This allows a single student to belong to multiple classes simultaneously.
"""

from sqlalchemy import Column, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from ..base_class import Base


class StudentClassMembership(Base):
    """
    SQLAlchemy model representing the many-to-many relationship between
    Students and Classes.
    """
    __tablename__ = "student_class_memberships"

    id = Column(String, primary_key=True, index=True)
    student_id = Column(
        String,
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    class_id = Column(
        String,
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Relationships
    student = relationship("Student", back_populates="class_memberships")
    class_ = relationship("Class", back_populates="student_memberships")

    # Ensure each student-class pair is unique
    __table_args__ = (
        UniqueConstraint("student_id", "class_id", name="uq_student_class"),
    )
