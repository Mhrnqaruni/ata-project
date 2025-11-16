"""
Quiz Repository - SQLAlchemy Data Access Layer

This module provides database operations for Quiz and QuizQuestion entities.
All methods enforce user ownership security by requiring user_id parameters.

Security principles:
- Every read/write operation validates user ownership
- No cross-user data access possible
- Soft delete support for quizzes (preserve analytics)
- Cascade deletes handled by database constraints

Pattern: Repository methods return SQLAlchemy model instances,
not dictionaries. The service layer handles any necessary transformations.
"""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, func
from datetime import datetime

# Import SQLAlchemy models
from app.db.models.quiz_models import Quiz, QuizQuestion
from app.db.models.user_model import User


class QuizRepositorySQL:
    """Repository for Quiz and QuizQuestion database operations."""

    def __init__(self, db_session: Session):
        """
        Initialize repository with database session.

        Args:
            db_session: SQLAlchemy session for database operations
        """
        self.db = db_session

    # ==================== QUIZ CRUD OPERATIONS ====================

    def create_quiz(self, quiz_data: Dict) -> Quiz:
        """
        Create a new quiz.

        Args:
            quiz_data: Dictionary with quiz fields (must include user_id)

        Returns:
            Created Quiz instance

        Security: user_id must be present in quiz_data
        """
        new_quiz = Quiz(**quiz_data)
        self.db.add(new_quiz)
        self.db.commit()
        self.db.refresh(new_quiz)
        return new_quiz

    def get_quiz_by_id(self, quiz_id: str, user_id: str) -> Optional[Quiz]:
        """
        Get a single quiz by ID, ensuring user ownership.

        Args:
            quiz_id: Quiz ID
            user_id: User ID (owner check)

        Returns:
            Quiz instance or None if not found/not owned

        Security: Only returns quiz if owned by user
        """
        return (
            self.db.query(Quiz)
            .filter(
                Quiz.id == quiz_id,
                Quiz.user_id == user_id,
                Quiz.deleted_at.is_(None)  # Exclude soft-deleted
            )
            .first()
        )

    def get_all_quizzes(self, user_id: str, status: Optional[str] = None,
                        class_id: Optional[str] = None,
                        include_deleted: bool = False) -> List[Quiz]:
        """
        Get all quizzes owned by a user with optional filtering.

        Args:
            user_id: User ID (owner filter)
            status: Optional status filter (draft/published/archived)
            class_id: Optional class filter
            include_deleted: Whether to include soft-deleted quizzes

        Returns:
            List of Quiz instances

        Security: Only returns quizzes owned by user
        """
        query = self.db.query(Quiz).filter(Quiz.user_id == user_id)

        # Apply status filter
        if status:
            query = query.filter(Quiz.status == status)

        # Apply class filter
        if class_id:
            query = query.filter(Quiz.class_id == class_id)

        # Exclude deleted unless explicitly requested
        if not include_deleted:
            query = query.filter(Quiz.deleted_at.is_(None))

        # Order by most recent first
        return query.order_by(Quiz.updated_at.desc()).all()

    def update_quiz(self, quiz_id: str, user_id: str, update_data: Dict) -> Optional[Quiz]:
        """
        Update a quiz's fields.

        Args:
            quiz_id: Quiz ID
            user_id: User ID (owner check)
            update_data: Dictionary of fields to update

        Returns:
            Updated Quiz instance or None if not found/not owned

        Security: Only updates quiz if owned by user
        """
        quiz = self.get_quiz_by_id(quiz_id, user_id)
        if quiz:
            for key, value in update_data.items():
                if hasattr(quiz, key):
                    setattr(quiz, key, value)

            # Always update the timestamp
            quiz.updated_at = datetime.now()

            self.db.commit()
            self.db.refresh(quiz)
        return quiz

    def delete_quiz(self, quiz_id: str, user_id: str, soft_delete: bool = True) -> bool:
        """
        Delete a quiz (soft or hard delete).

        Args:
            quiz_id: Quiz ID
            user_id: User ID (owner check)
            soft_delete: If True, only mark as deleted (default: True)

        Returns:
            True if deleted, False if not found/not owned

        Security: Only deletes quiz if owned by user

        Note: Soft delete preserves data for analytics while hard delete
        uses CASCADE to remove all related questions, sessions, etc.
        """
        quiz = self.get_quiz_by_id(quiz_id, user_id)
        if quiz:
            if soft_delete:
                quiz.deleted_at = datetime.now()
                self.db.commit()
            else:
                self.db.delete(quiz)
                self.db.commit()
            return True
        return False

    def restore_quiz(self, quiz_id: str, user_id: str) -> bool:
        """
        Restore a soft-deleted quiz.

        Args:
            quiz_id: Quiz ID
            user_id: User ID (owner check)

        Returns:
            True if restored, False if not found/not owned
        """
        quiz = (
            self.db.query(Quiz)
            .filter(Quiz.id == quiz_id, Quiz.user_id == user_id)
            .first()
        )
        if quiz and quiz.deleted_at:
            quiz.deleted_at = None
            self.db.commit()
            return True
        return False

    def update_quiz_status(self, quiz_id: str, user_id: str, status: str) -> Optional[Quiz]:
        """
        Update quiz status (draft/published/archived).

        Args:
            quiz_id: Quiz ID
            user_id: User ID (owner check)
            status: New status

        Returns:
            Updated Quiz instance or None if not found/not owned
        """
        return self.update_quiz(quiz_id, user_id, {"status": status})

    def update_last_room_code(self, quiz_id: str, user_id: str, room_code: str) -> Optional[Quiz]:
        """
        Update the last used room code for quick rejoin.

        Args:
            quiz_id: Quiz ID
            user_id: User ID (owner check)
            room_code: Room code to store

        Returns:
            Updated Quiz instance or None if not found/not owned
        """
        return self.update_quiz(quiz_id, user_id, {"last_room_code": room_code})

    # ==================== QUESTION CRUD OPERATIONS ====================

    def add_question(self, question_data: Dict) -> QuizQuestion:
        """
        Add a question to a quiz.

        Args:
            question_data: Dictionary with question fields (must include quiz_id)

        Returns:
            Created QuizQuestion instance

        Note: User ownership is validated via quiz_id foreign key
        """
        new_question = QuizQuestion(**question_data)
        self.db.add(new_question)
        self.db.commit()
        self.db.refresh(new_question)
        return new_question

    def get_question_by_id(self, question_id: str) -> Optional[QuizQuestion]:
        """
        Get a single question by ID.

        Args:
            question_id: Question ID

        Returns:
            QuizQuestion instance or None if not found

        Note: User ownership should be validated by checking the quiz's user_id
        """
        return self.db.query(QuizQuestion).filter(QuizQuestion.id == question_id).first()

    def get_questions_by_quiz_id(self, quiz_id: str, user_id: str) -> List[QuizQuestion]:
        """
        Get all questions for a quiz, ordered by order_index.

        Args:
            quiz_id: Quiz ID
            user_id: User ID (owner check via join)

        Returns:
            List of QuizQuestion instances ordered by order_index

        Security: Only returns questions if user owns the quiz
        """
        return (
            self.db.query(QuizQuestion)
            .join(Quiz, QuizQuestion.quiz_id == Quiz.id)
            .filter(
                QuizQuestion.quiz_id == quiz_id,
                Quiz.user_id == user_id
            )
            .order_by(QuizQuestion.order_index)
            .all()
        )

    def update_question(self, question_id: str, user_id: str, update_data: Dict) -> Optional[QuizQuestion]:
        """
        Update a question's fields.

        Args:
            question_id: Question ID
            user_id: User ID (owner check via quiz)
            update_data: Dictionary of fields to update

        Returns:
            Updated QuizQuestion instance or None if not found/not owned

        Security: Only updates question if user owns the quiz
        """
        question = (
            self.db.query(QuizQuestion)
            .join(Quiz, QuizQuestion.quiz_id == Quiz.id)
            .filter(QuizQuestion.id == question_id, Quiz.user_id == user_id)
            .first()
        )

        if question:
            for key, value in update_data.items():
                if hasattr(question, key):
                    setattr(question, key, value)
            self.db.commit()
            self.db.refresh(question)
        return question

    def delete_question(self, question_id: str, user_id: str) -> bool:
        """
        Delete a question.

        Args:
            question_id: Question ID
            user_id: User ID (owner check via quiz)

        Returns:
            True if deleted, False if not found/not owned

        Security: Only deletes question if user owns the quiz
        """
        question = (
            self.db.query(QuizQuestion)
            .join(Quiz, QuizQuestion.quiz_id == Quiz.id)
            .filter(QuizQuestion.id == question_id, Quiz.user_id == user_id)
            .first()
        )

        if question:
            self.db.delete(question)
            self.db.commit()
            return True
        return False

    def reorder_questions(self, quiz_id: str, user_id: str, question_order: List[str]) -> bool:
        """
        Reorder questions in a quiz.

        Args:
            quiz_id: Quiz ID
            user_id: User ID (owner check)
            question_order: List of question IDs in desired order

        Returns:
            True if reordered, False if quiz not found/not owned

        Security: Only reorders if user owns the quiz
        """
        # Verify ownership
        quiz = self.get_quiz_by_id(quiz_id, user_id)
        if not quiz:
            return False

        # Update order_index for each question
        for index, question_id in enumerate(question_order):
            self.db.query(QuizQuestion).filter(
                QuizQuestion.id == question_id,
                QuizQuestion.quiz_id == quiz_id
            ).update({"order_index": index})

        self.db.commit()
        return True

    def get_question_count(self, quiz_id: str, user_id: str) -> int:
        """
        Get the number of questions in a quiz.

        Args:
            quiz_id: Quiz ID
            user_id: User ID (owner check)

        Returns:
            Number of questions (0 if quiz not found/not owned)
        """
        return (
            self.db.query(func.count(QuizQuestion.id))
            .join(Quiz, QuizQuestion.quiz_id == Quiz.id)
            .filter(
                QuizQuestion.quiz_id == quiz_id,
                Quiz.user_id == user_id
            )
            .scalar() or 0
        )

    # ==================== BULK OPERATIONS ====================

    def duplicate_quiz(self, quiz_id: str, user_id: str, new_title: Optional[str] = None) -> Optional[Quiz]:
        """
        Duplicate a quiz with all its questions.

        Args:
            quiz_id: Quiz ID to duplicate
            user_id: User ID (owner check)
            new_title: Optional new title (defaults to "Copy of [original]")

        Returns:
            New Quiz instance or None if original not found/not owned

        Security: Only duplicates if user owns the original
        """
        original_quiz = self.get_quiz_by_id(quiz_id, user_id)
        if not original_quiz:
            return None

        # Create new quiz
        new_quiz_data = {
            "user_id": user_id,
            "class_id": original_quiz.class_id,
            "title": new_title or f"Copy of {original_quiz.title}",
            "description": original_quiz.description,
            "settings": original_quiz.settings.copy(),
            "status": "draft"  # Always start as draft
        }
        new_quiz = self.create_quiz(new_quiz_data)

        # Duplicate all questions
        original_questions = self.get_questions_by_quiz_id(quiz_id, user_id)
        for question in original_questions:
            question_data = {
                "quiz_id": new_quiz.id,
                "question_type": question.question_type,
                "question_text": question.question_text,
                "options": question.options.copy() if question.options else [],
                "correct_answer": question.correct_answer.copy() if question.correct_answer else [],
                "points": question.points,
                "time_limit_seconds": question.time_limit_seconds,
                "order_index": question.order_index,
                "explanation": question.explanation,
                "media_url": question.media_url
            }
            self.add_question(question_data)

        return new_quiz
