# /ata-backend/app/services/database_helpers/quiz_repository_sql.py

"""
This module contains all the raw SQLAlchemy queries for the Quiz and QuizQuestion
tables. It is the direct interface to the database for all quiz-related data,
and it is a final point of enforcement for data isolation.

Every method that reads or modifies user-owned data requires a `user_id`,
ensuring all operations are securely scoped to the authenticated user.
This module follows a "defense-in-depth" principle, meaning every function
is independently secure.
"""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime

# Import the SQLAlchemy models this repository will interact with.
from app.db.models.quiz_models import Quiz, QuizQuestion
from app.db.models.user_model import User
from app.db.models.class_student_models import Class


class QuizRepositorySQL:
    def __init__(self, db_session: Session):
        self.db = db_session

    # --- Quiz CRUD Methods ---

    def create_quiz(self, record: Dict) -> Quiz:
        """
        Creates a new Quiz record.
        This function expects the `user_id` to be present in the `record` dictionary,
        stamped by the calling service.
        """
        new_quiz = Quiz(**record)
        self.db.add(new_quiz)
        self.db.commit()
        self.db.refresh(new_quiz)
        return new_quiz

    def get_quiz_by_id(self, quiz_id: str, user_id: str) -> Optional[Quiz]:
        """
        Retrieves a single quiz by its ID, but only if it is owned by the
        specified user. This prevents unauthorized access to other users' quizzes.
        Excludes soft-deleted quizzes.
        """
        return (
            self.db.query(Quiz)
            .filter(
                Quiz.id == quiz_id,
                Quiz.user_id == user_id,
                Quiz.deleted_at.is_(None)
            )
            .first()
        )

    def get_all_quizzes_by_user(self, user_id: str, status: Optional[str] = None) -> List[Quiz]:
        """
        Retrieves all quizzes owned by a specific user, optionally filtered by status.
        Excludes soft-deleted quizzes. Ordered by most recent first.
        """
        query = (
            self.db.query(Quiz)
            .filter(Quiz.user_id == user_id, Quiz.deleted_at.is_(None))
        )

        if status:
            query = query.filter(Quiz.status == status)

        return query.order_by(Quiz.created_at.desc()).all()

    def get_quizzes_by_class(self, class_id: str, user_id: str) -> List[Quiz]:
        """
        Retrieves all quizzes for a specific class, ensuring ownership.
        Excludes soft-deleted quizzes.
        """
        return (
            self.db.query(Quiz)
            .filter(
                Quiz.class_id == class_id,
                Quiz.user_id == user_id,
                Quiz.deleted_at.is_(None)
            )
            .order_by(Quiz.created_at.desc())
            .all()
        )

    def update_quiz(self, quiz_id: str, user_id: str, data: Dict) -> Optional[Quiz]:
        """
        Updates a quiz, but only if it is owned by the specified user.
        """
        quiz = self.get_quiz_by_id(quiz_id=quiz_id, user_id=user_id)
        if quiz:
            for key, value in data.items():
                if hasattr(quiz, key):
                    setattr(quiz, key, value)
            quiz.updated_at = datetime.now()
            self.db.commit()
            self.db.refresh(quiz)
        return quiz

    def delete_quiz(self, quiz_id: str, user_id: str) -> bool:
        """
        Soft deletes a quiz by setting deleted_at timestamp,
        but only if it is owned by the specified user.
        """
        quiz = self.get_quiz_by_id(quiz_id=quiz_id, user_id=user_id)
        if quiz:
            quiz.deleted_at = datetime.now()
            self.db.commit()
            return True
        return False

    def permanently_delete_quiz(self, quiz_id: str, user_id: str) -> bool:
        """
        Permanently deletes a quiz from database, but only if it is owned by the specified user.
        Use with caution - this cannot be undone. Cascade delete will handle questions, sessions, etc.
        """
        quiz = self.get_quiz_by_id(quiz_id=quiz_id, user_id=user_id)
        if quiz:
            self.db.delete(quiz)
            self.db.commit()
            return True
        return False

    def restore_quiz(self, quiz_id: str, user_id: str) -> bool:
        """
        Restores a soft-deleted quiz by clearing the deleted_at timestamp.
        """
        quiz = (
            self.db.query(Quiz)
            .filter(
                Quiz.id == quiz_id,
                Quiz.user_id == user_id,
                Quiz.deleted_at.isnot(None)
            )
            .first()
        )
        if quiz:
            quiz.deleted_at = None
            self.db.commit()
            return True
        return False

    def update_quiz_status(self, quiz_id: str, user_id: str, status: str) -> bool:
        """
        Updates only the status field of a quiz.
        """
        quiz = self.get_quiz_by_id(quiz_id=quiz_id, user_id=user_id)
        if quiz:
            quiz.status = status
            quiz.updated_at = datetime.now()
            self.db.commit()
            return True
        return False

    def update_last_room_code(self, quiz_id: str, user_id: str, room_code: str) -> bool:
        """
        Updates the last_room_code field when a new session is created.
        """
        quiz = self.get_quiz_by_id(quiz_id=quiz_id, user_id=user_id)
        if quiz:
            quiz.last_room_code = room_code
            self.db.commit()
            return True
        return False

    # --- Question CRUD Methods ---

    def add_question(self, record: Dict) -> QuizQuestion:
        """
        Creates a new QuizQuestion record.
        Assumes the quiz_id in the record has already been validated for ownership.
        """
        new_question = QuizQuestion(**record)
        self.db.add(new_question)
        self.db.commit()
        self.db.refresh(new_question)
        return new_question

    def get_question_by_id(self, question_id: str, user_id: str) -> Optional[QuizQuestion]:
        """
        Retrieves a single question by its ID, but only if its parent quiz
        is owned by the specified user.
        """
        return (
            self.db.query(QuizQuestion)
            .join(Quiz, QuizQuestion.quiz_id == Quiz.id)
            .filter(
                QuizQuestion.id == question_id,
                Quiz.user_id == user_id,
                Quiz.deleted_at.is_(None)
            )
            .first()
        )

    def get_questions_by_quiz(self, quiz_id: str, user_id: str) -> List[QuizQuestion]:
        """
        Retrieves all questions for a specific quiz, ordered by order_index.
        Ensures the quiz is owned by the user.
        """
        # First verify quiz ownership
        quiz = self.get_quiz_by_id(quiz_id=quiz_id, user_id=user_id)
        if not quiz:
            return []

        return (
            self.db.query(QuizQuestion)
            .filter(QuizQuestion.quiz_id == quiz_id)
            .order_by(QuizQuestion.order_index)
            .all()
        )

    def update_question(self, question_id: str, user_id: str, data: Dict) -> Optional[QuizQuestion]:
        """
        Updates a question, but only if its parent quiz is owned by the specified user.
        """
        question = self.get_question_by_id(question_id=question_id, user_id=user_id)
        if question:
            for key, value in data.items():
                if hasattr(question, key):
                    setattr(question, key, value)
            self.db.commit()
            self.db.refresh(question)
        return question

    def delete_question(self, question_id: str, user_id: str) -> bool:
        """
        Deletes a question, but only if its parent quiz is owned by the specified user.
        """
        question = self.get_question_by_id(question_id=question_id, user_id=user_id)
        if question:
            self.db.delete(question)
            self.db.commit()
            return True
        return False

    def reorder_questions(self, quiz_id: str, user_id: str, question_ids_in_order: List[str]) -> bool:
        """
        Updates the order_index of questions based on the provided list order.
        Ensures the quiz is owned by the user.
        """
        quiz = self.get_quiz_by_id(quiz_id=quiz_id, user_id=user_id)
        if not quiz:
            return False

        for idx, question_id in enumerate(question_ids_in_order):
            question = (
                self.db.query(QuizQuestion)
                .filter(
                    QuizQuestion.id == question_id,
                    QuizQuestion.quiz_id == quiz_id
                )
                .first()
            )
            if question:
                question.order_index = idx

        self.db.commit()
        return True

    def get_question_count(self, quiz_id: str, user_id: str) -> int:
        """
        Returns the count of questions for a quiz.
        Ensures the quiz is owned by the user.
        """
        quiz = self.get_quiz_by_id(quiz_id=quiz_id, user_id=user_id)
        if not quiz:
            return 0

        return (
            self.db.query(QuizQuestion)
            .filter(QuizQuestion.quiz_id == quiz_id)
            .count()
        )

    def duplicate_quiz(self, quiz_id: str, user_id: str, new_title: str) -> Optional[Quiz]:
        """
        Creates a copy of an existing quiz with all its questions.
        """
        original_quiz = self.get_quiz_by_id(quiz_id=quiz_id, user_id=user_id)
        if not original_quiz:
            return None

        # Generate new IDs
        import uuid
        new_quiz_id = str(uuid.uuid4())

        # Create new quiz
        new_quiz = Quiz(
            id=new_quiz_id,
            user_id=user_id,
            class_id=original_quiz.class_id,
            title=new_title,
            description=original_quiz.description,
            instructions=original_quiz.instructions,
            status='draft',  # New quiz starts as draft
            settings=original_quiz.settings.copy() if original_quiz.settings else {},
            deleted_at=None
        )
        self.db.add(new_quiz)

        # Copy all questions
        original_questions = self.get_questions_by_quiz(quiz_id=quiz_id, user_id=user_id)
        for orig_question in original_questions:
            new_question = QuizQuestion(
                id=str(uuid.uuid4()),
                quiz_id=new_quiz_id,
                question_text=orig_question.question_text,
                question_type=orig_question.question_type,
                order_index=orig_question.order_index,
                points=orig_question.points,
                time_limit=orig_question.time_limit,
                options=orig_question.options.copy() if orig_question.options else {},
                correct_answer=orig_question.correct_answer.copy() if orig_question.correct_answer else {},
                explanation=orig_question.explanation,
                media_url=orig_question.media_url
            )
            self.db.add(new_question)

        self.db.commit()
        self.db.refresh(new_quiz)
        return new_quiz
