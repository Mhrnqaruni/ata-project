# /tests/test_analytics_and_matching.py (CORRECTED)

import pytest
from unittest.mock import MagicMock, AsyncMock, mock_open
import json
from types import SimpleNamespace

from app.services.assessment_helpers import analytics_and_matching
from app.models.assessment_model import AssessmentConfig, AssessmentConfigV2, QuestionConfig, SectionConfigV2

# --- Test Data Fixtures (Unchanged but confirmed correct) ---

@pytest.fixture
def mock_db_service():
    """Provides a mock of the DatabaseService for dependency injection."""
    return MagicMock()

@pytest.fixture
def v1_job_record():
    """Provides a mock database record (as an object) for a V1 assessment job."""
    v1_config = AssessmentConfig(
        assessmentName="V1 History Test", classId="cls_v1",
        questions=[
            QuestionConfig(id="q1", text="Who was the first president?", rubric="Name the person.", maxScore=10),
            QuestionConfig(id="q2", text="What year was the declaration signed?", rubric="Provide the year.", maxScore=10)
        ]
    )
    mock_record = MagicMock()
    mock_record.id = "job_v1_123"
    mock_record.status = "Completed"
    mock_record.config = v1_config.model_dump_json()
    return mock_record

@pytest.fixture
def mock_results_data():
    """Provides a list of mock result objects for analytics testing."""
    def create_mock_result(student_id, question_id, grade):
        mock = MagicMock()
        mock.student_id = student_id
        mock.question_id = question_id
        mock.grade = grade
        # Mock the SQLAlchemy __table__ attribute needed for the list comprehension
        mock.__table__ = MagicMock()
        mock.__table__.columns = [
            SimpleNamespace(name='student_id'),
            SimpleNamespace(name='question_id'),
            SimpleNamespace(name='grade')
        ]
        return mock

    return [
        create_mock_result('stu_1', 'q_1', 8),
        create_mock_result('stu_1', 'q_2', 10),
        create_mock_result('stu_2', 'q_1', 6),
        create_mock_result('stu_2', 'q_2', 7),
    ]

@pytest.fixture
def mock_v2_config_for_analytics():
    """Provides a valid V2 config object for analytics testing."""
    return AssessmentConfigV2.model_validate({
        "assessmentName": "Analytics Test", "classId": "cls_xyz", "scoringMethod": "per_question",
        "sections": [{"title": "Main Section", "questions": [
            {"id": "q_1", "text": "Q1", "rubric": "R1", "maxScore": 10},
            {"id": "q_2", "text": "Q2", "rubric": "R2", "maxScore": 10}
        ]}]
    })

# --- Unit Tests ---

def test_normalize_config_to_v2_from_v1_job(v1_job_record):
    """Tests that a V1 job config is correctly transformed into a V2 structure."""
    normalized_config = analytics_and_matching.normalize_config_to_v2(v1_job_record)
    assert isinstance(normalized_config, AssessmentConfigV2)
    assert len(normalized_config.sections) == 1
    assert normalized_config.sections[0].questions[0].text == "Who was the first president?"
    print("\n✅ SUCCESS: test_normalize_config_to_v2_from_v1_job passed.")

def test_calculate_analytics_success(mock_results_data, mock_v2_config_for_analytics):
    """Tests that the analytics calculations are correct."""
    analytics = analytics_and_matching.calculate_analytics(mock_results_data, mock_v2_config_for_analytics)
    assert analytics["classAverage"] == 77.5
    assert analytics["performanceByQuestion"]["q_1"] == 70.0
    print("\n✅ SUCCESS: test_calculate_analytics_success passed.")

# This test IS asynchronous, so we apply the marker directly to it.
@pytest.mark.asyncio
async def test_match_files_to_students(mocker, mock_db_service):
    """Tests that the file matching logic correctly calls the database on a match."""
    job_id = "job_match_test"
    user_id = "user_test_123"

    # --- FIX: Use a MagicMock object instead of a dict ---
    mock_job_record = MagicMock()
    mock_job_record.config = AssessmentConfig(assessmentName="Test", classId="cls_1", questions=[QuestionConfig(id='q1', text='t', rubric='r')]).model_dump_json()
    mock_job_record.answer_sheet_paths = json.dumps([{"path": "/path/to/alex_paper.pdf", "contentType": "application/pdf"}])

    # --- FIX: Use MagicMock objects for students ---
    mock_student = MagicMock()
    mock_student.id = "stu_alex_123"
    mock_student.name = "Alex Doe"
    mock_students = [mock_student]
    
    # Configure our mock database to return the test data
    mock_db_service.get_assessment_job.return_value = mock_job_record
    mock_db_service.get_students_by_class_id.return_value = mock_students
    
    # Mock the external OCR service
    mocker.patch('app.services.ocr_service.extract_text_from_file', return_value="some text containing the name alex doe here")

    mocker.patch("builtins.open", mock_open(read_data=b"fake file bytes"))

    await analytics_and_matching.match_files_to_students(mock_db_service, job_id, user_id)

    # Assert that the database was correctly updated after the match was found
    # --- FIX: Add the missing user_id to the assertion ---
    mock_db_service.update_student_result_path.assert_called_once_with(
        job_id, "stu_alex_123", "/path/to/alex_paper.pdf", "application/pdf", user_id
    )
    print("\n✅ SUCCESS: test_match_files_to_students passed.")