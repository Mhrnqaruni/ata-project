# /ata-backend/app/db/models/class_student_models.py (MODIFIED FOR MANY-TO-MANY)

"""
This module defines the SQLAlchemy ORM models for the `Class` and `Student`
entities, which represent a teacher's class roster and the individual students
within it.

Now supports many-to-many relationships through StudentClassMembership junction table.
"""

from sqlalchemy import Column, String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
# --- [CRITICAL MODIFICATION] ---
# Import the UUID type from SQLAlchemy's PostgreSQL dialects. This is necessary
# to ensure the `user_id` foreign key column has the exact same data type as
# the `User.id` primary key it points to.
from sqlalchemy.dialects.postgresql import UUID

from ..base_class import Base

class Class(Base):
    """
    SQLAlchemy model representing a class or course.

    This model is now linked to a User, establishing the core ownership
    for all roster-related data. A user owns a class, and a class contains students.
    """
    __tablename__ = "classes"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    
    # --- [CRITICAL MODIFICATION 1/2: THE PHYSICAL LINK] ---
    # This column creates the foreign key relationship to the `users` table.
    # - UUID(as_uuid=True): Ensures type compatibility with the User.id primary key.
    # - ForeignKey("users.id"): The database-level constraint.
    # - nullable=False: Guarantees every class has an owner.
    # - index=True: Optimizes database lookups for a user's classes.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # --- [CRITICAL MODIFICATION 2/2: THE LOGICAL LINK] ---
    # This SQLAlchemy relationship allows for easy, object-oriented access
    # to the owning User object from a Class instance (e.g., `my_class.owner`).
    # `back_populates="classes"` creates a two-way link with the `classes`
    # relationship defined in the `user_model.py` file.
    owner = relationship("User", back_populates="classes")

    # Many-to-many relationship with Students through StudentClassMembership
    student_memberships = relationship("StudentClassMembership", back_populates="class_", cascade="all, delete-orphan")
    students = relationship("Student", secondary="student_class_memberships", viewonly=True)


class Student(Base):
    """
    SQLAlchemy model representing a single student.
    Can belong to multiple classes through StudentClassMembership.
    """
    __tablename__ = "students"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    studentId = Column(String, unique=True, index=True, nullable=False)

    overallGrade = Column(Integer, nullable=True)
    performance_summary = Column(String, nullable=True)

    # Many-to-many relationship with Classes through StudentClassMembership
    class_memberships = relationship("StudentClassMembership", back_populates="student", cascade="all, delete-orphan")
    classes = relationship("Class", secondary="student_class_memberships", viewonly=True)


class StudentClassMembership(Base):
    """
    Junction table for the many-to-many relationship between Students and Classes.
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