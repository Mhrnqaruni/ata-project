import pytest
import json
import uuid
from typing import List, Optional
from decimal import Decimal
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from app.main import app
from app.services.database_service import get_db_service
from app.services.assessment_service import finalize_question
from app.db.models.assessment_models import Result, Assessment, ResultStatus, FinalizedBy
from app.db.models.class_student_models import Student
from app.models.user_model import User
from app.core.deps import get_current_active_user
from app.models import assessment_model as am

# --- Unit Tests for Consensus Logic ---
@pytest.mark.parametrize("grades, comments, max_score, expected_status, expected_grade, expected_finalized_by", [
    ([8.0, 8.0, 8.0], ["Good", "Great", "Excellent"], 10.0, ResultStatus.AI_GRADED, 8.0, FinalizedBy.AI),
    ([8.0, 7.0, 8.0], ["Good", "Okay", "Great"], 10.0, ResultStatus.AI_GRADED, 8.0, FinalizedBy.AI),
    ([8.0, 7.0, 6.0], ["Good", "Okay", "Bad"], 10.0, ResultStatus.PENDING_REVIEW, None, None),
    ([8.5, 8.6, 8.55], ["Good", "Great", "Excellent"], 10.0, ResultStatus.AI_GRADED, 8.55, FinalizedBy.AI),
    ([8.5, 7.2, 8.55], ["Good", "Okay", "Great"], 10.0, ResultStatus.AI_GRADED, 8.525, FinalizedBy.AI),
    ([8.5, 7.2, 6.1], ["Good", "Okay", "Bad"], 10.0, ResultStatus.PENDING_REVIEW, None, None),
    ([9.0, 9.05, 5.0], ["A", "B", "C"], 10.0, ResultStatus.AI_GRADED, 9.025, FinalizedBy.AI),
    ([9.0, 9.2, 9.4], ["A", "B", "C"], 10.0, ResultStatus.PENDING_REVIEW, None, None),
    ([8.0, None, 8.0], ["Good", "N/A", "Great"], 10.0, ResultStatus.AI_GRADED, 8.0, FinalizedBy.AI),
    ([8.0, None, 7.0], ["Good", "N/A", "Okay"], 10.0, ResultStatus.PENDING_REVIEW, None, None),
    ([None, None, 8.0], ["N/A", "N/A", "Good"], 10.0, ResultStatus.PENDING_REVIEW, None, None),
    ([None, None, None], ["N/A", "N/A", "N/A"], 10.0, ResultStatus.PENDING_REVIEW, None, None),
])
def test_finalize_question(
    grades: List[Optional[float]],
    comments: List[Optional[str]],
    max_score: float,
    expected_status: ResultStatus,
    expected_grade: Optional[float],
    expected_finalized_by: Optional[FinalizedBy]
):
    # Convert to Decimal for precision
    decimal_grades = [Decimal(str(g)) if g is not None else None for g in grades]
    result = finalize_question(decimal_grades, comments, max_score)
    assert result["status"] == expected_status
    if expected_grade is not None:
        assert result["grade"] is not None
        assert abs(Decimal(str(result["grade"])) - Decimal(str(expected_grade))) < Decimal("0.01")
    else:
        assert result["grade"] is None
    assert result["finalized_by"] == expected_finalized_by

# --- Integration Tests for API Endpoints (Refactored) ---

test_user_id = uuid.uuid4()
mock_user = User(id=test_user_id, email="test@example.com", hashed_password="password", is_active=True, is_superuser=False)
mock_db_service = MagicMock()

def override_get_current_active_user():
    return mock_user

def override_get_db_service():
    return mock_db_service

app.dependency_overrides[get_current_active_user] = override_get_current_active_user
app.dependency_overrides[get_db_service] = override_get_db_service

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_mocks():
    mock_db_service.reset_mock()

# --- Mock Data Factory ---
def create_mock_job(job_id, user_id):
    mock_job = MagicMock()
    mock_job.id = job_id
    mock_job.user_id = user_id
    mock_job.status = am.JobStatus.PENDING_REVIEW.value
    mock_job.ai_summary = "This is a mock AI summary."
    mock_job.config = {
        "assessmentName": "Test Assessment",
        "classId": "c1",
        "scoringMethod": "per_question",
        "totalScore": 100,
        "sections": [{
            "id": "sec1", "title": "Section 1", "total_score": 20,
            "questions": [{
                "id": "q1", "text": "Q1", "maxScore": 10, "rubric": "R1", "answer": "A1"
            }, {
                "id": "q2", "text": "Q2", "maxScore": 10, "rubric": "R2", "answer": "A2"
            }]
        }]
    }
    return mock_job

def create_mock_student(student_id, name):
    mock_student = MagicMock()
    mock_student.id = student_id
    mock_student.name = name
    return mock_student

def create_mock_result(job_id, student_id, question_id, status, grade, extracted_answer=""):
    mock_result = MagicMock()
    mock_result.job_id = job_id
    mock_result.student_id = student_id
    mock_result.question_id = question_id
    mock_result.status = status
    mock_result.grade = grade
    mock_result.extractedAnswer = extracted_answer
    mock_result.feedback = "This is mock feedback."
    return mock_result

