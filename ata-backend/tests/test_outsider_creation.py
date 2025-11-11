import pytest
from unittest.mock import MagicMock, AsyncMock, mock_open, patch
import json
from app.services.assessment_helpers import analytics_and_matching
from app.models.assessment_model import AssessmentConfig, QuestionConfig

@pytest.mark.asyncio
async def test_match_files_creates_outsider_for_unmatched_file(mocker):
    """
    Tests that when a file doesn't match any student in the roster,
    a new 'outsider' student is created with the correct attributes.
    """
    # 1. Setup Mocks
    mock_db_service = MagicMock()
    job_id = "job_outsider_test"
    user_id = "user_test"

    # Mock job record from the database
    mock_job_record = MagicMock()
    mock_job_record.answer_sheet_paths = json.dumps([{"path": "/path/to/unknown_person.pdf", "contentType": "application/pdf"}])

    # Mock config object
    mock_config = AssessmentConfig(assessmentName="Outsider Test", classId="cls_1", questions=[QuestionConfig(id='q1', text='t', rubric='r')])

    # Mock student record that will be returned after creation
    mock_new_student = MagicMock()
    mock_new_student.id = "stu_new_outsider_456"

    # Configure the mock DB service
    mock_db_service.get_assessment_job.return_value = mock_job_record
    mock_db_service.get_students_by_class_id.return_value = [] # No students in roster, forcing an outsider case
    mock_db_service.add_student.return_value = mock_new_student

    # Mock external services and built-ins
    mocker.patch('app.services.assessment_helpers.analytics_and_matching.normalize_config_to_v2', return_value=mock_config)
    mocker.patch('app.services.ocr_service.extract_text_from_file', return_value="some text that does not match anyone")
    mocker.patch("builtins.open", mock_open(read_data=b"fake file bytes"))
    mock_create_results = mocker.patch('app.services.assessment_helpers.analytics_and_matching._create_results_for_student')

    # 2. Execute the function
    await analytics_and_matching.match_files_to_students(mock_db_service, job_id, user_id)

    # 3. Assertions
    # Assert that a new student was added
    mock_db_service.add_student.assert_called_once()

    # Check the keyword arguments passed to add_student
    call_kwargs = mock_db_service.add_student.call_args.kwargs
    assert call_kwargs['is_outsider'] is True
    assert call_kwargs['origin_job_id'] == job_id
    assert call_kwargs['name'].startswith("Outsider")
    assert "outsider::" in call_kwargs['student_id_str']

    # Assert that results were created for the new outsider student
    mock_create_results.assert_called_once_with(
        mock_db_service,
        job_id,
        mock_new_student.id,
        mock_config,
        {"path": "/path/to/unknown_person.pdf", "contentType": "application/pdf"},
        user_id
    )
    print("\n✅ SUCCESS: test_match_files_creates_outsider_for_unmatched_file passed.")