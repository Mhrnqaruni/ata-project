"""
Quiz Management API Router

This module defines secure REST API endpoints for quiz CRUD operations.
All endpoints require JWT authentication and validate user ownership.

Endpoints:
- GET /api/quizzes - List all quizzes for current user
- POST /api/quizzes - Create a new quiz
- GET /api/quizzes/{quiz_id} - Get quiz details
- PUT /api/quizzes/{quiz_id} - Update quiz
- DELETE /api/quizzes/{quiz_id} - Delete quiz (soft delete)
- POST /api/quizzes/{quiz_id}/publish - Publish quiz
- POST /api/quizzes/{quiz_id}/duplicate - Duplicate quiz
- POST /api/quizzes/{quiz_id}/questions - Add question
- PUT /api/quizzes/{quiz_id}/questions/{question_id} - Update question
- DELETE /api/quizzes/{quiz_id}/questions/{question_id} - Delete question
- PUT /api/quizzes/{quiz_id}/questions/reorder - Reorder questions

Security: All operations validate user ownership via get_current_active_user dependency.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional

# Application imports
from ..models import quiz_model
from ..services import quiz_service
from ..services.database_service import DatabaseService, get_db_service
from ..core.deps import get_current_active_user
from ..db.models.user_model import User as UserModel

router = APIRouter()


# ==================== QUIZ COLLECTION ENDPOINTS ====================

@router.get("", response_model=List[quiz_model.QuizSummary], summary="Get All Quizzes")
def get_all_quizzes(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (draft/published/archived)"),
    class_id: Optional[str] = Query(None, description="Filter by class ID"),
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Retrieve all quizzes owned by the current user with optional filtering.

    Query Parameters:
    - status: Filter by quiz status
    - class_id: Filter by associated class

    Returns:
    - List of quiz summaries with question counts
    """
    quizzes = quiz_service.get_all_quizzes_with_counts(
        user_id=current_user.id,
        db=db,
        status=status_filter,
        class_id=class_id
    )

    return quizzes


@router.post("", response_model=quiz_model.QuizDetail, status_code=status.HTTP_201_CREATED, summary="Create New Quiz")
def create_quiz(
    quiz_data: quiz_model.QuizCreate,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Create a new quiz with optional initial questions.

    Request Body:
    - Quiz data (title, description, questions, etc.)

    Returns:
    - Created quiz with all questions

    Raises:
    - 422: Validation error (too many questions, invalid question data)
    """
    try:
        quiz = quiz_service.create_quiz_with_questions(
            quiz_data=quiz_data,
            user_id=current_user.id,
            db=db
        )

        # Fetch full details to return
        questions = db.get_questions_by_quiz_id(quiz.id, current_user.id)

        return {
            **quiz.__dict__,
            "questions": questions
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


# ==================== INDIVIDUAL QUIZ ENDPOINTS ====================

@router.get("/{quiz_id}", response_model=quiz_model.QuizDetail, summary="Get Quiz by ID")
def get_quiz(
    quiz_id: str,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Retrieve detailed information about a specific quiz.

    Path Parameters:
    - quiz_id: Quiz ID

    Returns:
    - Quiz details with all questions

    Raises:
    - 404: Quiz not found or access denied
    """
    quiz = db.get_quiz_by_id(quiz_id, current_user.id)
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with ID {quiz_id} not found or access denied"
        )

    questions = db.get_questions_by_quiz_id(quiz_id, current_user.id)

    return {
        **quiz.__dict__,
        "questions": questions
    }


@router.put("/{quiz_id}", response_model=quiz_model.QuizDetail, summary="Update Quiz")
def update_quiz(
    quiz_id: str,
    quiz_data: quiz_model.QuizUpdate,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Update a quiz's fields.

    Path Parameters:
    - quiz_id: Quiz ID

    Request Body:
    - Quiz update data (all fields optional)

    Returns:
    - Updated quiz with questions

    Raises:
    - 404: Quiz not found
    - 422: Validation error (e.g., publishing with no questions)
    """
    try:
        quiz = quiz_service.update_quiz_with_validation(
            quiz_id=quiz_id,
            user_id=current_user.id,
            update_data=quiz_data,
            db=db
        )

        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quiz with ID {quiz_id} not found"
            )

        questions = db.get_questions_by_quiz_id(quiz_id, current_user.id)

        return {
            **quiz.__dict__,
            "questions": questions
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Quiz")
def delete_quiz(
    quiz_id: str,
    hard_delete: bool = Query(False, description="Permanently delete (default: soft delete)"),
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Delete a quiz (soft delete by default).

    Path Parameters:
    - quiz_id: Quiz ID

    Query Parameters:
    - hard_delete: If true, permanently delete (default: false)

    Returns:
    - 204 No Content on success

    Raises:
    - 404: Quiz not found
    """
    deleted = db.delete_quiz(quiz_id, current_user.id, soft_delete=not hard_delete)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with ID {quiz_id} not found"
        )

    return None