# --- Refactored Tests ---

@patch('app.services.assessment_service.analytics_and_matching.normalize_config_to_v2')
def test_get_assessment_results_overview_success(mock_normalize):
    job_id = "test-job-1"
    user_id = str(test_user_id)

    mock_job = create_mock_job(job_id, user_id)
    mock_config = am.AssessmentConfigV2.model_validate(mock_job.config)
    mock_normalize.return_value = mock_config

    mock_db_service.get_assessment_job.return_value = mock_job
    mock_db_service.get_students_by_class_id.return_value = [
        create_mock_student("s1", "Alice"),
        create_mock_student("s2", "Bob")
    ]
    mock_db_service.get_all_results_for_job.return_value = [
        create_mock_result(job_id, "s1", "q1", ResultStatus.AI_GRADED, 8.0),
        create_mock_result(job_id, "s1", "q2", ResultStatus.TEACHER_GRADED, 9.0),
        create_mock_result(job_id, "s2", "q1", ResultStatus.AI_GRADED, 7.0),
        create_mock_result(job_id, "s2", "q2", ResultStatus.PENDING_REVIEW, None),
    ]
    # This mock is needed to satisfy the pydantic model for the response
    mock_db_service.get_student_result_path.return_value = "/fake/path.pdf"

    response = client.get(f"/api/assessments/{job_id}/results")

    assert response.status_code == 200
    data = response.json()
    assert data['jobId'] == job_id
    assert len(data['results']['s1']) == 2
    assert data['results']['s1']['q1']['grade'] == 8.0

def test_get_assessment_results_overview_not_found():
    job_id = "non-existent-job"
    mock_db_service.get_assessment_job.return_value = None

    response = client.get(f"/api/assessments/{job_id}/results")

    assert response.status_code == 404
    # Correct the expected error message to match the API
    assert response.json() == {"detail": f"Job {job_id} not found or access denied."}

@patch('app.services.assessment_service.analytics_and_matching.normalize_config_to_v2')
def test_get_student_assessment_for_review_success(mock_normalize):
    job_id = "test-job-1"
    student_id = "s1"
    user_id = str(test_user_id)

    mock_job = create_mock_job(job_id, user_id)
    mock_config = am.AssessmentConfigV2.model_validate(mock_job.config)
    mock_normalize.return_value = mock_config

    mock_db_service.get_assessment_job.return_value = mock_job
    # FIX: The service uses get_student_by_id, not get_student_by_student_id
    mock_db_service.get_student_by_id.return_value = create_mock_student(student_id, "Alice")
    mock_db_service.get_outsider_student_by_id.return_value = None
    mock_db_service.get_all_results_for_job.return_value = [
        create_mock_result(job_id, student_id, "q1", ResultStatus.AI_GRADED, 8.5, "This is the student answer."),
        create_mock_result(job_id, student_id, "q2", ResultStatus.PENDING_REVIEW, None, "Another answer."),
    ]

    # The entity_id in the URL should be the student's database ID
    response = client.get(f"/api/assessments/{job_id}/students/{student_id}/review")

    assert response.status_code == 200
    data = response.json()
    assert data['student_name'] == "Alice"
    assert len(data['per_question']) == 2
    q1_data = next(q for q in data['per_question'] if q['question_id'] == 'q1')
    assert q1_data['student_answer'] == "This is the student answer."

@patch('app.services.assessment_service.analytics_and_matching.normalize_config_to_v2')
def test_save_teacher_review_success(mock_normalize):
    job_id = "test-job-1"
    student_id = "s2"
    user_id = str(test_user_id)
    # FIX: The payload should be a single object, not a list
    review_payload = {"question_id": "q2", "grade": 9.0, "feedback": "Excellent work!"}

    mock_job = create_mock_job(job_id, user_id)
    mock_normalize.return_value = am.AssessmentConfigV2.model_validate(mock_job.config)

    mock_db_service.get_assessment_job.return_value = mock_job
    # Add mocks for the get_student_by_id and get_outsider_student_by_id calls
    mock_db_service.get_student_by_id.return_value = create_mock_student(student_id, "Test Student")
    mock_db_service.get_outsider_student_by_id.return_value = None

    # Mock the results for score recalculation
    mock_db_service.get_all_results_for_job.return_value = [
        create_mock_result(job_id, student_id, "q1", ResultStatus.AI_GRADED, 7.0),
        create_mock_result(job_id, student_id, "q2", ResultStatus.TEACHER_GRADED, 9.0),
    ]

    # FIX: The endpoint is a PATCH, not a POST, and the URL has changed
    response = client.patch(f"/api/assessments/{job_id}/students/{student_id}/review", json=review_payload)

    assert response.status_code == 200
    assert response.json()['totalScore'] == 16.0

    # FIX: The service now calls update_student_result_with_grade
    mock_db_service.update_student_result_with_grade.assert_called_once_with(
        job_id=job_id,
        student_id=student_id,
        question_id="q2",
        grade=9.0,
        feedback="Excellent work!",
        status=ResultStatus.TEACHER_GRADED.value,
        finalized_by=FinalizedBy.TEACHER.value,
        user_id=str(test_user_id)
    )