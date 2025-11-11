# /ata-backend/app/services/quiz_service.py

"""
This service module acts as the primary business logic layer for all operations
related to quiz creation, management, and questions.

It serves as a facade, orchestrating calls to the DatabaseService while enforcing
business rules, validation, and user ownership. Every function in this module
requires a `user_id` to ensure all operations are securely scoped to the
authenticated user.
"""

import uuid
from typing import List, Dict, Optional
from datetime import datetime
from fastapi import HTTPException, status

from ..models import quiz_model
from .database_service import DatabaseService
from ..core import quiz_config

# Get settings instance
settings = quiz_config.get_quiz_settings()


# --- Helper Functions (Pure Utilities) ---

def _generate_quiz_id() -> str:
    """Generates a unique quiz ID."""
    return f"quiz_{uuid.uuid4().hex[:16]}"


def _generate_question_id() -> str:
    """Generates a unique question ID."""
    return f"q_{uuid.uuid4().hex[:12]}"


def _validate_quiz_settings(settings_data: quiz_model.QuizSettingsSchema) -> Dict:
    """
    Validates quiz settings and returns a clean dictionary.
    """
    settings_dict = settings_data.model_dump()

    # Validate time limit
    if settings_dict.get('question_time_default'):
        if settings_dict['question_time_default'] < 5 or settings_dict['question_time_default'] > 600:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Question time limit must be between 5 and 600 seconds"
            )

    return settings_dict


def _validate_question_data(question: quiz_model.QuestionCreate, order_index: int) -> Dict:
    """
    Validates a question and prepares it for database insertion.
    Returns a clean dictionary ready for database.
    """
    question_record = {
        'id': _generate_question_id(),
        'question_text': question.question_text,
        'question_type': question.question_type.value,
        'order_index': order_index,
        'points': question.points,
        'time_limit': question.time_limit,
        'options': question.options,
        'correct_answer': question.correct_answer,
        'explanation': question.explanation
    }

    # Validate question-type-specific requirements
    if question.question_type == quiz_model.QuestionType.MULTIPLE_CHOICE:
        if 'choices' not in question.options or len(question.options['choices']) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Multiple choice questions must have at least 2 choices"
            )
        if 'answer' not in question.correct_answer:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Multiple choice questions must specify correct answer"
            )

    elif question.question_type == quiz_model.QuestionType.TRUE_FALSE:
        if 'answer' not in question.correct_answer or not isinstance(question.correct_answer['answer'], bool):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="True/false questions must have boolean answer"
            )

    elif question.question_type == quiz_model.QuestionType.SHORT_ANSWER:
        if 'keywords' in question.correct_answer and not isinstance(question.correct_answer['keywords'], list):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Short answer keywords must be a list"
            )

    return question_record


# --- Quiz CRUD Operations ---

def create_quiz(
    quiz_data: quiz_model.QuizCreate,
    user_id: str,
    db: DatabaseService
) -> quiz_model.QuizDetail:
    """
    Business logic to create a new quiz for the authenticated user.
    Validates settings and questions, then creates the quiz atomically.
    """
    # Validate question count
    if len(quiz_data.questions) > settings.MAX_QUESTIONS_PER_QUIZ:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Quiz cannot have more than {settings.MAX_QUESTIONS_PER_QUIZ} questions"
        )

    # Generate quiz ID
    quiz_id = _generate_quiz_id()

    # Validate and prepare settings
    settings_dict = _validate_quiz_settings(quiz_data.settings)

    # Create quiz record
    quiz_record = {
        'id': quiz_id,
        'user_id': user_id,
        'class_id': quiz_data.class_id,
        'title': quiz_data.title,
        'description': quiz_data.description,
        'instructions': quiz_data.instructions,
        'status': 'draft',  # New quizzes start as draft
        'settings': settings_dict
    }

    # Create the quiz
    db_quiz = db.create_quiz(quiz_record)

    # Add questions if provided
    if quiz_data.questions:
        for idx, question in enumerate(quiz_data.questions):
            question_record = _validate_question_data(question, idx)
            question_record['quiz_id'] = quiz_id
            db.add_question(question_record)

    # Fetch complete quiz with questions
    complete_quiz = db.get_quiz_by_id(quiz_id=quiz_id, user_id=user_id)
    questions = db.get_questions_by_quiz(quiz_id=quiz_id, user_id=user_id)

    # Convert to Pydantic response model
    return quiz_model.QuizDetail(
        id=complete_quiz.id,
        user_id=str(complete_quiz.user_id),
        class_id=complete_quiz.class_id,
        title=complete_quiz.title,
        description=complete_quiz.description,
        instructions=complete_quiz.instructions,
        status=complete_quiz.status,
        settings=quiz_model.QuizSettingsSchema(**complete_quiz.settings),
        last_room_code=complete_quiz.last_room_code,
        created_at=complete_quiz.created_at,
        updated_at=complete_quiz.updated_at,
        questions=[quiz_model.QuestionResponse.model_validate(q) for q in questions]
    )