@router.post("/{quiz_id}/publish", response_model=quiz_model.QuizDetail, summary="Publish Quiz")
def publish_quiz(
    quiz_id: str,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Publish a quiz (make it available for sessions).

    Path Parameters:
    - quiz_id: Quiz ID

    Returns:
    - Published quiz details

    Raises:
    - 404: Quiz not found
    - 422: Validation error (no questions, invalid question data)
    """
    # Validate quiz can be published
    is_valid, error_message = quiz_service.validate_publish_quiz(
        quiz_id=quiz_id,
        user_id=current_user.id,
        db=db
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_message
        )

    # Update status to published
    quiz = db.update_quiz_status(quiz_id, current_user.id, "published")

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with ID {quiz_id} not found"
        )

    questions = db.get_questions_by_quiz_id(quiz_id, current_user.id)

    return {
        **quiz.__dict__,
        "questions": questions
    }


@router.post("/{quiz_id}/duplicate", response_model=quiz_model.QuizDetail, status_code=status.HTTP_201_CREATED, summary="Duplicate Quiz")
def duplicate_quiz(
    quiz_id: str,
    new_title: Optional[str] = Query(None, description="Title for duplicated quiz"),
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Duplicate a quiz with all its questions.

    Path Parameters:
    - quiz_id: Quiz ID to duplicate

    Query Parameters:
    - new_title: Optional custom title (default: "Copy of [original]")

    Returns:
    - Duplicated quiz (status: draft)

    Raises:
    - 404: Quiz not found
    """
    new_quiz = db.duplicate_quiz(quiz_id, current_user.id, new_title)

    if not new_quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with ID {quiz_id} not found"
        )

    questions = db.get_questions_by_quiz_id(new_quiz.id, current_user.id)

    return {
        **new_quiz.__dict__,
        "questions": questions
    }


# ==================== QUESTION MANAGEMENT ENDPOINTS ====================

@router.post("/{quiz_id}/questions", response_model=quiz_model.QuizQuestionAdminResponse, status_code=status.HTTP_201_CREATED, summary="Add Question")
def add_question(
    quiz_id: str,
    question_data: quiz_model.QuizQuestionCreate,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Add a new question to a quiz.

    Path Parameters:
    - quiz_id: Quiz ID

    Request Body:
    - Question data

    Returns:
    - Created question

    Raises:
    - 404: Quiz not found
    - 422: Validation error (invalid question type, options, etc.)
    """
    # Verify quiz exists and user owns it
    quiz = db.get_quiz_by_id(quiz_id, current_user.id)
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with ID {quiz_id} not found"
        )

    # Check question count limit
    current_count = db.get_question_count(quiz_id, current_user.id)
    if current_count >= 100:  # MAX_QUESTIONS_PER_QUIZ
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Quiz already has maximum number of questions (100)"
        )

    # Create question
    question_dict = {
        "quiz_id": quiz_id,
        **question_data.model_dump()
    }

    try:
        question = db.add_question_to_quiz(question_dict)
        return question

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to create question: {str(e)}"
        )


@router.put("/{quiz_id}/questions/{question_id}", response_model=quiz_model.QuizQuestionAdminResponse, summary="Update Question")
def update_question(
    quiz_id: str,
    question_id: str,
    question_data: quiz_model.QuizQuestionUpdate,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Update a question.

    Path Parameters:
    - quiz_id: Quiz ID
    - question_id: Question ID

    Request Body:
    - Question update data (all fields optional)

    Returns:
    - Updated question

    Raises:
    - 404: Quiz or question not found
    """
    # Verify quiz exists
    quiz = db.get_quiz_by_id(quiz_id, current_user.id)
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with ID {quiz_id} not found"
        )

    # Update question
    update_dict = {k: v for k, v in question_data.model_dump().items() if v is not None}
    question = db.update_question(question_id, current_user.id, update_dict)

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question with ID {question_id} not found"
        )

    return question


@router.delete("/{quiz_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Question")
def delete_question(
    quiz_id: str,
    question_id: str,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Delete a question from a quiz.

    Path Parameters:
    - quiz_id: Quiz ID
    - question_id: Question ID

    Returns:
    - 204 No Content on success

    Raises:
    - 404: Quiz or question not found
    """
    # Verify quiz exists
    quiz = db.get_quiz_by_id(quiz_id, current_user.id)
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with ID {quiz_id} not found"
        )

    # Delete question
    deleted = db.delete_question(question_id, current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question with ID {question_id} not found"
        )

    return None


@router.put("/{quiz_id}/questions/reorder", response_model=quiz_model.SuccessResponse, summary="Reorder Questions")
def reorder_questions(
    quiz_id: str,
    question_order: List[str],
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Reorder questions in a quiz.

    Path Parameters:
    - quiz_id: Quiz ID

    Request Body:
    - List of question IDs in desired order

    Returns:
    - Success message

    Raises:
    - 404: Quiz not found
    - 422: Invalid question order
    """
    # Verify quiz exists
    quiz = db.get_quiz_by_id(quiz_id, current_user.id)
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with ID {quiz_id} not found"
        )

    # Reorder
    success = db.reorder_questions(quiz_id, current_user.id, question_order)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to reorder questions"
        )

    return {
        "message": "Questions reordered successfully",
        "data": {"quiz_id": quiz_id, "question_count": len(question_order)}
    }
