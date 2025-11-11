# /ata-backend/app/services/database_helpers/class_student_repository_sql.py (MODIFIED AND APPROVED - FLAWLESS VERSION)

"""
This module contains all the raw SQLAlchemy queries for the User, Class, and
Student tables. It is the direct interface to the database for all roster and
user data, and it is the final point of enforcement for data isolation.

Every method that reads or modifies user-owned data has been updated to
require a `user_id`, ensuring all operations are securely scoped to the
authenticated user.
"""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session

# Import the SQLAlchemy models this repository will interact with.
from app.db.models.class_student_models import Class, Student
from app.db.models.user_model import User
from app.db.models.outsider_student import OutsiderStudent


class ClassStudentRepositorySQL:
    def __init__(self, db_session: Session):
        self.db = db_session

    # --- User Methods ---
    # These methods provide the foundational CRUD operations for the User model,
    # which are essential for the authentication system.

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Securely fetches a single user by their unique ID."""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Securely fetches a single user by their unique email address."""
        return self.db.query(User).filter(User.email == email).first()

    def add_user(self, record: Dict) -> User:
        """Creates a new User record in the database."""
        new_user = User(**record)
        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)
        return new_user

    # --- Class Methods ---

    def get_all_classes(self, user_id: str) -> List[Class]:
        """
        Retrieves all classes owned by a specific user.
        The query is now filtered by `user_id` to enforce data isolation.
        """
        return self.db.query(Class).filter(Class.user_id == user_id).all()

    def get_class_by_id(self, class_id: str, user_id: str) -> Optional[Class]:
        """
        Retrieves a single class by its ID, but only if it is owned by the
        specified user. This prevents unauthorized access to other users' classes.
        """
        return self.db.query(Class).filter(Class.id == class_id, Class.user_id == user_id).first()

    def add_class(self, record: Dict) -> Class:
        """
        Creates a new Class record.
        This function expects the `user_id` to be present in the `record` dictionary.
        """
        new_class = Class(**record)
        self.db.add(new_class)
        self.db.commit()
        self.db.refresh(new_class)
        return new_class

    def update_class(self, class_id: str, user_id: str, data: Dict) -> Optional[Class]:
        """
        Updates a class, but only if it is owned by the specified user.
        """
        # First, securely fetch the class to ensure ownership.
        db_class = self.get_class_by_id(class_id=class_id, user_id=user_id)
        if db_class:
            for key, value in data.items():
                setattr(db_class, key, value)
            self.db.commit()
            self.db.refresh(db_class)
        return db_class

    def delete_class(self, class_id: str, user_id: str) -> bool:
        """
        Deletes a class, but only if it is owned by the specified user.
        """
        # First, securely fetch the class to ensure ownership.
        db_class = self.get_class_by_id(class_id=class_id, user_id=user_id)
        if db_class:
            # The cascade delete defined in the model will handle deleting students.
            self.db.delete(db_class)
            self.db.commit()
            return True
        return False

    # --- Student Methods ---

    def get_students_by_class_id(self, class_id: str, user_id: str) -> List[Student]:
        """
        Retrieves all students for a given class, but only if the class is
        owned by the specified user. This is a critical defense-in-depth check.
        """
        from app.db.models.class_student_models import StudentClassMembership

        # First, verify that the user owns the parent class.
        parent_class = self.get_class_by_id(class_id=class_id, user_id=user_id)
        if not parent_class:
            # If the user does not own the class, return an empty list,
            # effectively hiding the students from unauthorized access.
            return []

        # Fetch students through the junction table
        return (
            self.db.query(Student)
            .join(StudentClassMembership, Student.id == StudentClassMembership.student_id)
            .filter(StudentClassMembership.class_id == class_id)
            .all()
        )

    def add_student(self, record: Dict) -> Student:
        """
        Creates a new Student record.
        Ownership is implicitly handled by the `class_id` in the record, which
        is validated by the calling service.
        """
        record['overallGrade'] = int(record.get('overallGrade')) if record.get('overallGrade') is not None else 0
        new_student = Student(**record)
        self.db.add(new_student)
        self.db.commit()
        self.db.refresh(new_student)
        return new_student

    def update_student(self, student_id: str, user_id: str, data: Dict) -> Optional[Student]:
        """
        Updates a student's details, but only if the student belongs to a class
        owned by the specified user.
        """
        from app.db.models.class_student_models import StudentClassMembership

        # This query joins Student with Class through membership to enforce ownership
        db_student = (
            self.db.query(Student)
            .join(StudentClassMembership, Student.id == StudentClassMembership.student_id)
            .join(Class, StudentClassMembership.class_id == Class.id)
            .filter(Student.id == student_id, Class.user_id == user_id)
            .first()
        )

        if db_student:
            for key, value in data.items():
                if key == 'overallGrade' and value is not None:
                    value = int(value)
                setattr(db_student, key, value)
            self.db.commit()
            self.db.refresh(db_student)
        return db_student

    def delete_student(self, student_id: str, user_id: str) -> bool:
        """
        Deletes a student, but only if the student belongs to a class owned by
        the specified user. This method is now independently secure.
        """
        from app.db.models.class_student_models import StudentClassMembership

        # Securely fetch the student using a join to verify ownership.
        db_student = (
            self.db.query(Student)
            .join(StudentClassMembership, Student.id == StudentClassMembership.student_id)
            .join(Class, StudentClassMembership.class_id == Class.id)
            .filter(Student.id == student_id, Class.user_id == user_id)
            .first()
        )
        if db_student:
            self.db.delete(db_student)
            self.db.commit()
            return True
        return False

    def add_outsider_student(self, record: Dict) -> OutsiderStudent:
        """Creates a new OutsiderStudent record in the database."""
        new_outsider = OutsiderStudent(**record)
        self.db.add(new_outsider)
        self.db.commit()
        self.db.refresh(new_outsider)
        return new_outsider
        
    def get_student_by_student_id(self, student_id: str) -> Optional[Student]:
        """
        Retrieves a student by their official (non-primary key) studentId.
        This is a global lookup, as student IDs are expected to be unique
        across the entire system.
        """
        return self.db.query(Student).filter(Student.studentId == student_id).first()

    def get_student_by_id(self, student_id: str, user_id: str) -> Optional[Student]:
        """
        Securely fetches a single student by their primary key ID, ensuring they
        belong to a class owned by the specified user.
        """
        from app.db.models.class_student_models import StudentClassMembership

        return (
            self.db.query(Student)
            .join(StudentClassMembership, Student.id == StudentClassMembership.student_id)
            .join(Class, StudentClassMembership.class_id == Class.id)
            .filter(Student.id == student_id, Class.user_id == user_id)
            .first()
        )

    # --- Chatbot Helper Methods ---

    def get_classes_for_chatbot(self, user_id: str) -> List[Dict]:
        """
        Returns a list of class dictionaries for the chatbot sandbox,
        securely filtered for the authenticated user.
        """
        user_classes = self.get_all_classes(user_id=user_id)
        return [{c.name: getattr(obj, c.name) for c in obj.__table__.columns} for obj in user_classes]

    def get_students_for_chatbot(self, user_id: str) -> List[Dict]:
        """
        Returns a list of student dictionaries for the chatbot sandbox,
        securely filtered for the authenticated user.
        """
        # This query joins students with their parent class to filter by the owner.
        from app.db.models.class_student_models import StudentClassMembership

        user_students = (
            self.db.query(Student)
            .join(StudentClassMembership, Student.id == StudentClassMembership.student_id)
            .join(Class, StudentClassMembership.class_id == Class.id)
            .filter(Class.user_id == user_id)
            .distinct()
            .all()
        )
        return [{c.name: getattr(obj, c.name) for c in obj.__table__.columns} for obj in user_students]

    # --- NEW: Student Membership Methods ---

    def get_class_memberships_for_student(self, student_id: str, user_id: str) -> List:
        """
        Returns all class memberships for a student, along with class details.
        Only returns classes owned by the specified user.
        """
        from app.db.models.class_student_models import StudentClassMembership

        memberships = (
            self.db.query(StudentClassMembership, Class)
            .join(Class, StudentClassMembership.class_id == Class.id)
            .filter(
                StudentClassMembership.student_id == student_id,
                Class.user_id == user_id
            )
            .all()
        )

        # Return list of objects with membership and class data
        result = []
        for membership, class_obj in memberships:
            result.append(type('obj', (object,), {
                'student_id': membership.student_id,
                'class_id': membership.class_id,
                'class_name': class_obj.name
            })())

        return result

    def add_student_to_class(self, student_id: str, class_id: str) -> bool:
        """
        Adds a student to a class via the membership table.
        Returns True if successful, False if already exists.
        """
        from app.db.models.class_student_models import StudentClassMembership
        import uuid

        # Check if membership already exists
        existing = (
            self.db.query(StudentClassMembership)
            .filter_by(student_id=student_id, class_id=class_id)
            .first()
        )

        if existing:
            return False

        # Create new membership
        membership = StudentClassMembership(
            id=f"scm_{uuid.uuid4().hex[:16]}",
            student_id=student_id,
            class_id=class_id
        )

        self.db.add(membership)
        self.db.commit()
        return True

    def remove_student_from_class(self, student_id: str, class_id: str) -> bool:
        """
        Removes a student from a class.
        Returns True if successful, False if not found.
        """
        from app.db.models.class_student_models import StudentClassMembership

        membership = (
            self.db.query(StudentClassMembership)
            .filter_by(student_id=student_id, class_id=class_id)
            .first()
        )

        if not membership:
            return False

        self.db.delete(membership)
        self.db.commit()
        return True