def get_quiz_by_id(
    quiz_id: str,
    user_id: str,
    db: DatabaseService
) -> quiz_model.QuizDetail:
    """
    Retrieves a single quiz with all its questions, ensuring ownership.
    """
    db_quiz = db.get_quiz_by_id(quiz_id=quiz_id, user_id=user_id)

    if not db_quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with ID {quiz_id} not found or access denied"
        )

    # Get questions
    questions = db.get_questions_by_quiz(quiz_id=quiz_id, user_id=user_id)

    return quiz_model.QuizDetail(
        id=db_quiz.id,
        user_id=str(db_quiz.user_id),
        class_id=db_quiz.class_id,
        title=db_quiz.title,
        description=db_quiz.description,
        instructions=db_quiz.instructions,
        status=db_quiz.status,
        settings=quiz_model.QuizSettingsSchema(**db_quiz.settings),
        last_room_code=db_quiz.last_room_code,
        created_at=db_quiz.created_at,
        updated_at=db_quiz.updated_at,
        questions=[quiz_model.QuestionResponse.model_validate(q) for q in questions]
    )


def get_all_quizzes(
    user_id: str,
    status_filter: Optional[str],
    db: DatabaseService
) -> List[quiz_model.QuizSummary]:
    """
    Retrieves all quizzes for a user with optional status filtering.
    Returns summary view (without questions).
    """
    quizzes = db.get_all_quizzes_by_user(user_id=user_id, status=status_filter)

    summaries = []
    for quiz in quizzes:
        # Count questions
        question_count = db.get_question_count(quiz_id=quiz.id, user_id=user_id)

        summaries.append(
            quiz_model.QuizSummary(
                id=quiz.id,
                title=quiz.title,
                status=quiz.status,
                question_count=question_count,
                last_room_code=quiz.last_room_code,
                created_at=quiz.created_at,
                updated_at=quiz.updated_at
            )
        )

    return summaries


def get_quizzes_by_class(
    class_id: str,
    user_id: str,
    db: DatabaseService
) -> List[quiz_model.QuizSummary]:
    """
    Retrieves all quizzes for a specific class.
    """
    # Verify class ownership first
    db_class = db.get_class_by_id(class_id=class_id, user_id=user_id)
    if not db_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class with ID {class_id} not found or access denied"
        )

    quizzes = db.get_quizzes_by_class(class_id=class_id, user_id=user_id)

    summaries = []
    for quiz in quizzes:
        question_count = db.get_question_count(quiz_id=quiz.id, user_id=user_id)
        summaries.append(
            quiz_model.QuizSummary(
                id=quiz.id,
                title=quiz.title,
                status=quiz.status,
                question_count=question_count,
                last_room_code=quiz.last_room_code,
                created_at=quiz.created_at,
                updated_at=quiz.updated_at
            )
        )

    return summaries


def update_quiz(
    quiz_id: str,
    quiz_update: quiz_model.QuizUpdate,
    user_id: str,
    db: DatabaseService
) -> quiz_model.QuizDetail:
    """
    Updates an existing quiz's metadata (not questions).
    """
    # Verify quiz exists and user owns it
    existing_quiz = db.get_quiz_by_id(quiz_id=quiz_id, user_id=user_id)
    if not existing_quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with ID {quiz_id} not found or access denied"
        )

    # Prepare update data
    update_data = quiz_update.model_dump(exclude_unset=True)

    # Validate settings if provided
    if 'settings' in update_data:
        update_data['settings'] = _validate_quiz_settings(update_data['settings'])

    # Update quiz
    updated_quiz = db.update_quiz(quiz_id=quiz_id, user_id=user_id, data=update_data)

    # Return complete quiz
    return get_quiz_by_id(quiz_id=quiz_id, user_id=user_id, db=db)


def delete_quiz(
    quiz_id: str,
    user_id: str,
    db: DatabaseService
) -> bool:
    """
    Soft deletes a quiz (sets deleted_at timestamp).
    """
    success = db.delete_quiz(quiz_id=quiz_id, user_id=user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with ID {quiz_id} not found or access denied"
        )

    return True


def publish_quiz(
    quiz_id: str,
    user_id: str,
    db: DatabaseService
) -> quiz_model.QuizDetail:
    """
    Publishes a quiz (changes status from draft to published).
    Validates that quiz has at least one question.
    """
    # Verify quiz exists
    quiz = db.get_quiz_by_id(quiz_id=quiz_id, user_id=user_id)
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with ID {quiz_id} not found or access denied"
        )

    # Check question count
    question_count = db.get_question_count(quiz_id=quiz_id, user_id=user_id)
    if question_count == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot publish quiz with no questions"
        )

    # Update status
    db.update_quiz_status(quiz_id=quiz_id, user_id=user_id, status='published')

    return get_quiz_by_id(quiz_id=quiz_id, user_id=user_id, db=db)


def duplicate_quiz(
    quiz_id: str,
    new_title: str,
    user_id: str,
    db: DatabaseService
) -> quiz_model.QuizDetail:
    """
    Creates a copy of an existing quiz with all its questions.
    """
    # Verify original quiz exists
    original = db.get_quiz_by_id(quiz_id=quiz_id, user_id=user_id)
    if not original:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with ID {quiz_id} not found or access denied"
        )

    # Duplicate quiz
    new_quiz = db.duplicate_quiz(quiz_id=quiz_id, user_id=user_id, new_title=new_title)

    if not new_quiz:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to duplicate quiz"
        )

    return get_quiz_by_id(quiz_id=new_quiz.id, user_id=user_id, db=db)


# --- Question Management ---

def add_question(
    quiz_id: str,
    question_data: quiz_model.QuestionCreate,
    user_id: str,
    db: DatabaseService
) -> quiz_model.QuestionResponse:
    """
    Adds a new question to a quiz.
    """
    # Verify quiz exists and user owns it
    quiz = db.get_quiz_by_id(quiz_id=quiz_id, user_id=user_id)
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with ID {quiz_id} not found or access denied"
        )

    # Check question count limit
    current_count = db.get_question_count(quiz_id=quiz_id, user_id=user_id)
    if current_count >= settings.MAX_QUESTIONS_PER_QUIZ:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Quiz cannot have more than {settings.MAX_QUESTIONS_PER_QUIZ} questions"
        )

    # Prepare question record (order_index is current_count for append)
    question_record = _validate_question_data(question_data, current_count)
    question_record['quiz_id'] = quiz_id

    # Add question
    db_question = db.add_question(question_record)

    return quiz_model.QuestionResponse.model_validate(db_question)


def update_question(
    question_id: str,
    question_update: quiz_model.QuestionUpdate,
    user_id: str,
    db: DatabaseService
) -> quiz_model.QuestionResponse:
    """
    Updates an existing question.
    """
    # Verify question exists
    existing = db.get_question_by_id(question_id=question_id, user_id=user_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question with ID {question_id} not found or access denied"
        )

    # Prepare update data
    update_data = question_update.model_dump(exclude_unset=True)

    # Update question
    updated = db.update_question(question_id=question_id, user_id=user_id, data=update_data)

    return quiz_model.QuestionResponse.model_validate(updated)


def delete_question(
    question_id: str,
    user_id: str,
    db: DatabaseService
) -> bool:
    """
    Deletes a question from a quiz.
    """
    success = db.delete_question(question_id=question_id, user_id=user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question with ID {question_id} not found or access denied"
        )

    return True


def reorder_questions(
    quiz_id: str,
    question_ids: List[str],
    user_id: str,
    db: DatabaseService
) -> bool:
    """
    Reorders questions in a quiz.
    """
    # Verify quiz exists
    quiz = db.get_quiz_by_id(quiz_id=quiz_id, user_id=user_id)
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with ID {quiz_id} not found or access denied"
        )

    # Reorder
    success = db.reorder_questions(quiz_id=quiz_id, user_id=user_id, question_ids=question_ids)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reorder questions"
        )

    return True
